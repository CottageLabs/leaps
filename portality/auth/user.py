from portality.core import app

from flask import request


# used in account management to check if logged in user can edit user details
def update(obj,user):
    if obj.__type__ == 'account':
        if do_admin(user):
            return True
        else:
            return not user.is_anonymous() and user.id == obj.id
    else:
        return False


# if super user, can do anything. Only available via app settings
def is_super(user):
    return not user.is_anonymous() and user.id in app.config['SUPER_USER']


# a user that can login to the admin interface and do anything
# except create new accounts or alter app settings
def do_admin(user):
    if user.data.get('do_admin',False):
        return True
    else:
        return is_super(user)


# a user that can login to the admin area and edit students
def edit_students(user):
    if user.data.get('edit_students',False) or user.data.get('do_admin',False):
        return True
    else:
        return is_super(user)

# a user that can login to the admin area and view all content
def view_admin(user):
    if user.data.get('view_admin',False) or user.data.get('perform_and_manage_interviewers',False) or user.data.get('edit_students',False) or user.data.get('do_admin',False):
        return True
    else:
        return is_super(user)


# a user associated to an institution, who can see relevant students and submit PAEs
def is_institution(user):
    if user.data.get('institution',False):
        return user.data['institution']
    elif view_admin(user) and request.values.get('institution',False):
        return request.values['institution']
    else:
        return view_admin(user)


# a user associated to a school, who can see students of that school in the schools list
def is_school(user):
    if user.data.get('school',False):
        return user.data['school']
    elif view_admin(user) and request.values.get('school',False):
        return request.values['school']
    else:
        return view_admin(user)

# a user that can be assigned to interviews, who can see students assigned to them for interview
def perform_interviews(user):
    if user.data.get('perform_interviews',False) or user.data.get('perform_and_manage_interviewers',False):
        return user.data['id']
    elif view_admin(user) and request.values.get('interviewer',False):
        return request.values['interviewer']
    else:
        return view_admin(user)

def perform_and_manage_interviewers(user):
    if user.data.get('perform_and_manage_interviewers',False):
        return user.data['id']
    elif view_admin(user) and request.values.get('interviewer',False):
        return request.values['interviewer']
    else:
        return view_admin(user)


