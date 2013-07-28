import json
from copy import deepcopy

from flask import Blueprint, request, flash, abort, make_response, render_template, redirect
from flask.ext.login import current_user

from portality.core import app
import portality.models as models
from portality.view.leaps.forms import dropdowns


blueprint = Blueprint('schools', __name__)


# restrict everything in admin to logged in users
@blueprint.before_request
def restrict():
    adminsettings = models.Account.pull(app.config['SUPER_USER'][0]).data.get('settings',{})
    if not adminsettings.get('schools_unis',False):
        return render_template('leaps/admin/closed.html')
    if current_user.is_anonymous():
        return redirect('/account/login?next=' + request.path)
    if not current_user.agreed_policy and not current_user.view_admin:
        return redirect('/account/policy?next=' + request.path)
    if not current_user.is_school:
        abort(401)
    

# view students of the school of the logged-in person that have submitted forms
@blueprint.route('/')
def index():
    school = current_user.is_school
    qry = {'query':{'bool':{'must':[{'term':{'archive.exact':'current'}}]}},'size':10000}
    if not isinstance(school,bool):
        qry['query']['bool']['must'].append({'term':{'school.exact':school}})

    q = models.Student().query(q=qry)
    students = [i['_source'] for i in q.get('hits',{}).get('hits',[])]
    
    return render_template('leaps/schools/index.html', students=students, schools=dropdowns('school','name'))



