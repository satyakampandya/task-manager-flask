# coding=utf-8
"""
Migrating from old database to new database
"""
from datetime import datetime

from werkzeug.security import generate_password_hash

from models import Milestones, Projects, Qa, Tasks, Users, db as new_db
from models_old import Details, User


def add_modify_project_api(project_obj, developers, qas):
    """
    Updates project
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
        qa_obj = Qa.query.filter_by(erp_user_id=qa_id).first()
        project_obj.tm_quality_assurer_id.append(qa_obj)

    new_db.session.commit()


def reset_new_db():
    """
    Drops old db, and creates new one
    """
    new_db.drop_all()
    new_db.create_all()


def populate_developers():
    """
    Converts users table to new schema
    :return:
    """
    old_users = User.query.order_by(User.role.asc(), User.username.asc()).all()
    erp_user_id = 100
    for user in old_users:
        erp_user_id = erp_user_id + 1
        try:
            new_developer = Users()
            new_developer.tm_email_id = user.email
            new_developer.tm_password = generate_password_hash("Drc@1234", method='sha256')
            new_developer.tm_user_role = user.role.lower()
            new_developer.erp_user_id = erp_user_id
            new_developer.erp_user_name = user.username
            if not user.latest_task == "no":
                new_developer.tm_latest_task = datetime.strptime(user.latest_task, '%d/%m/%Y').date()
            new_db.session.add(new_developer)
            new_db.session.commit()
        except Exception as e:
            new_db.session.rollback()
    return Users.query.count()


def populate_qa():
    """
    Converts users table to new schema
    :return:
    """
    old_qas = sorted(set([str(task.qa) for task in Details.query.order_by(Details.qa.asc()).all()]))
    if '' in old_qas:
        old_qas.remove('')
    erp_qa_id = 200
    for qa in old_qas:
        erp_qa_id = erp_qa_id + 1
        try:
            new_qa = Qa()
            new_qa.erp_user_name = qa
            new_qa.tm_email_id = str(qa.replace(" ", ".").lower()) + str(erp_qa_id) + \
                                 '@drcsystems.com'
            new_qa.erp_user_id = erp_qa_id

            new_db.session.add(new_qa)
            new_db.session.commit()

        except Exception as e:
            new_db.session.rollback()

    return Qa.query.count()


def populate_milestones():
    """
    Populates Milestones
    """
    project_miles = sorted(set([(str(task.milestone), int(task.project_id)) for task in
                                Details.query.order_by(Details.milestone.asc()).all()]))
    mile_id = 300
    for mile in project_miles:
        mile_id += 1

        new_milestone = Milestones()
        new_milestone.erp_milestone_id = mile_id
        new_milestone.tm_milestone_name = mile[0]
        new_milestone.tm_milestone_project_id = mile[1]

        new_db.session.add(new_milestone)
        new_db.session.commit()

    return Milestones.query.count()


def populate_projects():
    """
    Populates projects model
    """
    project_ids = sorted(set([int(task.project_id) for task in Details.query.order_by(Details.project_id.asc()).all()]))
    dummy_project_id = 0

    for project_id in project_ids:
        dummy_project_id = dummy_project_id + 1

        developers = sorted(set([str(task.developer) for task in Details.query.filter_by(project_id=project_id).all()]))
        developer_ids = []
        for developer in developers:
            user = Users.query.filter_by(erp_user_name=developer).first()
            if user:
                developer_ids.append(user.erp_user_id)
        qas = sorted(set([str(task.qa) for task in Details.query.filter_by(project_id=project_id).all()]))
        if '' in qas:
            qas.remove('')
        if len(qas) > 0:
            qas_id = [Qa.query.filter_by(erp_user_name=qa).first().erp_user_id for qa in qas]
        else:
            qas_id = []

        new_object = Projects()
        new_object.tm_project_name = "Project " + str(dummy_project_id)
        new_object.erp_project_id = int(project_id)

        new_db.session.add(new_object)
        new_db.session.commit()

        add_modify_project_api(new_object, developers=developer_ids, qas=qas_id)

    return Projects.query.count()


def populate_tasks():
    """
    Populates tasks model
    """
    all_tasks = Details.query.all()
    for task in all_tasks:
        project_id = Projects.query.filter_by(erp_project_id=task.project_id).first()
        milestone_id = Milestones.query.filter_by(tm_milestone_name=task.milestone,
                                                  tm_milestone_project_id=task.project_id).first()
        developer_id = Users.query.filter_by(erp_user_name=task.developer).first()
        qa_id = None
        if task.qa:
            qa_id = Qa.query.filter_by(erp_user_name=task.qa).first().id
        if developer_id:
            new_task = Tasks()
            new_task.tm_task_project_id = project_id.id
            new_task.tm_task_title = task.task_title
            new_task.tm_milestone = milestone_id.id
            new_task.tm_start_date = datetime.strptime(task.start_date, '%d/%m/%Y').date()
            new_task.tm_end_date = datetime.strptime(task.end_date, '%d/%m/%Y').date()
            new_task.tm_estimated_hours = task.estimated_hours
            new_task.tm_qa = qa_id
            new_task.tm_developer = developer_id.id
            new_task.tm_priority = task.priority.capitalize()
            new_task.tm_type = task.type.capitalize()
            new_task.tm_description = task.description
            new_task.tm_added_on = datetime.strptime(task.added_on, '%d/%m/%Y').date()
            new_task.erp_task_status = False

            new_db.session.add(new_task)
            new_db.session.commit()

    return Details.query.count()


reset_new_db()
total_users = populate_developers()
total_qas = populate_qa()
total_milestones = populate_milestones()
total_projects = populate_projects()
total_tasks = populate_tasks()
