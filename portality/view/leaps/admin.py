import json, time
from copy import deepcopy

from flask import Blueprint, request, flash, abort, make_response, render_template, redirect, url_for
from flask.ext.login import current_user

from flask_weasyprint import HTML, render_pdf

from portality.core import app
from portality.view.leaps.forms import dropdowns
import portality.models as models

from datetime import date


blueprint = Blueprint('admin', __name__)


# restrict everything in admin to logged in users who can view admin, and only accept posts from users that can do admin
# also allow schools accounts through if getting a pdf in the right circumstances
@blueprint.before_request
def restrict():
    if current_user.is_anonymous():
        return redirect('/account/login?next=' + request.path)
    elif request.method == 'POST' and not ( ( current_user.edit_students and 'student/' in request.path ) or (current_user.perform_and_manage_interviewers and '/assign/' in request.path) or current_user.do_admin):
        abort(401)
    elif request.method == 'DELETE' and not current_user.do_admin:
        abort(401)
    dp = current_user.data['last_updated'].split(' ')[0].split('-')
    if date(int(dp[0]),int(dp[1]),int(dp[2])) < date(2018,8,1) and current_user.data.get('agreed_policy',False) == True:
        current_user.data['previously_agreed_policy'] = True
        current_user.data['agreed_policy'] = False
        current_user.save()
    if not current_user.agreed_policy:
        return redirect('/account/policy?next=' + request.path)
    elif not current_user.view_admin:
        abort(401)

# build an admin page where things can be done
@blueprint.route('/')
def index():

    qr = {
        "query":{
            "bool":{
                "must":[
                    {
                        "term":{
                            "archive"+app.config['FACET_FIELD']:"current"
                        }
                    }
                ],
                "must_not":[
                    {
                        "term":{
                            "school"+app.config['FACET_FIELD']:"TEST"
                        }
                    }
                ]
            }
        },
        "size":10000
    }

    stats = {}
    stats["total_submitted"] = models.Student.query(q=qr)['hits']['total']

    qr['query']['bool']['must'].append({"term":{"status"+app.config['FACET_FIELD']:"new"}})
    stats["new"] = models.Student.query(q=qr)['hits']['total']

    qr['query']['bool']['must'][1] = {"term":{"status"+app.config['FACET_FIELD']:"interviewed"}}
    stats["interviewed"] = models.Student.query(q=qr)['hits']['total']

    qr['query']['bool']['must'][1] = {"query_string":{"default_field": "applications.pae_requested", "query": "*"}}
    st = models.Student.query(q=qr)
    stats["students_pae_requested"] = st['hits']['total']
    
    stats["number_of_pae_requested"] = 0
    stats["number_of_pae_replies"] = 0
    stats["number_of_pae_issued"] = 0
    stats["number_of_pae_awaiting_email"] = 0
    for s in st['hits']['hits']:
        for appn in s['_source'].get('applications',[]):
            if 'pae_requested' in appn:
                stats["number_of_pae_requested"] += 1
            if 'pae_reply_received' in appn and len(appn['pae_reply_received']) > 0:
                stats["number_of_pae_replies"] += 1
            if 'pae_emailed' in appn and len(appn['pae_emailed']) > 0:
                stats["number_of_pae_issued"] += 1
            if ('pae_reply_received' in appn and len(appn['pae_reply_received']) > 0) and not ('pae_emailed' in appn and len(appn['pae_emailed']) > 0):
                stats["number_of_pae_awaiting_email"] += 1

    qr['query']['bool']['must'][1] = {"query_string":{"default_field": "interview.form_date", "query": "*"}}
    st = models.Student.query(q=qr)
    stats["number_of_interviews_done"] = st['hits']['total']

    qr['query']['bool']['must'][1] = {"query_string":{"default_field": "interview.completed_date", "query": "*"}}
    st = models.Student.query(q=qr)
    stats["number_of_interviews_completed"] = st['hits']['total']

    qr['query']['bool']['must_not'].append({"query_string":{"default_field": "interview.emailed_date", "query": "*"}})
    st = models.Student.query(q=qr)
    stats["number_of_action_plans_awaiting_email"] = st['hits']['total']

    stats["total_schools"] = models.School.query()['hits']['total']
    
    del qr['query']['bool']['must_not'][1]
    qr['query']['bool']['must'] = [qr['query']['bool']['must'][0]]
    qr['facets'] = {
        "schools":{
            "terms":{
                "field":"school"+app.config['FACET_FIELD'], 
                "size":1000
            }
        }
    }
    stats["schools_with_students_submitted"] = len(models.Student.query(q=qr)['facets']['schools']['terms'])

    return render_template('leaps/admin/index.html', stats=stats)


# update admin settings
@blueprint.route('/settings', methods=['GET','POST'])
def settings():
    if request.method == 'POST' and current_user.do_admin:
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
    interviewers = []
    users = models.Account.query(q={"query":{"query_string":{"query": "perform_interviews:*"}},"sort":{'id.exact':{'order':'asc'}}, "size":100000})
    if users['hits']['total'] != 0:
        for i in users['hits']['hits']:
            if i.get('_source',{}).get('perform_interviews',False): interviewers.append(i['_source']['id'])

    if uuid is None:
        return render_template('leaps/admin/students.html', interviewers=interviewers, archives=dropdowns('archive','name'))

    if uuid == "new":
        student = models.Student()
    else:
        student = models.Student.pull(uuid)
        if not student.data.get('simd_pc',False):
            try:
                dec = int(student.data['simd_decile'])
                if dec == 10 and student.data.get('simd_quintile',False) == 5:
                    dec = 100
                elif dec < 10:
                    dec = dec * 10
                student.data['simd_pc'] = str(dec)
                student.save()
            except:
                student.data['simd_pc'] = "unknown"
                student.save()
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
            selections=selections,
            interviewers=interviewers
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
                selections=selections,
                interviewers=interviewers
            )

@blueprint.route('/student/<uuid>/fix', methods=['GET'])
def studentfix(uuid=None):
    student = models.Student.pull(uuid)
    for appn in student.data['applications']:
        if appn.get('pae_reply_received',False) and not appn.get('pae_requested',False):
            for apd in student.data['applications']:
                if apd.get('pae_requested',False) and not apd.get('pae_reply_received',False):
                    appn['pae_requested'] = apd['pae_requested']
                    del apd['pae_requested']
                    break
    student.save()
    return redirect('/admin/student/' + uuid)

@blueprint.route('/student/assign', methods=['GET'])
def studentassign():
    interviewer = request.values.get('interviewer')
    query = json.loads(request.values.get('q','{"query":{"match_all":{}}}'))
    selected = json.loads(request.values.get('selected','[]'))
    counter = 0
    if interviewer and (request.values.get('q',False) or request.values.get('selected',False)):
        s = models.Student.query(q=query)
        for i in s.get('hits',{}).get('hits',[]): 
            if len(selected) == 0 or i['_source']['id'] in selected:
                student = models.Student.pull(i['_source']['id'])
                if student.data.get('interviewer', False) != interviewer and not student.data.get('interview', {}).get('emailed_date', False):
                    student.data['interviewer'] = interviewer
                    student.data['status'] = 'allocated_to_interviewer'
                    student.save()
                    counter += 1
    flash(str(counter) + ' selected records were assigned to ' + interviewer, 'success')
    rdu = '/admin/student'
    if request.values.get('q',False):
        if not query.get('fields', False): query["fields"] = ["last_name","first_name","date_of_birth","post_code","simd_decile","school","status","archive","id"]
        rdu += '?source=' + json.dumps(query)
    return redirect(rdu)

@blueprint.route('/student/<uuid>/assign/<iid>', methods=['POST'])
def assignstudent(uuid=None,iid=None):
    if uuid is None or iid is None: abort(404)
    student = models.Student.pull(uuid)
    if student is None: abort(404)
    if student.data.get('interviewer', False) != iid:
        student.data['interviewer'] = iid
        student.save()
    return iid

# move a particular record from one archive to another
@blueprint.route('/student/<uuid>/archive/<aid>', methods=['GET'])
def archivestudent(uuid=None,aid=None):
    if uuid is None or aid is None: abort(404)
    student = models.Student.pull(uuid)
    if student is None: abort(404)
    student.data['archive'] = aid.replace('______','/')
    student.save()
    return redirect(url_for('.archives'))

# print a student as a pdf
@blueprint.route('/student/<sid>.pdf', methods=['GET'])
@blueprint.route('/student/pdf', methods=['GET'])
def pdf(sid,giveback=False):
    if sid == "None":
        student = models.Student()
        thepdf = render_template('leaps/admin/student_pdf', students=[student.data])
    elif sid == "selected":
        query = json.loads(request.values.get('q','{"query":{"match_all":{}}}'))
        selected = json.loads(request.values.get('selected','[]'))
        s = models.Student.query(q=query)
        students = []
        for i in s.get('hits',{}).get('hits',[]):
            if len(selected) == 0 or i['_source']['id'] in selected:
                if not i['_source'].get('simd_pc',False):
                    if i['_source']['simd_decile'] == 'unknown':
                        i['_source']['simd_pc'] = 'unknown'
                    else:
                        try:
                            dec = int(i['_source'].get('simd_decile',0))
                            if dec == 10 and int(i['_source'].get('simd_quintile',0)) == 5:
                                dec = 100
                            elif dec < 10:
                                dec = dec * 10
                            i['_source']['simd_pc'] = str(dec)
                        except:
                            i['_source']['simd_pc'] = 'unknown'
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
            if not student.data.get('simd_pc',False):
                if student.data['simd_decile'] == 'unknown':
                    student.data['simd_pc'] = 'unknown'
                else:
                    try:
                        dec = int(student.data.get('simd_decile',0))
                        if dec == 10 and int(student.data.get('simd_quintile',0)) == 5:
                            dec = 100
                        elif dec < 10:
                            dec = dec * 10
                        student.data['simd_pc'] = str(dec)
                    except:
                        student.data['simd_pc'] = 'unknown'
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
    if ('q' in request.values or 'selected' in request.values) and 'archive' in request.values:
        query = json.loads(request.values.get('q','{"query":{"match_all":{}}}'))
        selected = json.loads(request.values.get('selected','[]'))
        s = models.Student.query(q=query)
        moved = 0
        for i in s.get('hits',{}).get('hits',[]): 
            if len(selected) == 0 or i['_source']['id'] in selected:
                mr = models.Student.pull(i['_source']['id'])
                mr.data["archive"] = request.values['archive']
                mr.save()
                moved += 1
        time.sleep(1)
        flash(str(moved) + ' records moved to archive ' + request.values['archive'])

    elif request.method == "POST":
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
        currentcount=models.Student.query(q={"query":{"bool":{"must":[{"term":{"archive"+app.config['FACET_FIELD']:"current"}}]}}}).get('hits',{}).get('total',0),
        archives=dropdowns('archive','name')
    )





