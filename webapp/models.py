#!/usr/bin/env python3

# Python Standard Library
import datetime as dt
from functools import wraps
# Third party imports
from flask import request
from flask_security import (RoleMixin, UserMixin, current_user)
from flask_sqlalchemy import SQLAlchemy

# SQLAlchemy configuration
db = SQLAlchemy()  # create a SQLAlchemy database connection object

# Define models
# Create intermediary/association table to support many-to-many relationship between Users and Roles
roles_users = db.Table('roles_users',
                       db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
                       db.Column('role_id', db.Integer, db.ForeignKey('role.id')))


class Role(db.Model, RoleMixin):
    """ Defines 'Role' databse model to use with SQLAlchemy.

        RoleMixin inherits default implementations from Flask-Security.
    """
    __tablename__ = 'role'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True)
    description = db.Column(db.String(255))

    # __str__ is required by Flask-Admin, so we can have human-readable values for the Role when editing a User.
    def __str__(self):
        return self.name

    # __hash__ is required to avoid the exception TypeError: unhashable type: 'Role' when saving a User
    def __hash__(self):
        return hash(self.name)


class User(db.Model, UserMixin):
    """ Defines 'User' database model to use with SQLAlchemy.

        UserMixin inherits default implementations from Flask-Security, who is subclassing from Flask-Login.
        This provides the following properties and methods:
            is_authenticated
            is_active
            is_anonymous
            get_auth_token()
            get_id()
            has_role(role)
    """
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, unique=True)
    password = db.Column(db.String(255), default='unused')
    nickname = db.Column(db.String(64), nullable=False)
    active = db.Column(db.Boolean())
    access_revoked = db.Column(db.Boolean(), default=False)

    # Flask-Security user tracking fields
    last_login_at = db.Column(db.DateTime)
    current_login_at = db.Column(db.DateTime)
    last_login_ip = db.Column(db.String(45))  # IPv6 address is max 45 chars
    current_login_ip = db.Column(db.String(45))
    login_count = db.Column(db.Integer)

    # Define relationships
    roles = db.relationship('Role', secondary=roles_users, backref=db.backref('users', lazy='dynamic'))
    logs = db.relationship('Log', back_populates='user')

    def __repr__(self):
        return '<User %r>' % self.nickname


class Log(db.Model):
    """ORM object used to log AmmCon commands"""
    __tablename__ = 'logs'

    id = db.Column(db.Integer, primary_key=True)
    command = db.Column(db.String(512))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    datetime = db.Column(db.DateTime, default=dt.datetime.utcnow)

    # Define relationships
    user = db.relationship('User', back_populates='logs')

    @classmethod
    def log_db(cls, f):
        """Decorator to log user actions"""

        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = current_user.id or None
            command_text = request.args.get('command', '', type=str)
            log = cls(
                command=command_text,
                user_id=user_id)
            db.session.add(log)
            db.session.commit()
            return f(*args, **kwargs)

        return decorated_function
