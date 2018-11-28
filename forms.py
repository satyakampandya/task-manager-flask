# coding=utf-8
"""
Forms
"""
from werkzeug.security import check_password_hash
from wtforms import fields, form, validators

from models import db, Users


class LoginForm(form.Form):
    """
    Login form
    """
    login = fields.StringField(validators=[validators.required()], label="Username")
    password = fields.PasswordField(validators=[validators.required()], label="Password")

    def validate_login(self, field):
        """
        Validates login process
        :param field:
        """
        user = self.get_user()

        if user is None:
            raise validators.ValidationError('Invalid user')

        if not check_password_hash(user.tm_password, self.password.data):
            raise validators.ValidationError('Invalid password')

    def get_user(self):
        """
        returns user
        :return:
        """
        return db.session.query(Users).filter_by(tm_email_id=self.login.data).first()