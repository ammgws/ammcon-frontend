from flask import (Blueprint, current_app, render_template, request)

blueprint = Blueprint('error_handlers', __name__)


@blueprint.app_errorhandler(400)
def key_error(e):
    """Handle invalid requests. Serves a generic error page."""
    # pass exception instance in exc_info argument
    current_app.logger.warning('Invalid request resulted in KeyError', exc_info=e)
    return render_template('error.html'), 400


@blueprint.app_errorhandler(403)
def unauthorized_access(error):
    """Handle 403 errors. Serves a generic error page."""
    current_app.logger.warning('Access forbidden: %s (Error message = %s)', request.path, error)
    return render_template('error.html'), 403


@blueprint.app_errorhandler(404)
def page_not_found(error):
    """Handle 404 errors. Only this error serves a non-generic page."""
    current_app.logger.warning('Page not found: %s (Error message = %s)', request.path, error)
    return render_template('page_not_found.html'), 404


@blueprint.app_errorhandler(500)
def internal_server_error(e):
    """Handle internal server errors. Serves a generic error page."""
    current_app.logger.warning('An unhandled exception is being displayed to the end user', exc_info=e)
    return render_template('error.html'), 500


@blueprint.app_errorhandler(Exception)
def unhandled_exception(e):
    """Handle all other errors that may occur. Serves a generic error page."""
    current_app.logger.error('An unhandled exception is being displayed to the end user', exc_info=e)
    return render_template('error.html'), 500
