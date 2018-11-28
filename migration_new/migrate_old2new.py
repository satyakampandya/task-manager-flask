# coding=utf-8
"""
Migrating from old database to new database
"""
import re
from datetime import datetime

from models import Milestones, Projects, Qa, Tasks, Users, db as new__db
from models_old import Milestones as _Milestones, Projects as _Projects, Qa as _Qa, Tasks as _Tasks, Users as _Users


def reset_new_db():
    """
    Drops old db, and creates new one
    """
    new__db.drop_all()
    new__db.create_all()


def populate_developers():
    """
    Converts users table to new schema
    :return:
    """
    old_users = _Users.query.all()
    for user in old_users:
        try:
            new_developer = Users()
            new_developer.tm_email_id = user.tm_email_id
            new_developer.tm_password = user.tm_password
            new_developer.tm_user_role = user.tm_user_role
            new_developer.erp_user_id = user.erp_user_id
            new_developer.erp_user_name = user.erp_user_name
            new_developer.tm_latest_task = user.tm_latest_task
            new__db.session.add(new_developer)
            new__db.session.commit()
        except Exception as e:
            import pdb
            pdb.set_trace()
            new__db.session.rollback()

    return Users.query.count()


def populate_qa():
    """
    Converts users table to new schema
    :return:
    """
    old_qas = _Qa.query.all()
    for qa in old_qas:
        try:
            new_qa = Qa()
            new_qa.erp_user_name = qa.erp_user_name
            new_qa.tm_email_id = qa.tm_email_id
            new_qa.erp_user_id = qa.erp_user_id

            new__db.session.add(new_qa)
            new__db.session.commit()

        except Exception as e:
            new__db.session.rollback()

    return Qa.query.count()


def populate_milestones():
    """
    Populates Milestones
    """
    project_miles = _Milestones.query.all()
    for mile in project_miles:
        new_milestone = Milestones()
        new_milestone.erp_milestone_id = mile.erp_milestone_id
        new_milestone.tm_milestone_name = mile.tm_milestone_name
        new_milestone.tm_milestone_project_id = mile.tm_milestone_project_id

        new__db.session.add(new_milestone)
        new__db.session.commit()

    return Milestones.query.count()


def add_modify_project_api(project_obj, developers, qas):
    """
    Updates project
    :param project_obj:
    :param developers:
    :param qas:
    """
    project_obj.tm_developer_id[:] = []
    project_obj.tm_quality_assurer_id[:] = []
    for dev in developers:
        dev_obj = Users.query.filter_by(id=dev).first()
        project_obj.tm_developer_id.append(dev_obj)
    for qa in qas:
        qa_obj = Qa.query.filter_by(id=qa).first()
        project_obj.tm_quality_assurer_id.append(qa_obj)

    new__db.session.commit()


def populate_projects():
    """
    Populates projects model
    """
    old_projects = _Projects.query.all()
    for project in old_projects:
        new_project = Projects()
        new_project.erp_project_id = project.erp_project_id
        new_project.tm_project_name = project.tm_project_name
        new_project.tm_project_status = project.tm_project_status
        developers = [dev.id for dev in project.tm_developer_id]
        qas = [qa.id for qa in project.tm_quality_assurer_id]
        new__db.session.add(new_project)
        new__db.session.commit()
        add_modify_project_api(new_project, developers, qas)

    return Projects.query.count()


def hasNumbers(inputString):
    """

    :param inputString:
    :return:
    """
    return any(char.isdigit() for char in inputString)


def populate_tasks():
    """
    Populates tasks model
    """
    all_tasks = _Tasks.query.all()
    for task in all_tasks:
        new_task = Tasks()
        new_task.tm_task_project_id = task.tm_task_project_id
        new_task.tm_task_title = task.tm_task_title
        new_task.tm_milestone = task.tm_milestone
        new_task.tm_start_date = task.tm_start_date
        new_task.tm_end_date = task.tm_end_date
        try:
            format1 = re.compile("([0-9]+):([0-9]+):([0-9]+)")
            format2 = re.compile("([0-9]+):([0-9]+)")
            format3 = re.compile("([0-9]+)")
            if format1.match(task.tm_estimated_hours):
                new_task.tm_estimated_hours = datetime.strptime(task.tm_estimated_hours, "%H:%M:%S").time()
            elif format2.match(task.tm_estimated_hours):
                new_task.tm_estimated_hours = datetime.strptime(task.tm_estimated_hours, "%H:%M").time()
            elif format3.match(task.tm_estimated_hours):
                new_task.tm_estimated_hours = datetime.strptime(task.tm_estimated_hours, "%H").time()
            else:
                new_task.tm_estimated_hours = datetime.strptime("08:00:00", "%H:%M:%S").time()
        except:
            new_task.tm_estimated_hours = datetime.strptime("08:00:00", "%H:%M:%S").time()
        new_task.tm_qa = task.tm_qa
        new_task.tm_developer = task.tm_developer
        new_task.tm_priority = task.tm_priority
        new_task.tm_type = task.tm_type
        new_task.tm_description = task.tm_description
        new_task.tm_added_on = task.tm_added_on
        new_task.erp_task_status = task.erp_task_status

        new__db.session.add(new_task)
        new__db.session.commit()

    return Tasks.query.count()


reset_new_db()
print "populate_developers()"
total_users = populate_developers()
print "Total Users : " + str(total_users)
print "populate_qa()"
total_qas = populate_qa()
print "Total Qas : " + str(total_qas)
print "populate_milestones()"
total_milestones = populate_milestones()
print "Total Milestones : " + str(total_milestones)
print "populate_projects()"
total_projects = populate_projects()
print "Total Projects : " + str(total_projects)
print "populate_tasks()"
total_tasks = populate_tasks()
print "Total Tasks : " + str(total_tasks)
