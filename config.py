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

CELERY_BROKER_URL = 'amqp://guest:guest@localhost:5672//'
CELERY_RESULT_BACKEND='amqp://guest:guest@localhost:5672//'
