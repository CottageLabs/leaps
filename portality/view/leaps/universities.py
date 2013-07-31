import json

from flask import Blueprint, request, flash, abort, make_response, render_template, redirect, url_for
from flask.ext.login import current_user

import time
from datetime import datetime

from flask_weasyprint import HTML, render_pdf

from portality.core import app
import portality.models as models
import portality.util
from portality.view.leaps.exports import download_csv
from portality.view.leaps.forms import dropdowns


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
    if not current_user.agreed_policy and not current_user.view_admin:
        return redirect('/account/policy?next=' + request.path)
    if not current_user.is_institution:
        abort(401)
    

# view students that intend to apply to the university of the logged-in person
@blueprint.route('/')
def index():
    return render_template(
        'leaps/universities/index.html', 
        students = _get_students(current_user.is_institution),
        institutions = dropdowns('institution','name')
    )


# give universities subject management control
@blueprint.route('/subjects', methods=['GET','POST'])
def subjects():
    if not isinstance(current_user.is_institution,bool):
        institution = models.Institution.pull_by_name(current_user.is_institution)
        if request.method == 'POST':
            institution.save_from_form(request)
            flash('Your changes have been saved.')
        return render_template('leaps/universities/subjects.html', institution=institution)
    elif current_user.view_admin:
        flash('You are an admin user, so you should manage institutional data via this admin interface.')
        return redirect('/admin/data/institution')
    else:
        abort(401)


# view particular PAE request
@blueprint.route('/pae/<appid>', methods=['GET','POST'])
def pae(appid):
    student, application = _get_student_for_appn(appid)
    
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

            if not app.config['DEBUG'] and 'LEAPS_EMAIL' in app.config and app.config['LEAPS_EMAIL'] != "":
                to = [app.config['LEAPS_EMAIL']]
                if 'ADMIN_EMAIL' in app.config and app.config['ADMIN_EMAIL'] != "":
                    to.append(app.config['ADMIN_EMAIL'])
                fro = app.config['LEAPS_EMAIL']
                subject = "PAE response received"
                message = "A response has been received via the online PAE response form.\n\n"
                message += "You can view the response at:\n\n"
                message += "https://leapssurvey.org/universities/pae/" + appid
                message += "\n\nThanks!"
                try:
                    util.send_mail(to=to, fro=fro, subject=subject, text=text)
                except:
                    flash('Email failed.')
            else:
                flash('If this was not debug mode and an email address was available, an email alert would have just been sent')

            flash('Thank you very much for submitting your response. It has been saved.')
            time.sleep(1)
            return redirect(url_for('.index'))


# print a PAE form for a student
@blueprint.route('/pae/<appid>.pdf')
def paepdf(appid,giveback=False):
    student, application = _get_student_for_appn(appid)
    if student is None: abort(404)

    thepdf = render_template('leaps/admin/student_pae', record=student, application=application)
    if giveback:
        return thepdf
    else:
        return render_pdf(HTML(string=thepdf))


# email a PAE to a student
@blueprint.route('/pae/<appid>/email')
def email(appid):
    student, application = _get_student_for_appn(appid)

    if not app.config['DEBUG'] and 'LEAPS_EMAIL' in app.config and app.config['LEAPS_EMAIL'] != "":
        to = [app.config['LEAPS_EMAIL']]
        if 'ADMIN_EMAIL' in app.config and app.config['ADMIN_EMAIL'] != "":
            to.append(app.config['ADMIN_EMAIL'])
        if 'email' in student:
            to.append(student['email'])
        school = models.School.pull_by_name(student.data['school'])
        if school is not None:
            for contact in school.data.get('contacts',[]):
                if conact.get('email',False):
                    to.append(contact['email'])
        fro = app.config['LEAPS_EMAIL']
        subject = "LEAPS PAE enquiry feedback"
        message = "" # TODO: write a message for the student and school contacts to see
        files = [] # TODO: get the pdf from paepdf(appid, giveback=True) and get send_mail to handle it without writing to disk
        try:
            util.send_mail(to=to, fro=fro, subject=subject, text=text, files=files)
            application['pae_emailed'] = datetime.now().strftime("%d/%m/%Y")
            which = 0
            count = 0
            for app in student.data['applications']:
                if app['appid'] == application['appid']: which = count
                count += 1
            student.data['applications'][which] = application
            student.save()
            flash('PAE has been emailed to ' + ",".join(to), "success")
        except:
            flash('Email failed.')
    else:
        flash('If this was not debug mode and an email address was available, an email alert would have just been sent')

    return redirect(url_for('.pae', appid=appid))
    

# export data for a particular university
@blueprint.route('/export')
def export():
    institution = current_user.is_institution
    students = _get_students(institution)
    # TODO: define the keys that universities are allowed to download
    # TODO: define how a student should be listed in an export
    # is it a line per student with all applications in one box, and removing students who have not applied to this uni
    # or is it a line per pae so students may be duplicated? like the page display? (in which case students who have not applied are not shown anyway)
    keys = [
        'first_name',
        'last_name',
        'date_of_birth',
        'gender',
        'post_code',
        'school',
        'late_decision_to_apply',
        'had_recent_careers_interview',
        'additional_qualification',
        'issues_affecting_performance',
        'career_plans',
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

        student = models.Student.pull(s)
        if student is None:
            return None, None
        else:
            application = {}
            for appn in student.data['applications']:
                if appn['appid'] == appid: application = appn
            return student, application

    except:
        return None, None


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
        #"sort":[{"field":"_process_paes_date"+app.config['FACET_FIELD'], "order":"desc"}],
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
                if appn['institution'] == institution and 'pae_requested' in appn:
                    allowedapps.append(appn)
            student['applications'] = allowedapps
    return students


