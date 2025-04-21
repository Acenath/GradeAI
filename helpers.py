import datetime

def is_teacher(cursor, email):
    cursor.execute(''' SELECT role FROM Users WHERE email = %s ''', (email))
    role_tuple = cursor.fetchall()
    return role_tuple[0][0] == 1

def register_positive(cursor, email, user_id):
    cursor.execute(''' SELECT * FROM Users WHERE email = %s OR user_id = %s ''', (email, user_id))
    user_tuple = cursor.fetchall()

    if user_tuple:
        return False
    
    return True

def check_user_exist(cursor, email, password):
    cursor.execute(''' SELECT * FROM Users WHERE email = %s and password = %s''', (email, password))
    user_tuple = cursor.fetchall()

    if user_tuple:
        return True
    
    return False

def add_user(cursor, email, first_name, last_name, user_id, password):
    role = 1
    cursor.execute(''' INSERT INTO Users (user_id, email, password, first_name, last_name, role, profile_picture_url, created_at, last_login)
                   VALUE(%s, %s, %s, %s, %s, %s, %s, %s, %s) ''', (15, email, password, first_name, last_name, role, "bubirurldir", datetime.datetime.now(), datetime.datetime.now()))