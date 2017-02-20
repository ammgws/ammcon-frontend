"""
Views that handle requests.
"""

# Imports from Python Standard Library
import datetime as dt
from functools import wraps
# Third party imports
import zmq
from flask import (abort, json, jsonify, render_template, redirect, request, url_for)
from flask_security import (current_user, login_required, logout_user)
from sqlalchemy import desc
# Ammcon imports
import ammcon.h_bytecmds as pcmd
import ammcon.helpers as helpers
from ammcon import Session
from ammcon.models import Device, Temperature, TemperatureSchema
from ammcon_frontend import app
from ammcon_frontend.models import Log


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
    start_datetime = dt.datetime.utcnow() - dt.timedelta(minutes=9999)
    end_datetime = dt.datetime.utcnow() - dt.timedelta(minutes=0)
    query = Session().query(Temperature).filter(Temperature.device_id == deviceid).filter(Temperature.datetime.between(start_datetime, end_datetime))
    print(query)
    results = query.all()
    print(results)

    temp_schema = TemperatureSchema(only=('datetime', 'temperature', 'humidity'))
    temps = temp_schema.dump(query, many=True).data

    return jsonify(temps)


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
@login_required
def graph_temps():
    """ Return data to use for plotting temperature/humidity values."""
    start_datetime = dt.datetime.utcnow() - dt.timedelta(hours=12)
    end_datetime = dt.datetime.utcnow() - dt.timedelta(minutes=0)

    query = Session().query(Temperature).filter(Temperature.datetime.between(start_datetime, end_datetime))
    #results = query.all()

    temp_schema = TemperatureSchema(only=('datetime', 'temperature', 'humidity'))
    temps = temp_schema.dump(query, many=True).data

    return jsonify(temps)


@app.route('/data/<deviceid>')
@login_required
def env_data_json(deviceid):
    """ Return temperature/humidity values for the specified device."""

    query = Session().query(Temperature).filter(Temperature.device_id == deviceid).order_by(desc(Temperature.datetime)).first()
    temp_schema = TemperatureSchema(only=('datetime', 'temperature', 'humidity'))
    temp = temp_schema.dump(query).data

    return jsonify(temp)


@app.route('/graphpage')
@login_required
def graph_page():
    return render_template('graph.html')


@app.route('/sidepanel')
def sidepanel():
    return render_template('side_panel.html')


@app.route('/commandmenu')
@login_required
def commandmenu():
    """ Serve command menu HTML. TO DO: send list of devices/commands?"""
    return render_template('command_menu.html')


@app.route('/')
@login_required
def index():
    """ Main page for Ammcon."""

    with open('/proc/uptime', 'r') as file:
        uptime_seconds = int(float(file.readline().split()[0]))
        uptime_str = str(dt.timedelta(seconds=uptime_seconds))

    template_data = {
        'date_time': dt.datetime.utcnow(),
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
        try:
            message_tracker = app.socket.send(command, copy=False, track=True)
        except zmq.ZMQError:
            app.logger.error("ZMQ send failed")
        app.logger.debug(message_tracker)

        # Added (temporarily) for debugging purposes
        n = 0
        while not message_tracker.done:
            app.logger.debug("yarp{}{}".format(command_text, n))
            n += 1

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
        app.db.create_all(bind=None)  # don't operate on binded databases
    except Exception as e:
        app.logger.error(e, exc_info=e)

    # Create the Roles "admin" and "end-user" -- unless they already exist
    app.user_datastore.find_or_create_role(name='admin', description='Administrator')
    app.user_datastore.find_or_create_role(name='end-user', description='End user')
    app.db.session.commit()

    # Connect to zeroMQ REQ socket, used to communicate with serial port
    # to do: handle disconnections somehow (though if background serial worker
    # fails then we're screwed anyway)
    context = zmq.Context().instance()
    app.socket = context.socket(zmq.REQ)
    # socket.setsockopt(zmq.RCVTIMEO, 500)  # timeout in ms
    app.socket.connect('tcp://localhost:5555')
    app.logger.info('############### Connected to zeroMQ server ###############')


if __name__ == '__main__':
    # Setup SSL certificate for Flask to use when running the Flask dev server
    ssl_context = (app.config['SSL_CERT'], app.config['SSL_KEY'])

    # Run Flask app using Flask development server
    app.run(host='0.0.0.0', port=8058, ssl_context=ssl_context, debug=False, use_reloader=False)
