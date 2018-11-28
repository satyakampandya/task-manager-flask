# coding=utf-8
"""
Task Manager implemented using flask admin
"""
import cookielib
import glob
import os
import urllib
import urllib2
from datetime import datetime

import flask_admin as admin
from flask import Flask, after_this_request, flash, json, jsonify, redirect, render_template, request, send_file, \
    url_for
from flask_admin import expose, helpers
from flask_admin.actions import action
from flask_admin.contrib import sqla
from flask_admin.contrib.sqla import validators
from flask_admin.form import TimeField, rules
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from markupsafe import Markup
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash
from wtforms import PasswordField, TextAreaField, validators as wtf_validator
from wtforms.validators import DataRequired

from extras import generate_dp, generate_xls, generate_zip
from forms import LoginForm
from models import Milestones, Projects, Qa, Tasks, Users, db

# Create Flask application
app = Flask(__name__)
app.config.from_pyfile('app.cfg')

db.init_app(app)

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
target_save_path_xls = os.path.join(APP_ROOT, 'xls_data/')
target_save_path_zip = os.path.join(APP_ROOT, 'zip_data/')

ADMIN = 'admin'
DEVELOPER = 'developer'

URL_ERP_LOGIN = app.config['URL_ERP_LOGIN']
URL_VIEW_PROFILE = app.config['URL_VIEW_PROFILE']
URL_ADD_TASK = app.config['URL_ADD_TASK']
URL_ERP_LOGOUT = app.config['URL_ERP_LOGOUT']

LOGIN_INFO = {
    'LoginForm[username]': app.config['USERNAME'],
    'LoginForm[password]': app.config['PASSWORD']
}


def init_login():
    """
    Initializes flask-login
    :return:
    """
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'

    @login_manager.user_loader
    def load_user(user_id):
        """
        User loader function
        :param user_id:
        :return:
        """
        return db.session.query(Users).get(user_id)


@app.route('/', methods=['GET', 'POST'])
def index():
    """
    Index page of Task Manager
    :return:
    """
    if current_user.is_authenticated:
        return redirect(url_for('admin.index'))
    else:
        return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Login view
    :return:
    """
    if current_user.is_authenticated:
        return redirect(url_for('admin.index'))

    form = LoginForm()
    if request.method == 'POST':
        login_form = LoginForm(request.form)
        if helpers.validate_form_on_submit(login_form):
            user = login_form.get_user()
            if user.tm_user_status:
                login_user(user)
                return redirect(url_for('admin.index'))
            else:
                flash('account_deactivated')
        return render_template('login.html', form=login_form)
    return render_template('login.html', form=form)


@app.route('/logout')
@login_required
def logout():
    """
    It logs out current user and redirects user to login page
    """
    logout_user()
    return redirect(url_for('login'))


def add_modify_project_api(project_obj, developers, qas):
    """
    Updates project with given developers and qas
    :param project_obj:
    :param developers:
    :param qas:
    """
    project_obj.tm_developer_id[:] = []
    project_obj.tm_quality_assurer_id[:] = []

    for dev_id in developers:
        developer_obj = Users.query.filter_by(erp_user_id=dev_id).first()
        project_obj.tm_developer_id.append(developer_obj)
    for qa_id in qas:
        qa_obj = Users.query.filter_by(erp_user_id=qa_id).first()
        project_obj.tm_quality_assurer_id.append(qa_obj)

    db.session.commit()


@app.route('/login_api', methods=['GET', 'POST'])
def login_api():
    """
    Login api used by TL to login from ERP
    """
    if current_user.get_id():
        user = Users.query.filter_by(id=current_user.get_id()).first()
        if user:
            if not user.tm_user_role == ADMIN:
                return jsonify(success=False, message="Admin Login Required")
            else:
                return jsonify(success=True, message="Already Logged In")
        return jsonify(success=False, message="Something went wrong")

    username = request.args.get('username', default=False)
    password = request.args.get('password', default=False)
    if username and password:
        user = Users.query.filter_by(tm_email_id=username).first()
        if user:
            if user.tm_user_role == ADMIN:
                if check_password_hash(user.tm_password, password):
                    login_user(user, remember=False)
                    return jsonify(success=True, message="Admin Logged in")
                else:
                    return jsonify(success=False, message="Wrong Password")
            return jsonify(success=False,
                           message="Developer trying to call login api")
        return jsonify(success=False, message="Invalid Username")
    return jsonify(success=False, message="Parameters Missing")


@app.route('/update_project_api', methods=['GET', 'POST'])
def update_project_api():
    """
    It will update projects when API is called from ERP
    :return:
    """
    if not current_user.is_authenticated:
        return jsonify(success=False, message="Login Required")
    else:
        user = Users.query.filter_by(id=current_user.get_id()).first()
        if user:
            if user.tm_user_role == ADMIN:
                json_data = request.args.get('json_data', default=False)
                if json_data:
                    project_data = json.loads(json_data)
                    project_id = project_data['id']
                    project_name = project_data['name']
                    project_milestones = project_data['milestones']
                    project_developers = project_data['developers']
                    project_qas = project_data['qas']

                    if project_id and project_name and project_milestones and project_developers:

                        all_milestone = [milestone.erp_milestone_id for milestone in Milestones.query.all()]
                        all_developer = [dev.erp_user_id for dev in Users.query.filter_by(tm_user_role=DEVELOPER).all()]
                        all_qa = [qa.erp_user_id for qa in Qa.query.all()]

                        for dev in project_developers:
                            if dev not in all_developer:
                                return jsonify(success=False, message="Invalid developer id")

                        for qa in project_qas:
                            if qa not in all_qa:
                                return jsonify(success=False, message="Invalid qa id")

                        db.session.commit()
                        erp_milestones = [milestone['id'] for milestone in project_milestones]

                        project_obj = Projects.query.filter_by(erp_project_id=project_id).first()
                        if project_obj:
                            try:
                                project_obj.tm_project_name = project_name
                                add_modify_project_api(project_obj, developers=project_developers, qas=project_qas)
                                db.session.commit()

                                for milestone in project_milestones:
                                    if milestone['id'] not in all_milestone:
                                        try:
                                            m_obj = Milestones(erp_milestone_id=milestone['id'],
                                                               tm_milestone_name=milestone['name'],
                                                               tm_milestone_project_id=project_obj.erp_project_id)
                                            db.session.add(m_obj)
                                            db.session.commit()
                                        except Exception as e:
                                            db.session.rollback()
                                            return jsonify(success=False, message=str(e))
                                    else:
                                        try:
                                            m_obj = Milestones.query.filter_by(erp_milestone_id=milestone['id']).first()
                                            m_obj.tm_milestone_name = milestone['name']
                                            db.session.commit()
                                        except Exception as e:
                                            db.session.rollback()
                                            return jsonify(success=False, message=str(e))

                                return jsonify(success=True, message="Project Updated")
                            except Exception as e:
                                db.session.rollback()
                                return jsonify(success=False, message=str(e))
                        else:

                            try:
                                project_obj = Projects(tm_project_name=project_name, erp_project_id=project_id,
                                                       tm_project_status=False)
                                db.session.add(project_obj)
                                db.session.commit()
                                add_modify_project_api(project_obj, milestones=erp_milestones,
                                                       developers=project_developers, qas=project_qas)
                                return jsonify(success=True, message="Project Added")
                            except Exception as e:
                                db.session.rollback()
                                return jsonify(success=False, message=str(e))
                else:
                    return jsonify(success=False, message="JSON data missing")
            else:
                return jsonify(success=False, message="Admin Login Required")

    return jsonify(success=False, message="Login Required")


class MainView(admin.AdminIndexView):
    """
    Team Leader View
    """

    def __init__(self):
        super(MainView, self).__init__()
        pass

    @expose('/', methods=['GET', 'POST'])
    def index(self):
        """
        :return:
        """
        user = Users.query.filter_by(id=current_user.get_id()).first()
        if user.tm_user_role == ADMIN:
            if request.method == "GET":
                date = '{0.day:02d}-{0.month:02d}-{0.year:4d}'.format(datetime.now().date())
            else:
                date = request.form['quick_date']
            all_tasks = Users.query.filter_by(tm_user_role=DEVELOPER, tm_user_status=True).order_by(
                Users.erp_user_name.asc()).all()
            present = []
            absent = []
            for task in all_tasks:
                last_id = Tasks.query.filter_by(tm_developer=task.id,
                                                tm_added_on=datetime.strptime(date, "%d-%m-%Y").date()).first()
                if last_id:
                    present.append(last_id)
                else:
                    absent.append(task)
            self._template_args['user'] = user
            self._template_args['all_users'] = all_tasks
            self._template_args['date'] = date
            self._template_args['present'] = present
            self._template_args['absent'] = absent
        else:
            if request.method == "GET":
                date = '{0.day:02d}-{0.month:02d}-{0.year:4d}'.format(datetime.now().date())
            else:
                date = request.form['quick_date']
            all_tasks = Tasks.query.filter_by(tm_developer=current_user.id,
                                              tm_added_on=datetime.strptime(date, "%d-%m-%Y").date())
            present = []
            absent = []
            for task in all_tasks.all():
                if task.erp_task_status:
                    present.append(task)
                else:
                    absent.append(task)
            self._template_args['user'] = user
            self._template_args['date'] = date
            self._template_args['present'] = present
            self._template_args['absent'] = absent
            self._template_args['is_there_tasks'] = bool(all_tasks.first())
        return super(MainView, self).index()

    @expose('/action/all', methods=['GET', 'POST'])
    def action_all(self):
        """
        For admin dashboard/developer dashboard, download all tasks per date functionality
        :return:
        """

        @after_this_request
        def delete(response):
            """
            Removes xls and zip file after download
            """
            try:
                os.chdir(xls_save_path)
                xls_files = glob.glob('*.xls')
                for xls in xls_files:
                    os.unlink(xls)
                os.chdir(zip_save_path)
                zip_files = glob.glob('*.zip')
                for _zip in zip_files:
                    os.unlink(_zip)
                os.chdir(APP_ROOT)
            except Exception as exception:
                os.chdir(APP_ROOT)
                flash('Failed to delete XLS/ZIP. ' + str(exception))
            return response

        if current_user.is_authenticated:
            date = datetime.strptime(request.args.get('date'), '%d-%m-%Y')
            if date:
                os.chdir(APP_ROOT)
                user_folder = str(current_user.id) + '_' + current_user.erp_user_name
                xls_save_path = target_save_path_xls + user_folder
                zip_save_path = target_save_path_zip + user_folder
                try:
                    if not os.path.exists(xls_save_path):
                        os.makedirs(xls_save_path)
                    if not os.path.exists(zip_save_path):
                        os.makedirs(zip_save_path)
                except Exception as e:
                    flash('Failed to create/locate XLS/ZIP saving path. ' + str(e))

                try:
                    if current_user.tm_user_role == ADMIN:
                        all_tasks = Tasks.query.filter_by(tm_added_on=date.date())
                        tasks_by_dev = sorted(set(
                            [task.tm_developer for task in all_tasks.all() if task.relative_developer.tm_user_status]))
                        for dev in tasks_by_dev:
                            project_of_dev = sorted(
                                set([task.tm_task_project_id for task in all_tasks.filter_by(tm_developer=dev).all()]))
                            for project in project_of_dev:
                                project_id = Projects.query.get(project)
                                tasks_of_dev = all_tasks.filter_by(tm_developer=dev, tm_task_project_id=project).all()
                                filename = generate_xls(tasks=tasks_of_dev, action=1, folder=user_folder,
                                                        project=project_id.erp_project_id)
                        z_name = "/Tasks_dev_wise_of_" + str(
                            '{0.day:02d}_{0.month:02d}_{0.year:4d}'.format(date.date()))
                        download_file = generate_zip(zip_name=z_name, user_folder=user_folder)
                        filename = APP_ROOT + "/" + download_file
                    else:
                        all_tasks = Tasks.query.filter_by(tm_added_on=date.date(), tm_developer=current_user.id)
                        project_of_dev = sorted(set([task.tm_task_project_id for task in all_tasks.all()]))
                        for project in project_of_dev:
                            project_id = Projects.query.get(project)
                            tasks_of_dev = all_tasks.filter_by(tm_task_project_id=project).all()
                            filename = generate_xls(tasks=tasks_of_dev, action=1, folder=user_folder,
                                                    project=project_id.erp_project_id)
                        if len(project_of_dev) > 1:
                            z_name = "/" + all_tasks.first().relative_developer.erp_user_name + '_' + str(date.date())
                            download_file = generate_zip(zip_name=z_name, user_folder=user_folder)
                            filename = APP_ROOT + "/" + download_file

                    return send_file(filename_or_fp=filename, as_attachment=True,
                                     attachment_filename=filename.split("/")[-1])

                except Exception as ex:
                    if current_user.tm_user_role == ADMIN:
                        flash('Failed to add tasks to XLS. ' + str(ex))
                    else:
                        flash('Failed to add tasks to XLS.')

        return redirect(url_for('admin.index'))

    @expose('/action/project', methods=['GET', 'POST'])
    def action_project_wise(self):
        """
        For admin dashboard, download all tasks per date project-wise functionality
        :return:
        """

        @after_this_request
        def delete(response):
            """
            Removes xls and zip file after download
            """
            try:
                os.chdir(xls_save_path)
                xls_files = glob.glob('*.xls')
                for xls in xls_files:
                    os.unlink(xls)
                os.chdir(zip_save_path)
                zip_files = glob.glob('*.zip')
                for _zip in zip_files:
                    os.unlink(_zip)
                os.chdir(APP_ROOT)
            except Exception as exception:
                os.chdir(APP_ROOT)
                flash('Failed to delete XLS/ZIP. ' + str(exception))
            return response

        if current_user.is_authenticated:
            if current_user.tm_user_role == ADMIN:
                date = datetime.strptime(request.args.get('date'), '%d-%m-%Y')
                if date:
                    user_folder = str(current_user.id) + '_' + current_user.erp_user_name
                    xls_save_path = target_save_path_xls + user_folder
                    zip_save_path = target_save_path_zip + user_folder

                    try:
                        if not os.path.exists(xls_save_path):
                            os.makedirs(xls_save_path)
                        if not os.path.exists(zip_save_path):
                            os.makedirs(zip_save_path)
                    except Exception as e:
                        flash('Failed to create/locate XLS/ZIP saving path. ' + str(e))

                    try:
                        all_tasks = Tasks.query.filter_by(tm_added_on=date.date())
                        tasks_by_project = sorted(set([task.tm_task_project_id for task in all_tasks.all()]))
                        for project in tasks_by_project:
                            tasks_of_project = [task for task in all_tasks.filter_by(tm_task_project_id=project).all()
                                                if task.relative_developer.tm_user_status]
                            filename = generate_xls(tasks_of_project, action=2, folder=user_folder)

                        if len(tasks_by_project) > 1:
                            z_name = "/Tasks_project_wise_of_" + str(
                                '{0.day:02d}_{0.month:02d}_{0.year:4d}'.format(date.date()))
                            download_file = generate_zip(zip_name=z_name, user_folder=user_folder)
                            filename = APP_ROOT + "/" + download_file

                        return send_file(filename_or_fp=filename, as_attachment=True,
                                         attachment_filename=filename.split("/")[-1])

                    except Exception as ex:
                        flash('Failed to add tasks to XLS. ' + str(ex))
        return redirect(url_for('admin.index'))

    @expose('/action/developer', methods=['GET', 'POST'])
    def action_developer(self):
        """
        :return:
        """

        @after_this_request
        def delete(response):
            """
            Removes xls and zip file after download
            """
            try:
                os.chdir(xls_save_path)
                xls_files = glob.glob('*.xls')
                for xls in xls_files:
                    os.unlink(xls)
                os.chdir(zip_save_path)
                zip_files = glob.glob('*.zip')
                for _zip in zip_files:
                    os.unlink(_zip)
                os.chdir(APP_ROOT)
            except Exception as exception:
                os.chdir(APP_ROOT)
                flash('Failed to delete XLS/ZIP. ' + str(exception))
            return response

        if current_user.is_authenticated:
            if current_user.tm_user_role == ADMIN:
                date = datetime.strptime(request.args.get('date'), '%d-%m-%Y')
                developer = request.args.get('developer')
                if date:
                    user_folder = str(current_user.id) + '_' + current_user.erp_user_name
                    xls_save_path = target_save_path_xls + user_folder
                    zip_save_path = target_save_path_zip + user_folder
                    try:
                        if not os.path.exists(xls_save_path):
                            os.makedirs(xls_save_path)
                        if not os.path.exists(zip_save_path):
                            os.makedirs(zip_save_path)
                    except Exception as e:
                        flash('Failed to create/locate XLS/ZIP saving path. ' + str(e))

                    try:
                        all_tasks = Tasks.query.filter_by(tm_added_on=date.date(), tm_developer=developer)
                        project_of_dev = sorted(
                            set([task.tm_task_project_id for task in
                                 all_tasks.filter_by(tm_developer=developer).all()]))
                        for project in project_of_dev:
                            project_id = Projects.query.get(project)
                            tasks_of_dev = all_tasks.filter_by(tm_developer=developer, tm_task_project_id=project).all()
                            filename = generate_xls(tasks=tasks_of_dev, action=1, folder=user_folder,
                                                    project=project_id.erp_project_id)

                        if len(project_of_dev) > 1:
                            z_name = "/" + all_tasks.first().relative_developer.erp_user_name + '_' + str(date.date())
                            download_file = generate_zip(zip_name=z_name, user_folder=user_folder)
                            filename = APP_ROOT + "/" + download_file

                        return send_file(filename_or_fp=filename, as_attachment=True,
                                         attachment_filename=filename.split("/")[-1])

                    except Exception as ex:
                        flash('Failed to add tasks to XLS. ' + str(ex))

        return redirect(url_for('admin.index'))

    @expose('/action/developer_all', methods=['GET', 'POST'])
    def action_developer_all(self):
        """
        For admin dashboard/ developer dashboard, download all tasks per date functionality
        :return:
        """

        @after_this_request
        def delete(response):
            """
            Removes xls and zip file after download
            """
            try:
                os.chdir(xls_save_path)
                xls_files = glob.glob('*.xls')
                for xls in xls_files:
                    os.unlink(xls)
                os.chdir(zip_save_path)
                zip_files = glob.glob('*.zip')
                for _zip in zip_files:
                    os.unlink(_zip)
                os.chdir(APP_ROOT)
            except Exception as exception:
                os.chdir(APP_ROOT)
                flash('Failed to delete XLS/ZIP. ' + str(exception))
            return response

        if current_user.is_authenticated:
            os.chdir(APP_ROOT)
            user_folder = str(current_user.id) + '_' + current_user.erp_user_name
            xls_save_path = target_save_path_xls + user_folder
            zip_save_path = target_save_path_zip + user_folder
            try:
                if not os.path.exists(xls_save_path):
                    os.makedirs(xls_save_path)
                if not os.path.exists(zip_save_path):
                    os.makedirs(zip_save_path)
            except Exception as e:
                flash('Failed to create/locate XLS/ZIP saving path. ' + str(e))

            try:
                developer = request.args.get('developer')
                if developer:
                    if current_user.tm_user_role == ADMIN:
                        all_tasks = Tasks.query.filter_by(tm_developer=developer)
                        user = Users.query.filter_by(id=developer).first()
                        if user:
                            z_name = "/All_Tasks_of_" + user.erp_user_name.replace(" ", "_") + str(
                                '{0.day:02d}_{0.month:02d}_{0.year:4d}'.format(datetime.now().date()))
                        else:
                            z_name = "/All_Tasks" + str(
                                '{0.day:02d}_{0.month:02d}_{0.year:4d}'.format(datetime.now().date()))
                    else:
                        all_tasks = Tasks.query.filter_by(tm_developer=current_user.id)
                        z_name = "/All_Tasks_" + current_user.erp_user_name.replace(" ", '_') + '_' + str(
                            '{0.day:02d}_{0.month:02d}_{0.year:4d}'.format(datetime.now().date()))

                    if all_tasks.first():
                        project_of_dev = sorted(set([task.tm_task_project_id for task in all_tasks.all()]))
                        for project in project_of_dev:
                            project_id = Projects.query.get(project)
                            tasks_of_dev = all_tasks.filter_by(tm_task_project_id=project).all()
                            filename = generate_xls(tasks=tasks_of_dev, action=1, folder=user_folder,
                                                    project=project_id.erp_project_id)

                        download_file = generate_zip(zip_name=z_name, user_folder=user_folder)
                        zip_filename = APP_ROOT + "/" + download_file

                        return send_file(filename_or_fp=zip_filename, as_attachment=True,
                                         attachment_filename=zip_filename.split("/")[-1])
                    else:
                        flash("Developer doesn't have any tasks")
            except Exception as ex:
                flash('Failed to add tasks to XLS.')

        return redirect(url_for('admin.index'))


class StandardModelView(sqla.ModelView):
    """
    Standard model view designed for Task Manager
    """
    can_create = True
    can_delete = False
    can_edit = True
    can_set_page_size = True
    can_view_details = False

    create_modal = False
    edit_modal = False

    page_size = 20


class AdminDeveloperView(StandardModelView):
    """
    Developer view of admin
    """

    column_list = ('erp_user_id', 'erp_user_name', 'tm_email_id', 'tm_latest_task', 'tm_user_status')

    column_exclude_list = ['tm_password', 'tm_user_role']

    column_labels = dict(erp_user_id='ERP Dev. ID', erp_user_name='ERP Dev. Name', tm_email_id='ERP Dev. Email',
                         tm_user_role='Role', tm_latest_task='Latest Task by Dev.', tm_password="Password",
                         tm_user_status='Status')

    column_descriptions = dict(erp_user_id='User id from ERP', erp_user_name='User name from ERP',
                               tm_email_id='User\'s email id', tm_user_role='User\'s role',
                               tm_latest_task='User\'s last submitted task', tm_password='User\'s password',
                               tm_user_status='User\'s Status in TM')

    column_default_sort = 'erp_user_id'

    column_sortable_list = ('erp_user_id', 'erp_user_name', 'tm_email_id', 'tm_user_status')

    column_searchable_list = ('erp_user_id', 'erp_user_name', 'tm_email_id', 'tm_latest_task')

    column_filters = ('erp_user_id', 'erp_user_name', 'tm_email_id', 'tm_latest_task', 'tm_user_status')

    form_excluded_columns = ('tm_user_role', 'tm_developer', 'developer_project')

    form_edit_rules = ('new_password', 'confirm_password')

    form_create_rules = ('erp_user_id', 'erp_user_name', 'tm_email_id', 'tm_password', 'tm_user_status')

    column_editable_list = ('erp_user_id', 'erp_user_name', 'tm_email_id', 'tm_user_status')

    form_args = dict(erp_user_id=dict(validators=[DataRequired()]), erp_user_name=dict(validators=[DataRequired()]),
                     tm_email_id=dict(validators=[DataRequired()]), tm_user_role=dict(validators=[DataRequired()]),
                     tm_latest_task=dict(validators=[DataRequired()]), tm_password=dict(validators=[DataRequired()]))

    def _latest_task_formatter(view, context, model, name):
        if model.tm_latest_task:
            url1 = url_for('admin.action_developer',
                           date=str('{0.day:02d}-{0.month:02d}-{0.year:4d}'.format(model.tm_latest_task)),
                           developer=str(model.id))
            icon1 = '<button type="button" class="btn btn-default btn-sm">' \
                    'Download &nbsp; <i class="fa fa-download" aria-hidden="true"></i></button>'
            url2 = url_for('admin.action_developer_all', developer=model.id)
            icon2 = '<button type="button" class="btn btn-default btn-sm">' \
                    'Download ALL &nbsp; <i class="fa fa-download" aria-hidden="true"></i></button>'
            a_tag1 = "<a href='%s' title='%s'>%s</a> " % (url1, str('{0.day:02d}-{0.month:02d}-{0.year:4d}'.format(
                model.tm_latest_task)), icon1)
            a_tag2 = "<a href='%s' title='Download ALL'>%s</a>" % (url2, icon2)
            markupstring = a_tag1 + a_tag2
            return Markup(markupstring)
        else:
            return ""

    column_formatters = {
        'tm_latest_task': _latest_task_formatter
    }

    def scaffold_form(self):
        """
        Adding custom form for setting password
        :return:
        """
        form_class = super(AdminDeveloperView, self).scaffold_form()
        form_class.new_password = PasswordField('New Password', [wtf_validator.Length(min=4, max=16),
                                                                 wtf_validator.DataRequired()])
        form_class.confirm_password = PasswordField('Confirm Password', [wtf_validator.Length(min=4, max=16),
                                                                         wtf_validator.DataRequired()])
        return form_class

    def update_model(self, form, model):
        """
        Update Model
        :param form:
        :param model:
        :return:
        """
        try:
            if 'new_password' in form.data or 'confirm_password' in form.data:
                if form.new_password.data == form.confirm_password.data:
                    form.populate_obj(model)
                    model.tm_password = generate_password_hash(form.new_password.data, method='sha256')
                    self.session.commit()
                    self._on_model_change(form, model, False)
                    self.session.commit()
                else:
                    raise validators.ValidationError('Both passwords should be same.')
            else:
                super(AdminDeveloperView, self).update_model(form, model)

        except Exception as ex:
            if not self.handle_view_exception(ex):
                flash('Failed to update record. ' + str(ex))

            self.session.rollback()
            return False
        else:
            self.after_model_change(form, model, False)

        return True

    def is_accessible(self):
        """
        Accessibility of the view
        :return:
        """
        if current_user.is_authenticated:
            if current_user.tm_user_role == ADMIN:
                return current_user.is_authenticated
        return False

    def get_query(self):
        """
        Custom query
        :return:
        """
        return self.session.query(self.model).filter(self.model.tm_user_role == DEVELOPER)

    def get_count_query(self):
        """
        Count of custom query result
        :return:
        """
        return self.session.query(func.count('*')).filter(self.model.tm_user_role == DEVELOPER)

    def create_model(self, form):
        """
        Create model from the form with hashed password
        """
        if helpers.validate_form_on_submit(form):
            form.tm_password.data = generate_password_hash(form.tm_password.data)
        return super(AdminDeveloperView, self).create_model(form)


class AdminQAView(StandardModelView):
    """
    QA view for admin
    """
    column_list = ('erp_user_id', 'erp_user_name', 'tm_email_id')

    column_labels = dict(erp_user_id='ERP Qa ID', erp_user_name='ERP Qa Name', tm_email_id='ERP Qa Email')

    column_descriptions = dict(erp_user_id='QA id from ERP', erp_user_name='QA name from ERP',
                               tm_email_id='QA\'s email id')

    column_default_sort = 'erp_user_id'

    column_sortable_list = ('erp_user_id', 'erp_user_name', 'tm_email_id')

    column_searchable_list = ('erp_user_id', 'erp_user_name', 'tm_email_id')

    column_filters = ('erp_user_id', 'erp_user_name', 'tm_email_id')

    form_excluded_columns = ('tm_qa', 'qa_project')

    form_create_rules = ('erp_user_id', 'erp_user_name', 'tm_email_id')

    form_edit_rules = form_create_rules

    form_args = dict(erp_user_id=dict(validators=[DataRequired()]), erp_user_name=dict(validators=[DataRequired()]),
                     tm_email_id=dict(validators=[DataRequired()]))

    def is_accessible(self):
        """
        Accessibility of the view
        :return:
        """
        if current_user.is_authenticated:
            if current_user.tm_user_role == ADMIN:
                return current_user.is_authenticated
        return False


class AdminMilestoneView(StandardModelView):
    """
    Milestone view for admin
    """
    can_edit = True
    column_list = ('tm_milestone_project_id', 'erp_milestone_id', 'tm_milestone_name', 'tm_milestone_status')

    column_labels = dict(tm_milestone_project_id="Project ID", erp_milestone_id='ID', tm_milestone_name='Name',
                         tm_milestone_status='Status')

    column_descriptions = dict(tm_milestone_project_id="Project ID", erp_milestone_id='Milestone id from ERP',
                               tm_milestone_name='Milestone name from ERP',
                               tm_milestone_status="Milestone's status, active/inactive")

    column_editable_list = ('tm_milestone_status',)

    column_default_sort = 'tm_milestone_project_id'

    column_sortable_list = ('tm_milestone_project_id', 'erp_milestone_id', 'tm_milestone_name', 'tm_milestone_status')

    column_searchable_list = ('erp_milestone_id', 'tm_milestone_name', 'tm_milestone_status')

    column_filters = ('tm_milestone_project_id', 'erp_milestone_id', 'tm_milestone_name', 'tm_milestone_status')

    form_create_rules = ('relative_project', 'erp_milestone_id', 'tm_milestone_name', 'tm_milestone_status')

    form_edit_rules = form_create_rules

    form_args = dict(relative_project=dict(validators=[DataRequired()]),
                     erp_milestone_id=dict(validators=[DataRequired()]),
                     tm_milestone_name=dict(validators=[DataRequired()]))

    def on_model_change(self, form, model, is_created):
        """
        On model change updating tm_milestone_project_id to project's erp_project_id
        """
        try:
            project_id = Projects.query.filter_by(id=form.relative_project.data.id).first()
            if project_id:
                model.tm_milestone_project_id = project_id.erp_project_id
                super(AdminMilestoneView, self).on_model_change(form, model, is_created)
            else:
                raise validators.ValidationError('You can not edit this task, task is already submitted in ERP')
        except AttributeError:
            super(AdminMilestoneView, self).on_model_change(form, model, is_created)

    def on_form_prefill(self, form, _id):
        """
        Customising edit form of milestones, to select relative project on edit form.
        :param _id: id of model object
        :param form: edit form object
        """
        milestone_obj = Milestones.query.filter_by(id=_id).one()
        form.relative_project.data = Projects.query.filter_by(
            erp_project_id=milestone_obj.tm_milestone_project_id).one()

    def is_accessible(self):
        """
        Accessibility of the view
        :return:
        """
        if current_user.is_authenticated:
            if current_user.tm_user_role == ADMIN:
                return current_user.is_authenticated
        return False


def filtering_developers():
    """
    For crete/edit project's form, filtering developers, getting only users whose user_role is developer
    :return:
    """
    return db.session.query(Users).filter(Users.tm_user_role == 'developer').filter(Users.tm_user_status == True)


class AdminProjectView(StandardModelView):
    """
    Project View for admin
    """
    can_view_details = True

    column_details_list = ('erp_project_id', 'tm_project_name', 'tm_developer_id', 'tm_quality_assurer_id',
                           'tm_project_status')

    column_list = ('erp_project_id', 'tm_project_name', 'tm_developer_id', 'tm_quality_assurer_id',
                   'tm_project_status')

    column_labels = dict(erp_project_id='ERP Projetc ID', tm_project_name='ERP Project Name',
                         tm_developer_id='Developers', tm_quality_assurer_id='QAs',
                         tm_project_status="Project's Status")

    column_descriptions = dict(erp_project_id='ERP Project ID', tm_project_name='ERP Project Name',
                               tm_developer_id='Project\'s Developers', tm_quality_assurer_id='Projects\'s QA',
                               tm_project_status='Projects\'s Status')

    column_default_sort = 'erp_project_id'

    column_sortable_list = ('erp_project_id', 'tm_project_name', 'tm_project_status')

    column_searchable_list = ('erp_project_id', 'tm_project_name', 'tm_project_status')

    column_filters = ('erp_project_id', 'tm_developer_id', 'tm_quality_assurer_id', 'tm_project_status')

    column_editable_list = ('tm_project_status',)

    form_edit_rules = ('erp_project_id', 'tm_project_name', 'tm_developer_id', 'tm_quality_assurer_id',
                       'tm_project_status')

    form_create_rules = ('erp_project_id', 'tm_project_name', 'tm_developer_id', 'tm_quality_assurer_id',
                         'tm_project_status')

    form_args = dict(erp_project_id=dict(validators=[DataRequired()]),
                     tm_project_name=dict(validators=[DataRequired()]),
                     tm_developer_id=dict(query_factory=filtering_developers, validators=[DataRequired()]))

    def _tm_developer_id(view, context, model, name):
        developers = []
        for developer in model.tm_developer_id:
            if developer.tm_user_status:
                developers.append(developer.erp_user_name)
        if developers:
            markupstring = "%s" % (', '.join(developers))
            return Markup(markupstring)
        else:
            return "NA"

    column_formatters = {
        'tm_developer_id': _tm_developer_id,
    }

    def is_accessible(self):
        """
        Accessibility of the view
        :return:
        """
        if current_user.is_authenticated:
            if current_user.tm_user_role == ADMIN:
                return current_user.is_authenticated
        return False


def _format_to_standard_date(date):
    return str('{0.day:02d}-{0.month:02d}-{0.year:4d}'.format(date))


class StandardTaskView(StandardModelView):
    """
    Standard Task View for Task Manager
    """
    can_view_details = True
    page_size = 20
    can_set_page_size = True

    column_list = ['relative_project', Tasks.tm_task_title, 'relative_milestone', Tasks.tm_start_date,
                   Tasks.tm_end_date, Tasks.tm_estimated_hours, 'relative_qa', Tasks.tm_priority, Tasks.tm_type,
                   Tasks.tm_description, Tasks.tm_added_on, Tasks.erp_task_status]

    column_labels = dict(relative_project='ERP Project ID', tm_task_title='Task Title', relative_milestone='Milestone',
                         tm_start_date='Start Date', tm_end_date='End Date', tm_estimated_hours='Est. Hours',
                         relative_qa='QA', relative_developer='Developer', tm_priority='Priority', tm_type='Type',
                         tm_description='Description', tm_added_on='Added On', erp_task_status='Task Status')

    column_descriptions = dict(relative_project='Project id of task', tm_task_title='Tasks\'s title',
                               relative_milestone='Task\'s milestone', tm_start_date='Task is started on this date',
                               tm_end_date='Task is ended on this date',
                               tm_estimated_hours='Task\'s estimated hours, please make sure you enter hours in this '
                                                  'format hh:mm:ss',
                               relative_qa='Task\'s quality assurer', tm_type='Task\'s type',
                               relative_developer='Task submitted by this developer', tm_priority='Task\'s priority',
                               tm_description='Task\'s description',
                               tm_added_on='Task added on',
                               erp_task_status='Status of Task, submitted to ERP or not')

    column_details_exclude_list = ('erp_task_status',)

    column_default_sort = ('id', True)

    column_sortable_list = None

    column_filters = ('relative_project', 'relative_qa', Tasks.tm_start_date,
                      Tasks.tm_end_date, Tasks.tm_added_on, Tasks.erp_task_status)

    form_choices = {'tm_type': [('New', 'New'), ('Bug', 'Bug')], 'tm_priority': [('High', 'High'), ('Low', 'Low')]}

    form_overrides = {
        'tm_description': TextAreaField,
        'tm_estimated_hours': TimeField
    }

    def _start_date_formatter(view, context, model, name):
        if model.tm_start_date:
            markupstring = "%s" % (_format_to_standard_date(model.tm_start_date))
            return Markup(markupstring)
        else:
            return "-"

    def _end_date_formatter(view, context, model, name):
        if model.tm_end_date:
            markupstring = "%s" % (_format_to_standard_date(model.tm_end_date))
            return Markup(markupstring)
        else:
            return "-"

    def _added_date_formatter(view, context, model, name):
        if model.tm_added_on:
            markupstring = "%s" % (_format_to_standard_date(model.tm_added_on))
            return Markup(markupstring)
        else:
            return "-"

    column_formatters = {
        'tm_start_date': _start_date_formatter,
        'tm_end_date': _end_date_formatter,
        'tm_added_on': _added_date_formatter,
    }

    def on_model_change(self, form, model, is_created):
        """
        If end date before start date, flag them invalid. And if task is submitted in ERP, flag them invalid
        """
        try:
            if is_created:
                model.tm_added_on = datetime.now().date()
            if not model.erp_task_status:
                if current_user.tm_user_role == DEVELOPER:
                    model.tm_developer = current_user.id
                    if form.relative_project.data:
                        project = Projects.query.filter_by(id=form.relative_project.data.id,
                                                           tm_project_status=True).filter(
                            Projects.tm_developer_id.any(id=current_user.id)).first()
                        if not project:
                            raise validators.ValidationError('Invalid Project ID!')
                    if form.relative_milestone.data:
                        milestone = Milestones.query.filter_by(
                            tm_milestone_status=True,
                            tm_milestone_project_id=form.relative_project.data.erp_project_id,
                            id=form.relative_milestone.data.id).first()
                        if not milestone:
                            raise validators.ValidationError('Invalid Milestone!')
                    if form.tm_end_date.data < form.tm_start_date.data:
                        raise validators.ValidationError('Invalid start/end date!')
                    if form.relative_qa.data:
                        qa = Projects.query.filter_by(id=form.relative_project.data.id).filter(
                            Projects.tm_quality_assurer_id.any(id=form.relative_qa.data.id)).first()
                        if not qa:
                            raise validators.ValidationError('Invalid QA!')
                else:
                    if form.tm_end_date.data < form.tm_start_date.data:
                        raise validators.ValidationError('Invalid start/end date!')

                super(StandardTaskView, self).on_model_change(form, model, is_created)
            else:
                raise validators.ValidationError('You can not edit this task, task is already submitted in ERP')
        except AttributeError:
            super(StandardTaskView, self).on_model_change(form, model, is_created)

    @action('export_date', 'Generate XLS [date-wise]', 'Are you sure you want to generate XLS for selected tasks?')
    def action_export_date_wise(self, ids):
        """
        date-wise action 0
        :param ids:
        """

        @after_this_request
        def delete(response):
            """
            Removes xls and zip file after download
            """
            try:
                os.chdir(xls_save_path)
                xls_files = glob.glob('*.xls')
                for xls in xls_files:
                    os.unlink(xls)
                os.chdir(zip_save_path)
                zip_files = glob.glob('*.zip')
                for _zip in zip_files:
                    os.unlink(_zip)
                os.chdir(APP_ROOT)
            except Exception as exception:
                os.chdir(APP_ROOT)
                flash('Failed to delete XLS/ZIP. ' + str(exception))
            return response

        os.chdir(APP_ROOT)
        user_folder = str(current_user.id) + '_' + current_user.erp_user_name
        xls_save_path = target_save_path_xls + user_folder
        zip_save_path = target_save_path_zip + user_folder

        try:
            if not os.path.exists(xls_save_path):
                os.makedirs(xls_save_path)
            if not os.path.exists(zip_save_path):
                os.makedirs(zip_save_path)
        except Exception as e:
            flash('Failed to create/locate XLS/ZIP saving path. ' + str(e))

        try:
            all_tasks = Tasks.query.filter(Tasks.id.in_(ids))
            tasks_per_day = sorted(set([task.tm_added_on for task in all_tasks.all()]))
            for day in tasks_per_day:
                tasks_of_day = all_tasks.filter_by(tm_added_on=day).all()
                filename = generate_xls(tasks=tasks_of_day, action=0, folder=user_folder)
            if len(tasks_per_day) > 1:
                z_name = current_user.erp_user_name.replace(" ", "_") + str(
                    '_{0.day:02d}_{0.month:02d}_{0.year:4d}'.format(datetime.now().date()))

                download_file = generate_zip(zip_name=z_name, user_folder=user_folder)
                filename = APP_ROOT + "/" + download_file

            return send_file(filename_or_fp=filename, as_attachment=True,
                             attachment_filename=filename.split("/")[-1])

        except Exception as ex:
            if not self.handle_view_exception(ex):
                raise

            flash('Failed to add tasks to XLS. ' + str(ex))

    @action('export_project', 'Generate XLS [project-wise]',
            'Are you sure you want to generate XLS for selected tasks?')
    def action_export_project_wise(self, ids):
        """
        project-wise action 2
        :param ids:
        """

        @after_this_request
        def delete(response):
            """
            Removes xls and zip file after download
            """
            try:
                os.chdir(xls_save_path)
                xls_files = glob.glob('*.xls')
                for xls in xls_files:
                    os.unlink(xls)
                os.chdir(zip_save_path)
                zip_files = glob.glob('*.zip')
                for _zip in zip_files:
                    os.unlink(_zip)
                os.chdir(APP_ROOT)
            except Exception as exception:
                os.chdir(APP_ROOT)
                flash('Failed to delete XLS/ZIP. ' + str(exception))
            return response

        os.chdir(APP_ROOT)
        user_folder = str(current_user.id) + '_' + current_user.erp_user_name
        xls_save_path = target_save_path_xls + user_folder
        zip_save_path = target_save_path_zip + user_folder

        try:
            if not os.path.exists(xls_save_path):
                os.makedirs(xls_save_path)
            if not os.path.exists(zip_save_path):
                os.makedirs(zip_save_path)
        except Exception as e:
            flash('Failed to create/locate XLS/ZIP saving path. ' + str(e))

        try:
            all_tasks = Tasks.query.filter(Tasks.id.in_(ids))
            tasks_by_project = sorted(set([task.tm_task_project_id for task in all_tasks.all()]))
            for project in tasks_by_project:
                tasks_of_project = all_tasks.filter_by(tm_task_project_id=project).all()
                filename = generate_xls(tasks_of_project, action=2, folder=user_folder)
            if len(tasks_by_project) > 1:
                z_name = "/Tasks_ProjectWise_of_" + str(
                    '{0.day:02d}_{0.month:02d}_{0.year:4d}'.format(datetime.now().date()))
                download_file = generate_zip(zip_name=z_name, user_folder=user_folder)
                filename = APP_ROOT + "/" + download_file

            return send_file(filename_or_fp=filename, as_attachment=True,
                             attachment_filename=filename.split("/")[-1])

        except Exception as ex:
            if not self.handle_view_exception(ex):
                raise

            flash('Failed to add tasks to XLS. ' + str(ex))

    @action('export_merge', 'Generate XLS [merge & download]',
            'Are you sure you want to generate XLS for selected tasks?')
    def action_export_merge(self, ids):
        """
        merged action 3
        :param ids:
        """

        @after_this_request
        def delete(response):
            """
            Removes xls and zip file after download
            """
            try:
                os.chdir(xls_save_path)
                xls_files = glob.glob('*.xls')
                for xls in xls_files:
                    os.unlink(xls)
                os.chdir(APP_ROOT)
            except Exception as exception:
                os.chdir(APP_ROOT)
                flash('Failed to delete XLS/ZIP. ' + str(exception))
            return response

        os.chdir(APP_ROOT)
        user_folder = str(current_user.id) + '_' + current_user.erp_user_name
        xls_save_path = target_save_path_xls + user_folder
        try:
            if not os.path.exists(xls_save_path):
                os.makedirs(xls_save_path)
        except Exception as e:
            flash('Failed to delete XLS/ZIP. ' + str(e))

        try:
            all_tasks = Tasks.query.filter(Tasks.id.in_(ids))
            filename = generate_xls(tasks=all_tasks, action=3, folder=user_folder)

            return send_file(filename_or_fp=filename, as_attachment=True,
                             attachment_filename=filename.split("/")[-1])
        except Exception as ex:
            if not self.handle_view_exception(ex):
                raise

            flash('Failed to add tasks to XLS. ' + str(ex))


def get_hour_minute(tm_estimated_hours):
    """
    Returns separated hours and minute from '08:00:00'
    :param tm_estimated_hours:
    :return:
    """
    if tm_estimated_hours.split(':')[0] and tm_estimated_hours.split(':')[1]:
        return tm_estimated_hours.split(':')[0], tm_estimated_hours.split(':')[1]
    else:
        flash('Estimated hours is not set properly, so default time is set to 08:00, please check')
        return '08', '00'


class AdminTaskView(StandardTaskView):
    """
    Project Task for admin
    """
    can_create = False
    can_delete = True

    column_searchable_list = (Users.id, Users.erp_user_name, Projects.erp_project_id, Qa.erp_user_name)

    column_list = (
        Tasks.tm_added_on, 'relative_project', Tasks.tm_task_title, 'relative_milestone',
        Tasks.tm_start_date, Tasks.tm_end_date, Tasks.tm_estimated_hours, 'relative_qa',
        'relative_developer', Tasks.tm_priority, Tasks.tm_type, Tasks.tm_description,)

    column_filters = (
        Projects.erp_project_id, Qa.erp_user_name, Users.erp_user_id, Users.erp_user_name, Tasks.tm_start_date,
        Tasks.tm_end_date, Tasks.tm_added_on, Tasks.erp_task_status)

    form_edit_rules = (
        'relative_project', 'tm_task_title', 'relative_milestone', rules.Field('tm_start_date'),
        rules.Field('tm_end_date'), 'tm_estimated_hours', 'relative_qa', 'relative_developer',
        'tm_priority', 'tm_type', 'tm_description')

    form_args = dict(
        relative_project=dict(validators=[DataRequired()]),
        tm_task_title=dict(validators=[DataRequired()]),
        relative_milestone=dict(validators=[DataRequired()]),
        tm_start_date=dict(validators=[DataRequired()], format='%d-%m-%Y'),
        tm_end_date=dict(validators=[DataRequired()], format='%d-%m-%Y'),
        tm_estimated_hours=dict(validators=[DataRequired()]),
        relative_developer=dict(validators=[DataRequired()]),
        tm_priority=dict(validators=[DataRequired()]),
        tm_type=dict(validators=[DataRequired()]),
        tm_description=dict(validators=[DataRequired()]))

    form_widget_args = {
        'tm_start_date': {'data-date-format': 'DD-MM-YYYY'},
        'tm_end_date': {'data-date-format': 'DD-MM-YYYY'},
        'relative_project': {'disabled': True},
        'relative_milestone': {'disabled': True},
        'relative_qa': {'disabled': True},
        'relative_developer': {'disabled': True},
    }

    def _developer_formatter(view, context, model, name):
        """
        Returns developer name in span tag with title as erp user id
        """
        if model.tm_developer:
            markupstring = "<span title='%s'> %s </span>" % (
                model.relative_developer.erp_user_id, model.relative_developer.erp_user_name)
            return Markup(markupstring)
        else:
            return "-"

    def _start_date_formatter(view, context, model, name):
        if model.tm_start_date:
            markupstring = "%s" % (_format_to_standard_date(model.tm_start_date))
            return Markup(markupstring)
        else:
            return "-"

    def _end_date_formatter(view, context, model, name):
        if model.tm_end_date:
            markupstring = "%s" % (_format_to_standard_date(model.tm_end_date))
            return Markup(markupstring)
        else:
            return "-"

    def _added_date_formatter(view, context, model, name):
        if model.tm_added_on:
            markupstring = "%s" % (_format_to_standard_date(model.tm_added_on))
            return Markup(markupstring)
        else:
            return "-"

    column_formatters = {
        'tm_start_date': _start_date_formatter,
        'tm_end_date': _end_date_formatter,
        'tm_added_on': _added_date_formatter,
        'relative_developer': _developer_formatter,
    }

    def add_to_erp(self, task_details, project_id):
        """
        Connects to ERP, and submits task
        :param project_id:
        :param task_details:
        :return:
        """
        cookies = cookielib.CookieJar()
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookies))

        # Login to ERP using login_info
        login_erp = opener.open(URL_ERP_LOGIN, urllib.urlencode(LOGIN_INFO))

        add_task_to_erp = opener.open(URL_ADD_TASK + '/' + project_id, urllib.urlencode(task_details))

        logout_erp = opener.open(URL_ERP_LOGOUT)

        if add_task_to_erp.url == URL_ERP_LOGIN:
            return False
        else:
            # if success
            return True

    @action('approve', 'Add to ERP', 'Are you sure you want to approve selected users?')
    def action_approve(self, ids):
        """
        Adding add to ERP action
        :param ids:
        """
        try:
            query = Tasks.query.filter(Tasks.id.in_(ids))
            count = 0
            for task in query.all():
                if not task.erp_task_status:
                    # add api call for adding task to ERP
                    t_type = 1
                    t_priority = 1
                    t_status = 1
                    t_qa = None
                    if task.tm_type == 'Bug':
                        t_type = 0
                    if task.tm_priority == "Low":
                        t_priority = 0
                    if task.relative_qa:
                        t_qa = task.relative_qa.erp_user_id
                    hour, minute = get_hour_minute(task.tm_estimated_hours)
                    estimated_hour_key = 'Tasks[task_estimated_hours][' + \
                                         str((datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) -
                                              datetime(1970, 1, 1)).total_seconds()) + ']'
                    task_details = {
                        'Tasks[task_title]': task.tm_task_title,
                        'Tasks[task_type]': t_type,
                        'Tasks[task_priority]': t_priority,
                        'Tasks[start_date]': '{0.day:02d}-{0.month:02d}-{0.year:4d}'.format(task.tm_start_date),
                        'Tasks[end_date]': '{0.day:02d}-{0.month:02d}-{0.year:4d}'.format(task.tm_end_date),
                        'hour': hour,
                        'minute': minute,
                        estimated_hour_key: hour + ':' + minute,
                        'Tasks[quality_assurer_id]': t_qa,
                        'Tasks[status]:': t_status,
                        'Tasks[delay_reason]': '',
                        'Tasks[project_id]': task.relative_project.erp_project_id,
                        'Tasks[milestone_id]': task.relative_milestone.erp_milestone_id,
                        'Tasks[developer_id]': task.relative_developer.erp_user_id,
                        'Tasks[task_description]': task.tm_description
                    }
                    project_id = str(task.relative_project.erp_project_id)
                    submitted = self.add_to_erp(task_details, project_id)
                    if submitted:
                        task.erp_task_status = True
                        db.session.commit()
                        count += 1
                    else:
                        return redirect(URL_ERP_LOGIN)

            if count:
                if len(ids) == count:
                    if count == 1:
                        flash('Selected task is successfully added to ERP.')
                    else:
                        flash('All selected tasks are successfully added to ERP.')
                else:
                    flash('New submitted tasks : ' + str(count) + ' AND Already submitted tasks : ' + str(
                        len(ids) - count))
            else:
                flash('All tasks are already submitted.')

        except Exception as ex:
            if not self.handle_view_exception(ex):
                raise

            flash('Failed to add tasks to ERP. ' + str(ex))

    @action('export_dev', 'Generate XLS [developer-wise]', 'Are you sure you want to generate XLS for selected tasks?')
    def action_export_developer_wise(self, ids):
        """
        developer-wise action 1
        :param ids:
        """

        @after_this_request
        def delete(response):
            """
            Removes xls and zip file after download
            """
            try:
                os.chdir(xls_save_path)
                xls_files = glob.glob('*.xls')
                for xls in xls_files:
                    os.unlink(xls)
                os.chdir(zip_save_path)
                zip_files = glob.glob('*.zip')
                for _zip in zip_files:
                    os.unlink(_zip)
                os.chdir(APP_ROOT)
            except Exception as exception:
                os.chdir(APP_ROOT)
                flash('Failed to delete XLS/ZIP. ' + str(exception))
            return response

        os.chdir(APP_ROOT)
        user_folder = str(current_user.id) + '_' + current_user.erp_user_name
        xls_save_path = target_save_path_xls + user_folder
        zip_save_path = target_save_path_zip + user_folder

        try:
            if not os.path.exists(xls_save_path):
                os.makedirs(xls_save_path)
            if not os.path.exists(zip_save_path):
                os.makedirs(zip_save_path)
        except Exception as e:
            flash('Failed to create/locate XLS/ZIP saving path. ' + str(e))

        try:
            all_tasks = Tasks.query.filter(Tasks.id.in_(ids))
            tasks_by_dev = sorted(set([task.tm_developer for task in all_tasks.all()]))
            for dev in tasks_by_dev:
                project_of_dev = sorted(
                    set([task.tm_task_project_id for task in all_tasks.filter_by(tm_developer=dev).all()]))
                for project in project_of_dev:
                    project_id = Projects.query.get(project)
                    tasks_of_dev = all_tasks.filter_by(tm_developer=dev, tm_task_project_id=project).all()
                    filename = generate_xls(tasks=tasks_of_dev, action=1, folder=user_folder,
                                            project=project_id.erp_project_id)
            if len(tasks_by_dev) > 1:
                z_name = "/Tasks_DeveloperWise_of_" + str(
                    '{0.day:02d}_{0.month:02d}_{0.year:4d}'.format(datetime.now().date()))
                download_file = generate_zip(zip_name=z_name, user_folder=user_folder)
                filename = APP_ROOT + "/" + download_file

            return send_file(filename_or_fp=filename, as_attachment=True,
                             attachment_filename=filename.split("/")[-1])

        except Exception as ex:
            if not self.handle_view_exception(ex):
                raise

            flash('Failed to add tasks to XLS. ' + str(ex))

    def is_accessible(self):
        """
        Accessibility of the view
        :return:
        """
        if current_user.is_authenticated:
            if current_user.tm_user_role == ADMIN:
                return current_user.is_authenticated
        return False

    def get_query(self):
        """
        Custom query to get only active user's tasks
        :return:
        """
        inactive_users = [user.id for user in Users.query.filter_by(tm_user_status=False).all()]
        return self.session.query(self.model).select_from(Tasks).filter(self.model.tm_developer.notin_(inactive_users))

    def get_count_query(self):
        """
        Count of custom query result
        :return:
        """
        inactive_users = [user.id for user in Users.query.filter_by(tm_user_status=False).all()]
        return self.session.query(func.count('*')).select_from(Tasks).filter(
            self.model.tm_developer.notin_(inactive_users))


def _get_milestone_list():
    """Returns milestone list of current user"""
    project_ids = Projects.query.with_entities(Projects.erp_project_id).filter_by(
        tm_project_status=True).filter(Projects.tm_developer_id.any(id=current_user.id))
    return Milestones.query.filter(Milestones.tm_milestone_project_id.in_(project_ids)). \
        filter_by(tm_milestone_status=True).all()


def _get_project_list():
    """Returns project list of current user"""
    return Projects.query.filter_by(tm_project_status=True).filter(Projects.tm_developer_id.any(id=current_user.id))


class StandardDeveloperTaskView(StandardTaskView):
    """
    Standard developer's task view
    """
    can_create = True
    can_edit = True
    can_delete = False

    column_list = ['relative_project', Tasks.tm_task_title, 'relative_milestone',
                   Tasks.tm_start_date, Tasks.tm_end_date, Tasks.tm_estimated_hours, 'relative_qa', Tasks.tm_priority,
                   Tasks.tm_type, Tasks.tm_description, Tasks.tm_added_on]
    form_create_rules = ('relative_project', 'tm_task_title', 'relative_milestone', rules.Field('tm_start_date'),
                         rules.Field('tm_end_date'), 'tm_estimated_hours', 'relative_qa', 'tm_priority', 'tm_type',
                         'tm_description')

    form_edit_rules = ('relative_project', 'tm_task_title', 'relative_milestone', rules.Field('tm_start_date'),
                       rules.Field('tm_end_date'), 'tm_estimated_hours', 'relative_qa', 'tm_priority', 'tm_type',
                       'tm_description')

    form_args = dict(relative_project=dict(validators=[DataRequired()], query_factory=_get_project_list),
                     tm_task_title=dict(validators=[DataRequired()]),
                     relative_milestone=dict(validators=[DataRequired()], query_factory=_get_milestone_list),
                     tm_start_date=dict(validators=[DataRequired()], format='%d-%m-%Y'),
                     tm_end_date=dict(validators=[DataRequired()], format='%d-%m-%Y'),
                     tm_estimated_hours=dict(validators=[DataRequired()]),
                     tm_priority=dict(validators=[DataRequired()]), tm_type=dict(validators=[DataRequired()]),
                     tm_description=dict(validators=[DataRequired()]))

    form_widget_args = {
        'tm_start_date': {'data-date-format': 'DD-MM-YYYY', 'data-minYear': '2000'},
        'tm_end_date': {'data-date-format': 'DD-MM-YYYY'},
    }

    def is_accessible(self):
        """
        Accessibility of the view
        :return:
        """
        if current_user.is_authenticated:
            if current_user.tm_user_role == DEVELOPER:
                return current_user.is_authenticated
        return False

    def after_model_change(self, form, model, is_created):
        """
        If task is created, then update latest task of developer
        :param form:
        :param model:
        :param is_created:
        """
        try:
            if is_created:
                current_user.tm_latest_task = datetime.now().date()
                db.session.commit()

        except Exception as e:
            db.session.rollback()
            flash('Error in updating latest task of developer')

    def after_model_delete(self, model):
        """
        If task is deleted then update developer's latest task
        :param model:
        :return:
        """
        try:
            latest_task = Tasks.query.filter_by(tm_developer=model.tm_developer).first()
            update_user_latest_task = Users.query.filter_by(id=model.tm_developer).first()
            if latest_task:
                latest_task = Tasks.query.filter_by(tm_developer=model.tm_developer).all()
                update_user_latest_task.tm_latest_task = latest_task[-1].tm_added_on
            else:
                update_user_latest_task.tm_latest_task = None
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash('Error in updating latest task of developer')

    def on_model_delete(self, model):
        """
        If task is submitted in ERP, flag them invalid deletion
        :param model:
        """
        try:
            if not model.erp_task_status:
                super(StandardDeveloperTaskView, self).on_model_delete(model)
            else:
                raise validators.ValidationError('You can not delete this task, task is already submitted in ERP')
        except AttributeError:
            super(StandardDeveloperTaskView, self).on_model_delete(model)


class DeveloperTaskView(StandardDeveloperTaskView):
    """
    Developer's view for current day's tasks
    """

    def get_query(self):
        """
        Custom query to get only current user's tasks of current day
        :return:
        """
        return self.session.query(self.model).filter(self.model.tm_developer == current_user.id).filter(
            self.model.tm_added_on == datetime.now().date())

    def get_count_query(self):
        """
        Count of custom query result
        :return:
        """
        return self.session.query(func.count('*')).filter(self.model.tm_developer == current_user.id).filter(
            self.model.tm_added_on == datetime.now().date())


class DeveloperAllTaskView(StandardDeveloperTaskView):
    """
    Developer's view for All tasks
    """

    def get_query(self):
        """
        Custom query to get only current user's all tasks
        :return:
        """
        return self.session.query(self.model).filter(self.model.tm_developer == current_user.id)

    def get_count_query(self):
        """
        Count of custom query result
        :return:
        """
        return self.session.query(func.count('*')).filter(self.model.tm_developer == current_user.id)


class ChangePasswordView(sqla.ModelView):
    """
    Change Password View
    """
    can_create = False
    can_edit = True
    can_delete = False

    column_list = [Users.erp_user_name, Users.tm_email_id]

    excluded_form_columns = ('erp_user_id', 'tm_email_id', 'erp_user_name', 'tm_user_role', 'tm_latest_task',
                             'tm_developer', 'developer_project', 'tm_user_status')

    def is_accessible(self):
        """
        Accessibility of the view
        :return:
        """
        if current_user.is_authenticated:
            return current_user.is_authenticated
        return False

    def scaffold_form(self):
        """
        Adding custom forms
        :return:
        """
        form_class = super(ChangePasswordView, self).scaffold_form()
        form_class.tm_password = PasswordField('Current Password', validators=[DataRequired()])
        form_class.new_password = PasswordField('New Password', validators=[DataRequired()])
        form_class.confirm_password = PasswordField('Confirm Password', validators=[DataRequired()])
        return form_class

    def update_model(self, form, model):
        """
        Update Model
        :param form:
        :param model:
        :return:
        """
        try:
            if check_password_hash(model.tm_password, form.tm_password.data):
                if form.new_password.data == form.confirm_password.data:
                    if check_password_hash(model.tm_password, form.new_password.data):
                        raise validators.ValidationError('New password should be different than current password')
                    form.populate_obj(model)
                    model.tm_password = generate_password_hash(form.new_password.data, method='sha256')
                    form.tm_password.data = model.tm_password
                    self.session.commit()
                    self._on_model_change(form, model, False)
                    self.session.commit()
                else:
                    raise validators.ValidationError('Both passwords should be same.')
            else:
                raise validators.ValidationError('Please enter correct current password')

        except Exception as ex:
            if not self.handle_view_exception(ex):
                flash('Failed to update record. ' + str(ex))

            self.session.rollback()
            return False
        else:
            self.after_model_change(form, model, False)

        return True

    def get_query(self):
        """
        Custom query to get only current user's detail
        :return:
        """
        return self.session.query(self.model).filter(self.model.id == current_user.id)

    def get_count_query(self):
        """
        Count of custom query result
        :return:
        """
        return self.session.query(func.count('*')).filter(self.model.id == current_user.id)


# Create admin
admin = admin.Admin(app, 'Task Manager', index_view=MainView(), base_template='layout.html',
                    template_mode='bootstrap3', url='/')

# admin views
admin.add_view(AdminDeveloperView(Users, db.session, name="Developers", endpoint="all_developers"))
admin.add_view(AdminQAView(Qa, db.session, name="Quality Assurer", endpoint="all_qas"))
admin.add_view(AdminMilestoneView(Milestones, db.session, name="Milestones", endpoint="all_milestones"))
admin.add_view(AdminProjectView(Projects, db.session, name="Projects", endpoint="all_projects"))
admin.add_view(AdminTaskView(Tasks, db.session, name="Tasks", endpoint="all_tasks"))

# developer views
admin.add_view(DeveloperTaskView(Tasks, db.session, name="Today's Tasks", endpoint="today_tasks"))
admin.add_view(DeveloperAllTaskView(Tasks, db.session, name="All Tasks", endpoint="my_tasks"))
admin.add_view(ChangePasswordView(Users, db.session, name="Profile", endpoint="profile"))


def gen_dp_all():
    """
    Generates dp for all users
    """
    all_users = Users.query.all()
    for u in all_users:
        generate_dp(u.erp_user_name, u.id)


def build_sample_db():
    """
    Drops old db, and creates new one
    """
    db.init_app(app)
    db.drop_all()
    db.create_all()
    tl_user = Users(erp_user_id=101, erp_user_name="ChandPrakash Rawat",
                    tm_email_id="chandprakash@drcsystems.com",
                    tm_password=generate_password_hash("Drc@1234", method='sha256'),
                    tm_user_role="admin")
    db.session.add(tl_user)
    db.session.commit()
    gen_dp_all()


if __name__ == '__main__':
    # Initialize flask-login
    init_login()
    # Build a sample db on the fly, if one does not exist yet.
    app_dir = os.path.realpath(os.path.dirname(__file__))
    database_path = os.path.join(app_dir, app.config['DATABASE_FILE'])
    if not os.path.exists(database_path):
        build_sample_db()

    # Start app
    app.run(host='0.0.0.0', port=8082)
