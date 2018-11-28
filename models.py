# coding=utf-8
"""
Models
"""
from datetime import datetime

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import ForeignKey
from sqlalchemy.orm import backref, relationship

db = SQLAlchemy()

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
    tm_latest_task = db.Column(db.Date, nullable=True)
    tm_user_status = db.Column(db.Boolean, default=True)

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
    tm_project_name = db.Column(db.String(255), nullable=False)
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
    tm_milestone_status = db.Column(db.Boolean, default=True)

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
    tm_start_date = db.Column(db.Date, nullable=False)
    tm_end_date = db.Column(db.Date, nullable=False)
    tm_estimated_hours = db.Column(db.Time, default=datetime.strptime("08:00:00", "%H:%M:%S").time(),
                                   nullable=False)
    tm_qa = db.Column(db.Integer, ForeignKey("qa.id"))
    tm_developer = db.Column(db.Integer, ForeignKey("users.id"))
    tm_priority = db.Column(db.String(50), nullable=False)
    tm_type = db.Column(db.String(50), nullable=False)
    tm_description = db.Column(db.String(), nullable=False)
    tm_added_on = db.Column(db.Date, nullable=False)
    erp_task_status = db.Column(db.Boolean, default=False)

    relative_project = relationship(Projects, backref=backref('tm_task_project_id'))
    relative_milestone = relationship(Milestones, backref=backref('tm_milestone'))
    relative_qa = relationship(Qa, foreign_keys=[tm_qa], backref=backref("tm_qa"))
    relative_developer = relationship(Users, foreign_keys=[tm_developer], backref=backref("tm_developer", uselist=True))

    def __unicode__(self):
        return str(self.tm_task_project_id)
