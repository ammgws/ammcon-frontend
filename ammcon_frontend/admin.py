# Third party imports
from flask_admin import Admin
from flask_admin.contrib import sqla
from flask_security import current_user
# Ammcon imports
from ammcon import Session
from ammcon.models import Device, Temperature
from ammcon_frontend import app, db
from ammcon_frontend.models import Log, Role, User


# Customized User model for Flask-Admin
class UserAdmin(sqla.ModelView):
    # Don't display the password on the list of Users
    column_exclude_list = ('password',)

    # Don't include the standard password field when creating or editing a User
    form_excluded_columns = ('password',)

    # Automatically display human-readable names for the current and available Roles when creating or editing a User
    column_auto_select_related = True

    # Prevent administration of Users unless the currently logged-in user has the "admin" role
    def is_accessible(self):
        return current_user.has_role('admin')


# Customized Role model for SQL-Admin
class RoleAdmin(sqla.ModelView):
    # Prevent administration of Roles unless the currently logged-in user has the "admin" role
    def is_accessible(self):
        return current_user.has_role('admin')


# Log model for SQL-Admin
class LogAdmin(sqla.ModelView):
    # Prevent administration of Logs unless the currently logged-in user has the "admin" role
    def is_accessible(self):
        return current_user.has_role('admin')


# Device model for SQL-Admin
class DeviceAdmin(sqla.ModelView):
    # Prevent administration of Devices unless the currently logged-in user has the "admin" role
    def is_accessible(self):
        return current_user.has_role('admin')


# Device model for SQL-Admin
class DeviceDataAdmin(sqla.ModelView):

    # sort by datetime in descending order (newest first)
    column_default_sort = ('datetime', True)

    # Prevent administration of Devices unless the currently logged-in user has the "admin" role
    def is_accessible(self):
        return current_user.has_role('admin')


# Initialize Flask-Admin
admin = Admin(app, url='/admin/', template_mode='bootstrap3')

# Add Flask-Admin views for Users and Roles databases
admin.add_view(UserAdmin(User, db.session))
admin.add_view(RoleAdmin(Role, db.session))
admin.add_view(LogAdmin(Log, db.session))
admin.add_view(DeviceAdmin(Device, Session()))
admin.add_view(DeviceDataAdmin(Temperature, Session()))
