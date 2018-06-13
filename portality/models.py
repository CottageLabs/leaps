
from datetime import datetime

from portality.core import app, current_user

from portality.dao import DomainObject as DomainObject

import requests, json, uuid

import portality.util as util

'''
Define models in here. They should all inherit from the DomainObject.
Look in the dao.py to learn more about the default methods available to the Domain Object.
When using portality in your own flask app, perhaps better to make your own models file somewhere and copy these examples
'''


class Student(DomainObject):
    __type__ = 'student'

    @classmethod
    def prep(cls, rec):
        if 'id' in rec:
            id_ = rec['id'].strip()
        else:
            id_ = cls.makeid()
            rec['id'] = id_

        # check for school changes and other things that should persist across saves
        try:
            old = Student.pull(rec['id'])
            if old.data.get('post_code',False) != rec.get('post_code',False):
                rec['simd_decile'] = ""
                rec['simd_quintile'] = ""
                rec['simd_pc'] = ""
            if old.data.get('school',False) != rec.get('school',False):
                rec['shep_school'] = ""
                rec['leaps_category'] = ""
                rec['local_authority'] = ""
            if old.data.get('_process_paes',False) and '_process_paes' not in rec:
                rec['_process_paes'] = old.data.get('_process_paes',False)
                rec['_process_paes_date'] = old.data.get('_process_paes_date',datetime.now().strftime("%d-%m-%Y"))
        except:
            pass
        
        rec['last_updated'] = datetime.now().strftime("%Y-%m-%d %H%M")

        if 'archive' not in rec:
            rec['archive'] = 'current'

        if 'created_date' not in rec:
            rec['created_date'] = datetime.now().strftime("%Y-%m-%d %H%M")
        
        if 'status' not in rec or rec['status'] == "":
            rec['status'] = 'new'
        elif rec['status'].startswith('paes') and not rec.get('_process_paes',False):
            rec['_process_paes'] = True
            rec['_process_paes_date'] = datetime.now().strftime("%d-%m-%Y")

        if 'simd_decile' not in rec or rec['simd_decile'] == "":
            s = Simd.pull_by_post_code(rec['post_code'])
            if s is not None:
                rec['simd_decile'] = s.data.get('simd_decile','SIMD decile missing')
                rec['simd_quintile'] = s.data.get('simd_quintile','SIMD quintile missing')
            else:
                rec['simd_decile'] = 'unknown'
                rec['simd_quintile'] = 'unknown'
                
        if 'simd_pc' not in rec or rec["simd_pc"] == "":
            if rec['simd_decile'] != 'unknown':
                dec = int(rec['simd_decile'])
                if dec == 10 and int(rec.get('simd_quintile',0)) == 5:
                    dec = 100
                elif dec < 10:
                    dec = dec * 10
                rec['simd_pc'] = str(dec)
            else:
                rec['simd_pc'] = 'unknown'
                

        if 'leaps_category' not in rec or rec['leaps_category'] == "":
            s = School.query(q={'query':{'term':{'name.exact':rec['school']}}})
            if s.get('hits',{}).get('total',0) == 0:
                rec['leaps_category'] = "unknown"
                rec['shep_school'] = "unknown"
                rec['local_authority'] = "unknown"
            else:
                rec['leaps_category'] = s.get('hits',{}).get('hits',[])[0]['_source'].get('leaps_category','unknown')
                rec['shep_school'] = s.get('hits',{}).get('hits',[])[0]['_source'].get('shep_school','unknown')
                rec['local_authority'] = s.get('hits',{}).get('hits',[])[0]['_source'].get('local_authority','unknown')

        if rec.get('shep_school',False) == "yes":
            rec['shep_school'] = True
        if rec.get('shep_school',False) == "no":
            rec['shep_school'] = False                
        if rec.get('shep_school',False) == "on":
            rec['shep_school'] = True
        if rec.get('shep_school',False) == "off":
            rec['shep_school'] = False                
        if rec.get('shep_school',False) == 1:
            rec['shep_school'] = True
        if rec.get('shep_school',False) == 0:
            rec['shep_school'] = False          

        if rec.get('simd_pc',False) == "yes":
            rec['simd_pc'] = True
        if rec.get('simd_pc',False) == "no":
            rec['simd_pc'] = False                
        if rec.get('simd_pc',False) == "on":
            rec['simd_pc'] = True
        if rec.get('simd_pc',False) == "off":
            rec['simd_pc'] = False                
        if rec.get('simd_pc',False) == 1:
            rec['simd_pc'] = True
        if rec.get('simd_pc',False) == 0:
            rec['simd_pc'] = False          

        return rec


    def save_from_form(self, request):
        
        rec = {
            "qualifications": [],
            "interests": [],
            "applications": [],
            "experience": []
        }
        if 'paequals' in self.data:
            rec['paequals'] = self.data['paequals']
        else:
            rec['paequals'] = {}
        if 'paelocs' in self.data:
            rec['paelocs'] = self.data['paelocs']
        else:
            rec['paelocs'] = {}
        
        for key in request.form.keys():
            if not key.startswith("qualification_") and not key.startswith("interest_") and not key.startswith("application_") and not key.startswith("experience_") and key not in ['submit']:
                val = request.form[key]
                if key == "summer_school" or key == "summer_school_applicant":
                    if val == "on":
                        rec[key] = "yes"
                    else:
                        rec[key] = "no"
                elif val == "on":
                    rec[key] = True
                elif val == "off":
                    rec[key] = False
                elif key in ['additional_qualifications','career_plans','issues_affecting_performance']:
                    rec[key] = util.dewindows(val)
                else:
                    rec[key] = val

        thirdquals = []
        fourthquals = []
        fifthquals = []
        sixthquals = []
        otherquals = []
        for k,v in enumerate(request.form.getlist('qualification_subject')):
            if v is not None and len(v) > 0 and v != " ":
                try:
                    qual = {
                        "subject": v,
                        "year": request.form.getlist('qualification_year')[k],
                        "level": request.form.getlist('qualification_level')[k],
                        "grade": request.form.getlist('qualification_grade')[k]
                    }
                    if qual['year'] == "Third year":
                        thirdquals.append(qual)
                    elif qual['year'] == "Fourth year":
                        fourthquals.append(qual)
                    elif qual['year'] == "Fifth year":
                        fifthquals.append(qual)
                    elif qual['year'] == "Sixth year":
                        sixthquals.append(qual)
                    else:
                        otherquals.append(qual)
                except:
                    pass
        rec['qualifications'] = thirdquals + fourthquals + fifthquals + sixthquals + otherquals

        for k,v in enumerate(request.form.getlist('interest_title')):
            if v is not None and len(v) > 0 and v != " ":
                try:
                    rec["interests"].append({
                        "title":v,
                        'brief_description': util.dewindows(request.form.getlist('interest_brief_description')[k])                        
                    })
                except:
                    pass
        for k,v in enumerate(request.form.getlist('application_subject')):
            if v is not None and len(v) > 0 and v != " ":
                try:
                    appn = {
                        "subject": v,
                        "institution": request.form.getlist('application_institution')[k],
                        "level": request.form.getlist('application_level')[k]
                    }
                    try:
                        appn['appid'] = request.form.getlist('application_appid')[k]
                        if 'appid' not in appn or appn['appid'] == "": appn['appid'] = Student.makeid()
                    except:
                        appn['appid'] = Student.makeid()
                    try:
                        appn['pae_reply_received'] = request.form.getlist('application_pae_reply_received')[k]
                    except:
                        pass
                    try:
                        appn['consider'] = request.form.getlist('application_consider')[k]
                    except:
                        pass
                    try:
                        appn['conditions'] = request.form.getlist('application_conditions')[k]
                    except:
                        pass
                    try:
                        appn['summer_school'] = request.form.getlist('application_summer_school')[k]
                    except:
                        pass
                    try:
                        appn['pae_emailed'] = request.form.getlist('application_pae_emailed')[k]
                    except:
                        pass
                    try:
                        appn['qid'] = request.form.getlist('application_qid')[k]
                    except:
                        pass
                    try:
                        if request.form.getlist('application_pae_requested')[k] == "Yes":
                            qid = uuid.uuid4().hex
                            rec['paequals'][qid] = rec['qualifications']
                            locset = {}
                            locset['post_code'] = self.data['post_code']
                            s = Simd.pull_by_post_code(request.form['post_code'])
                            if s is not None:
                                locset['simd_decile'] = s.data.get('simd_decile','SIMD decile missing')
                                locset['simd_quintile'] = s.data.get('simd_quintile','SIMD quintile missing')
                            else:
                                locset['simd_decile'] = 'unknown'
                                locset['simd_quintile'] = 'unknown'
                            if locset['simd_decile'] != 'unknown':
                                dec = int(locset['simd_decile'])
                                if dec == 10 and int(locset.get('simd_quintile',0)) == 5:
                                    dec = 100
                                elif dec < 10:
                                    dec = dec * 10
                                locset['simd_pc'] = str(dec)
                            else:
                                locset['simd_pc'] = 'unknown'
                            locset['simd20'] = self.data.get('simd20',False)
                            locset['simd40'] = self.data.get('simd40',False)
                            locset['school'] = self.data['school']
                            locset['leaps_category'] = rec['leaps_category']
                            rec['paelocs'][qid] = locset
                            appn['qid'] = qid
                            if 'pae_requested' not in appn:
                                appn['pae_requested'] = datetime.now().strftime("%d/%m/%Y")
                            if '_process_paes_date' not in rec:
                                rec['_process_paes_date'] = datetime.now().strftime("%d/%m/%Y")
                                if rec['status'] == 'paes_all_received':
                                    rec['status'] = 'paes_in_progress'
                                if rec['status'] not in ['paes_in_progress']:
                                    rec['status'] = 'paes_requested'
                        elif request.form.getlist('application_pae_requested')[k] != "No":
                            appn['pae_requested'] = request.form.getlist('application_pae_requested')[k]
                    except:
                        pass
                    rec["applications"].append(appn)
                except:
                    pass
        for k,v in enumerate(request.form.getlist('experience_title')):
            if v is not None and len(v) > 0 and v != " ":
                try:
                    rec["experience"].append({
                        "title":v,
                        "date_from": request.form.getlist('experience_date_from')[k],
                        "date_to": request.form.getlist('experience_date_to')[k],
                        'brief_description': util.dewindows(request.form.getlist('experience_brief_description')[k])
                    })
                except:
                    pass

        if self.id is not None: rec['id'] = self.id
        self.data = rec
        self.save()

    
class School(DomainObject):
    __type__ = 'school'

    @classmethod
    def pull_by_name(cls,name):
        res = cls.query(q={"query":{"term":{'name'+app.config['FACET_FIELD']:name}}})
        if res.get('hits',{}).get('total',0) == 1:
            return cls.pull( res['hits']['hits'][0]['_source']['id'] )
        else:
            return None

    @classmethod
    def prep(cls, rec):
        if 'id' in rec:
            id_ = rec['id'].strip()
        else:
            id_ = cls.makeid()
            rec['id'] = id_
        
        rec['last_updated'] = datetime.now().strftime("%Y-%m-%d %H%M")

        if 'created_date' not in rec:
            rec['created_date'] = datetime.now().strftime("%Y-%m-%d %H%M")
            
        if 'author' not in rec:
            try:
                rec['author'] = current_user.id
            except:
                rec['author'] = "anonymous"

        return rec

    def save(self):
        self.data = self.prep(self.data)
        
        old = self.pull(self.id)

        if old is not None:
            # remove any old accounts
            for oc in old.data.get('contacts',[]):
                if oc.get('email',"") not in [o.get('email',False) for o in self.data.get('contacts',[])]:
                    oldaccount = Account.pull(oc.get('email',""))
                    if oldaccount is not None: oldaccount.delete()
            
            # change school name on related accounts if any            
            if old.data.get('name',False) != self.data.get('name',False):
                res = Account.query(q={"query":{"term":{self.__type__+app.config['FACET_FIELD']:old.data['name']}}})
                for aid in [i['_source']['id'] for i in res.get('hits',{}).get('hits',[])]:
                    ua = Account.pull(aid)
                    if ua is not None and self.data.get('name',False):
                        ua.data[self.__type__] = self.data['name']
                        ua.save()

        for c in self.data.get('contacts',[]):
            # create any new accounts
            if c.get('email',"") != "" and ( old is None or c.get('email',"") not in [o.get('email',False) for o in old.data.get('contacts',[])] ):
                account = Account.pull(c['email'])
                if account is None:
                    c['email'] = c['email'].lower()
                    account = Account(
                        id=c['email'], 
                        email=c['email']
                    )
                    account.data[self.__type__] = self.data.get('name',"")
                    if len(c.get("password","")) > 1:
                        pw = c['password']
                        c['password'] = ""
                    else:
                        pw = "password"
                    account.set_password(pw)
                    account.save()
            # change any passwords
            elif c.get('email',"") != "" and c.get('password',"") != "":
                account = Account.pull(c['email'])
                account.set_password(c['password'])
                account.save()
                c['password'] = ""

        r = requests.post(self.target() + self.data['id'], data=json.dumps(self.data))

    def delete(self):
        # delete contact accounts
        for c in self.data.get('contacts',[]):
            if c['email'] != "":
                exists = Account.pull(c['email'])
                if exists is not None:
                    exists.delete()
        r = requests.delete(self.target() + self.id)

    def save_from_form(self, request):
        rec = {
            "contacts": [],
            "subjects": []
        }
        
        for k,v in enumerate(request.form.getlist('contact_email')):
            if v is not None and len(v) > 0 and v != " ":
                try:
                    rec["contacts"].append({
                        "name": request.form.getlist('contact_name')[k],
                        "department": request.form.getlist('contact_department')[k],
                        "phone": request.form.getlist('contact_phone')[k],
                        "email": v,
                        "password": request.form.getlist('contact_password')[k]
                    })
                except:
                    pass

        for k,v in enumerate(request.form.getlist('subject_name')):
            if v is not None and len(v) > 0 and v != " ":
                try:
                    rec["subjects"].append({
                        "name": v,
                        "level": request.form.getlist('subject_level')[k],
                        "coursecode": request.form.getlist('subject_coursecode')[k]
                    })
                except:
                    pass

        if 'gender_other' in request.form:
            if len(request.form['gender_other']) > 0:
                request.form['gender'] = request.form['gender_other']
            del request.form['gender_other']
        rec['shep_school'] = False
        for key in request.form.keys():
            if not key.startswith("contact_") and not key.startswith("subject_") and key not in ['submit']: #,'agreed']: removed this again, cos form already has agreement in it
                val = request.form[key]
                if key == 'shep_school':
                    if val == "on" or val == "yes":
                        rec[key] = True
                    else:
                        rec[key] = False
                else:
                    rec[key] = val

        if len(rec['contacts']) == 0: del rec['contacts']
        if len(rec['subjects']) == 0: del rec['subjects']
        for k, v in rec.items():
            self.data[k] = v
        
        self.save()


class Institution(School):
    __type__ = 'institution'

class Subject(DomainObject):
    __type__ = 'subject'

class Advancedsubject(DomainObject):
    __type__ = 'advancedsubject'

class Level(DomainObject):
    __type__ = 'level'

class Grade(DomainObject):
    __type__ = 'grade'

class Advancedlevel(DomainObject):
    __type__ = 'advancedlevel'

class Simd(DomainObject):
    __type__ = 'simd'

    @classmethod
    def prep(cls, rec):
        if 'id' not in rec:
            if 'post_code' in rec:
                rec['id'] = rec['post_code'].lower().replace(" ","")
            else:
                rec['id'] = cls.makeid()
        
        rec['last_updated'] = datetime.now().strftime("%Y-%m-%d %H%M")

        if 'created_date' not in rec:
            rec['created_date'] = datetime.now().strftime("%Y-%m-%d %H%M")
            
        if 'author' not in rec:
            try:
                rec['author'] = current_user.id
            except:
                rec['author'] = "anonymous"
                
        return rec

    @classmethod
    def pull_by_post_code(cls, post_code):
        return cls.pull(post_code.lower().replace(" ",""))


class Archive(DomainObject):
    __type__ = 'archive'

    def __len__(self):
        res = Student.query(terms={"archive"+app.config['FACET_FIELD']:self.data["name"]})
        return res['hits']['total']
    
    def delete(self):
        for kid in self.children(justids=True):
            k = Student.pull(kid)
            k.delete()
        r = requests.delete(self.target() + self.id)
    
    def children(self,justids=False):
        kids = []
        res = Student.query(terms={"archive"+app.config['FACET_FIELD']:self.data["name"]}, size=100000)
        if res['hits']['total'] != 0:
            if justids:
                kids = [i['_source']['id'] for i in res['hits']['hits']]
            else:
                kids = [i['_source'] for i in res['hits']['hits']]
        return kids

    @classmethod
    def pull_by_name(cls, name):
        r = cls.query(q={"query":{"term":{"name"+app.config['FACET_FIELD']:name}}})
        try:
            return cls.pull( r['hits']['hits'][0]['_source']['id'] )
        except:
            return None



# The account object, which requires the further additional imports
import portality.auth as auth
from werkzeug import generate_password_hash, check_password_hash
from flask.ext.login import UserMixin

class Account(DomainObject, UserMixin):
    __type__ = 'account'

    @classmethod
    def pull_by_email(cls,email):
        res = cls.query(q={"query":{"term":{'email'+app.config['FACET_FIELD']:email.lower()}}})
        if res.get('hits',{}).get('total',0) == 1:
            return cls.pull( res['hits']['hits'][0]['_source']['id'] )
        else:
            res = cls.query(q={"query":{"query_string":{'query':email.lower(),"default_field":"email"}}})
            if res.get('hits',{}).get('total',0) == 1:
                return cls.pull( res['hits']['hits'][0]['_source']['id'] )
            else:
                return None

    def set_password(self, password):
        self.data['password'] = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.data['password'], password)

    @property
    def is_super(self):
        return auth.user.is_super(self)

    @property
    def do_admin(self):
        return auth.user.do_admin(self)

    @property
    def edit_students(self):
        return auth.user.edit_students(self)

    @property
    def view_admin(self):
        return auth.user.view_admin(self)

    @property
    def is_institution(self):
        return auth.user.is_institution(self)

    @property
    def is_school(self):
        return auth.user.is_school(self)
            
    @property
    def agreed_policy(self):
        if not isinstance(self.is_school,bool) or not isinstance(self.is_institution,bool):
            return self.data.get('agreed_policy',False)
        else:
            return True

    
# a special object that allows a search onto all index types - FAILS TO CREATE INSTANCES
class Everything(DomainObject):
    __type__ = 'everything'

    @classmethod
    def target(cls):
        t = str(app.config['ELASTIC_SEARCH_HOST']).rstrip('/') + '/'
        t += app.config['ELASTIC_SEARCH_DB'] + '/'
        return t


