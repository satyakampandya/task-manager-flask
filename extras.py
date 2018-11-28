# coding=utf-8
"""
Contains essential methods for Task Manager
"""
import calendar
import os
import zipfile
from datetime import datetime, timedelta

import xlwt
from PIL import Image, ImageDraw, ImageFont

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
dp_target = os.path.join(APP_ROOT, 'static/images/user_images/')
font_target = os.path.join(APP_ROOT, 'static/fonts/DP_FONT.ttf')

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
target_save_path = os.path.join(APP_ROOT, 'xls_data/')


def get_str(_string):
    """
    Converts unicode to str
    :param _string:
    """
    if isinstance(_string, str):
        return _string.encode('utf-8')
    else:
        return unicode(_string).encode('utf-8')


def set_headers(ws):
    """
    Sets headers in XLS file
    """
    style = xlwt.easyxf(
        'font: bold on; pattern: pattern solid, fore_colour blue')
    ws.write(0, 0, "Task_Title", style)
    ws.write(0, 1, "Milestone", style)
    ws.write(0, 2, "Start_Date (DD/MM/YYYY)", style)
    ws.write(0, 3, "End_Date (DD/MM/YYYY)", style)
    ws.write(0, 4, "Estimated_Hours (HH:MM:SS)", style)
    ws.write(0, 5, "QA", style)
    ws.write(0, 6, "Developer", style)
    ws.write(0, 7, "Priority", style)
    ws.write(0, 8, "Type", style)
    ws.write(0, 9, "Description", style)


def fill_xls(ws, row, task_title, milestone, start_date, end_date, estimated_hours, qa, _developer, priority, _type,
             description):
    """
    For filling up XLS file
    """
    ws.write(row, 0, task_title)
    ws.write(row, 1, milestone)
    ws.write(row, 2, start_date)
    ws.write(row, 3, end_date)
    ws.write(row, 4, estimated_hours)
    ws.write(row, 5, qa)
    ws.write(row, 6, _developer)
    ws.write(row, 7, priority)
    ws.write(row, 8, _type)
    ws.col(9).width = 100 * 256
    ws.write(row, 9, description.encode('utf-8').replace("\r\n", "").strip())


def generate_xls(tasks, action, folder, project=None):
    """

    :param project:
    :param folder:
    :param tasks:
    :param action:
        date-wise : 0
        developer-wise : 1
        project-wise : 2
        merged : 3
        all_of_day : 4
    :return:
    """
    wb = xlwt.Workbook(encoding='utf-8')
    ws = wb.add_sheet('Sheet1')
    set_headers(ws)
    row = 0
    for task in tasks:
        if task.tm_qa:
            qa = task.relative_qa.erp_user_name
        else:
            qa = ""
        row = row + 1

        fill_xls(ws, row,
                 task.tm_task_title,
                 task.relative_milestone.tm_milestone_name,
                 '{0.day:02d}/{0.month:02d}/{0.year:4d}'.format(task.tm_start_date),
                 '{0.day:02d}/{0.month:02d}/{0.year:4d}'.format(task.tm_end_date),
                 task.tm_estimated_hours.strftime("%H:%M:%S"),
                 qa,
                 task.relative_developer.erp_user_name,
                 task.tm_priority.capitalize(),
                 task.tm_type.capitalize(),
                 task.tm_description)
    if not os.path.exists(target_save_path):
        os.makedirs(target_save_path)
    filename = 'download'
    if action == 0:
        filename = str('{0.day:02d}_{0.month:02d}_{0.year:4d}'.format(tasks[0].tm_added_on))
    elif action == 1:
        filename = str(tasks[0].relative_developer.erp_user_name.replace(' ', '_') +
                       '_{0.day:02d}_{0.month:02d}_{0.year:4d}'.format(tasks[0].tm_added_on) + str(project))
    elif action == 2:
        filename = str(tasks[0].relative_project.erp_project_id)
    elif action == 3:
        filename = 'Merged_tasks_' + str('{0.day:02d}_{0.month:02d}_{0.year:4d}'.format(datetime.now().date()))
    save_xls = target_save_path + folder + '/'
    path = save_xls + filename + '.xls'
    wb.save(path)
    return path


def get_next_date():
    """
    It returns next working date
    """
    today_date = datetime.now()
    weekday = calendar.day_name[today_date.weekday()]
    if weekday == 'Friday':
        next_date = today_date + timedelta(days=3)
    else:
        next_date = today_date + timedelta(days=1)
    return next_date.date()


def generate_zip(zip_name, user_folder):
    """

    :param zip_name:
    :param user_folder:
    :return:
    """
    zf = zipfile.ZipFile("zip_data/" + user_folder + zip_name + '.zip', "w")
    for dirname, subdirs, files in os.walk("xls_data/" + user_folder):
        for filename in files:
            zf.write(os.path.join(dirname, filename))
    zf.close()
    return zf.filename


def generate_dp(username, user_id):
    """
    Generates dp
    """
    # for display picture icon
    if not os.path.exists(dp_target):
        os.makedirs(dp_target)

    if username.split(" ")[1]:
        name = username.split(" ")[0][0].upper() + username.split(" ")[1][0].upper()
    else:
        name = " " + username.split(" ")[0].upper()

    w, h = (460, 460)
    color = (255, 188, 22)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)

    if ("MW" == name) or ("WM" == name):
        w_h = ((w - 800 / 2) / 2, (h - 920 / 2) / 2)
    elif any(i in name for i in 'MW'):
        w_h = ((w - 650 / 2) / 2, (h - 920 / 2) / 2)
    else:
        w_h = ((w - 516 / 2) / 2, (h - 920 / 2) / 2)

    if os.path.isfile(font_target):
        font = ImageFont.truetype("static/fonts/DP_FONT.ttf", 250)
        draw.text(w_h, name, fill=color, font=font)
    else:
        draw.text(w_h, name, fill=color)

    filename = dp_target + str(user_id) + ".png"
    im.save(filename, "PNG")
