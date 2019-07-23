import json

from flask import Blueprint, request, flash, abort, make_response, render_template, redirect, url_for
from flask.ext.login import current_user

import time
from datetime import datetime
from datetime import date
from copy import deepcopy

from flask_weasyprint import HTML, render_pdf

from portality.core import app
import portality.models as models
import portality.util as util
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
    dp = current_user.data['last_updated'].split(' ')[0].split('-')
    if date(int(dp[0]),int(dp[1]),int(dp[2])) < date(2018,8,1) and current_user.data.get('agreed_policy',False) == True:
        current_user.data['previously_agreed_policy'] = True
        current_user.data['agreed_policy'] = False
        current_user.save()
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
    if appid == 'unemailed':
        paes = _get_paes_awaiting_email()
        if 's' in request.values: paes = paes[0:int(request.values['s'])]
        resp = make_response( json.dumps(paes,indent=4) )
        resp.mimetype = "application/json"
        return resp

    else:
        student, application = _get_student_for_appn(appid)
        if not student.get('simd_pc',False):
            dec = int(student['simd_decile'])
            if dec == 10 and int(student.get('simd_quintile',0)) == 5:
                dec = 100
            elif dec < 10:
                dec = dec * 10
            student['simd_pc'] = str(dec)
        
        if request.method == 'GET':
            if application.get('pae_reply_received',False):
                msg = 'This Pre-Application Enquiry was responded to on ' + application['pae_reply_received']
                if current_user.do_admin:
                    msg += ". The university contacts can view it but cannot alter it."
                else:
                    msg += ". It cannot be altered."
                flash(msg)
            if 'paequals' in student and 'qid' in application and application['qid'] in student['paequals']:
                quals = student['paequals'][application['qid']]
            else:
                quals = student['qualifications']
            if 'paelocs' in student and 'qid' in application and application['qid'] in student['paelocs']:
                for key in student['paelocs'][application['qid']]:
                    student[key] = student['paelocs'][application['qid']][key]
            return render_template(
                'leaps/universities/pae.html', 
                student=student, 
                institution=current_user.is_institution, 
                application=application,
                quals=quals
            )

        elif request.method == 'POST':
            if len(application.get('pae_reply_received','')) > 0 and not current_user.do_admin:
                abort(401)
            elif current_user.view_admin and not current_user.do_admin:
                abort(401)
            else:
                application['pae_reply_received'] = datetime.now().strftime("%d/%m/%Y")
                application['consider'] = request.form.get('consider',"")
                application['conditions'] = request.form.get('conditions',"")
                application['summer_school'] = request.form.get('summer_school',False)

                # change record status too, if first or last PAE answer
                if student.data['status'] == 'paes_requested':
                    student.data['status'] = 'paes_in_progress'

                '''this has been disabled in favour of only marking complete once emailed by leaps
                complete = True
                for appn in student.data['applications']:
                    if not appn.get('pae_reply_received',False):
                        complete = False
                if complete and student.data['status'].startswith('paes'):
                    student.data['status'] = 'paes_complete'
                '''

                student.save()

                try:
                    to = [app.config['LEAPS_EMAIL']]
                    if app.config.get('ADMIN_EMAIL',False):
                        to.append(app.config['ADMIN_EMAIL'])
                    fro = app.config['LEAPS_EMAIL']
                    subject = "PAE response received"
                    text = "A response has been received via the online PAE response form.\n\n"
                    text += "You can view the response at:\n\n"
                    text += "https://leapssurvey.org/universities/pae/" + appid
                    text += "\n\nThanks!"
                    util.send_mail(to=to, fro=fro, subject=subject, text=text)
                except:
                    flash('Email failed.')

                flash('Thank you very much for submitting your response. It has been saved.')
                time.sleep(1)
                return redirect(url_for('.index'))


# print a PAE form for a student
@blueprint.route('/pae/<appid>.pdf')
def paepdf(appid,giveback=False):
    student, application = _get_student_for_appn(appid)
    if student is None: abort(404)

    if 'paequals' in student and 'qid' in application and application['qid'] in student['paequals']:
        quals = student['paequals'][application['qid']]
    else:
        quals = student['qualifications']
    if 'paelocs' in student and 'qid' in application and application['qid'] in student['paelocs']:
        for key in student['paelocs'][application['qid']]:
            student[key] = student['paelocs'][application['qid']][key]
    if not student.get('simd_pc',False):
        dec = int(student['simd_decile'])
        if dec == 10 and int(student.get('simd_quintile',0)) == 5:
            dec = 100
        elif dec < 10:
            dec = dec * 10
        student['simd_pc'] = str(dec)
    thepdf = render_template('leaps/admin/student_pae', record=student, application=application, quals=quals)
    if giveback:
        return HTML(string=thepdf).write_pdf()
    else:
        return render_pdf(HTML(string=thepdf))


# email a PAE to a student
@blueprint.route('/pae/<appid>/email')
def email(appid):
    if current_user.do_admin:
        if appid == "unemailed":
            # get all the PAEs that have been replied to but not yet emailed
            paes = _get_paes_awaiting_email()
            if 's' in request.values: paes = paes[0:int(request.values['s'])]
            for appn in paes:
                time.sleep(1)
                student, application = _get_student_for_appn(appn)
                _email_pae(student, application, False)
            time.sleep(1)
            flash(str(len(paes)) + ' PAEs were emailed','success')
            return redirect('/admin')
        else:
            student, application = _get_student_for_appn(appid)
            _email_pae(student, application)
            return redirect(url_for('.pae', appid=appid))

    else:
        abort(401) 
           

# export data for a particular university
@blueprint.route('/export')
def export():
    institution = current_user.is_institution
    students = _get_students(institution)
    keys = [
        'first_name',
        'last_name',
        'scn_number',
        'date_of_birth',
#        'gender',
        'post_code',
        'school',
        'leaps_category',
        'simd_decile',
#        'late_decision_to_apply',
#        'had_recent_careers_interview',
        'issues_affecting_performance',
        'additional_qualifications',
#        'career_plans',
        'first_attending_university',
        'looked_after_child',
        'low_income_family',
        'young_carer',
#        'law_application',
#        'early_application',
        'main_language_at_home',
        'additional_comments',
        'qualifications',
#        'pae_requested',
        'applications'
    ]
    print 'starting export with keys'
    print keys
    return download_csv(students,keys)



def _email_pae(student, application, flashable=True):
    try:
        fro = app.config['LEAPS_EMAIL']

        to = [app.config['LEAPS_EMAIL']]
        if app.config.get('ADMIN_EMAIL',False):
            to.append(app.config['ADMIN_EMAIL'])
        if 'email' in student:
            to.append(student['email'])

        try:
            studentname = student.data['first_name'] + " " + student.data['last_name']
            #studentname = studentname.encode("ascii","ignore")
            if not all(ord(char) < 128 for char in studentname):
                studentname = 'student'
        except:
            studentname = 'student'
        text = 'Dear ' + studentname + ',\n\n'

        school = models.School.pull_by_name(student.data['school'])
        if school is not None:
            foundone = False
            for contact in school.data.get('contacts',[]):
                if contact.get('email',False):
                    to.append(contact['email'])
                    if not foundone:
                        foundone = True
                        text += '( and copied to school contact '
                    else:
                        text += ', '
                    if contact.get('name',"") != "":
                        text += contact['name']
                    else:
                        text += contact['email']
            if foundone:
                text += " )\n\n"

        text += '''Pre-Application Enquiry (PAE) Response

    Following your LEAPS interview, we raised a Pre-Application Enquiry (PAE) with a university on your behalf. We asked whether or not they are likely to make you an offer for the course you are interested in, based on your qualifications to date.

    Please see the attached document for full details of their response. Make sure that you read everything carefully. Take time to check that all your qualifications are correct - the university's response is based on your qualifications as listed.

    This Pre-Application Enquiry (PAE) is a guide for you. Its purpose is to help you make the best use of your five UCAS choices by giving you an indication of how universities are likely to view your application. 

    If the university has said no, it will not be worthwhile making the same choice on your UCAS application. Pay attention to the reasons given for this response and make use of any comments when you come to make your final UCAS choices.

    If the university has said yes - great news! However do bear in mind that this is NOT a formal offer of study, nor does it guarantee that you will receive an offer. You still need to apply through UCAS and admissions tutors will take into account all of the information on your application. This includes your personal statement, academic reference and predicted grades. Competition for places will also
    be a factor as demand tends to fluctuate from year-to-year.

    If you have any questions at all regarding your PAE response, please contact us on LEAPS@ed.ac.uk or 0131 650 4676. We have copied this email to your school so that you can also discuss any concerns with your guidance teacher or UCAS co-ordinator.

    Kind regards,
    The LEAPS team

    ***Please note you will receive a separate email for each course we have enquired about. Responses may be received at different times.***'''

        subject = "LEAPS PAE enquiry feedback"

        files = [{
            'content': paepdf(application['appid'],giveback=True), 
            'filename': 'LEAPSPAE_' + studentname.replace(" ","_") + '_' + application['institution'] + '.pdf'
        }]

        util.send_mail(to=to, fro=fro, subject=subject, text=text, files=files)

        all_mailed = True
        for appn in student.data['applications']:
            if appn['appid'] == application['appid']:
                appn['pae_emailed'] = datetime.now().strftime("%d/%m/%Y")
            elif appn.get('pae_requested',False) and not appn.get('pae_emailed',False):
                all_mailed = False

        if all_mailed and student.data['status'].startswith('paes'):
            student.data['status'] = 'paes_complete'

        student.save()

        if flashable:
            flash('PAE has been emailed to ' + ",".join(to), "success")
    except:
        flash('There was an error processing the email. Please check and try again.')


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


def _get_paes_awaiting_email():
    qry = {
        'query':{
            'bool':{
                'must':[
                    {'term':
                        {'archive'+app.config['FACET_FIELD']:'current'}
                    },
                    {'term':
                        {'_process_paes':True}
                    },
                    {'query_string':
                        {'query':'*','default_field':'pae_reply_received'}
                    }
                ],
                'must_not':[
                    {'term':
                        {'status'+app.config['FACET_FIELD']:'paes_complete'}
                    }
                ]
            }
        },
        "sort":[{"_process_paes_date"+app.config['FACET_FIELD']:{"order":"desc"}}],
        'size':10000
    }

    q = models.Student().query(q=qry)
    students = [i['_source'] for i in q.get('hits',{}).get('hits',[])]
    paes = []
    for student in students:
        apps = student['applications']
        for appn in apps:
            if appn.get('pae_reply_received',"") != "" and appn.get('pae_emailed',"") == "":
                paes.append(appn['appid'])

    return paes


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
        "sort":[{"_process_paes_date"+app.config['FACET_FIELD']:{"order":"desc"}}],
        'size':10000
    }
    if not isinstance(institution,bool):
        qry['query']['bool']['must'].append({'term':{'applications.institution'+app.config['FACET_FIELD']:institution}})

    q = models.Student().query(q=qry)
    students = [i['_source'] for i in q.get('hits',{}).get('hits',[])]
    matchedstudents = []
    for student in students:
        allowedapps = []
        apps = student['applications']
        for appn in apps:
            if not isinstance(institution,bool):
                if appn['institution'] == institution and appn.get('pae_requested',"") != "":
                    allowedapps.append(appn)
            else:
                if appn.get('pae_requested',"") != "":
                    allowedapps.append(appn)
        if len(allowedapps) > 0:
            for a in allowedapps:
                s = deepcopy(student)
                s['applications'] = [a]
                s['pae_requested'] = a.get('pae_requested','')
                matchedstudents.append(s)
    return matchedstudents


