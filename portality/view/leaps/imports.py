import json, csv, time

from flask import Blueprint, request, flash, abort, make_response, render_template, redirect
from flask.ext.login import current_user

from portality.core import app
import portality.models as models
from portality.view.leaps.forms import dropdowns

blueprint = Blueprint('imports', __name__)


# restrict everything in admin to logged in users who can do admin
@blueprint.before_request
def restrict():
    if current_user.is_anonymous():
        return redirect('/account/login?next=' + request.path)
    elif current_user.is_institution and request.path.endswith('subjects'):
        pass
    elif not current_user.do_admin:
        abort(401)


# build an import page
@blueprint.route('/')
@blueprint.route('/<model>', methods=['GET','POST'])
def index(model=None, deleteall=False):
    if request.method == 'GET':
        if model == 'subjects':
            sd = dropdowns('institution','name')
        else:
            sd = None
        return render_template('leaps/admin/import.html', model=model, subjects=sd)
    elif request.method == 'POST':
        try:
            records = []
            if "csv" in request.files.get('upfile').filename:
                upfile = request.files.get('upfile')
                reader = csv.DictReader( upfile )
                records = [ row for row in reader ]
                sourcetype = "csv"
            elif "json" in request.files.get('upfile').filename:
                upfile = request.files.get('upfile')
                records = json.load(upfile)
                sourcetype = "json"

            if model is None:
                model = request.form.get('model',None)
                if model is None:
                    flash("You must specify what sort of records you are trying to upload.")
                    return render_template('leaps/admin/import.html')

            if model == 'subjects':
                klass = getattr(models, 'Institution' )
            else:
                klass = getattr(models, model[0].capitalize() + model[1:] )

            if (deleteall or request.values.get('deleteall',False)) and model != "subjects":
                klass.delete_all()

            if model.lower() in ['school'] and sourcetype == "csv":
                for rec in records:
                    if 'contacts' not in rec:
                        rec['contacts'] = []
                        c = {}
                        if rec.get('contact_name',"") != "":
                            c["name"] = rec['contact_name']
                            del rec['contact_name']
                        if rec.get('contact_email',"") != "":
                            c["email"] = rec['contact_email']
                            del rec['contact_email']
                        if rec.get('contact_department',"") != "":
                            c["department"] = rec['contact_department']
                            del rec['contact_department']
                        if rec.get('contact_phone',"") != "":
                            c["phone"] = rec['contact_phone']
                            del rec['contact_phone']
                        if rec.get('password',"") != "":
                            c["password"] = rec['password']
                            del rec['password']
                        if len(c.keys()) > 0: rec['contacts'].append(c)
                    c = klass(**rec)
                    c.save()

            elif model.lower() in ['institution'] and sourcetype == "csv":
                for rec in records:
                    if 'contacts' not in rec:
                        rec['contacts'] = []
                        c = {}
                        if rec.get('contact_name',"") != "":
                            c["name"] = rec['contact_name']
                            del rec['contact_name']
                        if rec.get('contact_email',"") != "":
                            c["email"] = rec['contact_email']
                            del rec['contact_email']
                        if rec.get('contact_department',"") != "":
                            c["department"] = rec['contact_department']
                            del rec['contact_department']
                        if rec.get('contact_phone',"") != "":
                            c["phone"] = rec['contact_phone']
                            del rec['contact_phone']
                        if len(c.keys()) > 0:
                            c['password'] = "m00shroom"
                            rec['contacts'].append(c)

                        c2 = {}
                        if rec.get('contact_name_2',"") != "":
                            c2["name"] = rec['contact_name_2']
                            del rec['contact_name_2']
                        if rec.get('contact_email_2',"") != "":
                            c2["email"] = rec['contact_email_2']
                            del rec['contact_email_2']
                        if rec.get('contact_department_2',"") != "":
                            c2["department"] = rec['contact_department_2']
                            del rec['contact_department_2']
                        if rec.get('contact_phone_2',"") != "" in rec:
                            c2["phone"] = rec['contact_phone_2']
                            del rec['contact_phone_2']
                        if len(c2.keys()) > 0:
                            c2['password'] = "m00shroom"
                            rec['contacts'].append(c2)

                    if 'subjects' in rec:
                        if len(rec['subjects']) == 0:
                            del rec['subjects']
                        else:
                            def splitup(subj):
                                if '\t' in subj:
                                    interim = subj.split('\t')
                                    obj = {}
                                    if len(interim) == 1:
                                        obj['name'] = interim[0]
                                    elif len(interim) == 2:
                                        obj['level'] = interim[0]
                                        obj['name'] = interim[1]
                                    elif len(interim) == 3:
                                        obj['level'] = interim[0]
                                        obj['name'] = interim[1]
                                        obj['coursecode'] = interim[2]
                                else:
                                    obj = {"name":subj}
                                return obj
                            rec['subjects'] = [splitup(i) for i in rec['subjects'].replace('\r','').split('\n') if len(i) > 0]

                    c = klass(**rec)
                    c.save()

            elif model.lower() == "subjects":
                try:
                    if isinstance(current_user.is_institution,bool):
                        if 'institution' not in request.values or request.values['institution'] == "":
                            flash('You cannot upload subjects without selecting an institution to upload them to. For uploading generic subjects, upload to subject or advancedsubject')
                            return redirect('/admin/import/subjects')
                        institution = klass().pull_by_name(request.values['institution'])
                    else:
                        institution = klass().pull_by_name(current_user.is_institution)

                    if not isinstance(records,list) or (len(records) > 0 and 'name' not in records[0].keys()):
                        flash('Your file appears to have no records or does not have the required keys - "name" is required. Please check your file and try again.')
                    else:
                        try:
                            institution.data['subjects'] = records
                            institution.save()
                            time.sleep(1)
                            flash(str(len(records)) + " subjects have been added.")
                        except:
                            flash('Sorry, there was an unknown error. Please check your file and try again')
                except:
                    flash('Sorry, there was an unknown error. Please check your file and try again')
                
                if isinstance(current_user.is_institution,bool):
                    return redirect('/admin/data/institution')
                else:
                    return redirect('/universities/subjects')

            else:
                klass().bulk(records)
            
            time.sleep(1)
            checklen = klass.query(q="*")['hits']['total']
            
            flash(str(len(records)) + " records have been imported, there are now " + str(checklen) + " records.")
            return redirect('admin/data/' + model)

        except:
            flash("There was an error importing your records. Please try again.")
            return render_template('leaps/admin/import.html', model=model)



