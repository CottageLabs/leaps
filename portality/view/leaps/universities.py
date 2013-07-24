import json

from flask import Blueprint, request, flash, abort, make_response, render_template, redirect, url_for
from flask.ext.login import current_user

from datetime import datetime

from flask_weasyprint import HTML, render_pdf

from portality.core import app
import portality.models as models
import portality.util
from portality.view.leaps.exports import download_csv


blueprint = Blueprint('universities', __name__)


# restrict everything in universities to logged in users
# and only show when enabled
# and make university users sign the policy on first access
@blueprint.before_request
def restrict():
    adminsettings = models.Account.pull(app.config['SUPER_USER'][0]).data.get('settings',{})
    if not adminsettings.get('schools_unis',False):
        return render_template('leaps/admin/closed.html')
    if current_user.is_anonymous():
        return redirect('/account/login?next=' + request.path)
    if not current_user.agreed_policy:
        return redirect('/account/policy?next=' + request.path)
    if not current_user.is_institution:
        abort(401)
    

# view students that intend to apply to the university of the logged-in person
@blueprint.route('/')
def index():
    institution = current_user.is_institution
    students = _get_students(institution)
    return render_template('leaps/universities/index.html', students=students, institution=institution)


# give universities subject management control
@blueprint.route('/subjects', methods=['GET','POST'])
def subjects():
    if not isinstance(current_user.is_institution,bool):
        institution = models.Institution.pull_by_name(current_user.is_institution)
        if request.method == 'POST':
            institution.save_from_form(request)
            flash('Your changes have been saved.')
        return render_template('leaps/universities/subjects.html', institution=institution)
    elif current_user.do_admin:
        flash('You are an admin user, so you should manage institutional data via the admin interface.')
        return redirect('/admin/data/institution')
    else:
        abort(401)


# view particular PAE request
@blueprint.route('/pae/<appid>', methods=['GET','POST'])
def pae(appid):
    student = _get_student_for_appn(appid)
    if student is None: abort(404)

    application = {}
    for appn in student.data['applications']:
        if appn['appid'] == appid: application = appn
    
    if request.method == 'GET':
        if application.get('pae_reply_received',False):
            msg = 'This Pre-Application Enquiry was responded to on ' + application['pae_reply_received']
            if current_user.do_admin:
                msg += ". The university contacts can view it but cannot alter it."
            else:
                msg += ". It cannot be altered."
            flash(msg)
        return render_template(
            'leaps/universities/pae.html', 
            student=student, 
            institution=current_user.is_institution, 
            application=application
        )

    elif request.method == 'POST':
        if application.get('pae_reply_received',False) and not current_user.do_admin:
            abort(401)
        else:
            application['pae_reply_received'] = datetime.now().strftime("%d/%m/%Y")
            application['consider'] = request.form.get('consider',"")
            application['conditions'] = request.form.get('conditions',"")
            application['summer_school'] = request.form.get('summer_school',False)

            # change record status too, if first or last PAE answer
            if student.data['status'] == 'paes_requested':
                student.data['status'] = 'paes_in_progress'
            complete = True
            for appn in student.data['applications']:
                if appn.get('pae_reply_received',False):
                    complete = False
            if complete and student.data['status'].startswith('paes'):
                student.data['status'] = 'paes_all_received'

            student.save()

            # then email the lEAPS admin
            if current_user.do_admin:
                wrn = "Changes saved but no email alert sent, as you are a LEAPS admin user anyway."
                print wrn
                flash(wrn)
            elif app.config['DEBUG']:
                wrn = 'Debug mode on. If it were not, an attempt to send an email would have just occurred.'
                print wrn
                flash(wrn)
            else:
                subject = "PAE response received"
                message = "A response has been received via the online response form.\n\n"
                message += "You can view the response at:\n\n"
                message += "https://leapssurvey.org/universities/pae/" + appid
                message += "\n\nThanks!"
                addr = app.config.get("LEAPS_EMAIL",app.config.get("ADMIN_EMAIL",False))
                # TODO: check if emails work without reply-to header set.
                # if not, augment send_mail to accept headers={'Reply-To': addr} or something
                if addr:
                    util.send_mail([addr],[addr],subject,message)
                else:
                    wrn = 'No email address available to send alert message to.'
                    print wrn
                    flash(wrn)

            flash('Thank you very much for submitting your response. It has been saved.')
            return redirect(url_for('.index'))


# print a PAE form for a student
@blueprint.route('/pae/<appid>.pdf')
def paepdf(appid):
    student = _get_student_for_appn(appid)
    if student is None: abort(404)

    application = {}
    for appn in student.data['applications']:
        if appn['appid'] == appid: application = appn

    html = render_template('leaps/admin/student_pae', record=student, application=application)
    return render_pdf(HTML(string=html))


# export data for a particular university
@blueprint.route('/export')
def export():
    institution = current_user.is_institution
    students = _get_students(institution)
    # TODO: define the keys that universities are allowed to download
    keys = [
        'first_name',
        'last_name',
        'post_code',
        'school',
        'qualifications',
        'applications'
    ]
    return download_csv(students,keys)


def _get_student_for_appn(appid):
    institution = current_user.is_institution
    try:
        # return a student where one of their applications has the matching PAE ID
        # and where one of their applications is to the same institution as that of the current user
        # (may return some where the current user cannot respond, but is close enough - they have access to the student data anyway)
        qry = {
            "query":{
                "bool":{
                    "must":[
                        {
                            "term":{
                                "applications.appid"+app.config['FACET_FIELD']:appid
                            }
                        }
                    ]
                }
            }
        }
        if not isinstance(institution,bool):
            qry['query']['bool']['must'].append({'term':{'applications.institution'+app.config['FACET_FIELD']:institution}})

        s = models.Student.query(q=qry)['hits']['hits'][0]['_source']['id']
        return models.Student.pull(s)

    except:
        return None


def _get_students(institution):
    qry = {
        'query':{
            'bool':{
                'must':[
                    {'term':
                        {'archive'+app.config['FACET_FIELD']:'current'}
                    },
                    {'term':
                        {'_process_paes':True}
                    }
                ]
            }
        },
        'size':10000
    }
    if not isinstance(institution,bool):
        qry['query']['bool']['must'].append({'term':{'applications.institution'+app.config['FACET_FIELD']:institution}})

    q = models.Student().query(q=qry)
    students = [i['_source'] for i in q.get('hits',{}).get('hits',[])]
    if not isinstance(institution,bool):
        for student in students:
            allowedapps = []
            apps = student['applications']
            for appn in apps:
                if appn['institution'] == institution: allowedapps.append(appn)
            student['applications'] = allowedapps
    return students


