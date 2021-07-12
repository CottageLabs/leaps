
from flask import Flask, request, abort, render_template
from flask.views import View
from flask.ext.login import login_user, current_user

import portality.models as models
from portality.core import app, login_manager

from portality.view.leaps.account import blueprint as account
from portality.view.leaps.admin import blueprint as admin
from portality.view.leaps.universities import blueprint as universities
from portality.view.leaps.schools import blueprint as schools
from portality.view.leaps.interviews import blueprint as interviews
from portality.view.leaps.forms import blueprint as forms
from portality.view.leaps.imports import blueprint as imports
from portality.view.leaps.exports import blueprint as exports

from portality.view.graph import blueprint as graph
from portality.view.query import blueprint as query
from portality.view.stream import blueprint as stream


app.register_blueprint(account, url_prefix='/account')
app.register_blueprint(admin, url_prefix='/admin')
app.register_blueprint(universities, url_prefix='/universities')
app.register_blueprint(schools, url_prefix='/schools')
app.register_blueprint(schools, url_prefix='/interviews')
app.register_blueprint(forms, url_prefix='/survey')
app.register_blueprint(imports, url_prefix='/admin/import')
app.register_blueprint(exports, url_prefix='/admin/export')

app.register_blueprint(graph, url_prefix='/graph')
app.register_blueprint(query, url_prefix='/query')
app.register_blueprint(stream, url_prefix='/stream')



@login_manager.user_loader
def load_account_for_login_manager(userid):
    out = models.Account.pull(userid)
    return out

@app.context_processor
def set_current_context():
    """ Set some template context globals. """
    return dict(current_user=current_user, app=app, adminsettings=models.Account.pull(app.config['SUPER_USER'][0]).data.get('settings',{}))


@app.before_request
def standard_authentication():
    """Check remote_user on a per-request basis."""
    remote_user = request.headers.get('REMOTE_USER', '')
    if remote_user:
        user = models.Account.pull(remote_user)
        if user:
            login_user(user, remember=False)
    # add a check for provision of api key
    elif 'api_key' in request.values:
        res = models.Account.query(q='api_key:"' + request.values['api_key'] + '"')['hits']['hits']
        if len(res) == 1:
            user = models.Account.pull(res[0]['_source']['id'])
            if user:
                login_user(user, remember=False)


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(401)
def page_not_found(e):
    return render_template('401.html'), 401
        
        
@app.route('/')
def default():
    return render_template('leaps/index.html')


@app.route('/policy')
def policy():
    return render_template('leaps/policy.html')


if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=app.config['DEBUG'], port=app.config['PORT'])

