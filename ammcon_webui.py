#!/usr/bin/env python3

# Imports from Python Standard Library
import datetime as dt
import logging
import logging.handlers
import os.path
from os import urandom  # pylint: disable=C0412
from sys import path
# Third party imports
# from celery import Celery
from flask import Flask, flash, json, redirect, render_template, request, url_for
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from flask_sqlalchemy import SQLAlchemy
# Ammcon imports
from auth import OAuthSignIn
import h_bytecmds as PCMD
import helpers
from huey_config import huey  # import our "huey" object
from huey_worker import handle_command  # import our task


# Flask configuration
app = Flask(__name__, template_folder='templates')
app.config.from_object('config')
# Generate secret key using the operating system's RNG.
# This key is used to sign sessions (i.e. cookies), but is also needed for
# Flask's "flash" to work.
app.secret_key = urandom(24)

# Celery configuration - to implement later after figuring out best practice
# celery = Celery(app.name,
#                backend=app.config['CELERY_BACKEND'],
#                broker=app.config['CELERY_BROKER_URL'])
# celery.conf.update(app.config)
# TaskBase = celery.Task
# class ContextTask(TaskBase):
#    abstract = True
#    def __call__(self, *args, **kwargs):
#        with app.app_context():
#            return TaskBase.__call__(self, *args, **kwargs)
# celery.Task = ContextTask

# SQLAlchemy configuration
if os.environ.get('DATABASE_URL') is None:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
db = SQLAlchemy(app)

# Flask-Login configuration
lm = LoginManager(app)
lm.login_view = 'login'  # Rediret non-logged in users to this view
lm.session_protection = "strong"


@lm.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

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

# Create SQLAlchemy database file if it does not already exist.
db.create_all()


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(64), nullable=False, unique=True)
    nickname = db.Column(db.String(64), nullable=False)


@app.route('/')
@login_required
def index():
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
@login_required
def run_command():
    command = request.args.get('command', '', type=str)
    logging.debug('[WebUI] Command "%s" received. '
                  'Sending to command queue for processing...', command)
    command = PCMD.micro_commands.get(command, "invalid")
    command_task = handle_command(command)
    response = command_task.get(blocking=True)
    # if/when using celery:
    # response = get_cmd_response.delay(command)
    logging.debug('[WebUI] Received reply into response queue. '
                  'Reply received: %s', helpers.print_bytearray(response))

    # To do: fix up all these kludges. Decide on universal response format #

    if response is None:
        response = 'EMPTY'
    elif command.startswith('temp'):
        temp, humidity = helpers.temp_val(response)
        response = '{0}{1}\n{2}%'.format(temp,
                                         u'\N{DEGREE CELSIUS}',
                                         humidity)
    elif bytes([response[1]]) == PCMD.nak:
        response = 'NAK'
    elif bytes([response[1]]) == PCMD.ack:
        response = 'ACK'
    else:
        response = 'UNKNOWN'

    if command == 'htpc wol':
        response = helpers.send_magic_packet('BC:5F:F4:FA:85:DB')

    return json.dumps({'response': response})


#@celery.task()
#def get_cmd_response():
#    response = response_queue.get()  # blocks until response is found
#    # response.wait()
#    return response


#@celery.task()
#def serial_port_worker():
#    # Setup queues for communicating with serial port thread
#    command_queue = Queue()
#    response_queue = Queue()
#    
#    # Setup and start serial port manager thread.
#    # Port: Linux using FTDI USB adaptor; '/dev/ttyUSB0' should be OK.
#    #       Linux using rPi GPIO Rx/Tx pins; '/dev/ttyAMA0'
#    #       Windows using USB adaptor or serial port; 'COM1', 'COM2', etc.
#    serial_port = SerialManager('/dev/ttyUSB0',
#                                command_queue, response_queue)
#    serial_port.start()


#@celery.task()
#def temp_logger():
#    # Setup temp logging thread
#    temp_logger = TempLogger(60, cwd,
#                             command_queue, response_queue)
#    # Start temp logger thread
#    temp_logger.start()


@app.before_request
def before_request():
    if request.url.startswith('http://'):
        url = request.url.replace('http://', 'https://', 1)
        code = 301
        return redirect(url, code=code)


@app.route('/authorize/<provider>')
def oauth_authorize(provider):
    # Redirect user to main page if already logged in.
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    oauth = OAuthSignIn.get_provider(provider)
    return oauth.authorize()


@app.route('/callback/<provider>')
def oauth_callback(provider):
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
    if email in app.config('ALLOWED_EMAILS'):
        return True
    return False


@app.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return render_template('login.html')


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.errorhandler(404)
def page_not_found(error):
    logging.warning('[WebUI] Page not found: %s (Error message = %s)', (request.path), error)
    return render_template('page_not_found.html'), 404


if __name__ == '__main__':

    return_val = handle_command('test')
    print(return_val.get(blocking=True))
    logging.info('############### huey task result: %s ###############', return_val.get(blocking=True))

    # Setup SSL certificate for Flask to use
    # context = ('ssl.crt', 'ssl.key')
    # ssl.key = RSA Private Key (Passphrase removed after creation so that
    # we aren't prompted for passphrase everytime server is restarted - note
    # that this means Triple-DES encryption is removed from the final file.)
    # Using a 1024 bit RSA key encrypted using Triple-DES (on first creation),
    # and stored in a PEM format so that it is readable as ASCII text.
    #
    # ssl.crt = certificate self-signed using the above key.
    #
    # 1. Generate SSL key with passphrase: openssl genrsa -des3 -out ssl.key 1024
    # 2. Generate CSR (Certificate Signing Request): openssl req -new -key ssl.key -out ssl.csr
    # 3. Remove passphrase from key: cp ssl.key ssl.key.original
    #                                openssl rsa -in ssl.key.original -out ssl.key
    # 4. Generate self-signed cert: openssl x509 -req -days 365 -in ssl.csr -signkey ssl.key -out ssl.crt
    # 5. Set file permissions for the unencrypted key: chmod 640 ssl.key
    #                                                  chown root:ssl-cert (only members of 'ssl-cert' user group can access)
    # OR
    # Use LetsEncrpyt/certbot to generate trusted certificate
    context = ('kayoway_com.crt', 'kayoway_com.key')

    # Turning debug mode on (during development) seems to cause issues with AmmCon,
    # so explicitly set to False as a reminder (Flask default is False)
    # Test: set debug to True and set temp logger interval to 1sec and it will
    # act strange, almost as if multiple threads are accessing serial port
    # (program flow not as expected, commands being sent twice in a row before
    # the previous command is processed, etc).
    # When debug is False everything operates as expected.
    # Would like to delve more into this but need to develop other parts first.
    # (Probably a sign that the code as is will not run correctly when managed by nginx etc)
    # Also setting reloader to false as well (though it should be if debug is off), see:
    # http://stackoverflow.com/questions/9276078/whats-the-right-approach-for-calling-functions-after-a-flask-app-is-run?rq=1
    app.run(host='0.0.0.0', port=8058, ssl_context=context, debug=False, use_reloader=False)
