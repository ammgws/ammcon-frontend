#!/usr/bin/env python3
"""
Ammcon is a personal home automation project. This file provides the web UI.
.. module:: ammcon
   :platform: Unix
   :synopsis: Ammcon main module.
.. moduleauthor:: ammgws
"""

# Imports from Python Standard Library
import datetime as dt
import logging.handlers
import os.path
from functools import wraps
# Third party imports
import zmq
from flask import (Flask, abort, flash, json, render_template, redirect, request, session, url_for)
from flask_login import (LoginManager, UserMixin, current_user, login_required, login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.contrib.fixers import ProxyFix
# Ammcon imports
import h_bytecmds as pcmd
import helpers
from auth import OAuthSignIn

# Flask configuration
app = Flask(__name__, template_folder='templates')
app.config.from_object('flask_config')  # load Flask config file
# Get client IP (remote address) from the X-Forward set by the proxy server (AmmCon should never be run without a proxy)
app.wsgi_app = ProxyFix(app.wsgi_app)

# Get Flask secret key from config file or environment variable.
# This key is used to sign sessions (i.e. cookies), but is also needed for Flask's flashing system to work.
if os.environ.get('FLASK_SECRET_KEY') is None:
    app.secret_key = app.config['SECRET_KEY']
else:
    app.secret_key = os.environ['FLASK_SECRET_KEY']

# SQLAlchemy configuration
if os.environ.get('SQLALCHEMY_DATABASE_URL') is None:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['SQLALCHEMY_DATABASE_URL']
db = SQLAlchemy(app)  # create a SQLAlchemy db object from our app object
# Create SQLAlchemy database table if it does not already exist.
db.create_all()


class User(UserMixin, db.Model):
    """ Defines 'User' database model to use with SQLAlchemy."""
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(64), nullable=False, unique=True)
    nickname = db.Column(db.String(64), nullable=False)


# Flask-Login configuration
lm = LoginManager(app)  # create a LoginManager object from our app object
lm.login_view = 'login'  # Redirect non-logged in users to this view
lm.login_message = 'You must login to access AmmCon.'
lm.session_protection = "basic"  # actions requiring a fresh session will require reauthentication, otherwise OK


@lm.user_loader
def load_user(user_id):
    """ User loader for SQLAlchemy. """
    return User.query.get(int(user_id))


# Configure loggers
log_format = logging.Formatter(
    fmt='%(asctime)s.%(msecs).03d %(name)-12s %(levelname)-8s %(message)s (%(filename)s:%(lineno)d)',
    datefmt='%Y-%m-%d %H:%M:%S')
log_folder = app.config['LOG_FOLDER']
log_filename = '_{0}.log'.format(dt.datetime.now().strftime("%Y%m%d_%Hh%Mm%Ss"))
flask_log_handler = logging.handlers.RotatingFileHandler(os.path.join(log_folder, 'flask' + log_filename),
                                                         maxBytes=5 * 1024 * 1024,
                                                         backupCount=3)
flask_log_handler.setFormatter(log_format)
app.logger.addHandler(flask_log_handler)
app.logger.setLevel(level=app.config['LOG_LEVEL'])
app.logger.info('############### Starting Ammcon Web UI ###############')

# Connect to zeroMQ REQ socket, used to communicate with serial port
# to do: handle disconnections somehow (though if background serial worker
# fails then we're screwed anyway)
context = zmq.Context()
socket = context.socket(zmq.REQ)
# socket.setsockopt(zmq.RCVTIMEO, 500)  # timeout in ms
socket.connect('tcp://localhost:5555')
app.logger.info('############### Connected to zeroMQ server ###############')


def internal_only(f):
    """ Decorator used to only allow requests from whitelisted IP addresses."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.remote_addr in app.config['ALLOWED_IP_ADDR']:
            return f(*args, **kwargs)
        else:
            app.logger.warning('Attempted access from: %s', request.remote_addr)
            return abort(403)
    return decorated_function


@app.route('/')
@login_required
def index():
    """ Main page for Ammcon."""
    current_date_time = dt.datetime.now()
    date_time_str = current_date_time.strftime('%Y-%m-%d %H:%M')

    with open('/proc/uptime', 'r') as file:
        uptime_seconds = int(float(file.readline().split()[0]))
        uptime_str = str(dt.timedelta(seconds=uptime_seconds))

    template_data = {
        'date_time': date_time_str,
        'uptime': uptime_str
    }

    return render_template('index.html', **template_data)


@app.route('/command', methods=['GET', 'POST'])
def run_command():
    """ Get command from web UI, and if valid send it off to the micro."""

    # Redirect back to login page if session expired or unauthorised
    # Cannot use @login_required since commands are sent using AJAX and
    # redirects cannot be detected clientside.
    if not current_user.is_authenticated:
        app.logger.info('Received command request from unauthenticated user.')
        return json.dumps({'redirect': url_for('login')})

    command_text = request.args.get('command', '', type=str)
    command = pcmd.micro_commands.get(command_text, None)
    if command:
        app.logger.info('Command "%s" received. '
                        'Sending message: %s', command_text, command)
        socket.send(command)
        response = socket.recv()  # blocks until response is found
        app.logger.info('Response received: %s', helpers.print_bytearray(response))
    else:
        response = None
        app.logger.info('Invalid command. Do nothing')

    # To do: fix up all these kludges. Decide on universal response format.
    if response is None:
        response = 'INVALID'
    elif command_text.startswith('temp'):
        temp, humidity = helpers.temp_val(response)
        response = '{0}{1}\n{2}%'.format(temp,
                                         u'\N{DEGREE CELSIUS}',
                                         humidity)
    elif command_text == 'htpc wol':
        response = helpers.send_magic_packet(app.config['MAC_ADDR'], app.config['BROADCAST_ADDR'])
    elif bytes([response[1]]) == pcmd.nak:
        response = 'NAK'
    elif bytes([response[1]]) == pcmd.ack:
        response = 'ACK'
    else:
        response = 'UNKNOWN'

    current_date_time = dt.datetime.now()
    date_time_str = current_date_time.strftime('%Y-%m-%d %H:%M:%S')

    app.logger.info('Finished handling command request.')

    return json.dumps({'response': response,
                       'time': date_time_str})


@app.route('/command/scene/htpc/<state>')
@internal_only
def set_scene_htpc(state):
    """Set scene for HTPC (e.g. turning off the lights when playback starts.) """
    if state == 'playing':
        # turn off all lights in the HTPC room
        command_text = 'living off'
    elif state == 'paused':
        # turn on the far light in the HTPC room
        command_text = 'living2 low'
    elif state == 'stopped':
        # turn on both lights in the HTPC room
        command_text = 'living on'
    else:
        command_text = 'ignore'

    command = pcmd.micro_commands.get(command_text, None)
    if command:
        app.logger.info('Command "%s" received. '
                        'Sending message: %s', command_text, command)
        socket.send(command)
        response = socket.recv()  # blocks until response is found
        app.logger.info('Response received: %s', helpers.print_bytearray(response))
    else:
        app.logger.info('Invalid command. Do nothing')
    return 'Scene set.'


@app.route('/authorize/<provider>')
def oauth_authorize(provider):
    """ OAUTH authorization flow. """
    # Redirect user to main page if already logged in.
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    oauth = OAuthSignIn.get_provider(provider)
    return oauth.authorize()


@app.route('/callback/<provider>')
def oauth_callback(provider):
    """ Sign in using OAUTH, and redirect back to main page. """
    # Redirect user to main page if already logged in.
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    # Otherwise, attempt to sign user in using OAUTH
    oauth = OAuthSignIn.get_provider(provider)
    username, email = oauth.callback()
    if email is None:
        # Note: Google returns email but other oauth services such as Twitter do not.
        flash('Authentication failed.')
        return redirect(url_for('login'))
    elif not allowed_email(email):
        flash('You are not authorised to use AmmCon.', 'error')
        return redirect(url_for('login'))
    # Check whether the user (email address) already exists in the database.
    user = User.query.filter_by(email=email).first()
    # Create user if necessary.
    if not user:
        # Use first part of email if name is not available.
        if not username:
            username = email.split('@')[0]
        # Create user object
        user = User(nickname=username, email=email)
        # Save to database
        db.session.add(user)
        db.session.commit()
    # Log in the user, and remember them for their next visit unless they log out.
    login_user(user, remember=True)
    return redirect(url_for('index'))


@app.route('/login')
def login():
    """Serve login page if not authenticated."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    """Logout user and redirect to login page."""
    logout_user()
    return redirect(url_for('login'))


@app.before_request
def make_session_permanent():
    app.logger.debug('Set session to permanent before request.')
    session.permanent = True


@app.before_first_request
def setup():
    app.logger.debug('This is before first request')


@app.errorhandler(400)
def key_error(e):
    """Handle invalid requests. Serves a generic error page."""
    # pass exception instance in exc_info argument
    app.logger.warning('Invalid request resulted in KeyError', exc_info=e)
    return render_template('error.html'), 400


@app.errorhandler(403)
def unauthorized_access(error):
    """Handle 403 errors. Serves a generic error page."""
    app.logger.warning('Access forbidden: %s (Error message = %s)', request.path, error)
    return render_template('error.html'), 403


@app.errorhandler(404)
def page_not_found(error):
    """Handle 404 errors. Only this error serves a non-generic page."""
    app.logger.warning('Page not found: %s (Error message = %s)', request.path, error)
    return render_template('page_not_found.html'), 404


@app.errorhandler(500)
def internal_server_error(e):
    """Handle internal server errors. Serves a generic error page."""
    app.logger.warning('An unhandled exception is being displayed to the end user', exc_info=e)
    return render_template('error.html'), 500


@app.errorhandler(Exception)
def unhandled_exception(e):
    """Handle all other errors that may occur. Serves a generic error page."""
    app.logger.error('An unhandled exception is being displayed to the end user', exc_info=e)
    return render_template('error.html'), 500


def allowed_email(email):
    """ Check if the email used to sign in is an allowed user of Ammcon. """
    if email in app.config['ALLOWED_EMAILS']:
        return True
    else:
        app.logger.info('Unauthorised user login attempt.')
    return False

if __name__ == '__main__':
    # Setup SSL certificate for Flask to use when running the Flask dev server
    ssl_context = (app.config['SSL_CERT'], app.config['SSL_KEY'])

    # Run Flask app using Flask development server
    app.run(host='0.0.0.0', port=8058, ssl_context=ssl_context, debug=False, use_reloader=False)
