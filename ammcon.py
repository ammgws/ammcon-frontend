#!/home/ammcon/pytalk/py3env-ammcon/bin/python3

'''Ammcon - server for Ammcon home automation system'''

# Imports from Python Standard Library
import datetime as dt
import logging
import os.path
from argparse import ArgumentParser
from subprocess import check_output
from sys import path
from threading import Thread
from time import sleep
from urllib.parse import urlencode

# Third party imports
from configparser import ConfigParser
from matplotlib import rcParams
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import requests
import serial
import ssl
from imgurpython import ImgurClient
from imgurpython.helpers.error import ImgurClientError
from queue import Queue
from sleekxmpp import ClientXMPP
from sleekxmpp.exceptions import IqError, IqTimeout
from sleekxmpp.xmlstream import cert

# Ammcon imports
import h_bytecmds as PCMD

__title__ = 'ammcon'
__version__ = '0.0.1'

# Get absolute path of the dir script is run from
cwd = path[0]  # pylint: disable=C0103


class _ImgurClient():
    ''' Handle authentication and image uploading to Imgur. '''

    def __init__(self):
        self.config_values = ConfigParser()
        self.config_values.read(os.path.join(cwd, 'ammcon_config.ini'))
        self.client_id = self.config_values.get('Imgur', 'client_id')
        self.client_secret = self.config_values.get('Imgur', 'client_secret')
        self.access_token = self.config_values.get('Imgur', 'access_token')
        self.refresh_token = self.config_values.get('Imgur', 'refresh_token')
        self.client = ImgurClient(self.client_id, self.client_secret)

    def save_config(self):
        ''' Save tokens to config file.'''
        self.config_values['Imgur']['access_token'] = self.access_token
        self.config_values['Imgur']['refresh_token'] = self.refresh_token
        with open(os.path.join(cwd, 'ammcon_config.ini'), 'w') as config_file:
            self.config_values.write(config_file)

    def authenticate(self):
        '''Authenticate with Imgur and obtain access & refresh tokens.'''
        # Authorization flow, pin example (see Imgur docs for other auth types)s
        authorization_url = self.client.get_auth_url('pin')
        print("Go to the following URL: {0}".format(authorization_url))

        # Read in the pin typed into the terminal
        pin = input("Enter pin code: ")
        credentials = self.client.authorize(pin, 'pin')
        self.access_token = credentials['access_token']
        self.refresh_token = credentials['refresh_token']
        self.client.set_user_auth(self.access_token, self.refresh_token)

        # Save tokens for next login
        self.save_config()

    def login(self):
        '''Login to Imgur using refresh token.'''
        # Get client ID, secret and refresh_token from auth.ini
        self.client.set_user_auth(self.access_token, self.refresh_token)

    def upload(self, image_path):
        '''Upload image to Imgur and return link.'''
        return self.client.upload_from_path(image_path, anon=False)


def is_holiday():
    '''Check whether today is a holiday, as bus timetable will be different'''
    with open(os.path.join(cwd, 'holidays.txt'), 'r') as text_file:
        holidays = text_file.readlines()
    date_format = "%Y/%m/%d"
    holiday_datetimes = [dt.datetime.strptime(t.strip('\r\n'), date_format)
                         for t in holidays]
    holiday_datetimes = [t.date() for t in holiday_datetimes]
    return dt.date.today() in holiday_datetimes


def check_bus(direction, _time):
    '''Check bus timetable since Google Maps doesn't support Himeji buses yet.

    Args:
        direction -- bus heading; either 'home' or 'himeji'
        _time -- time you want to ride the bus (usually the current time)
    Returns:
        Time of previous bus, next bus and next bus after that.
    '''

    # Provide shorthand since easier to input 'home' when sending from phone
    if direction == 'home':
        dirn = 'shimotenohigashi'

    # Determine which timetable to reference based on the current day
    if is_holiday():
        filename = 'to_{0}_bustimes_sunday.txt'.format(dirn)
    elif _time.isoweekday() in range(1, 6):
        filename = 'to_{0}_bustimes_weekday.txt'.format(dirn)
    elif _time.isoweekday() == 6:
        filename = 'to_{0}_bustimes_saturday.txt'.format(dirn)
    elif _time.isoweekday() == 7:
        filename = 'to_{0}_bustimes_sunday.txt'.format(dirn)
    with open(os.path.join(cwd, filename), 'r') as text_file:
        bus_sched = text_file.readlines()

    bus_noriba = [row.split(', ')[0] for row in bus_sched]
    bus_times = [row.split(', ')[1] for row in bus_sched]

    date_format = "%H:%M"
    bus_datetimes = [dt.datetime.strptime(t.strip('\r\n'), date_format)
                     for t in bus_times]
    bus_datetimes = [t.replace(year=_time.year,
                               month=_time.month,
                               day=_time.day)
                     for t in bus_datetimes]

    try:
        if bus_datetimes.index(_time):
            next_bus = _time
    except (ValueError, IndexError):
        next_bus = min(bus_datetimes, key=lambda date: abs(_time-date))
        if next_bus < _time:
            try:
                next_bus = bus_datetimes[bus_datetimes.index(next_bus)+1]
            except IndexError:
                next_bus = bus_datetimes[0]
                nextnext_bus = bus_datetimes[1]
        previous_bus = bus_datetimes[bus_datetimes.index(next_bus)-1]
        try:
            nextnext_bus = bus_datetimes[bus_datetimes.index(next_bus)+1]
        except IndexError:
            nextnext_bus = bus_datetimes[0]

    results = ('-------prev-------\n'
               '({0}) {1}\n'
               '-------next-------\n'
               '({2}) {3}\n'
               '({4}) {5}').format(bus_noriba[bus_datetimes.index(previous_bus)],
                                   previous_bus.strftime(date_format),
                                   bus_noriba[bus_datetimes.index(next_bus)],
                                   next_bus.strftime(date_format),
                                   bus_noriba[bus_datetimes.index(nextnext_bus)],
                                   nextnext_bus.strftime(date_format)
                                  )
    return results


def sliding_mean(data, window=5):
    '''Take an array of numbers and smooth them out. See: http://goo.gl/6ScgxV

    Args:
        data -- list of data to be smoothed
        window -- window to use for sliding mean
    Returns:
        List of smoothed data
    '''
    smoothed_data = []
    for i in range(len(data)):
        indices = range(max(i - window + 1, 0),
                        min(i + window + 1, len(data)))
        avg = 0
        for j in indices:
            avg += float(data[j])
        avg /= float(len(indices))
        smoothed_data.append(avg)

    return smoothed_data


def get_graph_data(num_hours):
    ''' Parse temp log file and get data for graphing

    Args:
        hours -- how many hours back to go
    Returns:
        Tuple of lists
    '''
    # 正常では温度は１分おきに記録しているため、ログファイルの最後の（n=hours*60）エントリー
    # のみ見たら処理時間を最小限にできる.
    # Need to make this Windows friendly.. alternative to tail??
    temp_log = check_output(['tail',
                             '-'+str(num_hours*60),
                             os.path.join(cwd, 'temp_log.txt')])
    temp_log = temp_log.decode().split('\n')
    # Remove last item since it will be null ('') due to the last line of
    # the logfile ending with a newline char
    del temp_log[-1]

    # 上記データの記録時間を確認し該当するデータ（ref_time～現在時刻のデータ）のみ残しておく
    # ログファイルの形式: 2016-07-01 23:22, 28.00degC @53.00%RH
    #                  　　 日付    時間,　　 温度　　 　　　湿度
    ref_time = dt.datetime.now() - dt.timedelta(hours=int(num_hours))
    temp_times = []
    temp_vals = []
    humidity_vals = []
    for line in temp_log:
        _data = line.split(', ')
        timestamp = dt.datetime.strptime(_data[0], "%Y-%m-%d %H:%M")
        temp = _data[1][:5]
        humidity = _data[1][11:16]
        if is_number(temp) and ref_time <= timestamp:
            temp_times.append(timestamp)
            temp_vals.append(temp)
            humidity_vals.append(humidity)

    if len(temp_times) <= 2:
        return "Not enough data points to create graph"

    temp_vals = sliding_mean(temp_vals)
    humidity_vals = sliding_mean(humidity_vals)

    return (temp_times, temp_vals, humidity_vals)


def graph(num_hours):
    '''Generate graph of past n hours of room temperature

    Args:
        hours -- how many hours back to graph
    Returns:
        Message to send back to Hangouts user
    '''

    temp_times, temp_vals, humidity_vals = get_graph_data(num_hours)

    # Setup plot, title, axes labels
    fig = plt.figure()
    ax1 = fig.add_subplot(111,
                          xlabel='time',
                          # ylabel=u'Temp (\u00B0C)',
                          ylabel='Temp (degC)',
                          title='Temperature over last {0} hour(s)'.format(num_hours))
    ax1.yaxis.label.set_color('blue')
    ax2 = ax1.twinx()  # Setup second y-axis (using same x-axis)
    ax2.yaxis.label.set_color('red')
    ax2.set_ylabel('%RH')
    rcParams.update({'figure.autolayout': True})

    # Plot the graphs
    ax1.plot(temp_times, temp_vals)
    ax2.plot(temp_times, humidity_vals, 'red')

    # Annotate the min and max temps on the graph
    min_temp = min(temp_vals)
    min_timestamp = temp_times[temp_vals.index(min_temp)]
    max_temp = max(temp_vals)
    max_timestamp = temp_times[temp_vals.index(max_temp)]
    ax1.annotate(str(min_temp)[:5],
                 xy=(mdates.date2num(min_timestamp), min_temp),
                 xytext=(-20, 20),
                 textcoords='offset points',
                 arrowprops=dict(arrowstyle='-|>'),
                 bbox=dict(boxstyle='round,pad=0.2', fc='yellow', alpha=0.3)
                )
    ax1.annotate(str(max_temp)[:5],
                 xy=(mdates.date2num(max_timestamp), max_temp),
                 xytext=(-20, 20),
                 textcoords='offset points',
                 arrowprops=dict(arrowstyle='-|>'),
                 bbox=dict(boxstyle='round,pad=0.2', fc='yellow', alpha=0.3)
                )

    # Setup x-axis formatting
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax1.xaxis.set_major_locator(mdates.MinuteLocator(interval=num_hours*5))
    # Rotate and right align x-axis date ticklabels so they don't overlap.
    plt.gcf().autofmt_xdate()

    folder = os.path.join(cwd, 'graphs')
    if not os.path.exists(folder):
        os.makedirs(folder)
    filename = 'tempPlot_{0}.png'.format(dt.datetime.now().strftime("%Y%m%d_%Hh%Mm%Ss"))
    plt.savefig(os.path.join(folder, filename))

    # Login to Imgur and upload image
    imgur_client = _ImgurClient()
    try:
        imgur_client.login()
    except ImgurClientError as err:
        print(err.error_message)
        # command_log.info('%s; %s', err.error_message, err.status_code)
        imgur_client.authenticate()
    imgur_resp = imgur_client.upload(os.path.join(folder, filename))

    # Prepare message to send back to Hangouts user
    return 'Graph of last {0} hour(s): {1}'.format(num_hours, imgur_resp['link'])


def is_number(num):
    ''' Placeholder docstring - update later '''
    try:
        float(num)
        return True
    except ValueError:
        pass

    return False

# def is_valid_temp(s):
#    '''Determine if the detected change in room temperature is
#    within defined limit'''
#    # Current implementation is broken.
#    # Also need to consider the time between temp values
#    try:
#        is_number(s)
#        if abs(float(s) - float(prev_temp)) > MAX_TEMP_CHANGE:
#            return True
#    except ValueError:
#        pass
#
#    return False


def current_time():
    '''Return datetime object of current time in format YYYY-MM-DD HH:MM.'''
    now = dt.datetime.now()
    return str(now.strftime("%Y-%m-%d %H:%M"))


def is_valid_ac_mode(mode):
    '''Determine if received AC mode command is valid.'''
    if mode in ['auto', 'heat', 'dry', 'cool']:
        return True
    return False


def is_valid_ac_fan(fan_speed):
    '''Determine if received AC fan speed command is valid.'''
    if fan_speed in ['auto', 'quiet', '1', '2', '3']:
        return True
    return False


def is_valid_ac_temp(temp):
    '''Determine if received AC temperature command is valid.
       Probably differs per manufacturer but will set to 17<->30 degrees.
    '''
    try:
        if 17 <= temp <= 30:
            return True
    except ValueError:
        pass
    return False


def build_ac_command(ac_temp, ac_mode, ac_fan, ac_spec, ac_power):
    '''Build up AC control command for microcontroller based on
    received Hangouts command.
    '''
    temp = chr(int(ac_temp)-17)

    mode_dict = {'auto': '\x00',
                 'cool': '\x01',
                 'dry': '\x02',
                 'heat': '\x03'}
    mode = mode_dict[ac_mode]

    fan_dict = {'auto': '\x00',
                'quiet': '\x02',
                '1': '\x04',
                '2': '\x08',
                '3': '\x0c'}
    fan = fan_dict[ac_fan]

    spec_dict = {'powerful': '\x01',
                 'sleep': '\x03',
                 'default': '\x00'}
    spec = spec_dict[ac_spec]

    if ac_power == 'on':
        power = '\x01'
    else:
        power = '\x00'

    # AC cmd: Start byte | header | power | temp | mode | fan | spec | end byte
    cmd = '\xCE\xAC{0}{1}{2}{3}{4}x7F'.format(power, temp, mode, fan, spec)
    return cmd


class _SerialSim():
    '''Simulate serial port & microcontroller for debugging purposes.'''
    def __init__(self):
        self.random = __import__('random')
        self.waiting = False
        self.response = None

    def write(self, command):
        '''Simulate ser.write functionality. Send out random temp values.'''
        if command == PCMD.micro_commands['temp']:
            temp = round(self.random.uniform(0.5, 40.0), 2)
            humidity = round(self.random.uniform(25.00, 90.00), 2)
            self.response = 'Temp is {0}degC @{1}%RH'.format(temp,
                                                             humidity).encode()
            self.waiting = True
            sleep(2)  # Wait a couple secs for readline to finish
            self.waiting = False
        else:
            random_msg = self.random.randint(0, 100)
            self.response = 'ohk {0}'.format(random_msg).encode()

    def readline(self):
        '''Simulate ser.readline functionality.'''
        return self.response

    def inWaiting(self):  # pylint: disable=C0103
        '''Simulate ser.inWaiting functionality.'''
        return self.waiting


class _AmmConSever(ClientXMPP):
    '''
    Create AmmCon server to handle connection to serial port
    and Hangouts server
    '''

    # pylint: disable=too-many-instance-attributes
    # 11 instance variables seems OK to me in this case

    def __init__(self, debug_mode, config_path):
        # Setup loggers
        self.command_log = logging.getLogger('Ammcon.CommandLog')
        self.temp_log = logging.getLogger('Ammcon.TempLog')
        self.xmpp_log = logging.getLogger('Ammcon.XMPP')

        # Set up serial port instance
        self.setup_serial(debug_mode)

        # Read in Ammcon config values
        self.config = ConfigParser()
        self.config.read(config_path)

        # Get AmmCon user information
        self.amm_hangouts_id = self.config.get('Amm', 'HangoutsID')
        self.amm_name = self.config.get('Amm', 'Name')
        self.amm_email = self.config.get('Amm', 'Email')

        # Get access token and email address for Hangouts login
        access_token = self.authenticate(config_path)
        ammcon_email = google_getemail(access_token)

        # Setup new SleekXMPP client to connect to Hangouts
        # Not passing in password arg as using OAUTH2 to login
        ClientXMPP.__init__(self,
                            jid=ammcon_email,
                            password=None,
                            sasl_mech='X-OAUTH2')
        self.credentials['access_token'] = access_token
        # Note auto_reconnect seems to be broken if access token is expired
        # at the time reconnect is attempted.
        self.auto_reconnect = True
        # Register XMPP plugins (order does not matter.)
        self.register_plugin('xep_0030')  # Service Discovery
        self.register_plugin('xep_0004')  # Data Forms
        self.register_plugin('xep_0199')  # XMPP Ping

        # The session_start event will be triggered when the
        # XMPP client establishes its connection with the server
        # and the XML streams are ready for use. We want to
        # listen for this event so that we can initialize our roster.
        self.add_event_handler('session_start', self.start)

        # Triggered whenever a message stanza is received.
        # Note this includes MUC and error messages.
        self.add_event_handler('message', self.message)

        # Triggered whenever a 'connected' xmpp event is stanza is received,
        # in particular when connection to xmpp server is established.
        # Fetches a new access token and update the class' access_token value.
        # This is a workaround for a bug I've encountered when SleekXMPP
        # attempts to reconnect, but fails due to using an old access token.
        # Access token is first set when initialising the client, however since
        # Google access tokens expire after one hour, if SleekXMPP attempts a
        # reconnect after one hour has passed, the sasl_mechanism will submit
        # the old access token and end up failing (failed_auth') and the server
        # instance is ended.
        self.add_event_handler('connected', self.reconnect_workaround(config_path))

        # Using a Google Apps custom domain, the certificate
        # does not contain the custom domain, just the GTalk
        # server name. So we will need to process invalid
        # certifcates ourselves and check that it really
        # is from Google.
        self.add_event_handler("ssl_invalid_cert", self.invalid_cert)

        # Setup serial manager thread and queues
        self.command_queue = Queue()
        self.response_queue = Queue()
        serial_manager_thread = Thread(target=self.serial_manager,
                                       args=(self.command_queue,
                                             self.response_queue, ))
        serial_manager_thread.daemon = True
        serial_manager_thread.start()

        # Setup temp logger timer thread
        temp_logger_thread = Thread(target=self.temp_logger)
        # Disable daemon so that thread isn't killed during a file write
        temp_logger_thread.daemon = False
        self.stop_threads = 0  # flag used to gracefully exit thread
        temp_logger_thread.start()

    def authenticate(self, config_path):
        ''' Get access token for Hangouts login.
        Note that Google access token expires in 3600 seconds.
        '''
        # Get Hangouts login details from config file
        client_id = self.config.get('General', 'client_id')
        client_secret = self.config.get('General', 'client_secret')
        refresh_token = self.config.get('General', 'refresh_token')

        # Authenticate with Google and get access token for Hangouts
        if not refresh_token:
            # If no refresh token set in config file, then need to start
            # new authorization flow and get access token that way.
            self.xmpp_log.debug('No refresh token in config file (val = %s of type %s)',
                                refresh_token,
                                type(refresh_token))
            access_token, refresh_token = google_authenticate(client_id,
                                                              client_secret)
            # Save refresh token for next login
            self.config.set('General', 'refresh_token', refresh_token)
            with open(config_path, 'wb') as config_file:
                self.config.write(config_file)
        else:
            # Use existing refresh token to get access token
            self.xmpp_log.debug('Found refresh token in config file. '
                                'Generating access token...')
            access_token = google_refresh(client_id,
                                          client_secret,
                                          refresh_token)
        return access_token

    def auth_workaround(self, config_path):
        ''' Workaround for SleekXMPP reconnect.
        If a reconnect is attempted after access token is expired,
        auth fails and the client is stopped. Get around this by updating the
        access token whenever the client establishes a connection to the XMPP
        server. By product is that access token is requested twice upon startup.
        '''
        self.credentials['access_token'] = self.authenticate(self, config_path)

    def setup_serial(self, debug_mode):
        ''' Setup serial port. If debug is set then create fake port. '''
        if not debug_mode:
            # First setup serial connection to Ammcon microcontroller.
            # When using FTDI USB adapter on Linux then '/dev/ttyUSB0'
            # otherwise '/dev/ttyAMA0' if using rPi GPIO RX/TX
            # or 'COM1' etc on Windows.
            try:
                self.ser = serial.Serial('/dev/ttyUSB0', 57600, timeout=1)
            except serial.SerialException:
                # Attempt to read from closed port
                print('No device detected or could not connect - '
                      'attempting reconnect in 10 seconds')
                sleep(10)
                self.ser = serial.Serial('/dev/ttyUSB0', 57600, timeout=1)
        else:
            # Set up fake serial port to allow testing without hardware
            self.ser = _SerialSim()

    def invalid_cert(self, pem_cert):
        ''' Verify that certificate originates from Google. '''
        der_cert = ssl.PEM_cert_to_DER_cert(pem_cert)
        try:
            cert.verify('talk.google.com', der_cert)
            self.xmpp_log.debug("CERT: Found GTalk certificate")
        except cert.CertificateError as err:
            self.xmpp_log.error(err)
            self.disconnect(send_close=False)

    def start(self, event):  # pylint: disable=W0613
        '''
        Process the session_start event.

        Typical actions for the session_start event are
        requesting the roster and broadcasting an initial
        presence stanza.

        Like every event handler this accepts a single parameter which
        typically is the stanza that was received that caused the event.
        In this case, event will just be an empty dictionary,
        since there is no associated data.

        Args:
            event -- An empty dictionary. The session_start
                     event does not provide any additional
                     data.
        '''

        self.send_presence()

        try:
            self.get_roster()
        except IqError as err:
            self.xmpp_log.error('There was an error getting the roster')
            self.xmpp_log.error(err.iq['error']['condition'])
            self.disconnect()
        except IqTimeout:
            self.xmpp_log.error('Server is taking too long to respond')
            self.disconnect(send_close=False)

    def message(self, msg):
        '''
        Process incoming message stanzas, check user and
        send valid Ammcon commands to microcontroller.

        Args:
            msg -- The received message stanza. See SleekXMPP docs for
            stanza objects and the Message stanza to see how it may be used.
        Returns:
            Message to send back to Hangouts user
        '''

        # Message stanzas may include MUC messages and error messages,
        # hence check the message type before processing.
        if msg['type'] in ('chat', 'normal'):

            hangouts_user = str(msg['from'])
            command = str(msg['body']).lower()
            response = None
            print('----------------')
            print('Hangouts User ID: {0}'.format(hangouts_user))
            print('Received command: {0}'.format(command))
            print('----------------')

            if self.amm_hangouts_id in hangouts_user:
                print('ammID verified')
                if command in PCMD.micro_commands:
                    print('Command received. Sending to microcontroller...')
                    response = self.send_rs232_command(PCMD.micro_commands[command])
                elif command == 'bus himeji':
                    response = check_bus('himeji', dt.datetime.now())
                elif command == 'bus home':
                    response = check_bus('home', dt.datetime.now())
                elif command[:5] == 'graph':
                    hours = int(float(command[5:]))
                    if is_number(hours) and 1 < hours <= 24:
                        response = graph(hours)
                elif command == 'help':
                    response = ('AmmCon commands:\n'
                                'acxx [Set aircon temp. to xx]\n'
                                'ac mode auto/heat/dry/cool [Set aircon mode]\n'
                                'ac fan auto/quiet/1/2/3 [Set aircon fan setting]\n'
                                'ac powerful [Set aircon to powerful setting]\n'
                                'ac sleep [Enables aircon sleep timer]\n'
                                'ac on/off [Turn on/off aircon]\n'
                                'tv on/off/mute [Turn on/off or mute TV]\n'
                                'bedroom on/off [Turn on/off bedroom lights]\n'
                                'bedroom on full [Turn on bedroom lights to brightest setting]\n'
                                'living on/off [Turn on/off both living room lights]\n'
                                'living night [Set living room lights to night-light mode]\n'
                                'living blue/mix/yellow [Set colour temp of living room lights]\n'
                                'open/close [Open/close curtains]\n'
                                'temp [Get current room temp.]\n'
                                'sched on [Activate scheduler for aircon]\n'
                                'sched hour xx [Set scheduler hour]\n'
                                'sched minute xx [Set scheduler minute]\n'
                                'graphxx [Get graph of temp. over last xx hours]\n'
                                'graph=actual [Set graphing function to plot raw data]\n'
                                'graph=smooth [Set graphing function to plot smoothed data]\n'
                                'smoothingx [Set graph smoothing window to x]\n'
                                'bus himeji [Get times for next bus to Himeji]\n'
                                'bus home [Get times for next bus home]\n')
                else:
                    print('Command not recognised')
                # Send reply back to Hangouts (only if verified user)
                msg.reply(response).send()
            else:
                print('Unauthorised user rejected')

            print('Response: {0} of type {1}'.format(response, type(response)))

    def serial_manager(self, command_queue, response_queue):
        ''' Manage communication for serial port.'''
        for command in iter(command_queue.get, None):
            response = None
            try:
                response = self.send_rs232_command(PCMD.micro_commands[command])
            finally:
                response_queue.put(response)
            command_queue.task_done()

    def send_rs232_command(self, command):
        '''Send command to microcontroller via RS232.
        This function deals directly with the serial port.
        '''
        try:
            self.ser.write(command)
        except serial.SerialTimeoutException:
            #  Timeout for port exceeded (only if timeout is set).
            return -1

        sleep(0.2)  # Give 200ms for microcontroller to react and respond

        try:
            response = self.ser.readline()
        except serial.SerialException:
            # Attempted to read from closed port
            return -2

        while self.ser.inWaiting() > 0:
            response += self.ser.readline()
        self.command_log.info('Command sent: %s', command)
        # Convert byte array to ascii string, strip newline chars
        return str(response, 'ascii').rstrip('\r\n')

    def temp_logger(self):
        '''Get current temperature and log to file.'''
        while self.stop_threads == 0:
            # print('Entered temp_logger thread')
            self.command_queue.put('temp')
            temp = self.response_queue.get()  # block until response is found

            if temp.startswith('Temp is '):
                with open(os.path.join(cwd, 'temp_log.txt'), 'a') as text_file:
                    text_file.write('{0}, {1}\n'.format(current_time(),
                                                        temp[8:].strip('\r\n')))
            else:
                self.temp_log.debug('Unable to get valid temperature. '
                                    'Value received: %s', temp)
            # Aim for 1 minute intervals between temp logs. Break it up into
            # 1sec sleeps so don't have to wait 60s when quitting thread.
            for _ in range(60):
                sleep(1)


def google_authenticate(oauth2_client_id, oauth2_client_secret):
    '''Start authorisation flow to get new access + refresh token.'''

    # Start by getting authorization_code for Hangouts scope.
    # Email info scope used to get email address for login.
    # OAUTH2 client ID and secret are obtained through Google Apps Developers
    # Console for the account I use for Ammcon.
    oauth2_scope = ('https://www.googleapis.com/auth/googletalk '
                    'https://www.googleapis.com/auth/userinfo.email')
    oauth2_login_url = 'https://accounts.google.com/o/oauth2/v2/auth?{}'.format(
        urlencode(dict(
            client_id=oauth2_client_id,
            scope=oauth2_scope,
            redirect_uri='urn:ietf:wg:oauth:2.0:oob',
            response_type='code',
            access_type='offline',
        ))
    )

    # Print auth URL and wait for user to input authentication code
    print(oauth2_login_url)
    auth_code = input("Enter auth code from the above link: ")

    # Make an access token request using the newly acquired authorisation code
    token_request_data = {
        'client_id': oauth2_client_id,
        'client_secret': oauth2_client_secret,
        'code': auth_code,
        'grant_type': 'authorization_code',
        'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob',
        'access_type': 'offline',
    }
    oauth2_token_request_url = 'https://www.googleapis.com/oauth2/v4/token'
    resp = requests.post(oauth2_token_request_url, data=token_request_data)
    values = resp.json()
    access_token = values['access_token']
    refresh_token = values['refresh_token']
    return access_token, refresh_token


def google_refresh(oauth2_client_id, oauth2_client_secret, refresh_token):
    '''Make an access token request using existing refresh token.'''
    # Google has limit of 25 refresh tokens per user account per client.
    # When limit reached, creating a new token automatically invalidates the
    # oldest token without warning. (Limit does not apply to service accounts.)
    # https://developers.google.com/accounts/docs/OAuth2#expiration
    token_request_data = {
        'client_id': oauth2_client_id,
        'client_secret': oauth2_client_secret,
        'refresh_token': refresh_token,
        'grant_type': 'refresh_token',
    }
    oauth2_token_request_url = 'https://www.googleapis.com/oauth2/v4/token'
    resp = requests.post(oauth2_token_request_url, data=token_request_data)
    values = resp.json()
    access_token = values['access_token']
    print('Access token expires in {} seconds'.format(values['expires_in']))
    return access_token


def google_getemail(access_token):
    '''Get email address for Hangouts login.'''
    authorization_header = {"Authorization": "OAuth %s" % access_token}
    resp = requests.get("https://www.googleapis.com/oauth2/v2/userinfo",
                        headers=authorization_header)
    values = resp.json()
    email = values['email']
    return email


def main():
    '''Parse command line args, setup logging and start server instance.'''

    # Get command line arguments
    parser = ArgumentParser(description='Run Ammcon server.')
    parser.add_argument('-ds', '--debugsim',
                        dest='mode', action='store_const',
                        const=1, default=0,
                        help='start in debug mode with simulated serial port')
    parser.add_argument('-c', '--configfile',
                        dest='config_path', action='store',
                        default=os.path.join(cwd, 'ammcon_config.ini'),
                        help='set path to config ini')
    parser.add_argument('-v', action='version', version=__version__)
    args = parser.parse_args()

    # Set up logging to file. Level 5 = verbose to catch mostly everything.
    # Set level to logging.DEBUG for debug, logging.ERROR for errors only.
    logging.basicConfig(level=5,
                        format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                        datefmt='%Y-%m-%d %H:%M',
                        filename=os.path.join(cwd, 'ammcon.log'),
                        filemode='a')
    # Lower log level so that OAUTH2 details etc aren't logged
    logging.getLogger('requests').setLevel(logging.WARNING)

    # Setup AmmCon server instance
    server = _AmmConSever(args.mode, args.config_path)

    # Connect to Hangouts and start processing XMPP stanzas.
    if server.connect(address=('talk.google.com', 5222),
                      reattempt=True,
                      use_tls=True):
        server.process(block=True)
        # When the above is interrupted the server instance will end, so allow
        # temp logger thread to exit gracefully by sending stop signal.
        server.stop_threads = 1
        print('****************************Done******************************')
    else:
        print('Unable to connect to Hangouts.')

if __name__ == '__main__':
    main()
