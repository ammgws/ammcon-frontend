#!/usr/bin/env python3

# Imports from Python Standard Library
import datetime as dt
import logging
import logging.handlers
import os.path
from os import urandom  # pylint: disable=C0412
from sys import path
# Third party imports
import zmq
from flask import (Flask, flash, json, redirect, render_template, request,
                   url_for)
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         current_user, login_required)
from flask_sqlalchemy import SQLAlchemy
# Ammcon imports
import h_bytecmds as PCMD
import helpers
from auth import OAuthSignIn

# Flask configuration
app = Flask(__name__, template_folder='templates')
app.config.from_object('flask_config')
# Generate secret key using the operating system's RNG.
# This key is used to sign sessions (i.e. cookies), but is also needed for
# Flask's "flash" to work.
app.secret_key = urandom(24)

# SQLAlchemy configuration
if os.environ.get('DATABASE_URL') is None:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
db = SQLAlchemy(app)

# Flask-Login configuration
lm = LoginManager(app)
lm.login_view = 'login'  # Rediret non-logged in users to this view
lm.login_message = 'You must login to access AmmCon.'
lm.session_protection = "strong"


@lm.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Connect to zeroMQ REQ socket
context = zmq.Context()
socket = context.socket(zmq.REQ)
socket.connect("tcp://localhost:5555")

# Get absolute path of the dir script is run from
cwd = path[0]  # pylint: disable=C0103

# Configure root logger. Level 5 = verbose to catch mostly everything.
logger = logging.getLogger()
logger.setLevel(level=5)
log_filename = 'ammcon_{0}.log'.format(dt.datetime.now().strftime("%Y%m%d_%Hh%Mm%Ss"))
log_handler = logging.handlers.RotatingFileHandler(os.path.join(cwd, 'logs', log_filename),
                                                   maxBytes=5242880,
                                                   backupCount=3)
log_format = logging.Formatter(fmt='%(asctime)s.%(msecs).03d %(name)-12s %(levelname)-8s %(message)s (%(filename)s:%(lineno)d)',
                               datefmt='%Y-%m-%d %H:%M:%S')
log_handler.setFormatter(log_format)
logger.addHandler(log_handler)
# Lower requests module's log level so that OAUTH2 details aren't logged
logging.getLogger('requests').setLevel(logging.WARNING)
# Quieten SleekXMPP output
# logging.getLogger('sleekxmpp.xmlstream.xmlstream').setLevel(logging.INFO)
logging.info('############### Starting Ammcon ###############')

# Create SQLAlchemy database file if it does not already exist.
db.create_all()


class User(UserMixin, db.Model):
    ''' Defines 'User' database structure to use with SQLAlchemy.'''
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(64), nullable=False, unique=True)
    nickname = db.Column(db.String(64), nullable=False)


@app.route('/')
@login_required
def index():
    ''' Main page for Ammcon.'''
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
    ''' Get command from web UI, and if valid send it off to the micro.'''

    # Redirect back to login page if session expired or unauthorised
    # Cannot use @login_required since commands are sent using AJAX and
    # redirects cannot be detected clientside.
    if not current_user.is_authenticated:
        return json.dumps({'redirect': url_for('login')})

    command_text = request.args.get('command', '', type=str)
    logging.debug('Command "%s" received. '
                  'Sending off for processing...', command_text)
    command = PCMD.micro_commands.get(command_text, "invalid")
    socket.send(command)
    response = socket.recv()  # blocks until response is found
    logging.debug('Response received: %s', helpers.print_bytearray(response))

    # To do: fix up all these kludges. Decide on universal response format.

    if response is None:
        response = 'EMPTY'
    elif command_text.startswith('temp'):
        temp, humidity = helpers.temp_val(response)
        response = '{0}{1}\n{2}%'.format(temp,
                                         u'\N{DEGREE CELSIUS}',
                                         humidity)
    elif command_text == 'htpc wol':
        response = helpers.send_magic_packet('BC:5F:F4:FA:85:DB')
    elif bytes([response[1]]) == PCMD.nak:
        response = 'NAK'
    elif bytes([response[1]]) == PCMD.ack:
        response = 'ACK'
    else:
        response = 'UNKNOWN'

    current_date_time = dt.datetime.now()
    date_time_str = current_date_time.strftime('%Y-%m-%d %H:%M')

    return json.dumps({'response': response,
                       'time': date_time_str})


@app.route('/authorize/<provider>')
def oauth_authorize(provider):
    ''' OAUTH authorization flow. '''
    # Redirect user to main page if already logged in.
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    oauth = OAuthSignIn.get_provider(provider)
    return oauth.authorize()


@app.route('/callback/<provider>')
def oauth_callback(provider):
    ''' Sign in using OAUTH, and redirect back to main page. '''
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
        nickname = username
        # Use first part of email if name is not available.
        if nickname is None or nickname == "":
            nickname = email.split('@')[0]
        # Create user object
        user = User(nickname=username, email=email)
        # Save to database
        db.session.add(user)
        db.session.commit()
    # Log in the user, and remember them for their next visit unless they log out.
    login_user(user, remember=True)
    return redirect(url_for('index'))


def allowed_email(email):
    ''' Check if the email used to sign in is an allowed user of Ammcon. '''
    if email in app.config['ALLOWED_EMAILS']:
        return True
    return False


@app.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.errorhandler(404)
def page_not_found(error):
    logging.warning('Page not found: %s (Error message = %s)', (request.path), error)
    return render_template('page_not_found.html'), 404


if __name__ == '__main__':
    # Setup SSL certificate for Flask to use
    ssl_context = ('kayoway_com.crt', 'kayoway_com.key')

    # Run Flask app using Flask development server
    app.run(host='0.0.0.0', port=8058, ssl_context=ssl_context, debug=False, use_reloader=False)
