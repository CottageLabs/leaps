
from datetime import datetime
import cStringIO as StringIO

import json, string

from flask import Blueprint, request, flash, abort, make_response, render_template, redirect, send_file
from flask.ext.login import current_user

from portality.core import app
import portality.models as models
import portality.util as util


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
    query = json.loads(request.values.get('q','{"query":{"match_all":{}}}'))
    selected = json.loads(request.values.get('selected','[]'))

    if request.method == 'GET':
        return render_template('leaps/exports/index.html', query=json.dumps(query), selected=json.dumps(selected))

    elif request.method == 'POST':
        keys = request.form.keys()
        s = models.Student.query(q=query)
        students = []
        for i in s.get('hits',{}).get('hits',[]): 
            if len(selected) == 0 or i['_source']['id'] in selected:
                students.append(i['_source'])
        
        keys = [ i for i in keys if i not in ['query','submit','selected']]
        
        return download_csv(students,keys)

def fixify(strng):
    newstr = ''
    allowed = string.lowercase + string.uppercase + "@!%&*()_-+=;:~#./?[]{}, '" + '0123456789'
    for part in strng:
        if part == '\n':
            newstr += '  '
        elif part in allowed:
            newstr += part
    return newstr

def download_csv(recordlist,keys):
    # re-order some of the keys
    if 'simd_pc' in keys:
        keys.remove('simd_pc')
        keys = ['simd_pc'] + keys
    if 'simd_decile' in keys:
        keys.remove('simd_decile')
        keys = ['simd_decile'] + keys
    if 'post_code' in keys:
        keys.remove('post_code')
        keys = ['post_code'] + keys
    if 'local_authority' in keys:
        keys.remove('local_authority')
        keys = ['local_authority'] + keys
    if 'shep_school' in keys:
        keys.remove('shep_school')
        keys = ['shep_school'] + keys
    if 'leaps_category' in keys:
        keys.remove('leaps_category')
        keys = ['leaps_category'] + keys
    if 'school' in keys:
        keys.remove('school')
        keys = ['school'] + keys
    if 'post_code' in keys:
        keys.remove('post_code')
        keys = ['post_code'] + keys
    if 'address' in keys:
        keys.remove('address')
        keys = ['address'] + keys
    if 'gender' in keys:
        keys.remove('gender')
        keys = ['gender','gender_other'] + keys
    if 'date_of_birth' in keys:
        keys.remove('date_of_birth')
        keys = ['date_of_birth'] + keys
    if 'last_name' in keys:
        keys.remove('last_name')
        keys = ['last_name'] + keys
    if 'first_name' in keys:
        keys.remove('first_name')
        keys = ['first_name'] + keys
    if 'applications' in keys:
        keys.remove('applications')
        keys = keys + ['applications','pae_requested','notes','pae_replied','pae_consider','pae_conditions']

    # make a csv string of the records
    csvdata = StringIO.StringIO()
    firstrecord = True
    for record in recordlist:
        # for the first one, put the keys on the first line, otherwise just newline
        if firstrecord:
            fk = True
            for key in keys:
                if fk:
                    fk = False
                else:
                    csvdata.write(',')
                if key == 'simd_pc':
                    csvdata.write('"simd %"')
                elif key == 'summer_school':
                    csvdata.write('"summer school interest"')
                else:
                    csvdata.write('"' + key + '"')
            csvdata.write('\n')
            firstrecord = False
        else:
            csvdata.write('\n')
        # and then add each record as a line with the keys as chosen by the user
        firstkey = True
        for key in keys:
            if firstkey:
                firstkey = False
            elif key not in ['pae_requested','notes','pae_replied','pae_consider','pae_conditions','gender_other']:
                csvdata.write(',')
            if (key in record.keys() or key in ['address','simd_pc']) and key != 'gender_other':
                if key == 'applications':
                    appns = ""
                    reqs = ""
                    notes = ""
                    repls = ""
                    cons = ""
                    conds = ""
                    firstline = True
                    for line in record[key]:
                        if firstline:
                            splitter = ""
                            firstline = False
                        else:
                            splitter = '\n'
                        appns += splitter + line['level'] + " " + line['subject'] + " at " + line['institution']
                        if 'pae_requested' in line:
                            reqs += splitter + line['pae_requested']
                        else:
                            reqs += splitter
                        if 'notes' in line:
                            notes += splitter + line['notes']
                        else:
                            notes += splitter
                        if line.get('pae_reply_received',"") != "":
                            repls += splitter + line['pae_reply_received']
                            try:
                                cons += splitter + line['consider']
                            except:
                                cons += splitter
                            try:
                                conds += splitter + fixify(line['conditions'])
                            except:
                                conds += splitter
                    tidykey = appns + '","' + reqs + '","' + notes + '","' + repls + '","' + cons + '","' + conds
                elif key in ['interests','qualifications','experience']:
                    tidykey = ""
                    firstline = True
                    for line in record[key]:
                        if firstline:
                            firstline = False
                        else:
                            tidykey += '\n'
                        if key == 'interests':
                            tidykey += fixify(line['title']) + " - " + fixify(line['brief_description'])
                        elif key =='qualifications':
                            tidykey += line['year'] + " grade " + line['grade'] + " in " + line['level'] + " " + line['subject']
                        elif key == 'experience':
                            tidykey += line['date_from'] + " to " + line['date_to'] + " " + fixify(line['title']) + " - " + fixify(line['brief_description'])
                elif key == 'address':
                    if record.get('address_line_1',False):
                        tidykey = fixify(record['address_line_1']) + '\r\n'
                    else:
                        tidykey = ''
                    if record.get('address_line_2',False):
                        tidykey += fixify(record['address_line_2']) + '\r\n'
                    if record.get('city',False):
                        tidykey += fixify(record['city'])
                elif key == 'simd_pc':
                    if record.get('simd_pc',False):
                        tidykey = record['simd_pc']
                    else:
                        try:
                            dec = int(record['simd_decile'])
                            if dec == 10 and int(record.get('simd_quintile',0)) == 5:
                                dec = 100
                            elif dec < 10:
                                dec = dec * 10
                            tidykey = str(dec)
                        except:
                            tidykey = ''
                elif key == 'gender':
                    tidykey = ''
                    if datetime(int(record['created_date'].split('-')[0]),int(record['created_date'].split('-')[1]),int(record['created_date'].split('-')[2].split(' ')[0])) > datetime(2018,6,1):
                        if record[key] == 'Male':
                            tidykey = 'Man / Male (including trans man)'
                        elif record[key] == 'Female':
                            tidykey = 'Woman / Female (including trans woman)'
                        elif record[key] == 'Other':
                            tidykey = 'In another way'
                        elif record[key] == 'Do not wish to disclose':
                            tidykey = 'Prefer not to say'
                        else:
                            tidykey = record[key]
                    else:
                        tidykey = record.get(key,'')
                    tidykey += '","' + fixify(record.get('gender_other','').replace('"',''))
                elif key not in ['pae_requested','notes','pae_replied','pae_consider','pae_conditions','gender_other']:
                    if isinstance(record[key],bool):
                        if record[key]:
                            tidykey = "true"
                        else:
                            tidykey = "false"
                    else:
                        tidykey = fixify(record[key].replace('"',"'"))
                if record['archive'] in ['2012_2013'] and key != "applications":
                    try:
                        tidykey = util.dewindows(tidykey)
                    except:
                        pass
                    try:
                        tidykey = fixify(tidykey)
                    except:
                        pass
                try:
                    csvdata.write('"' + tidykey + '"')
                except:
                    print "errored on writing a key to the csvdata, probably because of ascii error"
            elif key not in ['pae_requested','notes','pae_replied','pae_consider','pae_conditions','gender_other']:
                csvdata.write("")
    # dump to the browser as a csv attachment
    csvdata.seek(0)
    return send_file(
        csvdata, 
        mimetype='text/csv',
         attachment_filename="leaps_export_" + datetime.now().strftime("%d%m%Y%H%M") + ".csv",
        as_attachment=True
    )


