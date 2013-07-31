'''
A forms system

Build a form template, build a handler for its submission, receive data from end users
'''

import json

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
    
    if request.method == 'GET':
        # TODO: if people are logged in it may be necessary to render a form with previously submitted data
        selections={
            "schools": dropdowns('school'),
            "subjects": dropdowns('subject'),
            "advancedsubjects": dropdowns('advancedsubject'),
            "levels": dropdowns('level'),
            "grades": dropdowns('grade'),
            "institutions": dropdowns('institution'),
            "advancedlevels": dropdowns('advancedlevel')
        }
        if not current_user.is_anonymous():
            if not current_user.do_admin:
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

    if request.method == 'POST':
        student = models.Student()
        student.save_from_form(request)

        if not app.config['DEBUG'] and 'LEAPS_EMAIL' in app.config and app.config['LEAPS_EMAIL'] != "":
            to = [app.config['LEAPS_EMAIL']]
            if 'ADMIN_EMAIL' in app.config and app.config['ADMIN_EMAIL'] != "":
                to.append(app.config['ADMIN_EMAIL'])
            fro = app.config['LEAPS_EMAIL']
            subject = "New student survey submitted"
            text = 'A student has just submitted a survey. View it in the admin interfacet at '
            text += '<a href="http://leapssurvey.org/admin/student/' + student.id
            text += '">http://leapssurvey.org/admin/student/' + student.id + '</a>.'
            try:
                util.send_mail(to=to, fro=fro, subject=subject, text=text)
            except:
                flash('Email failed.')
        else:
            flash('If this was not debug mode and an email address was available, an email alert would have just been sent')
                
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
    return [i.get('term','') for i in r.get('facets',{}).get(key,{}).get("terms",[])]


