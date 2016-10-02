SQLALCHEMY_TRACK_MODIFICATIONS = False

# Account used: xxx@yyy.com
GOOGLE_LOGIN_CLIENT_ID = ""
GOOGLE_LOGIN_CLIENT_SECRET = ""
OAUTH_CREDENTIALS = { 'google': {'id': GOOGLE_LOGIN_CLIENT_ID,
                                 'secret': GOOGLE_LOGIN_CLIENT_SECRET}
                    }
# List of email addresses allowed to sign in to AmmCon using OAuth
ALLOWED_EMAILS = ['email1@gmail.com',
                  'email2@gmail.com']
                  
# SSL certificate filename
SSL_CERT = 'xxx.crt'
SSL_KEY = 'xxx.key'

# Logging
LOG_LEVEL = 'DEBUG'
# full path to folder to store logs in
LOG_FOLDER = '/path/to/logs'