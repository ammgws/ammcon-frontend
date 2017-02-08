"""
Views that handle requests.
"""

# Imports from Python Standard Library
import datetime as dt
from functools import wraps
# Third party imports
from flask import (abort, after_this_request, flash, json, jsonify, render_template, redirect, request, url_for)
from flask_security import (current_user, login_required, login_user, logout_user)
# Ammcon imports
import ammcon.h_bytecmds as pcmd
import ammcon.helpers as helpers
from ammcon.templogger import Session, Device, Temperature, TemperatureSchema
from ammcon_frontend import app
from ammcon_frontend.auth import OAuthSignIn
from ammcon_frontend.models import User, Log


def internal_only(f):
    """ Route decorator used to only allow requests from whitelisted IP addresses set in config file."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.remote_addr in app.config['ALLOWED_IP_ADDR']:
            return f(*args, **kwargs)
        else:
            app.logger.warning('Attempted access from: %s', request.remote_addr)
            return abort(403)

    return decorated_function


@app.route('/test/<deviceid>')
@internal_only
def test_page(deviceid):
    start_datetime = dt.datetime.utcnow() - dt.timedelta(minutes=5)
    end_datetime = dt.datetime.utcnow() - dt.timedelta(minutes=0)
    query = Session().query(Temperature).filter(Temperature.device_id == deviceid).filter(Temperature.datetime.between(start_datetime, end_datetime))
    print(query)
    results = query.all()
    print(results)

    return "ohk"


# TO DO: interface for creating new devices
@app.route('/createdevice/<deviceid>')
@internal_only
def create_device(deviceid):
    # Create new device and add to database
    session = Session()
    device = Device(device_id=deviceid, device_desc='Living room')
    session.add(device)
    session.commit()
    session.close()
    return "ohk"


@app.route('/graph')
def graph_temps():
    start_datetime = dt.datetime.utcnow() - dt.timedelta(hours=24)
    end_datetime = dt.datetime.utcnow() - dt.timedelta(minutes=0)

    query = Session().query(Temperature).filter(Temperature.datetime.between(start_datetime, end_datetime))
    results = query.all()
    print(results)

    temp_schema = TemperatureSchema(only=('datetime', 'temperature', 'humidity'))
    temps = temp_schema.dump(query, many=True).data

    return jsonify(temps)


@app.route('/graphpage')
def graph_page():
    return render_template('graph.html')


@app.route('/sidepanel')
def sidepanel():
    return render_template('side_panel.html')


@app.route('/commandmenu')
def commandmenu():
    return render_template('command_menu.html')


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
@Log.log_db
def run_command():
    """ Get command from web UI, and if valid send it off to the micro."""

    # TO DO: fix up all these kludges. Decide on universal response format.

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
        app.socket.send(command)
        response = app.socket.recv()  # blocks until response is found
        app.logger.info('Response received: %s', helpers.print_bytearray(response))
    elif command_text == 'htpc wol':
        response = helpers.send_magic_packet(app.config['MAC_ADDR'], app.config['BROADCAST_ADDR'])
        app.logger.info('Sent WOL packet')
    else:
        response = None
        app.logger.info('Invalid command. Do nothing')

    if response is None:
        response = 'INVALID'
    elif response == 'ACK':
        response = 'ACK'
    elif command_text.startswith('temp'):
        temp, humidity = helpers.temp_val(response)
        response = '{0}{1}\n{2}%'.format(temp,
                                         u'\N{DEGREE CELSIUS}',
                                         humidity)
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
        app.socket.send(command)
        response = app.socket.recv()  # blocks until response is found
        app.logger.info('Response received: %s', helpers.print_bytearray(response))
    else:
        app.logger.info('Invalid command. Do nothing')
    return 'Scene set.'


@app.route('/command/scene/goodmorning')
@internal_only
def set_scene_morning():
    """Set scene to go along with morning alarm (e.g. turn on bedroom lights.)"""
    # TO DO: make private API calls use non-blocking zmq
    command_text = 'bedroom on'
    command = pcmd.micro_commands.get(command_text, None)
    if command:
        app.logger.info('Command "%s" received. '
                        'Sending message: %s', command_text, command)
        app.socket.send(command)
        response = app.socket.recv()  # blocks until response is found
        app.logger.info('Response received: %s', helpers.print_bytearray(response))
    else:
        app.logger.info('Invalid command. Do nothing')
    return 'Scene set.'


@app.route('/authorize/<provider>')
def oauth_authorize(provider):
    """ OAUTH authorization flow. """
    # Redirect user to main page if already logged in.
    if current_user.is_authenticated:
        app.logger.debug("Redirect authenticated user to main page.")
        return redirect(url_for('index'))
    oauth = OAuthSignIn.get_provider(provider)
    return oauth.authorize()


@app.route('/callback/<provider>')
def oauth_callback(provider):
    """ Sign in using OAUTH, and redirect back to main page. """
    # Redirect user to main page if already logged in.
    if current_user.is_authenticated:
        app.logger.debug("Redirect authenticated user to main page.")
        return redirect(url_for('index'))

    # Otherwise, attempt to sign user in using OAUTH
    oauth = OAuthSignIn.get_provider(provider)
    username, email, photo_url = oauth.callback()
    if email is None:
        # Note: Google returns email but other oauth services such as Twitter do not.
        app.logger.info('OAUTH login failed - null email received.')
        flash('Authentication failed.')
        return redirect(url_for('login'))
    elif not allowed_email(email):
        app.logger.info('Unauthorised email address attempted OAUTH login.')
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
        user = app.user_datastore.create_user(nickname=username, email=email, photo_url=photo_url)
        # default_role = user_datastore.find_role(name="end-user")
        # Give admin roles to preconfigured admin user if not already given
        if email == app.config['ADMIN_ACCOUNT']:
            app.user_datastore.add_role_to_user(user, 'admin')
        else:
            app.user_datastore.add_role_to_user(user, 'end-user')
        # Commit to database
        app.db.session.commit()
        app.logger.info('Created user for {0} with role {1}.'.format(user.email, user.roles))

    # Log in the user, and remember them for their next visit unless they log out.
    login_user(user, remember=True)

    @after_this_request
    # Need to call datastore.commit() after directly using login_user function to
    # make sure the Flask-Security trackable fields are saved to the datastore.
    # See: https://github.com/mattupstate/flask-security/pull/567
    def save_user(response):
        app.user_datastore.commit()
        app.logger.debug('Saved user {0} to database.'.format(user.email))
        return response

    return redirect(url_for('index'))


@app.route('/login')
def login():
    """Serve login page if not authenticated."""
    if current_user.is_authenticated:
        app.logger.debug("Redirect authenticated user to main page.")
        return redirect(url_for('index'))
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    """Logout user and redirect to login page."""
    logout_user()
    return redirect(url_for('login'))


# Removing for now. This was causing Flask to Set-Cookie to everything, including when serving static files.
# Originally added this so that user won't have to relogin between browser/device restarts, but seems like the cookies
# will last long enough without this: logged in on 20161209 00:29, cookie expiry date set to 20171209 15:29.
# @app.before_request
# def make_session_permanent():
#    app.logger.debug('Set session to permanent before request.')
#    session.permanent = True


@app.before_first_request
def setup():
    app.logger.debug('This is before first request')
    # Create any SQLAlchemy database tables that do not already exist
    try:
        # don't operate on binded databases
        app.db.create_all(bind=None)
    except Exception as e:
        app.logger.error(e, exc_info=e)

    # Create the Roles "admin" and "end-user" -- unless they already exist
    app.user_datastore.find_or_create_role(name='admin', description='Administrator')
    app.user_datastore.find_or_create_role(name='end-user', description='End user')

    app.db.session.commit()


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
