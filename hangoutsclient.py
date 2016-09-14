#!/usr/bin/env python3

'''Ammcon - server for Ammcon home automation system'''

# Imports from Python Standard Library
import datetime as dt
import logging
from sys import path
from urllib.parse import urlencode

# Third party imports
from configparser import ConfigParser
import requests
import ssl
from sleekxmpp import ClientXMPP
from sleekxmpp.exceptions import IqError, IqTimeout
from sleekxmpp.xmlstream import cert

# Ammcon imports
import h_bytecmds as PCMD
import helpers

# Get absolute path of the dir script is run from
cwd = path[0]  # pylint: disable=C0103


class HangoutsClient(ClientXMPP):
    '''
    Client for connecting to Hangouts
    '''

    # pylint: disable=too-many-instance-attributes
    # 11 instance variables seems OK to me in this case

    def __init__(self, config_path, command_queue, response_queue):
        # Read in Ammcon config values
        self.config = ConfigParser()
        self.config.read(config_path)
        self.config_path = config_path
        logging.debug('[Hangouts] Using config file: %s', config_path)

        # Get AmmCon user information from config file
        self.amm_hangouts_id = self.config.get('Amm', 'HangoutsID')
        self.amm_name = self.config.get('Amm', 'Name')

        # Get Hangouts OAUTH info from config file
        self.client_id = self.config.get('General', 'client_id')
        self.client_secret = self.config.get('General', 'client_secret')
        self.refresh_token = self.config.get('General', 'refresh_token')
        # Generate access token
        self.token_expiry = None
        self.access_token = None
        self.google_authenticate()

        # Get email address for Hangouts login
        ammcon_email = self.google_get_email()
        logging.debug('[Hangouts] Going to login using: %s', ammcon_email)

        # Setup new SleekXMPP client to connect to Hangouts.
        # Not passing in password arg as using OAUTH2 to login
        ClientXMPP.__init__(self,
                            jid=ammcon_email,
                            password=None,
                            sasl_mech='X-OAUTH2')
        self.auto_reconnect = True  # Restart stream in the event of an error
        #: Max time to delay between reconnection attempts (in seconds)
        self.reconnect_max_delay = 300

        # Register XMPP plugins (order does not matter.)
        # To do: remove unused plugins
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
        # Fetches a new access token and updates the class' access_token value.
        # This is a workaround for a bug I've encountered when SleekXMPP
        # attempts to reconnect, but fails due to using an old access token.
        # Access token is first set when initialising the client, however since
        # Google access tokens expire after one hour, if SleekXMPP attempts a
        # reconnect after one hour has passed, the sasl_mechanism will submit
        # the old access token and end up failing ('failed_auth') and the
        # server instance is ended.
        self.add_event_handler('connected', self.reconnect_workaround)

        # Using a Google Apps custom domain, the certificate
        # does not contain the custom domain, just the GTalk
        # server name. So we will need to process invalid
        # certifcates ourselves and check that it really
        # is from Google.
        self.add_event_handler("ssl_invalid_cert", self.invalid_cert)

        # Setup reference to the command and response queues
        self.command_queue = command_queue
        self.response_queue = response_queue

    def reconnect_workaround(self, event):  # pylint: disable=W0613
        ''' Workaround for SleekXMPP reconnect.
        If a reconnect is attempted after access token is expired,
        auth fails and the client is stopped. Get around this by updating the
        access token whenever the client establishes a connection to the XMPP
        server. Byproduct is that access token is requested twice upon startup.
        '''
        self.google_authenticate()
        self.credentials['access_token'] = self.access_token

    def invalid_cert(self, pem_cert):
        ''' Verify that certificate originates from Google. '''
        der_cert = ssl.PEM_cert_to_DER_cert(pem_cert)
        try:
            cert.verify('talk.google.com', der_cert)
            logging.debug("[Hangouts] Found Hangouts certificate")
        except cert.CertificateError as err:
            logging.error(err)
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
            logging.error('[Hangouts] There was an error getting the roster')
            logging.error(err.iq['error']['condition'])
            self.disconnect()
        except IqTimeout:
            logging.error('[Hangouts] Server is taking too long to respond')
            self.disconnect(send_close=False)

    def message(self, msg):
        '''
        Process incoming message stanzas, check user and
        send valid Ammcon commands to microcontroller.
        Note: message stanzas may include MUC messages and error messages.

        Args:
            msg -- The received message stanza. See SleekXMPP docs for
            stanza objects and the Message stanza to see how it may be used.
        Returns:
            Message to send back to Hangouts user
        '''

        # Google Hangouts seems to only use the 'chat' type for messages
        # Hangouts sends the following stanzas apart from actual messages from the user:
        # ・When user is typing: <composing xmlns="http://jabber.org/protocol/chatstates" />
        # ・Paused after typing: <paused xmlns="http://jabber.org/protocol/chatstates" />
        # ・Inactive (seems to be if user deletes message without sending): <inactive xmlns="http://jabber.org/protocol/chatstates" />
        if msg['type'] in ('chat', 'normal'):

            hangouts_user = str(msg['from'])
            command = str(msg['body']).lower()
            response = None

            if self.amm_hangouts_id in hangouts_user:
                logging.debug('[Hangouts] ammID verified (%s)', hangouts_user)
                if command in PCMD.micro_commands:
                    logging.debug('[Hangouts] Command "%s" received. '
                                  'Sending to command queue for processing...', command)
                    self.command_queue.put(PCMD.micro_commands[command])
                    response = self.response_queue.get()  # block until response is found
                    logging.debug('[Hangouts] Received reply into response queue: %s', helpers.print_bytearray(response))
                elif command == 'bus himeji':
                    response = helpers.check_bus('himeji', dt.datetime.now())
                elif command == 'bus home':
                    response = helpers.check_bus('home', dt.datetime.now())
                elif command[:5] == 'graph':
                    hours = int(float(command[5:]))
                    if helpers.is_number(hours) and 1 < hours <= 24:
                        response = helpers.graph(hours)
                elif command.startswith('interval'):
                    self.templog_interval = int(command[8:])
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
                    logging.info('[Hangouts] Command not recognised')
                # Send reply back to Hangouts (only if verified user)
                # kludge below
                if type(response == bytes):
                    msg.reply(helpers.print_bytearray(response)).send()
                else:
                    msg.reply(response).send()
            else:
                logging.info('[Hangouts] Unauthorised user rejected: %s', hangouts_user)

            logging.debug('[Hangouts] Response: %s of type %s', response, type(response))

    def google_authenticate(self):
        ''' Get access token for Hangouts login.
        Note that Google access token expires in 3600 seconds.
        '''
        # Authenticate with Google and get access token for Hangouts
        if not self.refresh_token:
            # If no refresh token is found in config file, then need to start
            # new authorization flow and get access token that way.
            # Note: Google has limit of 25 refresh tokens per user account per client.
            # When limit reached, creating a new token automatically invalidates the
            # oldest token without warning. (Limit does not apply to service accounts.)
            # https://developers.google.com/accounts/docs/OAuth2#expiration
            logging.debug('[Hangouts] No refresh token in config file (val = %s of type %s). '
                          'Need to generate new token.',
                          self.refresh_token,
                          type(self.refresh_token))
            # Get authorisation code from user
            auth_code = self.google_authorisation_request()
            # Request access token using authorisation code
            self.google_token_request(auth_code)
            # Save refresh token for next login attempt or application startup
            self.config.set('General', 'refresh_token', self.refresh_token)
            with open(self.config_path, 'w') as config_file:
                self.config.write(config_file)
        elif (self.access_token is None) or (dt.datetime.now() > self.token_expiry):
            # Use existing refresh token to get new access token.
            logging.debug('[Hangouts] Using refresh token to generate new access token.')
            # Request access token using existing refresh token
            self.google_token_request()
        else:
            # Access token is still valid, no need to generate new access token.
            logging.debug('[Hangouts] Access token is still valid - no need to regenerate.')
            return

    def google_authorisation_request(self):
        '''Start authorisation flow to get new access + refresh token.'''

        # Start by getting authorization_code for Hangouts scope.
        # Email scope is used to get email address for Hangouts login.
        oauth2_scope = ('https://www.googleapis.com/auth/googletalk '
                        'https://www.googleapis.com/auth/userinfo.email')
        oauth2_login_url = 'https://accounts.google.com/o/oauth2/v2/auth?{}'.format(
            urlencode(dict(
                client_id=self.client_id,
                scope=oauth2_scope,
                redirect_uri='urn:ietf:wg:oauth:2.0:oob',
                response_type='code',
                access_type='offline',
            ))
        )

        # Print auth URL and wait for user to grant access and
        # input authentication code into the console.
        print(oauth2_login_url)
        auth_code = input("Enter auth code from the above link: ")
        return auth_code

    def google_token_request(self, auth_code=None):
        '''Make an access token request and get new token(s).
           If auth_code is passed then both access and refresh tokens will be
           requested, otherwise the existing refresh token is used to request
           an access token.

           Update the following class variables:
            access_token
            refresh_token
            token_expiry
           '''
        # Build request parameters. Order doesn't seem to matter, hence using dict.
        token_request_data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
        }
        if auth_code is None:
            # Use existing refresh token to get new access token.
            token_request_data['refresh_token'] = self.refresh_token
            token_request_data['grant_type'] = 'refresh_token'
        else:
            # Request new access and refresh token.
            token_request_data['code'] = auth_code
            token_request_data['grant_type'] = 'authorization_code'
            # 'urn:ietf:wg:oauth:2.0:oob' signals to the Google Authorization
            # Server that the authorization code should be returned in the
            # title bar of the browser, with the page text prompting the user
            # to copy the code and paste it in the application.
            token_request_data['redirect_uri'] = 'urn:ietf:wg:oauth:2.0:oob'
            token_request_data['access_type'] = 'offline'

        # Make token request to Google.
        oauth2_token_request_url = 'https://www.googleapis.com/oauth2/v4/token'
        resp = requests.post(oauth2_token_request_url, data=token_request_data)
        # If request is successful then Google returns values as a JSON array
        values = resp.json()
        self.access_token = values['access_token']
        if auth_code:  # Need to save value of new refresh token
            self.refresh_token = values['refresh_token']
        self.token_expiry = dt.datetime.now() + dt.timedelta(seconds=int(values['expires_in']))
        logging.info('[Hangouts] Access token expires on %s', self.token_expiry.strftime("%Y/%m/%d %H:%M"))

    def google_get_email(self):
        '''Get email address for Hangouts login.'''
        authorization_header = {"Authorization": "OAuth %s" % self.access_token}
        resp = requests.get("https://www.googleapis.com/oauth2/v2/userinfo",
                            headers=authorization_header)
        # If request is successful then Google returns values as a JSON array
        values = resp.json()
        return values['email']
