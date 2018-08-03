import json
from copy import deepcopy

from flask import Blueprint, request, flash, abort, make_response, render_template, redirect
from flask.ext.login import current_user

from flask_weasyprint import HTML, render_pdf

from portality.core import app
import portality.models as models
from portality.view.leaps.forms import dropdowns
from portality.view.leaps.admin import pdf
from portality.view.leaps.exports import download_csv

import datetime


blueprint = Blueprint('schools', __name__)


# restrict everything in admin to logged in users
@blueprint.before_request
def restrict():
    adminsettings = models.Account.pull(app.config['SUPER_USER'][0]).data.get('settings',{})
    if not adminsettings.get('schools_unis',False):
        return render_template('leaps/admin/closed.html')
    if current_user.is_anonymous():
        return redirect('/account/login?next=' + request.path)
    dp = current_user.data['last_updated'].split(' ')[0].split('-')
    if datetime.date(int(dp[0]),int(dp[1]),int(dp[2])) < datetime.date(2018,8,1) and current_user.data.get('agreed_policy',False) == True:
        current_user.data['previously_agreed_policy'] = True
        current_user.data['agreed_policy'] = False
        current_user.save()
    if not current_user.agreed_policy:
        return redirect('/account/policy?next=' + request.path)
    if not current_user.is_school:
        abort(401)
    

# view students of the school of the logged-in person that have submitted forms
@blueprint.route('/')
def index():
    school = current_user.is_school
    students = _get_students(school)
    return render_template('leaps/schools/index.html', students=students, schools=dropdowns('school','name'))


# view students of the school of the logged-in person that have submitted forms
@blueprint.route('/student/<sid>.pdf')
def getpdf(sid):
    school = current_user.is_school
    
    student = models.Student.pull(sid)
    if student is None:
        abort(404)
    elif student.data['status'] in ["new","awaiting_interview","absent"] and (current_user.is_super or current_user.do_admin or student.data['school'] == school):
        thepdf = pdf(sid,True)
        return render_pdf(HTML(string=thepdf))
    else:
        abort(401)


# view students of the school of the logged-in person that have submitted forms
@blueprint.route('/export')
def export(sid):
    school = current_user.is_school
    
# export data for a particular school
@blueprint.route('/export')
def export():
    school = current_user.is_school
    students = _get_students(school)
    keys = [
        'first_name',
        'last_name',
        'date_of_birth',
        'status',
        'school',
        'school_house'
    ]
    return download_csv(students,keys)



def _get_students(school):
    qry = {'sort':[{'created_date.exact':{'order':'desc'}}],'query':{'bool':{'must':[{'term':{'archive.exact':'current'}}]}},'size':10000}
    # NOTE the index mapping has date detection off, so this sort may not be in correct order. If not, add a sort function here
    # the format is %Y-%m-%d %H%M
    if not isinstance(school,bool):
        qry['query']['bool']['must'].append({'term':{'school.exact':school}})

    q = models.Student().query(q=qry)
    students = [i['_source'] for i in q.get('hits',{}).get('hits',[])]
    return students




