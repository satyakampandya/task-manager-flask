# coding=utf-8
"""
Models
"""
import re
from datetime import datetime

from flask import Flask
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import ForeignKey
from sqlalchemy.dialects.sqlite import DATE
from sqlalchemy.orm import backref, relationship
from werkzeug.security import generate_password_hash

app = Flask(__name__)
app.config['DATABASE_FILE'] = 'xls_data_db_old.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
app.config['SECRET_KEY'] = 'Thisissupposedtobesecret!'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + app.config['DATABASE_FILE']

db = SQLAlchemy(app)
db.init_app(app)

custom_date = DATE(
    storage_format="%(day)02d-%(month)02d-%(year)04d",
    regexp=re.compile("(?P<day>\d+)-(?P<month>\d+)-(?P<year>\d+)")
)

project_developer = db.Table('project_developers',
                             db.Column('tm_project_id', db.Integer, db.ForeignKey('projects.id')),
                             db.Column('tm_developer_id', db.Integer, db.ForeignKey('users.id')),
                             db.PrimaryKeyConstraint('tm_project_id', 'tm_developer_id'))

project_qa = db.Table('project_qas',
                      db.Column('tm_project_id', db.Integer, db.ForeignKey('projects.id')),
                      db.Column('tm_quality_assurer_id', db.Integer, db.ForeignKey('qa.id')),
                      db.PrimaryKeyConstraint('tm_project_id', 'tm_quality_assurer_id'))


class Users(UserMixin, db.Model):
    """
    This class is used for User table
    """
    id = db.Column(db.Integer, primary_key=True)
    erp_user_id = db.Column(db.Integer, unique=True, nullable=False)
    erp_user_name = db.Column(db.String(50), nullable=False)

    tm_email_id = db.Column(db.String(50), unique=True, nullable=False)
    tm_password = db.Column(db.String(80), nullable=False)
    tm_user_role = db.Column(db.String(10), nullable=False, default="developer")
    tm_latest_task = db.Column(custom_date)

    def is_authenticated(self):
        """
        Returns true if user is authenticated
        :return:
        """
        return True

    def is_active(self):
        """
        Returns if a user is active or not
        :return:
        """
        return True

    def is_anonymous(self):
        """
        Returns if a user is anonymous or not
        :return:
        """
        return False

    def get_id(self):
        """
        Returns id of user
        :return:
        """
        return self.id

    # Required for administrative interface
    def __unicode__(self):
        return self.erp_user_name


class Qa(db.Model):
    """
    This class is used for QA table
    """
    id = db.Column(db.Integer, primary_key=True)
    erp_user_id = db.Column(db.Integer, unique=True, nullable=False)
    erp_user_name = db.Column(db.String(50), nullable=False)
    tm_email_id = db.Column(db.String(50), unique=True, nullable=False)

    def __unicode__(self):
        return self.erp_user_name


class Projects(db.Model):
    """
    Projects Modal
    """
    # Task Manager Fields
    id = db.Column(db.Integer, primary_key=True)
    erp_project_id = db.Column(db.Integer, unique=True)
    tm_project_name = db.Column(db.String(50), nullable=False)
    tm_project_status = db.Column(db.Boolean, default=True)

    tm_developer_id = db.relationship('Users', secondary=project_developer,
                                      backref=db.backref('developer_project', lazy='select'))
    tm_quality_assurer_id = db.relationship('Qa', secondary=project_qa,
                                            backref=db.backref('qa_project', lazy='select'))

    def __unicode__(self):
        return str(self.erp_project_id) + ': ' + self.tm_project_name


class Milestones(db.Model):
    """
    Milestones Modal
    """
    id = db.Column(db.Integer, primary_key=True)
    erp_milestone_id = db.Column(db.Integer, unique=True, nullable=False)
    tm_milestone_name = db.Column(db.String(50), nullable=False)
    tm_milestone_project_id = db.Column(db.Integer, ForeignKey("projects.id"), nullable=False)
    relative_project = db.relationship(Projects, backref=db.backref('tm_milestone_project_id'))

    def __unicode__(self):
        return str(self.tm_milestone_project_id) + ": " + self.tm_milestone_name


class Tasks(db.Model):
    """
    Table Structure of Tasks Table
    """
    id = db.Column(db.Integer, primary_key=True)
    tm_task_project_id = db.Column(db.Integer, ForeignKey("projects.id"))
    tm_task_title = db.Column(db.String(50), nullable=False)
    tm_milestone = db.Column(db.Integer, ForeignKey("milestones.id"))
    tm_start_date = db.Column(custom_date, nullable=False)
    tm_end_date = db.Column(custom_date, nullable=False)
    tm_estimated_hours = db.Column(db.String(50), nullable=False)
    tm_qa = db.Column(db.Integer, ForeignKey("qa.id"))
    tm_developer = db.Column(db.Integer, ForeignKey("users.id"))
    tm_priority = db.Column(db.String(50), nullable=False)
    tm_type = db.Column(db.String(50), nullable=False)
    tm_description = db.Column(db.String(), nullable=False)
    tm_added_on = db.Column(custom_date, default=datetime.now().date(), nullable=False)
    erp_task_status = db.Column(db.Boolean, default=False)

    relative_project = relationship(Projects, backref=backref('tm_task_project_id'))
    relative_milestone = relationship(Milestones, backref=backref('tm_milestone'))
    relative_qa = relationship(Qa, foreign_keys=[tm_qa], backref=backref("tm_qa"))
    relative_developer = relationship(Users, foreign_keys=[tm_developer], backref=backref("tm_developer", uselist=True))

    def __unicode__(self):
        return str(self.tm_task_project_id)


def build_sample_db():
    """
    Drops old db, and creates new one
    """
    db.drop_all()
    db.create_all()
    tl_user = Users(erp_user_id=101, erp_user_name="ChandPrakash Rawat",
                    tm_email_id="chandprakash@drcsystems.com",
                    tm_password=generate_password_hash("Drc@1234", method='sha256'),
                    tm_user_role="admin")
    db.session.add(tl_user)
    db.session.commit()
