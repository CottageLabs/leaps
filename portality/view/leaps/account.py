import uuid, json, time

from flask import Blueprint, request, make_response, url_for, flash, redirect, abort
from flask import render_template
from flask.ext.login import login_user, logout_user, current_user
from flask.ext.wtf import Form, TextField, TextAreaField, SelectField, BooleanField, PasswordField, HiddenField, validators, ValidationError

from datetime import date

from urlparse import urlparse, urljoin

from portality.view.leaps.forms import dropdowns
from portality import auth
from portality.core import app
import portality.models as models
import portality.util as util

blueprint = Blueprint('account', __name__)


@blueprint.route('/')
def index():
    if current_user.is_anonymous():
        abort(401)
    if not current_user.do_admin:
        return redirect('/account/' + current_user.id)
    users = models.Account.query(q={"query":{"match_all":{}},"sort":{'id.exact':{'order':'asc'}}, "size":100000})
    userstats = {
        "super_user": 0,
        "do_admin": 0,
        "edit_students": 0,
        "view_admin": 0,
        "school_users": 0,
        "institution_users": 0
    }
    if users['hits']['total'] != 0:
        accs = [models.Account.pull(i['_source']['id']) for i in users['hits']['hits']]
        # explicitly mapped to ensure no leakage of sensitive data. augment as necessary
        users = []
        for acc in accs:
            if acc.id in app.config['SUPER_USER']:
                userstats['super_user'] += 1
            elif acc.data.get('do_admin',False):
                userstats["do_admin"] += 1
            elif acc.data.get('edit_students',False):
                userstats["edit_students"] += 1
            elif acc.data.get('view_admin',False):
                userstats["view_admin"] += 1
            if acc.data.get('school',"") != "": userstats["school_users"] += 1
            if acc.data.get('institution',"") != "": userstats["institution_users"] += 1

            user = {'id':acc.id}
            if 'created_date' in acc.data:
                user['created_date'] = acc.data['created_date']
            if request.values.get('users',False) == False or (request.values['users'] == 'school' and acc.data.get('school','') != '') or (request.values['users'] == 'institution' and acc.data.get('institution','') != '') or (request.values['users'] == 'super' and acc.id in app.config['SUPER_USER']) or (request.values['users'] not in ['school','institution','super'] and acc.data.get(request.values['users'],False)):
                users.append(user)
    if util.request_wants_json():
        resp = make_response( json.dumps(users, sort_keys=True, indent=4) )
        resp.mimetype = "application/json"
        return resp
    else:
        return render_template('account/all.html', users=users, userstats=userstats, showing=request.values.get('users',False))


@blueprint.route('/<username>', methods=['GET','POST', 'DELETE'])
def username(username):
    acc = models.Account.pull(username)

    if current_user.do_admin and ( ( request.method == 'POST' and request.values.get('submit','') == "Delete account" ) or request.method == 'DELETE' ):
        if acc: acc.delete()
        time.sleep(1)
        flash("Account " + str(acc.id) + " deleted")
        return redirect('/account')
    elif request.method == 'POST':
        if not auth.user.update(acc,current_user):
            abort(401)
        info = request.json if request.json else request.values
        if info.get('id',False):
            if info['id'] != username:
                acc = models.Account.pull(info['id'])
            else:
                info['api_key'] = acc.data['api_key']
        for k, v in info.items():
            if k == 'password':
                acc.set_password(info['password'])
            elif k not in ['submit']:
                acc.data[k] = info[k]
        acc.save()
        flash('Account updated', "success")
        return render_template('account/view.html', account=acc)
    else:
        if not acc:
            abort(404)
        if util.request_wants_json():
            if not auth.user.update(acc,current_user):
                abort(401)
            resp = make_response( json.dumps(acc.data, sort_keys=True, indent=4) )
            resp.mimetype = "application/json"
            return resp
        else:
            return render_template('account/view.html', account=acc)


def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and \
           ref_url.netloc == test_url.netloc

def get_redirect_target():
    for target in request.args.get('next'), request.referrer:
        if not target:
            continue
        if is_safe_url(target):
            return target

class RedirectForm(Form):
    next = HiddenField()

    def __init__(self, *args, **kwargs):
        Form.__init__(self, *args, **kwargs)
        if not self.next.data:
            self.next.data = get_redirect_target() or ''

    def redirect(self, endpoint='index', **values):
        if is_safe_url(self.next.data):
            return redirect(self.next.data)
        target = get_redirect_target()
        return redirect(target or url_for(endpoint, **values))

class LoginForm(RedirectForm):
    username = TextField('Username', [validators.Required()])
    password = PasswordField('Password', [validators.Required()])

@blueprint.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm(request.form, csrf_enabled=False)
    if request.method == 'POST' and form.validate():
        password = form.password.data
        username = form.username.data
        user = models.Account.pull(username)
        if user is None:
            user = models.Account.pull_by_email(username)
        if user is not None:
            dp = user.data['last_updated'].split(' ')[0].split('-')
            if date(int(dp[0]),int(dp[1]),int(dp[2])) < date(2018,8,1) and user.data.get('agreed_policy',False) == True:
                user.data['previously_agreed_policy'] = True
                user.data['agreed_policy'] = False
                user.save()
        if user is not None and user.check_password(password):
            login_user(user, remember=True)
            flash('Welcome back.', 'success')
            return form.redirect('index')
        else:
            flash('Incorrect username/password', 'error')
    if request.method == 'POST' and not form.validate():
        flash('Invalid form', 'error')
    return render_template('account/login.html', form=form)

@blueprint.route('/forgot', methods=['GET', 'POST'])
def forgot():
    if request.method == 'POST':
        un = request.form.get('un',"")
        account = models.Account.pull(un)
        if account is None: account = models.Account.pull_by_email(un)
        if account is None:
            flash('Sorry, your account username / email address is not recognised. Please contact us.')
        else:
            newpass = util.generate_password()
            account.set_password(newpass)
            account.save()

            to = [account.data['email'],app.config['LEAPS_EMAIL']]
            fro = app.config['LEAPS_EMAIL']
            subject = "LEAPS password reset"
            text = "A password reset request for LEAPS account " + account.id + " has been received and processed.\n\n"
            text += "The new password for this account is " + newpass + ".\n\n"
            text += "You can access your account here:\n\n"
            text += '<a href="https://leapssurvey.org/account/' + account.id
            text += '">https://leapssurvey.org/account/' + account.id + '</a>\n\n'
            text += "If you did NOT request this change, please contact LEAPS immediately.\n\n"
            try:
                util.send_mail(to=to, fro=fro, subject=subject, text=text)
                flash('Your password has been reset. Please check your emails.')
                if app.config.get('DEBUG',False):
                    flash('Debug mode - new password was set to ' + newpass)
            except:
                flash('Email failed.')
                if app.config.get('DEBUG',False):
                    flash('Debug mode - new password was set to ' + newpass)

    return render_template('account/forgot.html')


@blueprint.route('/policy', methods=['GET', 'POST'])
def policy():
    if request.method == 'GET':
        return render_template('account/policy.html')
    elif request.method == 'POST':
        user = models.Account.pull(current_user.id)
        if user:
            user.data['agreed_policy'] = True
            user.save()
            return redirect(get_redirect_target())
        else:
            flash('There was an error. Please try again.', 'error')


@blueprint.route('/logout')
def logout():
    logout_user()
    flash('You are now logged out', 'success')
    return redirect('/')


def existscheck(form, field):
    test = models.Account.pull(form.w.data)
    if test:
        raise ValidationError('Taken! Please try another.')

class RegisterForm(Form):
    w = TextField('Username', [validators.Length(min=3, max=25),existscheck], description="usernames")
    n = TextField('Email Address', [validators.Length(min=3, max=35), validators.Email(message='Must be a valid email address')])
    s = PasswordField('Password', [
        validators.Required(),
        validators.EqualTo('c', message='Passwords must match')
    ])
    c = PasswordField('Repeat Password')
    school = SelectField('School', choices=[(i,i) for i in [""]+dropdowns('school')])
    institution = SelectField('Institution', choices=[(i,i) for i in [""]+dropdowns('institution')])
    view_admin = BooleanField('View admin')
    edit_students = BooleanField('Edit students')
    do_admin = BooleanField('Do admin')

@blueprint.route('/register', methods=['GET', 'POST'])
def register():
    if not app.config.get('PUBLIC_REGISTER',False) and not current_user.do_admin:
        abort(401)
    form = RegisterForm(request.form, csrf_enabled=False)
    if request.method == 'POST' and form.validate():
        api_key = str(uuid.uuid4())
        account = models.Account(
            id=form.w.data.strip(), 
            email=form.n.data.strip(),
            api_key=api_key,
            school = form.school.data,
            institution = form.institution.data,
            view_admin = form.view_admin.data,
            edit_students = form.edit_students.data,
            do_admin = form.do_admin.data
        )
        account.set_password(form.s.data)
        account.save()
        time.sleep(1)
        flash('Account created for ' + account.id, 'success')
        return redirect('/account')
    if request.method == 'POST' and not form.validate():
        flash('Please correct the errors', 'error')
    return render_template('account/register.html', form=form)

