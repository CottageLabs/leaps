import json, time
from copy import deepcopy

from flask import Blueprint, request, flash, abort, make_response, render_template, redirect, url_for
from flask.ext.login import current_user

from flask_weasyprint import HTML, render_pdf

from portality.core import app
from portality.view.leaps.forms import dropdowns
import portality.models as models



blueprint = Blueprint('admin', __name__)


# restrict everything in admin to logged in users who can view admin, and only accept posts from users that can do admin
@blueprint.before_request
def restrict():
    if current_user.is_anonymous():
        return redirect('/account/login?next=' + request.path)
    elif request.method == 'POST' and not current_user.do_admin:
        abort(401)
    elif not current_user.view_admin:
        abort(401)

# build an admin page where things can be done
@blueprint.route('/')
def index():

    # TODO: complete these stats calcs
    stats = {
        "total_submitted": models.Student.query(q={"query":{"bool":{"must":[{"term":{"archive"+app.config['FACET_FIELD']:"current"}}]}}})['hits']['total'],
        "awaiting_interview":models.Student.query(q={"query":{"bool":{"must":[{"term":{"archive"+app.config['FACET_FIELD']:"current"}},{"term":{"status"+app.config['FACET_FIELD']:"awaiting_interview"}}]}}})['hits']['total'],
        "interviewed":models.Student.query(q={"query":{"bool":{"must":[{"term":{"archive"+app.config['FACET_FIELD']:"current"}},{"term":{"status"+app.config['FACET_FIELD']:"interviewed"}}]}}})['hits']['total'],
        "paes_forwarded":models.Student.query(q={"query":{"bool":{"must":[{"term":{"archive"+app.config['FACET_FIELD']:"current"}},{"term":{"status"+app.config['FACET_FIELD']:"paes_forwarded"}}]}}})['hits']['total'],
        "awaiting_all_pae":models.Student.query(q={"query":{"bool":{"must":[{"term":{"archive"+app.config['FACET_FIELD']:"current"}},{"term":{"status"+app.config['FACET_FIELD']:"paes_requested"}}]}}})['hits']['total'],
        "awaiting_some_pae":models.Student.query(q={"query":{"bool":{"must":[{"term":{"archive"+app.config['FACET_FIELD']:"current"}},{"term":{"status"+app.config['FACET_FIELD']:"paes_in_progress"}}]}}})['hits']['total'],
        "all_pae_received":models.Student.query(q={"query":{"bool":{"must":[{"term":{"archive"+app.config['FACET_FIELD']:"current"}},{"term":{"status"+app.config['FACET_FIELD']:"paes_all_received"}}]}}})['hits']['total'],
        "total_schools":models.School.query()['hits']['total'],
        "schools_with_students_submitted":len(models.Student.query(q={
            "query":{
                "bool":{
                    "must":[
                        {
                            "term":{
                                "archive"+app.config['FACET_FIELD']:"current"
                            }
                        }
                    ]
                }
            },
            "size":0,
            "facets":{
                "schools":{
                    "terms":{
                        "field":"school"+app.config['FACET_FIELD'], 
                        "size":1000
                    }
                }
            }
        })['facets']['schools']['terms']),
        "universities_pae_outstanding":len(models.Student.query(q={
            "query":{
                "bool":{
                    "must":[
                        {
                            "term":{
                                "archive"+app.config['FACET_FIELD']:"current"
                            }
                        }
                    ],
                    "should":[
                        {
                            "term":{
                                "status"+app.config['FACET_FIELD']:"paes_requested"
                            }
                        },
                        {
                            "term":{
                                "status"+app.config['FACET_FIELD']:"paes_in_progress"
                            }
                        }
                    ],
                    "minimum_should_match":1
                }
            },
            "size":0,
            "facets":{
                "unis":{
                    "terms":{
                        "field":"applications.institution"+app.config['FACET_FIELD'], 
                        "size":1000
                    }
                }
            }
        })['facets']['unis']['terms'])
    }
    return render_template('leaps/admin/index.html', stats=stats)



# update admin settings
@blueprint.route('/settings', methods=['GET','POST'])
def settings():
    if request.method == 'POST':
        inputs = request.json
        acc = models.Account.pull(app.config['SUPER_USER'][0])
        if 'settings' not in acc.data: acc.data['settings'] = {}
        for key in inputs.keys():
            acc.data['settings'][key] = inputs[key]
        acc.save()
        return ""
    else:
        abort(404)


# show a particular student record for editing
@blueprint.route('/student')
@blueprint.route('/student/<uuid>', methods=['GET','POST','DELETE'])
def student(uuid=None):
    if uuid is None:
        return render_template('leaps/admin/students.html')

    if uuid == "new":
        student = models.Student()
    else:
        student = models.Student.pull(uuid)
        if student is None: abort(404)

    selections={
        "schools": dropdowns('school'),
        "subjects": dropdowns('subject'),
        "advancedsubjects": dropdowns('advancedsubject'),
        "levels": dropdowns('level'),
        "grades": dropdowns('grade'),
        "institutions": dropdowns('institution'),
        "advancedlevels": dropdowns('advancedlevel'),
        "local_authorities": dropdowns('school','local_authority'),
        "leaps_categories": dropdowns('school','leaps_category'),
        "simd_deciles": dropdowns('simd','simd_decile'),
        "simd_quintiles": dropdowns('simd','simd_quintile'),
        "archives": dropdowns('archive','name')
    }

    if request.method == 'GET':
        return render_template(
            'leaps/admin/student.html', 
            record=student, 
            selections=selections
        )
    elif ( request.method == 'POST' and request.values.get('submit','') == "Delete" ) or request.method == 'DELETE':
        student.delete()
        time.sleep(1)
        flash("Student " + str(student.id) + " deleted")
        return redirect(url_for('.student'))
    elif request.method == 'POST':
        student.save_from_form(request)
        if uuid == 'new':
            flash("New student record has been created", "success")
            return redirect(url_for('.student') + '/' + str(student.id))
        else:
            flash("Student record has been updated", "success")
            return render_template(
                'leaps/admin/student.html', 
                record=student, 
                selections=selections
            )


# print a student as a pdf
@blueprint.route('/student/<sid>.pdf', methods=['GET'])
@blueprint.route('/student/pdf', methods=['GET'])
def pdf(sid,giveback=False):
    if sid == "None":
        student = models.Student()
        thepdf = render_template('leaps/admin/student_pdf', students=[student.data])
    elif sid == "selected":
        query = json.loads(request.values.get('q','{"query":{"match_all":{}}}'))
        if 'size' in request.values: query['size'] = request.values['size']
        selected = json.loads(request.values.get('selected','[]'))
        s = models.Student.query(q=query)
        students = []
        for i in s.get('hits',{}).get('hits',[]):
            if len(selected) == 0 or i['_source']['id'] in selected:
                students.append( i['_source'] )
        if len(students) == 0:
            abort(404)
        else:
            thepdf = render_template('leaps/admin/student_pdf', students=students)
    else:
        student = models.Student.pull(sid)
        if student is None:
            abort(404)
        else:
            thepdf = render_template('leaps/admin/student_pdf', students=[student.data])

    if giveback:
        return thepdf
    else:
        return render_pdf(HTML(string=thepdf))

    
# do updating of schools / institutes / courses / pae answers / interview data
@blueprint.route('/data')
@blueprint.route('/data/<model>')
@blueprint.route('/data/<model>/<uuid>', methods=['GET','POST','DELETE'])
def data(model=None,uuid=None):
    if request.method == 'GET':
        if model is None:
            return render_template('leaps/admin/data.html')
        elif uuid is None:
            return render_template('leaps/admin/data.html', model=model)
        else:
            if uuid == "new":
                return render_template('leaps/admin/datamodel.html', model=model, record=None)
            else:
                klass = getattr(models, model[0].capitalize() + model[1:] )
                rec = klass().pull(uuid)
                if rec is None:
                    abort(404)
                else:
                    return render_template('leaps/admin/datamodel.html', model=model, record=rec)

    elif ( request.method == 'POST' and request.values.get('submit','') == "Delete" ) or request.method == 'DELETE':
        if model is not None:
            klass = getattr(models, model[0].capitalize() + model[1:] )
            if uuid is not None:
                rec = klass().pull(uuid)
                if rec is not None:
                    rec.delete()
                    flash(model + " " + str(rec.id) + " deleted")
                    return redirect(url_for('.data'))
                else:
                    abort(404)
            else:
                abort(404)
        else:
            abort(404)    

    elif request.method == 'POST':
        if model is not None:
            klass = getattr(models, model[0].capitalize() + model[1:] )
            if uuid is not None and uuid != "new":
                rec = klass().pull(uuid)
                if rec is None:
                    abort(404)
                else:
                    rec.save_from_form(request)
                    flash("Your " + model + " has been updated", "success")
                    return render_template('leaps/admin/datamodel.html', model=model, record=rec)
            else:
                rec = klass()
                rec.save_from_form(request)
                flash("Your new " + model + " has been created", "success")
                return redirect(url_for('.data') + '/' + model + '/' + str(rec.id))
        else:
            abort(404)


# do archiving
@blueprint.route('/archive', methods=['GET','POST'])
def archives():
    if request.method == "POST":
        action = request.values['submit']
        if action == "Create":
            a = models.Archive( name=request.values['archive'] )
            a.save()
            flash('New archive named ' + a.data["name"] + ' created')
        elif action == "Move":
            a = models.Archive.pull_by_name(request.values['move_from'])
            b = models.Archive.pull_by_name(request.values['move_to'])
            if a is None or b is None:
                flash('Sorry. One of the archives you specified could not be identified...')
            else:
                lena = len(a)
                for i in a.children(justids=True):
                    ir = models.Student.pull(i)
                    ir.data["archive"] = b.data["name"]
                    ir.save()
                time.sleep(1)
                flash(str(lena) + ' records moved from archive ' + a.data["name"] + ' to archive ' + b.data["name"] + ', which now contains ' + str(len(b)) + ' records. Archive ' + a.data["name"] + ' still exists, but is now empty. Feel free to delete it if you wish, or use it to put more records in.')
        elif action == "Delete":
            a = models.Archive.pull_by_name(request.values['delete'])
            length = len(a)
            a.delete()
            flash('Archive ' + a.data["name"] + ' deleted, along with all ' + str(length) + ' records it contained.')

        time.sleep(1)

    return render_template(
        'leaps/admin/archive.html', 
        currentcount=models.Student.query().get('hits',{}).get('total',0),
        archives=dropdowns('archive','name')
    )








