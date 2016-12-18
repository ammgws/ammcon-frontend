# Python Standard Library
import datetime as dt
import logging.handlers
import os
# Third party imports
import zmq
from flask import Flask
from flask_security import Security, SQLAlchemyUserDatastore
from werkzeug.contrib.fixers import ProxyFix
# AmmCon views imports are done after app instance is created to avoid circular imports
from webapp.models import db

# Create and configure Flask app
app = Flask(__name__, template_folder='templates')
app.config.from_object('flask_config')  # load Flask config file
app.logger.info("Using config: %s" % app.config['ENVIRONMENT'])

# Get Flask secret key from config file or environment variable.
# This key is used to sign sessions (i.e. cookies), but is also needed for Flask's flashing system to work.
if os.environ.get('FLASK_SECRET_KEY') is None:
    app.secret_key = app.config['SECRET_KEY']
else:
    app.secret_key = os.environ['FLASK_SECRET_KEY']
# Get client IP (remote address) from the X-Forward set by the proxy server (AmmCon should never be run without a proxy)
app.wsgi_app = ProxyFix(app.wsgi_app)

# SQLAlchemy configuration
if os.environ.get('SQLALCHEMY_DATABASE_URL') is None:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['SQLALCHEMY_DATABASE_URL']
# Initialise SQLAlchemy databse object with our app instance
app.db = db
app.db.init_app(app)

# Initialize the SQLAlchemy data store and Flask-Security.
app.user_datastore = SQLAlchemyUserDatastore(app.db, models.User, models.Role)
app.security = Security(app, app.user_datastore)

# import views after app instance is instantiated to avoid circular reference
# noinspection PyPep8
from webapp import views

# Configure loggers
log_format = logging.Formatter(
    fmt='%(asctime)s.%(msecs).03d %(name)-12s %(levelname)-8s %(message)s (%(filename)s:%(lineno)d)',
    datefmt='%Y-%m-%d %H:%M:%S')
log_folder = app.config['LOG_FOLDER']
log_filename = '_{0}.log'.format(dt.datetime.now().strftime("%Y%m%d_%Hh%Mm%Ss"))
flask_log_handler = logging.handlers.RotatingFileHandler(os.path.join(log_folder, 'flask' + log_filename),
                                                         maxBytes=5 * 1024 * 1024,
                                                         backupCount=3)
flask_log_handler.setFormatter(log_format)
app.logger.addHandler(flask_log_handler)
app.logger.setLevel(level=app.config['LOG_LEVEL'])
app.logger.info('############### Starting Ammcon Web UI ###############')

# Connect to zeroMQ REQ socket, used to communicate with serial port
# to do: handle disconnections somehow (though if background serial worker
# fails then we're screwed anyway)
context = zmq.Context()
app.socket = context.socket(zmq.REQ)
# socket.setsockopt(zmq.RCVTIMEO, 500)  # timeout in ms
app.socket.connect('tcp://localhost:5555')
app.logger.info('############### Connected to zeroMQ server ###############')
