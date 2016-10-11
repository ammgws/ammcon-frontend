#!/usr/bin/env python3

"""Helper functions used in Ammcon"""

# Imports from Python Standard Library
import datetime as dt
import logging
import os.path
from socket import socket, AF_INET, SOCK_DGRAM, SOL_SOCKET, SO_BROADCAST
from subprocess import check_output
from sys import path
# Third party imports
from configparser import ConfigParser
from matplotlib import rcParams
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from imgurpython import ImgurClient
from imgurpython.helpers.error import ImgurClientError

# Get absolute path of the dir script is run from
cwd = path[0]  # pylint: disable=C0103


def temp_str(response):
    temp = '{0}.{1}degC @{2}.{3}%RH'.format(int(response[0]),
                                            int(response[1]),
                                            int(response[2]),
                                            int(response[3]))
    return temp


def temp_val(response):
    payload = response[4:-2]
    temp = int(payload[0]) + 0.01 * int(payload[1])
    humidity = int(payload[2]) + 0.01 * int(payload[3])
    return temp, humidity


def print_bytearray(input_array):
    if input_array:
        return [hex(n) for n in input_array]
    return b''


def send_magic_packet(mac_address, broadcast_address, port=9):
    # Create an IPv4, UDP socket
    sock = socket(family=AF_INET, type=SOCK_DGRAM)
    # Enable sending datagrams to broadcast addresses
    sock.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)
    # Build magic packet
    mac_address = bytes.fromhex(mac_address.replace(':', ''))
    magic_packet = b'\xFF' * 6 + mac_address * 16
    # Send magic packet
    result = sock.sendto(magic_packet, (broadcast_address, port))
    # Success: sent all 102 bytes of the magic packet
    if result == len(magic_packet):
        ack = 'ACK'
    # Fail: not all bytes were sent
    else:
        ack = 'NAK'
    return ack


class _ImgurClient():
    """ Handle authentication and image uploading to Imgur. """

    def __init__(self):
        self.config_values = ConfigParser()
        self.config_values.read(os.path.join(cwd, 'ammcon_config.ini'))
        self.client_id = self.config_values.get('Imgur', 'client_id')
        self.client_secret = self.config_values.get('Imgur', 'client_secret')
        self.access_token = self.config_values.get('Imgur', 'access_token')
        self.refresh_token = self.config_values.get('Imgur', 'refresh_token')
        self.client = ImgurClient(self.client_id, self.client_secret)

    def save_config(self):
        """ Save tokens to config file."""
        self.config_values['Imgur']['access_token'] = self.access_token
        self.config_values['Imgur']['refresh_token'] = self.refresh_token
        with open(os.path.join(cwd, 'ammcon_config.ini'), 'w') as config_file:
            self.config_values.write(config_file)

    def authenticate(self):
        """Authenticate with Imgur and obtain access & refresh tokens."""
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
        """Login to Imgur using refresh token."""
        # Get client ID, secret and refresh_token from auth.ini
        self.client.set_user_auth(self.access_token, self.refresh_token)

    def upload(self, image_path):
        """Upload image to Imgur and return link."""
        return self.client.upload_from_path(image_path, anon=False)


def is_holiday():
    """Check whether today is a holiday, as bus timetable will be different"""
    with open(os.path.join(cwd, 'bus', 'holidays.txt'), 'r') as text_file:
        holidays = text_file.readlines()
    date_format = "%Y/%m/%d"
    holiday_datetimes = [dt.datetime.strptime(t.strip('\r\n'), date_format)
                         for t in holidays]
    holiday_datetimes = [t.date() for t in holiday_datetimes]
    return dt.date.today() in holiday_datetimes


def check_bus(direction, _time):
    """Check bus timetable since Google Maps doesn't support Himeji buses yet.

    Args:
        direction -- bus heading; either 'home' or 'himeji'
        _time -- time you want to ride the bus (usually the current time)
    Returns:
        Time of previous bus, next bus and next bus after that.
    """

    # Provide shorthand since easier to input 'home' when sending from phone
    if direction == 'home':
        direction = 'shimotenohigashi'

    # Determine which timetable to reference based on the current day
    if is_holiday():
        filename = 'to_{0}_bustimes_sunday.txt'.format(direction)
    elif _time.isoweekday() in range(1, 6):
        filename = 'to_{0}_bustimes_weekday.txt'.format(direction)
    elif _time.isoweekday() == 6:
        filename = 'to_{0}_bustimes_saturday.txt'.format(direction)
    elif _time.isoweekday() == 7:
        filename = 'to_{0}_bustimes_sunday.txt'.format(direction)
    with open(os.path.join(cwd, 'bus', filename), 'r') as text_file:
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
        next_bus = min(bus_datetimes, key=lambda date: abs(_time - date))
        if next_bus < _time:
            try:
                next_bus = bus_datetimes[bus_datetimes.index(next_bus) + 1]
            except IndexError:
                next_bus = bus_datetimes[0]
                nextnext_bus = bus_datetimes[1]
        previous_bus = bus_datetimes[bus_datetimes.index(next_bus) - 1]
        try:
            nextnext_bus = bus_datetimes[bus_datetimes.index(next_bus) + 1]
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
    """Take an array of numbers and smooth them out. See: http://goo.gl/6ScgxV

    Args:
        data -- list of data to be smoothed
        window -- window to use for sliding mean
    Returns:
        List of smoothed data
    """
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
    """ Parse temp log file and get data for graphing

    Args:
        hours -- how many hours back to go
    Returns:
        Tuple of lists
    """
    # 正常では温度は１分おきに記録しているため、ログファイルの最後の（n=hours*60）エントリー
    # のみ見たら処理時間を最小限にできる.
    # Need to make this Windows friendly.. alternative to tail??
    temp_log = check_output(['tail',
                             '-' + str(num_hours * 60),
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
    """Generate graph of past n hours of room temperature

    Args:
        hours -- how many hours back to graph
    Returns:
        Message to send back to Hangouts user
    """

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
    ax1.xaxis.set_major_locator(mdates.MinuteLocator(interval=num_hours * 5))
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
        logging.info('%s; %s', err.error_message, err.status_code)
        imgur_client.authenticate()
    imgur_resp = imgur_client.upload(os.path.join(folder, filename))

    # Prepare message to send back to Hangouts user
    return 'Graph of last {0} hour(s): {1}'.format(num_hours, imgur_resp['link'])


def is_number(num):
    """ Placeholder docstring - update later """
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
    """Return datetime object of current time in format YYYY-MM-DD HH:MM."""
    now = dt.datetime.now()
    return str(now.strftime("%Y-%m-%d %H:%M"))


def is_valid_ac_mode(mode):
    """Determine if received AC mode command is valid."""
    if mode in ['auto', 'heat', 'dry', 'cool']:
        return True
    return False


def is_valid_ac_fan(fan_speed):
    """Determine if received AC fan speed command is valid."""
    if fan_speed in ['auto', 'quiet', '1', '2', '3']:
        return True
    return False


def is_valid_ac_temp(temp):
    """Determine if received AC temperature command is valid.
       Probably differs per manufacturer but will set to 17<->30 degrees.
    """
    try:
        if 17 <= temp <= 30:
            return True
    except ValueError:
        pass
    return False


def build_ac_command(ac_temp, ac_mode, ac_fan, ac_spec, ac_power):
    """Build up AC control command for microcontroller based on
    received Hangouts command.
    """
    temp = chr(int(ac_temp) - 17)

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
