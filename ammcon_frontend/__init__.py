# Python Standard Library
import datetime as dt
import logging.handlers
import os
# Third party imports
import zmq
from flask import Flask
from flask_security import Security, SQLAlchemyUserDatastore
from werkzeug.contrib.fixers import ProxyFix
# Ammcon imports (note views are imported below after app instance is created)
from ammcon_frontend.config import LOCAL_PATH, LOG_PATH
from ammcon_frontend.models import db, User, Role

# Create and configure Flask app
app = Flask(__name__, instance_path=LOCAL_PATH, instance_relative_config=True)

if os.environ.get('AMMCON_MODE') not in ['config.Production', 'config.Development', 'config.Testing']:
    # Load production config by default
    config_name = 'config.Production'
else:
    config_name = os.environ['AMMCON_MODE']
print("Loading config: {}".format(config_name))
app.config.from_object(config_name)
# Override config with user-edited config from Flask instance folder
app.config.from_pyfile('config.py', silent=False)

# Get Flask secret key from config file or environment variable.
# This key is used to sign sessions (i.e. cookies), but is also needed for Flask's flashing system to work.
if os.environ.get('FLASK_SECRET_KEY') is None:
    app.secret_key = app.config['SECRET_KEY']
else:
    app.secret_key = os.environ['FLASK_SECRET_KEY']

# Get client IP (remote address) from the X-Forward set by the proxy server (AmmCon should never be run without a proxy)
app.wsgi_app = ProxyFix(app.wsgi_app)

# Initialise SQLAlchemy databse object with our app instance
app.db = db
app.db.init_app(app)

# Initialize the SQLAlchemy data store and Flask-Security.
app.user_datastore = SQLAlchemyUserDatastore(app.db, User, Role)
app.security = Security(app, app.user_datastore)

# import views after app instance is instantiated to avoid circular reference
# noinspection PyPep8
from ammcon_frontend import admin, views

# Configure loggers
if not os.path.exists(LOG_PATH):
    os.makedirs(LOG_PATH, exist_ok=True)
log_format = logging.Formatter(
    fmt='%(asctime)s.%(msecs).03d %(name)-12s %(levelname)-8s %(message)s (%(filename)s:%(lineno)d)',
    datefmt='%Y-%m-%d %H:%M:%S')
log_filename = 'ammcon_flask_{0}.log'.format(dt.datetime.now().strftime("%Y%m%d_%Hh%Mm%Ss"))
flask_log_handler = logging.handlers.RotatingFileHandler(
    os.path.join(LOG_PATH, log_filename),
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
