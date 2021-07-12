
from flask import Blueprint, request, abort, render_template, redirect
from flask.ext.login import current_user

from flask_weasyprint import HTML, render_pdf

from portality.core import app
import portality.models as models
import portality.util as util

from datetime import datetime, date


blueprint = Blueprint('interviews', __name__)


# restrict everything in admin to logged in users
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
    if not current_user.agreed_policy:
        return redirect('/account/policy?next=' + request.path)
    if not current_user.perform_interviews:
        abort(401)
    

# view students of the logged-in interviewer
@blueprint.route('/')
def index():
    interviewer = current_user.perform_interviews
    qry = {'sort':[{'created_date.exact':{'order':'desc'}}],'query':{'bool':{'must':[{'term':{'archive.exact':'current'}}]}},'size':10000}
    if not isinstance(interviewer,bool):
        qry['query']['bool']['must'].append({'term':{'interviewer.exact':school}})
    q = models.Student().query(q=qry)
    students = [i['_source'] for i in q.get('hits',{}).get('hits',[])]
    return render_template('leaps/interviews/index.html', students=students)

@blueprint.route('/<sid>.pdf')
def interviewPDF(sid):
    interviewer = current_user.perform_interviews
    student = models.Student.pull(sid)
    if student is None:
        abort(404)
    elif interviewer != True and interviewer != student.data.get('interviewer'):
        abort(401)
    else:
        thepdf = render_template('leaps/admin/student_pdf', students=[student.data])
        return render_pdf(HTML(string=thepdf))

@blueprint.route('/<sid>/form', methods=['GET', 'POST'])
def interviewForm(sid):
    student = models.Student.pull(sid)
    interviewer = current_user.perform_interviews
    if student is None:
        abort(404)
    elif interviewer != True and interviewer != student.data.get('interviewer'):
        abort(401)
    elif request.method is 'GET':
        student = models.Student.pull(sid)
        return render_template('leaps/interviews/form.html', student=student)
    else:
        # save the form into the student record
        if not student.data.get('interview',False):
            student.data['interview'] = {}
        for field in request.values.keys()
            student.data['interview'][field] = request.values.get(field)
        student.data['interview']['form_date'] = datetime.now().strftime("%Y-%m-%d %H%M")
        student.save()
        flash('The interview admin form data has been saved to the student record')
        return render_template('leaps/interviews/form.html', student=student)
        
@blueprint.route('/<sid>/plan', methods=['GET', 'POST'])
def interviewPlan(sid):
    student = models.Student.pull(sid)
    interviewer = current_user.perform_interviews
    if student is None:
        abort(404)
    elif interviewer != True and interviewer != student.data.get('interviewer'):
        abort(401)
    elif request.method is 'GET':
        interviewer = current_user.perform_interviews
        student = models.Student.pull(sid)
        return render_template('leaps/interviews/plan.html', student=student)
    else:
        # save the plan into the student record
        flash('The interview action plan data has been saved to the student record')
        return render_template('leaps/interviews/plan.html', student=student)
    
# print a PAE form for a student
@blueprint.route('/<sid>/plan.pdf')
def interviewPlanPDF(sid,giveback=False):
    student = models.Student.pull(sid)
    interviewer = current_user.perform_interviews
    if student is None: 
        abort(404)
    elif interviewer != True and interviewer != student.data.get('interviewer'):
        abort(401)
    else:
        thepdf = render_template('leaps/admin/student_action_plan', record=student)
        if giveback:
            return HTML(string=thepdf).write_pdf()
        else:
            return render_pdf(HTML(string=thepdf))



# email an interview form to a student
@blueprint.route('/<sid>/email')
def interviewEmail(sid):
    if current_user.do_admin:
        if sid == "unemailed":
            # get all the interviews that have action plans completed but not yet emailed
            interviews = _get_interviews_awaiting_email()
            if 's' in request.values: interviews = interviews[0:int(request.values['s'])]
            for student in interviews:
                time.sleep(1)
                _email_interview(student, False)
            time.sleep(1)
            flash(str(len(interviews)) + ' interviews were emailed','success')
            return redirect('/admin')
        else:
            student = models.Student.pull(sid)
            if student is None:
                abort(404)
            else:
                _email_interview(student)
                return redirect('/interviews')
    else:
        abort(401) 
           

def _email_interview(student, flashable=True):
    try:
        fro = app.config['LEAPS_EMAIL']
        to = [app.config['LEAPS_EMAIL']]
        #if app.config.get('ADMIN_EMAIL',False):
        #    to.append(app.config['ADMIN_EMAIL'])
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

        text += '''
Thank you for attending your recent LEAPS interview. We hope you found it helpful. Please find
attached a copy of the action plan that your interviewer has prepared for you. It should reflect the
conversation that you had in your interview, and give you some steps to help you move forward with
your plans.

Please remember LEAPS is always available should you need any more help as you go forward,

Good luck and best wishes

The LEAPS TEAM'''

        subject = "LEAPS interview action plan"

        files = [{
            'content': paepdf(application['appid'],giveback=True), 
            'filename': 'LEAPS_interview_' + studentname.replace(" ","_") + '_action_plan.pdf'
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
            flash('Interview action plan has been emailed to ' + ",".join(to), "success")
    except:
        flash('There was an error processing the email. Please check and try again.')



def _get_interviews_awaiting_email():
    qry = {
        'query':{
            'bool':{
                'must':[
                    {'term':
                        {'archive'+app.config['FACET_FIELD']:'current'}
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
    return [i['_source'] for i in q.get('hits',{}).get('hits',[])]



