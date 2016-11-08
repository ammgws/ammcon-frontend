# Flask secret key. Can generate using os.urandom(24)
SECRET_KEY = b''

SQLALCHEMY_TRACK_MODIFICATIONS = False

# Account used: xxx@yyy.com
GOOGLE_LOGIN_CLIENT_ID = ""
GOOGLE_LOGIN_CLIENT_SECRET = ""
OAUTH_CREDENTIALS = {'google': {'id': GOOGLE_LOGIN_CLIENT_ID,
                                'secret': GOOGLE_LOGIN_CLIENT_SECRET}
                     }

# List of email addresses allowed to sign in to AmmCon using OAuth
ALLOWED_EMAILS = ['email1@gmail.com',
                  'email2@gmail.com']

# SSL certificate filename for using SSL when running using Flask development server
SSL_CERT = 'xxx.crt'
SSL_KEY = 'xxx.key'

# Logging
LOG_LEVEL = 'DEBUG'
# full path to folder to store logs in
LOG_FOLDER = '/path/to/logs'

# Cookies
REMEMBER_COOKIE_SECURE = True  # Restricts the “Remember Me” cookie’s scope to HTTPS

# HTPC WoL info TODO: move to proper file
MAC_ADDR = 'FF:FF:FF:FF:FF:FF'
BROADCAST_ADDR = '99.99.99.255'

# Allowed IP addresses for private API
ALLOWED_IP_ADDR = ['192.168.0.1']
