# coding=utf-8
"""
This file is used to get all configs related to App
"""
# from __future__ import unicode_literals

import os

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
target_sql_path = os.path.join(APP_ROOT, 'xls_data_db_old.db')

# db = SQLAlchemy()

from flask import Flask

app = Flask(__name__)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
app.config['SECRET_KEY'] = 'Thisissupposedtobesecret!'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + target_sql_path

db = SQLAlchemy(app)
db.init_app(app)


class User(UserMixin, db.Model):
    """
    This class is used for user table
    """
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    email = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(80))
    role = db.Column(db.String(10))
    latest_task = db.Column(db.String(10))
    # logged_in = db.Column(db.BOOLEAN, default=0)


class Details(UserMixin, db.Model):
    """
    Table Structure of Details Table
    """
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.String(200))
    task_title = db.Column(db.String(50))
    milestone = db.Column(db.String(50))
    start_date = db.Column(db.String(50))
    end_date = db.Column(db.String(50))
    estimated_hours = db.Column(db.String(50))
    qa = db.Column(db.String(200))
    developer = db.Column(db.String(50))
    priority = db.Column(db.String(50))
    type = db.Column(db.String(50))
    description = db.Column(db.String(500))
    added_on = db.Column(db.String(10))


def get_secret_key():
    """
    This is used to get secret key
    :return: returns secret key
    """
    return 'Thisissupposedtobesecret!'


def get_sql_path():
    """
    This is used to get database path
    :return: returns database path
    """
    return 'sqlite:///' + target_sql_path
