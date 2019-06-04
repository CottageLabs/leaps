import os, requests, json, uuid
from flask import Flask

from portality import default_settings
from flask.ext.login import LoginManager, current_user
login_manager = LoginManager()

from werkzeug import generate_password_hash

def create_app():
    app = Flask(__name__)
    configure_app(app)
    if app.config['INITIALISE_INDEX']: initialise_index(app)
    setup_error_email(app)
    login_manager.setup_app(app)
    return app

def configure_app(app):
    app.config.from_object(default_settings)
    # parent directory
    here = os.path.dirname(os.path.abspath( __file__ ))
    config_path = os.path.join(os.path.dirname(here), 'app.cfg')
    if os.path.exists(config_path):
        app.config.from_pyfile(config_path)

def initialise_index(app):
    mappings = app.config["MAPPINGS"]
    i = str(app.config['ELASTIC_SEARCH_HOST']).rstrip('/')
    i += '/' + app.config['ELASTIC_SEARCH_DB']
    for key, mapping in mappings.iteritems():
        im = i + "/_mapping/" + key         # es 1.x
        typeurl = i + "/" + key
        exists = requests.head(typeurl)     # es 1.x
        if exists.status_code != 200:
            ri = requests.post(i)
            r = requests.put(im, json.dumps(mapping))
            print key, r.status_code            
            if key == "archive":
                a = requests.post(i + '/archive/current', data=json.dumps({
                    'name':'current',
                    'id': 'current'
                }))
                print 'default archive named "current" has been created'
    if len(app.config.get('SUPER_USER',[])) != 0:
        un = app.config['SUPER_USER'][0]
        ia = i + '/account/' + un
        ae = requests.get(ia)
        if ae.status_code != 200:
            su = {
                "id":un, 
                "email":"test@test.com",
                "api_key":str(uuid.uuid4()),
                "password":generate_password_hash(un)
            }
            #c = requests.post(ia, data=json.dumps(su))
            #print "first superuser account created for user " + un + " with password " + un 

def setup_error_email(app):
    ADMINS = app.config.get('ADMINS', '')
    if not app.debug and ADMINS:
        import logging
        from logging.handlers import SMTPHandler
        mail_handler = SMTPHandler('127.0.0.1',
                                   'server-error@no-reply.com',
                                   ADMINS, 'error')
        mail_handler.setLevel(logging.ERROR)
        app.logger.addHandler(mail_handler)

app = create_app()

