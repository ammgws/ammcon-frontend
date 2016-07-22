#!/home/ammcon/pytalk/py3env-ammcon/bin/python3

'''Ammcon - server for Ammcon home automation system'''

# Imports from Python Standard Library
import datetime as dt
import logging
import os
import subprocess
import sys
import time
from argparse import ArgumentParser
from threading import Thread
from urllib.parse import urlencode

# Third party imports
from configparser import ConfigParser
from matplotlib import rcParams
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import queue
import requests
import serial
import ssl
from imgurpython import ImgurClient
from imgurpython.helpers.error import ImgurClientError
import sleekxmpp
from sleekxmpp.xmlstream import cert

# Ammcon imports
import h_bytecmds as PCMD

__title__ = 'ammcon'
__version__ = '0.0.1'

# Get absolute path of the dir script is run from
cwd = sys.path[0]  # pylint: disable=C0103


class _ImgurClient():
    '''
    Handle authentication and image uploading to Imgur.
    '''

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
        # Authorization flow, pin example (see Imgur docs for other auth types)
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
        filename = 'to_{0}bustimes_sunday.txt'.format(dirn)
    elif _time.isoweekday() in range(1, 6):
        filename = 'to_{0}bustimes_weekday.txt'.format(dirn)
    elif _time.isoweekday() == 6:
        filename = 'to_{0}bustimes_saturday.txt'.format(dirn)
    elif _time.isoweekday() == 7:
        filename = 'to_{0}bustimes_sunday.txt'.format(dirn)
    with open(os.path.join(cwd, filename), 'r') as text_file:
        bus_sched = text_file.readlines()

    bus_noriba = [row.split(', ')[0] for row in bus_sched]
    bus_times = [row.split(', ')[1] for row in bus_sched]

    date_format = "%H:%M"
    bus_datetimes = [dt.datetime.strptime(t.strip('\r\n'), date_format)
                     for t in bus_times]
    bus_datetimes = [t.replace(year=_time.year, month=_time.month, day=_time.day)
                     for t in bus_datetimes]

    try:
        if bus_datetimes.index(time):
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

    results = ('-------prev-------'
               '({0}) {1}'
               '-------next-------'
               '({2}) {3}'
               '({4}) {5}').format(bus_noriba[bus_datetimes.index(previous_bus)],
                                   previous_bus.strftime(date_format),
                                   bus_noriba[bus_datetimes.index(next_bus)],
                                   next_bus.strftime(date_format),
                                   bus_noriba[bus_datetimes.index(nextnext_bus)],
                                   nextnext_bus.strftime(date_format)
                                  )
    return results


def sliding_mean(data_array, window=5):
    '''Take an array of numbers and smooth them out. See: http://goo.gl/6ScgxV

    Args:
        data_array -- list of data to be smoothed
        window -- window to use for sliding mean
    Returns:
        Smoothed data in numpy array
    '''
    data_array = np.array(data_array)
    new_list = []
    for i in range(len(data_array)):
        indices = range(max(i - window + 1, 0),
                        min(i + window + 1, len(data_array)))
        avg = 0
        for j in indices:
            avg += data_array[j]
        avg /= float(len(indices))
        new_list.append(avg)

    return np.array(new_list)


def graph(hours, graph_type='smooth', smoothing=5):
    '''Generate graph of past n hours of room temperature

    Args:
        hours -- how many hours back to graph
        graph_type -- choose whether to use smoothing or just plot raw data
        smoothing -- window to use for smoothing function
    Returns:
        Message to send back to Hangouts user
    '''

    # 正常では温度は１分おきに記録しているため、ログファイルの最後の（n=hours*60）エントリーだけ見たら処理時間を最小限にできる
    # Need to make this Windows friendly.. alternative to tail??
    temp_list = subprocess.check_output(['tail',
                                         '-'+str(hours*60),
                                         os.path.join(cwd,
                                                      'temp_log.txt')])
    temp_list = temp_list.decode().split('\n')
    # Remove last item since it will be null ('') due to the last line of
    # the logfile ending with a newline char
    del temp_list[-1]

    # 上記抜粋したデータの記録時間を確認し該当するデータ（ref_time～現在時刻のデータ）のみ残しておく
    # ログファイルの形式: 2016-07-01 23:22, 28.00degC @53.00%RH
    #                   日付    時間,　　 温度　　 @湿度
    date_format = "%Y-%m-%d %H:%M"
    ref_time = dt.datetime.now() - dt.timedelta(hours=int(hours))
    edited_temp_list = []
    for line in temp_list:
        try:
            if (is_number(line.strip('\n').split(', ')[1][:5]) and
                    ref_time <= dt.datetime.strptime(line.strip('\n').split(',')[0], date_format)):
                edited_temp_list.append(line.strip())
        except (ValueError, IndexError, TypeError):
            pass

    if len(edited_temp_list) <= 2:
        return "Not enough data points to create graph"

    temp_times = [dt.datetime.strptime(t.split(', ')[0], date_format) for t in edited_temp_list]
    temp_vals = [float(row.split(', ')[1][:5]) for row in edited_temp_list]
    humidity_vals = [float(row.split(', ')[1][11:16]) for row in edited_temp_list]

    fig = plt.figure()
    ax1 = fig.add_subplot(111)
    ax2 = ax1.twinx()  # Setup second y-axis (using same x-axis)

    title_text = 'Temperature over last {0} hour(s)'.format(hours)
    ax1.set_title(title_text)
    ax1.set_xlabel('time')
    ax1.set_ylabel('degC')
    ax2.set_ylabel('%RH')
    rcParams.update({'figure.autolayout': True})

    if graph_type == 'smooth':
        temp_vals = sliding_mean(temp_vals, smoothing)
        humidity_vals = sliding_mean(humidity_vals, smoothing)
    else:
        # Plot raw data - mostly for debugging purposes
        ax1.plot(temp_times, temp_vals)
        ax2.plot(temp_times, humidity_vals, 'r')

    # Annotate the min and max temps on the graph
    temp_vals_min = min(temp_vals)
    temp_vals_min_time = temp_times[temp_vals.index(temp_vals_min)]
    temp_vals_max = max(temp_vals)
    temp_vals_max_time = temp_times[temp_vals.index(temp_vals_max)]
    ax1.annotate(str(temp_vals_min),
                 (mdates.date2num(temp_vals_min_time), temp_vals_min),
                 xytext=(-20, 20),
                 textcoords='offset points',
                 arrowprops=dict(arrowstyle='-|>'),
                 bbox=dict(boxstyle='round,pad=0.2', fc='yellow', alpha=0.3)
                )
    ax1.annotate(str(temp_vals_max),
                 (mdates.date2num(temp_vals_max_time), temp_vals_max),
                 xytext=(-20, 20),
                 textcoords='offset points',
                 arrowprops=dict(arrowstyle='-|>'),
                 bbox=dict(boxstyle='round,pad=0.2', fc='yellow', alpha=0.3)
                )

    # Setup x-axis formatting
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax1.xaxis.set_major_locator(mdates.MinuteLocator(interval=hours*5))
    # Rotate and right align x-axis date ticklabels so they don't overlap.
    plt.gcf().autofmt_xdate()

    folder = os.path.join(cwd, 'graphs')
    if not os.path.exists(folder):
        os.makedirs(folder)
    filename = 'tempPlot_{0}.png'.format(time.strftime("%Y%m%d_%H-%M-%S"))
    plt.savefig(folder+filename)

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
    return 'Graph of last {0} hour(s): {1}'.format(hours, imgur_resp['link'])


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
            time.sleep(2)  # Wait a couple secs for readline to finish
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


class _AmmConSever(sleekxmpp.ClientXMPP):
    '''
    Create AmmCon server to handle connection to serial port
    and Hangouts server
    '''

    def __init__(self, debug_mode, config_path):
        # Get absolute path of the dir script is run from
        self.cwd = sys.path[0]

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
                time.sleep(10)
                self.ser = serial.Serial('/dev/ttyUSB0', 57600, timeout=1)
        else:
            # Set up fake serial port to allow testing without hardware
            self.ser = _SerialSim()

        # Read in Ammcon config values
        self.config = ConfigParser()
        self.config.read(config_path)
        # Get AmmCon user information
        self.amm_hangouts_id = self.config.get('Amm', 'HangoutsID')
        self.amm_name = self.config.get('Amm', 'Name')
        self.amm_email = self.config.get('Amm', 'Email')
        self.wyn_hangouts_id = self.config.get('Wyn', 'HangoutsID')
        self.wyn_name = self.config.get('Wyn', 'Name')
        self.wyn_email = self.config.get('Wyn', 'Email')
        # Get Hangouts login details
        self.refresh_token = self.config.get('General', 'RefreshToken')
        self.oauth2_client_id = self.config.get('General', 'OAuth2_Client_ID')
        self.oauth2_client_secret = self.config.get('General', 'OAuth2_Client_Secret')

        # Setup loggers
        self.command_log = logging.getLogger('Ammcon.CommandLog')
        self.temp_log = logging.getLogger('Ammcon.TempLog')
        self.xmpp_log = logging.getLogger('Ammcon.XMPP')

        # Authenticate with Google and get access token for Hangouts
        if not self.refresh_token:
            self.access_token, self.refresh_token = google_authenticate(self.oauth2_client_id, self.oauth2_client_secret)
            # Save refresh token for next login
            self.config.set('General', 'RefreshToken', self.refresh_token)
            with open(config_path, 'wb') as config_file:
                self.config.write(config_file)
        else:
            self.access_token = google_refresh(self.oauth2_client_id,
                                               self.oauth2_client_secret,
                                               self.refresh_token)
        self.ammcon_email = google_getemail(self.access_token)

        # Setup new SleekXMPP client to connect to Hangouts
        # Not using real password as using OAUTH2 to login
        sleekxmpp.ClientXMPP.__init__(self, self.ammcon_email, 'yarp')
        self.credentials['access_token'] = self.access_token
        self.auto_reconnect = True
        # Register XMPP plugins (order does not matter.)
        self.register_plugin('xep_0030')  # Service Discovery
        self.register_plugin('xep_0004')  # Data Forms
        self.register_plugin('xep_0199')  # XMPP Ping

        # The session_start event will be triggered when the
        # XMPP client establishes its connection with the server
        # and the XML streams are ready for use. We want to
        # listen for this event so that we can initialize
        # our roster.
        self.add_event_handler("session_start", self.start)

        # The message event is triggered whenever a message
        # stanza is received. Be aware that that includes
        # MUC messages and error messages.
        self.add_event_handler("message", self.message)

        # Using a Google Apps custom domain, the certificate
        # does not contain the custom domain, just the GTalk
        # server name. So we will need to process invalid
        # certifcates ourselves and check that it really
        # is from Google.
        self.add_event_handler("ssl_invalid_cert", self.invalid_cert)

        # Set Ammcon default settings
        self.graph_type = 'smooth'
        self.smoothing = 5
        # Max temp change allowed in log interval (sensor is ±0.5degC)
        # self.max_temp_change = 2.0

        # Setup serial manager thread and queues
        self.command_queue = queue.Queue()
        self.response_queue = queue.Queue()
        serial_manager_thread = Thread(target=self.serial_manager,
                                       args=(self.command_queue,
                                             self.response_queue, ))

        # Disable daemon for now as thread will not gracefully exit
        # (probably no problem for serial port thread, but disable for now)
        # serial_manager_thread.daemon = True
        serial_manager_thread.start()

        # Setup temp logger timer thread
        temp_logger_thread = Thread(target=self.temp_logger)
        # Disable daemon for now as thread will not gracefully exit
        # (could exit during file write. need to add stop event handler))
        # temp_logger_thread.daemon = True
        temp_logger_thread.start()

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
        self.get_roster()

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
                else:
                    if command == 'bus himeji':
                        response = check_bus('himeji', dt.datetime.now())
                    elif command == 'bus home':
                        response = check_bus('home', dt.datetime.now())
                    elif command == 'graph=actual':
                        self.graph_type = 'actual'
                    elif command == 'graph=smooth':
                        self.graph_type = 'smooth'
                    elif command[:9] == 'smoothing':
                        if (is_number(int(float(command[9:]))) and
                                int(float(command[9:])) > 0 and
                                int(float(command[9:])) < 10):
                            self.smoothing = int(float(command[9:]))
                    elif command[:5] == 'graph':
                        if (is_number(int(float(command[5:]))) and
                                int(float(command[5:])) > 0 and
                                int(float(command[5:])) < 25):
                            response = graph(int(float(command[5:])),
                                             self.graph_type,
                                             self.smoothing)
                        else:
                            response = 'Accepted range: graph1 - graph24'
                    elif command == 'help':
                        response = ('AmmCon commands:'
                                    'acxx [Set aircon temp. to xx]'
                                    'ac mode auto/heat/dry/cool [Set aircon mode]'
                                    'ac fan auto/quiet/1/2/3 [Set aircon fan setting]'
                                    'ac powerful [Set aircon to powerful setting]'
                                    'ac sleep [Enables aircon sleep timer]'
                                    'ac on/off [Turn on/off aircon]'
                                    'tv on/off/mute [Turn on/off or mute TV]'
                                    'bedroom on/off [Turn on/off bedroom lights]'
                                    'bedroom on full [Turn on bedroom lights to brightest setting]'
                                    'living on/off [Turn on/off both living room lights]'
                                    'living night [Set living room lights to night-light mode]'
                                    'living blue/mix/yellow [Set colour temp of living room lights]'
                                    'open/close [Open/close curtains]'
                                    'temp [Get current room temp.]'
                                    'sched on [Activate scheduler for aircon]'
                                    'sched hour xx [Set scheduler hour to xx]'
                                    'sched minute xx [Set scheduler minute]'
                                    'graphxx [Get graph of temp. over last xx hours]'
                                    'graph=actual [Set graphing function to plot raw data]'
                                    'graph=smooth [Set graphing function to plot smoothed data]'
                                    'smoothingx [Set graph smoothing window to x]'
                                    'bus himeji [Get times for next bus to Himeji]'
                                    'bus home [Get times for next bus home]')
                    else:
                        print('Command not recognised')
            elif self.wyn_hangouts_id in hangouts_user:
                if command == 'temp':
                    info = self.send_rs232_command(PCMD.micro_commands[command])
                    response = '{0}. Quite to your liking, Sir {1}, Lord of the Itiots?'.format(info, self.wyn_name)
                elif 'bribe' in command:
                    response = 'Come meet me in person to discuss'
                elif 'fef' in command:
                    response = 'CHIP'
                else:
                    response = '{0} evil thwarted'.format(self.wyn_name)
            else:
                print('Unauthorised user rejected')
                response = 'Rejected'

            print('Response: {0} of type {1}'.format(response, type(response)))
            if response:
                msg.reply(response).send()

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
        '''Send command to microcontroller via RS232'''
        try:
            self.ser.write(command)
        except serial.SerialTimeoutException:
            #  Timeout for port exceeded (only if timeout is set).
            return -1

        time.sleep(0.2)  # Give 200ms for microcontroller to react and respond

        try:
            response = self.ser.readline()
        except serial.SerialException:
            # Attempt to read from closed port
            return -2

        while self.ser.inWaiting() > 0:
            response += self.ser.readline()
        self.command_log.info('Command sent: %s', command)
        # Convert byte array to ascii string, strip newline chars
        return str(response, 'ascii').rstrip('\r\n')

    def temp_logger(self):
        '''Get current temperature and log to file.'''
        while True:
            # print('Entered temp_logger thread')
            self.command_queue.put('temp')
            temp = self.response_queue.get()

            if not temp:
                self.command_queue.put('temp')
                temp = self.response_queue.get()

            if temp.startswith('Temp is '):
                with open(os.path.join(cwd, 'temp_log.txt'), 'a') as text_file:
                    text_file.write('{0}, {1}\n'.format(current_time(),
                                                        temp[8:].strip('\r\n')))
                sys.stdout.flush()
            else:
                self.temp_log.debug('Unable to get valid temperature. '
                                    'Value received: %s', temp)
            # Aim for 1 minute-ish intervals between temp logs
            time.sleep(60)


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
    if server.connect(('talk.google.com', 5222)):
        server.process(block=True)
        print('****************************Done******************************')
    else:
        print('Unable to connect to Hangouts.')

if __name__ == '__main__':
    main()
