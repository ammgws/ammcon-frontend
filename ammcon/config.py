import os.path

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
CONFIG_PATH = os.path.join(os.path.expanduser("~"), '.ammcon')
LOG_PATH = os.path.join(CONFIG_PATH, 'logs')
SERIAL_PORT = '/dev/ttyUSB0'


class BaseConfig(object):
    # ***************************************************
    # *** USER OVERRIDABLE SETTINGS                   ***
    # *** (USE CONFIG FROM FLASK INSTANCE FOLDER)     ***
    # ***************************************************

    DEBUG = False
    TESTING = False

    # Flask secret key. Generate using os.urandom(24)
    SECRET_KEY = ''

    # For OAUTH
    GOOGLE_LOGIN_CLIENT_ID = ''
    GOOGLE_LOGIN_CLIENT_SECRET = ''
    OAUTH_CREDENTIALS = {'google': {'id': GOOGLE_LOGIN_CLIENT_ID,
                                    'secret': GOOGLE_LOGIN_CLIENT_SECRET}
                         }

    # List of email addresses allowed to sign in to AmmCon using OAuth
    ALLOWED_EMAILS = ['email1@gmail.com',
                      'email2@gmail.com']
    # Preconfigured admin account
    ADMIN_ACCOUNT = 'adminuseraccounte@gmail.com'

    # Logging
    # TO DO: log to syslog instead?
    LOG_LEVEL = 'INFO'
    LOG_FOLDER = '/var/log/ammcon'

    # SSL certificate filename for using SSL when running using Flask development server
    SSL_CERT = 'xxx.crt'
    SSL_KEY = 'xxx.key'

    # HTPC WoL info TODO: move to proper file
    MAC_ADDR = 'FF:FF:FF:FF:FF:FF'
    BROADCAST_ADDR = '99.99.99.255'

    # Allowed IP addresses for private API
    ALLOWED_IP_ADDR = ['192.168.0.1']

    # ***************************************************
    # *** DO NOT CHANGE THE BELOW SETTINGS            ***
    # ***************************************************

    # SQLAlchemy
    SQLALCHEMY_DATABASE_URI = 'sqlite:///db.sqlite'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_MIGRATE_REPO = os.path.join(BASE_DIR, 'db_repository')

    # Cookies
    REMEMBER_COOKIE_SECURE = True  # Restricts the “Remember Me” cookie’s scope to HTTPS
    SESSION_COOKIE_HTTPONLY = True  # Default is true but set here for peace of mind
    SESSION_COOKIE_SECURE = True  # Set secure flag to prevent HTTPS cookies from leaking over HTTP
    SESSION_PROTECTION = 'basic'  # actions requiring a fresh session will require reauthentication, otherwise OK

    # Flask-Security
    SECURITY_LOGIN_USER_TEMPLATE = 'login.html'
    SECURITY_TRACKABLE = True


class Production(BaseConfig):
    SECRET_KEY = b'\xb8UfLF\x83\x1bt\x8a\xdf;>\xf7\x1ep\x0b\xa7\xdd_\x94O\x16\x17\x88'


class Development(BaseConfig):
    from os import urandom
    SECRET_KEY = urandom(24)
    DEBUG = True
    LOG_LEVEL = 'DEBUG'

    # Derestrict HTTPS specific settings so that we can dev with HTTP
    REMEMBER_COOKIE_SECURE = False
    SESSION_COOKIE_SECURE = False


class TestingConfig(BaseConfig):
    from os import urandom
    SECRET_KEY = urandom(24)
    TESTING = True
    LOG_LEVEL = 'DEBUG'
    ALLOWED_IP_ADDR = ['127.0.0.1']
