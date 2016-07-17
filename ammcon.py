#!/home/ammcon/pytalk/py3env-ammcon/bin/python3

'''Ammcon - server for Ammcon home automation system'''

__title__ = 'ammcon'
__version__ = '0.0.1'

import sys
import logging

import sleekxmpp
from sleekxmpp.xmlstream import cert
import ssl

from urllib.parse import urlparse, urlencode
import requests

from matplotlib import rcParams
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scipy.interpolate import interp1d
from scipy.interpolate import UnivariateSpline
import numpy as np

import os
import subprocess
import time
import datetime

import serial

from threading import Thread
from queue import queue

import smtplib
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart

from imgurpython import ImgurClient
import configparser

import h_bytecmds as PCMD

# Get absolute path of the dir script is run from
cwd = sys.path[0]
    
def imgur_upload(imgur_client, image_path):
    '''Upload image to Imgur and return link.'''
    result = imgur_client.upload_from_path(image_path, anon=False)
    return result
    
def imgur_readconfig():
    '''Upload image to Imgur and return link.'''
    # Get client ID and secret from auth.ini
    config = configparser.ConfigParser()
    config.read(cwd + '/imgur_config.ini')
    client_id = config.get('credentials', 'client_id')
    client_secret = config.get('credentials', 'client_secret')
    refresh_token = config.get('credentials', 'refresh_token')
    return (client_id, client_secret, refresh_token)
    
def imgur_authenticate():
    '''Authenticate with Imgur and obtain access & refresh tokens.'''
    # Get client ID and secret from auth.ini
    client_id, client_secret, refresh_token = imgur_readconfig()
    client = ImgurClient(client_id, client_secret)

    # Authorization flow, pin example (see Imgur docs for other auth types)
    authorization_url = client.get_auth_url('pin')
    print("Go to the following URL: {0}".format(authorization_url))
    
    # Read in the pin typed into the terminal
    pin = input("Enter pin code: ")
    credentials = client.authorize(pin, 'pin')
    client.set_user_auth(credentials['access_token'], credentials['refresh_token'])

    # print("Authentication successful.")
    # print("   Access token:  {0}".format(credentials['access_token']))
    # print("   Refresh token: {0}".format(credentials['refresh_token']))
    
    with open('imgur_config.ini', 'w') as file:
            file.write("[credentials]\n")
            file.write("client_id={0}\n".format(client_id))
            file.write("client_secret={0}\n".format(client_secret))
            file.write("access_token={0}\n".format(credentials['access_token']))
            file.write("refresh_token={0}\n".format(credentials['refresh_token']))
            
    return client

def imgur_login():
    '''Login to Imgur using access token / refresh token.'''
    # Get client ID, secret and refresh_token from auth.ini
    client_id, client_secret, refresh_token = imgur_readconfig()
    client = ImgurClient(client_id, client_secret)
    client.set_user_auth(access_token, refresh_token)
    return client
    
def is_holiday():
    '''Check whether today is a holiday or not, as bus timetable changes depending on this.'''
    with open(cwd + '/holidays.txt', 'r') as f:
        holidays = f.readlines()
    date_format = "%Y/%m/%d"
    holiday_datetimes = [datetime.datetime.strptime(t.strip('\r\n'), date_format) for t in holidays]
    holiday_datetimes = [t.date() for t in holiday_datetimes]
    return datetime.date.today() in holiday_datetimes

def check_bus(to, time):
    '''Check bus timetable since Google Maps doesn't support Himeji buses yet.
       
    Args:
        to -- bus heading; either 'home' or 'himeji'
        time -- time you want to ride the bus (usually the current time)
    Returns:
        Time of previous bus, next bus and next bus after that.
    '''
    
    # Provide shorthand for shimotenohigashi since easier to input 'home' when sending from phone
    if to == 'home':
        to = 'shimotenohigashi'
        
    # Determine which timetable to reference based on the current day
    if is_holiday():
        file_path = cwd + '/to_'+to+'_bustimes_sunday.txt'
    elif time.isoweekday() in range(1, 6): 
        file_path = cwd + '/to_'+to+'_bustimes_weekday.txt'
    elif time.isoweekday() == 6:
        file_path = cwd + '/to_'+to+'_bustimes_saturday.txt'
    elif time.isoweekday() == 7:
        file_path = cwd + '/to_'+to+'_bustimes_sunday.txt'
    with open(file_path, 'r') as f:    
        bus_sched = f.readlines()

    bus_noriba = [row.split(', ')[0] for row in bus_sched]
    bus_times = [row.split(', ')[1] for row in bus_sched]
    
    date_format = "%H:%M"
    busdatetimes = [datetime.datetime.strptime(t.strip('\r\n'), date_format) for t in bus_times]
    busdatetimes = [t.replace(year=time.year, month = time.month, day = time.day) for t in busdatetimes]
    
    try:
        if (busdatetimes.index(time)):
            nextBus = time
    except (ValueError, IndexError):
        nextBus = min(busdatetimes,key=lambda date : abs(time-date))
        if nextBus < time:
            try:
                nextBus = busdatetimes[busdatetimes.index(nextBus)+1]
            except (IndexError):
                nextBus = busdatetimes[0]
                nextnextBus = busdatetimes[1]  
        previousBus = busdatetimes[busdatetimes.index(nextBus)-1]
        try:
            nextnextBus = busdatetimes[busdatetimes.index(nextBus)+1]
        except (IndexError):
            nextnextBus = busdatetimes[0]
            
    results = ( '-------prev-------\n'+ '(' + bus_noriba[busdatetimes.index(previousBus)] + ') ' + previousBus.strftime(date_format) + 
            '\n-------next-------\n' + '(' + bus_noriba[busdatetimes.index(nextBus)] + ') ' + nextBus.strftime(date_format) + 
            '\n' + '(' + bus_noriba[busdatetimes.index(nextnextBus)] + ') ' + nextnextBus.strftime(date_format) )
    
    return results

def sliding_mean(data_array, window=5):
    '''This function takes an array of numbers and smoothes them out. See: http://goo.gl/6ScgxV
           
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
        graph_type -- choose whether to use smoothing function or just plot raw data
        smoothing -- window to use for smoothing function
    Returns:
        Message to send back to Hangouts user
    '''
    date_format = "%Y-%m-%d %H:%M"
    ref_time = datetime.datetime.now() - datetime.timedelta(hours=int(hours))
    
    #正常では温度は１分おきに記録しているため、ログファイルの最後の（n=hours*60）エントリーだけ見たら処理時間を最小限にできる
    tempList = subprocess.check_output(['tail', '-'+str(hours*60), cwd + '/temp_log.txt'])
    tempList = tempList.decode()
    tempList = tempList.split('\n')
    del tempList[-1] #remove last item since it will be null ('') due to the last line of the logfile ending with a newline char

    #上記抜粋したデータの記録時間を確認し該当するデータ（ref_time～現在時刻のデータ）のみ残しておく
    #ログファイルの形式: 2016-07-01 23:22, 28.00degC @53.00%RH
    #                   日付    時間,　　 温度　　 @湿度
    editTempList = []
    for line in tempList:
        try:
            if is_number(line.strip('\n').split(', ')[1][:5]) and ref_time <= datetime.datetime.strptime(line.strip('\n').split(',')[0], date_format):
                editTempList.append(line.strip())
        except (ValueError, IndexError, TypeError):
            pass
    
    if len(editTempList) <= 2:
        return "Not enough data points to create graph"
    
    temptimes = [datetime.datetime.strptime(t.split(', ')[0], date_format) for t in editTempList]    
    temptimes_float = mdates.date2num(temptimes) #convert datetime to float in order to use scipy interpolation function    
    tempvals = [float(row.split(', ')[1][:5]) for row in editTempList]      
    humidityvals = [float(row.split(', ')[1][11:16]) for row in editTempList]
    
    # Attempts at smoothing data for more aesthetic plot. 
    # Works fine sometimes, othertimes unexpectedly large values are produced - haven't yet figured out the cause
    # Probably shouldn't be using interpolation/splines here and just use a moving average
    #
    # temptimes_expanded = np.linspace(temptimes_float.min(), temptimes_float.max(), hours*60*10) #expand temptimes to hours*60*10 points in order to produce smoother plot
    # tempvals_interpolate = interp1d(temptimes_float, tempvals, kind='cubic') #cubic interpolation function
    # ax1.plot(temptimes_expanded, tempvals_interpolate(temptimes_expanded))
    # tempvals_smooth = UnivariateSpline(temptimes_float, tempvals) #smoothing function
    # ax1.plot(temptimes_expanded, tempvals_smooth(temptimes_expanded))
    
    fig = plt.figure()
    ax1 = fig.add_subplot(111)
    ax2 = ax1.twinx() # Setup second y-axis (using same x-axis)
	
    if int(hours) == 1:
        titleText = 'Temp over last '  +  str(hours) + ' hours'
    else:
        titleText = 'Temp over last '  +  str(hours) + ' hours'
    ax1.set_title(titleText)
    ax1.set_xlabel('time')
    ax1.set_ylabel('degC')
    ax2.set_ylabel('%RH')
    rcParams.update({'figure.autolayout': True})
    
    if (graph_type == 'actual'):
        # Plot raw data - mostly for debugging purposes
        ax1.plot(temptimes, tempvals)
        ax2.plot(temptimes, humidityvals, 'r')
    else: 
        smoothed_tempvals = sliding_mean(tempvals, smoothing)
        smoothed_humidityvals = sliding_mean(humidityvals, smoothing)
        ax1.plot(temptimes, smoothed_tempvals)
        ax2.plot(temptimes, smoothed_humidityvals, 'r')
    
    # Annotate the min and max temps on the graph
    tempvals_min = min(tempvals)
    tempvals_min_time = temptimes[tempvals.index(tempvals_min)]
    tempvals_max = max(tempvals)
    tempvals_max_time = temptimes[tempvals.index(tempvals_max)]
    ax1.annotate(str(tempvals_min), (mdates.date2num(tempvals_min_time), tempvals_min), xytext=(-20,20), 
                textcoords='offset points', arrowprops=dict(arrowstyle='-|>'),
                bbox=dict(boxstyle='round,pad=0.2', fc='yellow', alpha=0.3))
    ax1.annotate(str(tempvals_max), (mdates.date2num(tempvals_max_time), tempvals_max), xytext=(-20,20), 
                textcoords='offset points', arrowprops=dict(arrowstyle='-|>'),
                bbox=dict(boxstyle='round,pad=0.2', fc='yellow', alpha=0.3))

    # Setup x-axis formatting
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax1.xaxis.set_major_locator(mdates.MinuteLocator(interval=hours*5))
    plt.gcf().autofmt_xdate() #Rotate and right align x-axis date ticklabels so they don't overlap. 
    
    folder = cwd + '/graphs'
    if not os.path.exists(folder):
        os.makedirs(folder)
    filename = '/tempPlot_' + time.strftime("%Y%m%d_%H-%M-%S") + '.png'
    plt.savefig(folder+filename)
    
    try:
        imgur_client = imgur_login()
    except:
        imgur_client = imgur_authenticate()
        
    imgur_resp = imgur_upload(imgur_client, folder+filename)
    image_link = imgur_resp['link']
    
    msg = 'Graph of last ' + str(hours)
    if int(hours) == 1:
        msg = msg + ' hour uploaded: '
    else:
        msg = msg + ' hours uploaded: '
    return msg + str(image_link)
    
def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        pass
 
    # Can't remember why I had this.. possibly from when was still using Python2
    try:
        import unicodedata
        unicodedata.numeric(s)
        return True
    except (TypeError, ValueError):
        pass
 
    return False
    
def is_valid_temp(s):
# Current implementation is broken. Also need to consider the time between temp values
    '''Determine if the detected change in room temperature is within defined limit'''
    try:
        is_number(s)
        if abs(float(s) - float(prev_temp)) > MAX_TEMP_CHANGE:
            return True
    except ValueError:
        pass
        
    return False
  
def send_RS232_command(ser, command):
    '''Send command to microcontroller via RS232'''
    ser.write(command)
    time.sleep(0.2) # Give 200ms for microcontroller to react and respond
    msg = ser.readline()
    while ser.inWaiting() > 0:
            msg += ser.readline()
    command_log.info('{0},{1}\n'.format(current_time(), command))
    # Convert byte array to ascii string, strip newline chars
    return str(msg, 'ascii').rstrip('\r\n')

class temp_logger(Thread):
    '''Set up temp logger daemon thread. Need to look into using Queue'''
    def __init__(self):
        self.stopped = False
        Thread.__init__(self)

    def run(self):
        while not self.stopped:
            self.log_temp()
            # Sleep 60 seconds in order to get 1 minute intervals between temp logs
            time.sleep(60)
    
    def read_temp(self):
        '''Get temperature from microcontroller. Try one more time if valid temperature not received.'''
        temp = send_RS232_command(PCMD.micro_commands['temp'])
        #if not is_valid_temp(temp):
        if not temp:
            temp = send_RS232_command(PCMD.micro_commands['temp'])
            #if not is_valid_temp(temp):
            if not temp:
                return -1 # Flag as invalid temperature
        return temp
    
    def log_temp(self):
        '''Log temperature and current time to file. Need to look into using Queue'''
        temp = self.read_temp()
        if (temp != -1):
            with open(cwd + '/temp_log.txt', 'a') as f:
                f.write('{0}, {1}\n'.format(current_time(), str(temp).strip('\r\n')))
            sys.stdout.flush()
        else:
            temp_log.debug("Unable to get valid temperature from microcontroller. Value received: {0}".format(str(temp))) 
       
def current_time():
    '''Return datetime object of current time in the format YYYY-MM-DD HH:MM.'''
    now = datetime.datetime.now()
    return str(now.strftime("%Y-%m-%d %H:%M"))
    
def is_valid_AC_mode(s):
    '''Determine if received AC mode command is valid.'''
    if s in ['auto', 'heat', 'dry', 'cool']:
        return True
    return False

def is_valid_AC_fan(s):
    '''Determine if received AC fan speed command is valid.'''
    if s in ['auto', 'quiet', '1', '2', '3']:
        return True
    return False    

def is_valid_AC_temp(s):
    '''Determine if received AC temperature command is valid.
       Probably differs per manufacturer but will set to 17<->30 degrees.
    '''
    try:
        is_number(s)
        if 17 <= s <= 30:
            return True
    except ValueError:
        pass
    return False
    
def build_AC_command():
    '''Build up AC control command for microcontroller based on received Hangouts command.'''
    
    # !!!Need to get rid of global variables in a later edit!!! 
    # AC control needs total overhaul anyway
    global AC_TEMP
    global AC_MODE
    global AC_FAN
    global AC_SPEC
    global AC_POWER
    
    if (AC_MODE == 'auto'):
        mode = '\x00'
    elif (AC_MODE == 'cool'):
        mode = '\x01'
    elif (AC_MODE == 'dry'):
        mode = '\x02'
    elif (AC_MODE == 'heat'):
        mode = '\x03'

    if (AC_FAN == 'auto'):
        fan= '\x00'
    elif (AC_FAN == 'quiet'):
        fan = '\x02'
    elif (AC_FAN == '1'):
        fan = '\x04'
    elif (AC_FAN == '2'):
        fan = '\x08'
    elif (AC_FAN == '3'):
        fan = '\x0c'   
        
    if (AC_SPEC == 'powerful'):
        spec = '\x01'
    elif (AC_SPEC == 'sleep'):
        spec = '\x03'
    else:
        spec = '\x00'
        
    # AC command: Start byte | header | power | temp | mode | fan | spec | end byte
    cmd = '\xCE\xAC\x01' + chr(int(AC_TEMP)-17) + mode + fan + spec + '\x7F'
    return cmd

class _AmmConSever(sleekxmpp.ClientXMPP):
    '''
    Create AmmCon server to handle connection to serial port
    and Hangouts server
    '''

    def __init__(self):
        # Get absolute path of the dir script is run from
        self.cwd = sys.path[0]
        
        # Setup loggers
        self.command_log = logging.getLogger('Ammcon.CommandLog')
        self.temp_log = logging.getLogger('Ammcon.TempLog')
        # Lower log level for requests module so that OAUTH2 details etc aren't logged
        logging.getLogger('requests').setLevel(logging.WARNING)
        
        # First setup serial connection to Ammcon microcontroller.
        # When using FTDI USB adapter on Linux then '/dev/ttyUSB0'
        # otherwise '/dev/ttyAMA0' if using rPi GPIO RX/TX
        # or 'COM1' etc on Windows.
        try:
            self.ser = serial.Serial('/dev/ttyUSB0', 57600, timeout=1)
        except self.serial.SerialException:
            print('No device detected or could not connect - attempting reconnect in 10 seconds')
            time.sleep(10)
            self.ser = serial.Serial('/dev/ttyUSB0', 57600, timeout=1)

        # Read in Ammcon config values
        self.config = configparser.ConfigParser()
        self.config.read(self.cwd + '/ammcon_config.ini')
        # Get AmmCon user information
        self.amm_hangoutsID = self.config.get('Amm', 'HangoutsID')
        self.amm_name = self.config.get('Amm', 'Name')
        self.amm_email = self.config.get('Amm', 'Email')
        self.wyn_hangoutsID = self.config.get('Wyn', 'HangoutsID')
        self.wyn_name = self.config.get('Wyn', 'Name')
        self.wyn_email = self.config.get('Wyn', 'Email')
        # Get Hangouts login details
        self.refresh_token = self.config.get('General', 'RefreshToken')
        self.oauth2_client_ID = self.config.get('General', 'OAuth2_Client_ID')
        self.oauth2_client_secret = self.config.get('General', 'OAuth2_Client_Secret')
        
        # Authenticate with Google and get access token for logging into Hangouts
        if not self.refresh_token:
            self.access_token, self.refresh_token = google_authenticate(self.oauth2_client_ID, self.oauth2_client_secret)
            # Save refresh token so we don't have to go through auth process everytime we want to login
            self.config.set('General', 'RefreshToken', self.refresh_token)
            with open(cwd + '/ammcon_config.ini', 'wb') as f:
                self.config.write(f)
        else:
            self.access_token = google_refresh(self.oauth2_client_ID, self.oauth2_client_secret, self.refresh_token)
        self.ammcon_email = google_getemail(self.access_token)

        # Setup new SleekXMPP client to connect to Hangouts
        # Not using real password for password arg as using OAUTH2 to login (arbitrarily set to 'yarp'.)
        sleekxmpp.ClientXMPP.__init__(self, self.ammcon_email, 'yarp')
        self.credentials['access_token'] = self.access_token
        self.auto_reconnect = True
        # Register XMPP plugins (order in which they are registered does not matter.)
        self.register_plugin('xep_0030') # Service Discovery
        self.register_plugin('xep_0004') # Data Forms
        self.register_plugin('xep_0199') # XMPP Ping

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
        #self.max_temp_change = 2.0 # Max realistic temp change allowed in logging interval (default is 1min). (temp sensor is ±0.5degC)
        #self.prev_temp = avr_serial('templog')

        # Setup temp logger thread
        # Need to look into using Queue
        temp_logger_thread = temp_logger()
        temp_logger_thread.daemon = True
        temp_logger_thread.start()
        
    def invalid_cert(self, pem_cert):
        der_cert = ssl.PEM_cert_to_DER_cert(pem_cert)
        try:
            cert.verify('talk.google.com', der_cert)
            xmpp_log.debug("CERT: Found GTalk certificate")
        except cert.CertificateError as err:
            xmpp_log.error(err.message)
            self.disconnect(send_close=False)

    def start(self, event):
        '''
        Process the session_start event.

        Typical actions for the session_start event are
        requesting the roster and broadcasting an initial
        presence stanza.

        Args:
            event -- An empty dictionary. The session_start
                     event does not provide any additional
                     data.
        '''
        self.send_presence()
        self.get_roster()

    def message(self, msg):
        '''
        Process incoming message stanzas, check user and send valid Ammcon commands to microcontroller.
        
        Args:
            msg -- The received message stanza. See the SleekXMPP docs for stanza objects 
            and the Message stanza to see how it may be used.
        Returns:
            Message to send back to Hangouts user
        '''

        #Message stanzas may include MUC messages and error messages, hence check the message type before processing.
        if msg['type'] in ('chat', 'normal'):
            
            hangouts_user = str(msg['from'])
            command = str(msg['body'])
            print('----------------')
            print('Hangouts User ID: {0}'.format(hangouts_user))
            print('Received command: {0}'.format(command))
            print('----------------')
                        
            if self.amm_hangoutsID in hangouts_user:
                if command in PCMD.micro_commands:
                    print('Command received. Sending to microcontroller...')
                    response = send_RS232_command(ser, PCMD.micro_commands[command])
                else:
                    if command == 'bus himeji':
                        msg = check_bus('himeji', datetime.datetime.now())
                    elif command == 'bus home':
                        msg = check_bus('home', datetime.datetime.now())
                    elif command == 'graph=actual':
                        graph_type = 'actual'
                    elif command == 'graph=smooth':
                        graph_type = 'smooth'
                    elif command[:9] == 'smoothing':
                        if is_number(int(float(command[9:]))) and int(float(command[9:])) > 0 and int(float(command[9:])) < 10 :
                            smoothing = int(float(command[9:]))
                    elif command[:5] == 'graph':
                        if is_number(int(float(command[5:]))) and int(float(command[5:])) > 0 and int(float(command[5:])) < 25 :
                            msg = graph(int(float(command[5:])), graph_type, smoothing)
                        else:
                            msg = 'Incorrect usage. Accepted range: graph1 to graph24'
                    elif 'help' in command:
                        msg = ( 'AmmCon commands:\n\n acxx [Set aircon temp. to xx]\n '
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
                                                     'living blue/mix/yellow [Set colour temperature of living room lights]\n'
                                                     'open/close [Open/close curtains]\n'
                                                     'temp [Get current room temp.]\n'
                                                     'sched on [Activate scheduler for aircon]\n'
                                                     'sched hour xx [Set scheduler hour]\n'
                                                     'sched minute xx [Set scheduler minute]\n'
                                                     'graphxx [Get graph of temp. over last xx hours]'
                                                     'graph=actual [Set graphing function to plot raw data]\n'
                                                     'graph=smooth [Set graphing function to plot smoothed data]\n'
                                                     'smoothingx [Set graph smoothing window to x]\n'
                                                     'bus himeji [Get times for next bus to Himeji]\n'
                                                     'bus home [Get times for next bus home]\n' )
            elif self.wyn_hangoutsID in hangouts_user:
                    if command == 'temp':
                        info = send_RS232_command(ser, PCMD.micro_commands[command])
                        response = '{0}. Quite to your liking, Sir {1}, Lord of the Itiots?'.format(info, wyn_name)
                    elif 'bribe' in command:
                        response = 'Come meet me in person to discuss'
                    elif 'fef' in command:
                        response = 'CHIP'
                    else:
                        response = '{0} evil thwarted'.format(self.wyn_name)
            else:
                    print('Unauthorised user rejected')
                    response = 'Rejected'
            
            msg.reply(response).send()

def google_authenticate(oauth2_client_ID, oauth2_client_secret):
    # Start authorisation flow to get new access + refresh token.

    # Start by getting authorization_code for Hangouts scope. Email info scope used to get email address for login
    # OAUTH2 client ID and secret are obtained through Google Apps Developers Console for the account I use for Ammcon
    OAUTH2_SCOPE         = 'https://www.googleapis.com/auth/googletalk https://www.googleapis.com/auth/userinfo.email'
    OAUTH2_LOGIN_URL     = 'https://accounts.google.com/o/oauth2/v2/auth?{}'.format(
        urlencode(dict(
            client_id     = oauth2_client_ID,
            scope         = OAUTH2_SCOPE,
            redirect_uri  = 'urn:ietf:wg:oauth:2.0:oob',
            response_type = 'code',
            access_type   = 'offline',
        ))
    )
    
    # Print auth URL and wait for user to input authentication code
    print(OAUTH2_LOGIN_URL) 
    auth_code = input("Enter auth code from the above link: ")

    # Make an access token request using the newly acquired authorisation code
    token_request_data = {
        'client_id':     oauth2_client_ID,
        'client_secret': oauth2_client_secret,
        'code':          auth_code,
        'grant_type':    'authorization_code',
        'redirect_uri':  'urn:ietf:wg:oauth:2.0:oob',
        'access_type':   'offline',
    }
    OAUTH2_TOKEN_REQUEST_URL = 'https://www.googleapis.com/oauth2/v4/token'
    r = requests.post(OAUTH2_TOKEN_REQUEST_URL, data=token_request_data)
    res = r.json()            
    access_token = res['access_token']
    refresh_token = res['refresh_token']
    return access_token, refresh_token
    
def google_refresh(oauth2_client_ID, oauth2_client_secret, refresh_token):
    # Make an access token request using existing refresh token
    token_request_data = {
        'client_id':     oauth2_client_ID,
        'client_secret': oauth2_client_secret,
        'refresh_token': refresh_token,
        'grant_type':    'refresh_token',
    }
    OAUTH2_TOKEN_REQUEST_URL = 'https://www.googleapis.com/oauth2/v4/token'
    r = requests.post(OAUTH2_TOKEN_REQUEST_URL, data=token_request_data)
    res = r.json()
    access_token = res['access_token']
    return access_token

def google_getemail(access_token):
    # Get email address for Hangouts login
    authorization_header = {"Authorization": "OAuth %s" % access_token}
    usr_req = requests.get("https://www.googleapis.com/oauth2/v2/userinfo", headers=authorization_header)
    usr_req_res = usr_req.json()
    email = usr_req_res['email']
    return email
    
def main():
    # Get absolute path of the dir script is run from
    cwd = sys.path[0]
    # Set up logging to file. Level 5 = verbose to catch everything. Set level to logging.DEBUG for debug, logging.ERROR for errors only.
    logging.basicConfig(level=5,
                        format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                        datefmt='%Y-%m-%d %H:%M"',
                        filename=cwd + '/ammcon.log',
                        filemode='a')

    # Setup AmmCon server instance
    server = _AmmConSever()
    # Connect to Hangouts and start processing XMPP stanzas.
    if server.connect(('talk.google.com', 5222)):
        server.process(block=True)
        print('*****************************Done*******************************')
    else:
        print('Unable to connect to Hangouts.')

if __name__ == '__main__':
    main()