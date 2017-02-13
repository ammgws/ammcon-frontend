# Third party imports
import os.path
import requests
import shutil
from flask import (Blueprint, after_this_request, current_app, flash, redirect, url_for)
from flask_security import (current_user, login_user)
# Ammcon imports
from ammcon_frontend.auth_providers import OAuthSignIn
from ammcon_frontend.models import User

blueprint = Blueprint('oauth', __name__)


@blueprint.route('/authorize/<provider>')
def oauth_authorize(provider):
    """ OAUTH authorization flow. """
    # Redirect user to main page if already logged in.
    if current_user.is_authenticated:
        current_app.logger.debug("Redirect authenticated user to main page.")
        return redirect(url_for('index'))
    else:
        # Otherwise redirect user to oauth authorisation url
        oauth = OAuthSignIn.get_provider(provider)
        return oauth.authorize()


@blueprint.route('/callback/<provider>')
def oauth_callback(provider):
    """ Sign in using OAUTH, and redirect back to main page. """
    # Redirect user to main page if already logged in.
    if current_user.is_authenticated:
        current_app.logger.debug("Redirect authenticated user to main page.")
        return redirect(url_for('index'))

    # Otherwise, attempt to sign user in using OAUTH
    oauth = OAuthSignIn.get_provider(provider)
    username, email, photo_url = oauth.callback()

    if email is None:
        # Note: Google returns email but other oauth services such as Twitter do not.
        current_app.logger.info('OAUTH login failed - null email received.')
        flash('Authentication failed.')
        return redirect(url_for('login'))
    elif not allowed_email(email):
        current_app.logger.info('Unauthorised email address attempted OAUTH login.')
        flash('You are not authorised to use AmmCon.', 'error')
        return redirect(url_for('login'))

    # Check whether the user (email address) already exists in the database.
    user = User.query.filter_by(email=email).first()
    # Create user if necessary.
    if not user:
        # Use first part of email if name is not available.
        if not username:
            username = email.split('@')[0]

        # Download profile picture from Google and save to disk (link expires after a while so need to save locally)
        filename = store_profile_picture(photo_url)

        # Create user object
        user = current_app.user_datastore.create_user(nickname=username, email=email, photo_url=filename)

        # default_role = user_datastore.find_role(name="end-user")

        # Give admin roles to preconfigured admin user if not already given
        if email == current_app.config['ADMIN_ACCOUNT']:
            current_app.user_datastore.add_role_to_user(user, 'admin')
        else:
            current_app.user_datastore.add_role_to_user(user, 'end-user')

        # Commit to database
        current_app.db.session.commit()
        current_app.logger.info('Created user for {0} with role {1}.'.format(user.email, user.roles))

    # Log in the user, and remember them for their next visit unless they log out.
    login_user(user, remember=True)

    @after_this_request
    # Need to call datastore.commit() after directly using login_user function to
    # make sure the Flask-Security trackable fields are saved to the datastore.
    # See: https://github.com/mattupstate/flask-security/pull/567
    def save_user(response):
        current_app.user_datastore.commit()
        current_app.logger.debug('Saved user {0} to database.'.format(user.email))
        return response

    return redirect(url_for('index'))


def allowed_email(email):
    """ Check if the email used to sign in is an allowed user of Ammcon. """
    if email in current_app.config['ALLOWED_EMAILS']:
        return True
    else:
        current_app.logger.info('Unauthorised user login attempt.')
    return False


def store_profile_picture(url):
    response = requests.get(url, stream=True)
    output_filename = url.replace(':', '').replace('/', '').replace('.', '') + '.jpg'

    current_app.logger.debug(os.path.join('static/', output_filename))

    with open(os.path.join('static/', output_filename), 'wb') as f:
        response.raw.decode_content = True
        shutil.copyfileobj(response.raw, f)
    return output_filename
