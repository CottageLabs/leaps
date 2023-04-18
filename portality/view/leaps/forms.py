'''
A forms system

Build a form template, build a handler for its submission, receive data from end users
'''

import json, re

from flask import Blueprint, request, abort, make_response, render_template, flash, redirect, url_for
from flask.ext.login import current_user

from portality.core import app

import portality.models as models
import portality.util as util


blueprint = Blueprint('forms', __name__)


# a forms overview page at the top level, can list forms or say whatever needs said about forms, or catch closed forms
@blueprint.route('/')
def intro():
    # make this an actual decision on whether or not survey is open or closed
    adminsettings = models.Account.pull(app.config['SUPER_USER'][0]).data.get('settings',{})
    if adminsettings.get('survey',False):
        return redirect(url_for('.student'))
    else:
        return render_template('leaps/survey/closed.html')
        

# a generic form completion confirmation page
@blueprint.route('/complete')
def complete():
    return render_template('leaps/survey/complete.html')


# form handling endpoint, by form name - define more for each form required
@blueprint.route('/student', methods=['GET','POST'])
def student():

    # for forms requiring auth, add an auth check here
    adminsettings = models.Account.pull(app.config['SUPER_USER'][0]).data.get('settings',{})
    
    if request.method == 'GET':
        # TODO: if people are logged in it may be necessary to render a form with previously submitted data
        selections = {
            "schools": dropdowns('school'),
            "subjects": dropdowns('subject'),
            "advancedsubjects": dropdowns('advancedsubject'),
            "levels": dropdowns('level'),
            "grades": dropdowns('grade'),
            "institutions": dropdowns('institution'),
            "advancedlevels": dropdowns('advancedlevel')
        }
        selections['school_categories'] = {}
        r = models.School().query(q={'query':{'match_all':{}},'size': 1000})
        for s in r['hits']['hits']:
            selections['school_categories'][re.sub('[^a-z]+', '', s['_source']['name'].lower())] = s['_source']['leaps_category']

        if adminsettings.get('survey',False) or not current_user.is_anonymous(): #current_user.view_admin:
            if current_user.is_anonymous() or not current_user.do_admin:
                if 'TEST' in selections['schools']:
                    selections['schools'] = [i for i in selections['schools'] if i != 'TEST']
                if 'TEST' in selections['institutions']:
                    selections['institutions'] = [i for i in selections['institutions'] if i != 'TEST']
            response = make_response(
                render_template(
                    'leaps/survey/survey.html', 
                    selections = selections,
                    data={}
                )
            )
            response.headers['Cache-Control'] = 'public, no-cache, no-store, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            return response
        else:
            return render_template('leaps/survey/closed.html')

    if request.method == 'POST':
        if adminsettings.get('survey',False) or (not current_user.is_anonymous() and current_user.view_admin):
            student = models.Student()
            student.save_from_form(request)

            try:
                to = [app.config['LEAPS_EMAIL']]
                #if app.config.get('ADMIN_EMAIL',False):
                #    to.append(app.config['ADMIN_EMAIL'])
                fro = app.config['LEAPS_EMAIL']
                subject = "New student survey submitted"
                text = 'A student has just submitted a survey. View it in the admin interfacet at '
                text += '<a href="http://leapssurvey.org/admin/student/' + student.id
                text += '">http://leapssurvey.org/admin/student/' + student.id + '</a>.'
                util.send_mail(to=to, fro=fro, subject=subject, text=text)
            except:
                flash('Email failed.')
                
        return redirect(url_for('.complete'))


def dropdowns(model,key='name'):
    qry = {
        'query':{'match_all':{}},
        'size': 0,
        'facets':{}
    }
    qry['facets'][key] = {"terms":{"field":key+app.config['FACET_FIELD'],"order":'term', "size":100000}}
    klass = getattr(models, model[0].capitalize() + model[1:] )
    r = klass().query(q=qry)
    terms = [i.get('term','') for i in r.get('facets',{}).get(key,{}).get("terms",[])]
    if model.lower() == 'grade':
        tops = ['Currently sitting','A','B','C','D','E','F','No Award','A*']
        for top in reversed(tops):
            if top in terms:
                terms.remove(top)
                terms.insert(0,top)
    return terms


