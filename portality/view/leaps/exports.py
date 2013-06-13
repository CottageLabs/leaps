
from datetime import datetime
import cStringIO as StringIO

import json

from flask import Blueprint, request, flash, abort, make_response, render_template, redirect, send_file
from flask.ext.login import current_user

from portality.core import app
import portality.models as models


blueprint = Blueprint('reports', __name__)


# restrict everything in exports to logged in users who can view admin
@blueprint.before_request
def restrict():
    if current_user.is_anonymous():
        return redirect('/account/login?next=' + request.path)
    elif not current_user.view_admin:
        abort(401)


@blueprint.route('/', methods=['GET','POST'])
def index():
    query = json.loads(request.values.get('query','{"query":{"match_all":{}}}'))
    if 'size' in request.values: query['size'] = request.values['size']
    selected = json.loads(request.values.get('selected','[]'))

    if request.method == 'GET':
        return render_template('leaps/exports/index.html', query=json.dumps(query), selected=json.dumps(selected))

    elif request.method == 'POST':
        keys = request.form.keys()
        s = models.Student.query(q=query)
        students = []
        for i in s.get('hits',{}).get('hits',[]): 
            if (selected and i['_source']['id'] in selected) or not selected:
                students.append(i['_source'])
        
        del keys['query']
        del keys['submit']
        del keys['selected']
        
        return download_csv(students,keys)


def download_csv(recordlist,keys):
    # make a csv string of the records
    csvdata = StringIO.StringIO()
    firstrecord = True
    for record in recordlist:
        # make sure this record has all the keys we would expect
        for key in keys:
            if key not in record.keys():
                record[key] = ""
        # for the first one, put the keys on the first line, otherwise just newline
        if firstrecord:
            fk = True
            for key in sorted(record.keys()):
                if key in keys: # ignore keys that have not been selected by the user
                    if fk:
                        fk = False
                    else:
                        csvdata.write(',')
                    csvdata.write('"' + key + '"')
            csvdata.write('\n')
            firstrecord = False
        else:
            csvdata.write('\n')
        # and then add each record as a line with the keys as chosen by the user
        firstkey = True
        for key in sorted(record.keys()):
            if key in keys:
                if firstkey:
                    firstkey = False
                else:
                    csvdata.write(',')
                if key in ['applications','interests','qualifications','experience']:
                    tidykey = ""
                    firstline = True
                    for line in record[key]:
                        if firstline:
                            firstline = False
                        else:
                            tidykey += '\n'
                        if key == 'applications':
                            tidykey += line['level'] + " " + line['subject'] + " at " + line['institution']
                        elif key == 'interests':
                            tidykey += line['title'] + " - " + line['brief_description']
                        elif key =='qualifications':
                            tidykey += line['year'] + " grade " + line['grade'] + " in " + line['level'] + " " + line['subject']
                        elif key == 'experience':
                            tidykey += line['date_from'] + " to " + line['date_to'] + " " + line['title'] + " - " + line['brief_description']
                else:
                    if isinstance(record[key],bool):
                        if record[key]:
                            tidykey = "true"
                        else:
                            tidykey = "false"
                    else:
                        tidykey = record[key].replace('"',"'")
                csvdata.write('"' + tidykey + '"')

    # dump to the browser as a csv attachment
    csvdata.seek(0)
    return send_file(
        csvdata, 
        mimetype='text/csv',
         attachment_filename="leaps_export_" + datetime.now().strftime("%d%m%Y%H%M") + ".csv",
        as_attachment=True
    )
            





import reportlab, html5lib

# output the student details to a pdf template
def pdf():
    pass
    # get the data for the student - or if no student print a blank pdf
    # get the student pdf template, and run it through the template renderer

    # should this be a blank PAE form requesting response, or a PAE form showing responses
    
    #template = get_template('student_pdf_template')
    #filename = "blank_form"
    #context = Context({"student":"obj")
    #html  = template.render(context)

    #result = StringIO.StringIO()
    #pdf = pisa.pisaDocument(StringIO.StringIO(html.encode("ISO-8859-1", 'ignore')), result,)
    
    # set the status to show the PAE has been sent, and to whom / why / when

    

# here are the old email methods to copy            
# write something to email a PAE form to an institute
'''
from django.core.mail import EmailMessage
def emailpae(paeform,unique_url="",to=['leaps@ed.ac.uk'],message=""):
    subject = "Pre-Application Enquiry from LEAPS"
    if not message:
        message = "LEAPS PAE form attached"
    fromwho = "leaps@ed.ac.uk"
    msg = EmailMessage(subject, message, fromwho, to, headers={'Reply-To': 'leaps@ed.ac.uk'})
    msg.attach('PAE_request.pdf',paeform,'application/pdf')
    msg.send()

'''


# prep a pae for print / email
def ppae(request,admin_site):
    if not request.user.is_staff:
        return HttpResponseForbidden()

    ref = request.GET.get("pae","")
    if not ref:
        ref = request.POST.get("pae","")

    if request.method == "POST":
        if request.POST.get("email",None):
            emails = request.POST["emailaddress"].split(',')
            return pdfy(request,ref,"pae",emails,request.POST["content"])
        else:
            return pdfy(request,ref,"pae")
    else:
        paeobj = Pae.objects.get(pk=ref)
        
        message = "Request for Pre-application enquiry response\n\n"
        message += "Please find attached a PAE from LEAPS.\n\n"
        message += "To enable us to complete our work efficiently, we would appreciate if you could respond to this form "
        message += "via our online response collector. To do so, simply go to the following website address:\n\n"
        message += "https://leapssurvey.org/paes?i=" + str(ref)
        message += "\n\nIf you require input from multiple colleagues, please forward this email to those colleagues "
        message += "and request that they also use the online response collector."
        message += "\n\nThe relevant information you require to make your choices is included in the attached form.\n\n"
        message += "Alternatively, you can print the form and complete by hand, then return either by scanning and "
        message += "emailing back to us, or by post. Our email and postal addresses are also included on the form.\n\n"
        message += "This is an auto-generated email. If you have received this email in error, "
        message += "please contact us using the details below, or delete this email.\n\n"
        message += "Thank you very much for your help, and we look forward to hearing from you.\n\n"
        message += "The LEAPS team\n\n"
        message += "7 Buccleuch Place\nEdinburgh\nEH8 9LW\n\n"
        message += "leaps@ed.ac.uk\n0131 650 4676"

        render_vals = {
            "pae": ref,
            "paeobj":paeobj,
            "message":message
        }
        return render_to_response('ppae.html',render_vals,RequestContext(request, {}))
        



# a function to serialize students to csv
def serialise(request):
    ids = [item for item in request.POST["ids"].split(",")]

    # check in case all were selected
    if 'archive' in request.POST:
        archid = request.POST['archive']
    else:
        archid = 1
    if 'getall' in request.POST:
        if request.POST['getall']:
            ids = []
            recs = Student.objects.filter(archive__id__exact=archid)
            for obj in recs:
                ids.append(obj.id)
        
    students = []
    for ref in ids:
        student = student_for_render(ref)
        cleanstudent = {}
        for model in student:
            if not student[model]:
                if model == 'ExtraAcademicAndCareer':
                    blank = {
                        "any_career_plans":"",
                        "late_decision_to_apply":"",
                        "had_recent_careers_interview":"",
                        "any_additional_qualifications":"",
                        "other_academic_issues":""
                    }
                elif model == 'Interview':
                    blank = {
                        "first_attending_university":"",
                        "mothers_occupation":"",
                        "fathers_occupation":"",
                        "number_of_siblings":"",
                        "place_in_siblings":"",
                        "household_composition":"",
                        "main_language_at_home":"",
                        "looked_after_child":"",
                        "low_income_family":"",
                        "young_carer":"",
                        "law_application":"",
                        "early_application":"",
                        "previous_interview":"",
                        "HN_only_candidate":"",
                        "PAE_action":"",
                        "additional_comments":"",
                        "created": "",
                        "last_altered":""
                    }
                else:
                    blank = {}
                student[model].append(blank)
            if model+"---all" in request.POST:
                cleanstudent[model] = student[model]
            else:
                cleanrows = []
                for row in student[model]:
                    newrow = {}
                    for key,value in row.items():
                        if model+"---"+key in request.POST:
                            newrow[key] = value
                    if newrow:
                        cleanrows.append(newrow)
                cleanstudent[model] = cleanrows
#            if model not in cleanstudent.keys():
#                cleanstudent[model] = student[model]
        if cleanstudent:
            students.append(cleanstudent)
        #students.append(student)
    
    # if specific institute filter applied, restrict applications and paes to only that institute
    inst = request.POST.get('inst',False)
    if inst:
        for student in students:
            filteredapps = []
            filteredpaes = []
            for record in student['Application']:
                if record['institute'] == inst:
                    filteredapps.append(record)
            for record in student['Pae']:
                if record['institute'] == inst:
                    filteredpaes.append(record)
            student['Application'] = filteredapps
            student['Pae'] = filteredpaes
    
    response = HttpResponse(render_to_response('student_csv_template',{"students":students}), mimetype='text/csv',)
    response['Content-Disposition'] = "attachment; filename=report_%s.csv" % datetime.datetime.now().strftime("%d%m%Y")
    return response



