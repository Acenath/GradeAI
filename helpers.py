import datetime
from hashlib import sha256
import csv

def zip_to_rubric(cursor, zip_rubric, user_id, class_id, assignment_title):
    for fold, (rubric_desc, rubric_val) in enumerate(zip_rubric):
        create_rubric(cursor, f"rubric_{fold}", rubric_val, rubric_desc, user_id, class_id, assignment_title)

def create_rubric(cursor, name, score, description, created_by, class_id, assignment_title):
    cursor.execute('''INSERT INTO Rubric (rubric_id, name, score, description, created_at, created_by)
                   VALUES (%s, %s, %s, %s, %s, %s)''', (f"{class_id}_{assignment_title}", name, score, description, datetime.datetime.now(), created_by))

def create_assignment(cursor, assignment_title, assignment_desc, assignment_deadline, class_id, total_score):
    assignment_id = f"{class_id}_{assignment_title}"
    cursor.execute(''' INSERT INTO Assignment (assignment_id, title, description, deadline, class_id, total_score) 
                   VALUES (%s, %s, %s, %s, %s, %s)''', (assignment_id, assignment_title, assignment_desc, assignment_deadline, class_id, total_score))

def fetch_classes(cursor, user_id):
    cursor.execute("SELECT * FROM Class WHERE teacher_id = %s", (user_id,))
    courses = cursor.fetchall()
    return courses

def enroll_students(cursor, student_id, class_id):
    cursor.execute(''' INSERT INTO Enrollment (enrollment_id, enrolled_at, class_id, student_id)
                           VALUES (%s, %s, %s, %s)''', (f"{class_id}_{student_id}",datetime.datetime.now(), class_id, student_id))

def csv_to_enroll(cursor, student_csv_file, class_id):
    with open(student_csv_file, "r") as f:
        student_rows = csv.reader(f)
        for row in student_rows:
            student_id = row[0]
            if register_positive(cursor, "_", student_id):
                enroll_students(cursor, student_id, class_id)            

def create_class(cursor, course_code, course_name, teacher_id):
    cursor.execute('''INSERT INTO Class (class_id, name, created_at, teacher_id) 
                   VALUES (%s, %s, %s, %s)''', (course_code, course_name, datetime.datetime.now(), teacher_id))
    
def hash_password(password):
    return sha256(password.encode("utf-8")).hexdigest()

def role_parser(email): 
    return email.split("@")[1].split(".")[0][-1: -3: -1] == "nu" # its "un" actually but in reverse you can add [::-1] to make it normal
    
def register_positive(cursor, email, user_id):
    cursor.execute(''' SELECT * FROM Users WHERE email = %s OR user_id = %s ''', (email, user_id))
    user_tuple = cursor.fetchall()

    if user_tuple:
        return False
    
    return True

def update_last_login(cursor, email, password):
    cursor.execute(''' UPDATE Users SET last_login = %s WHERE email = %s and password = %s ''', (datetime.datetime.now(), email, hash_password(password)))

def fetch_user(cursor, email, password):
    cursor.execute(''' SELECT * FROM Users WHERE email = %s and password = %s''', (email, hash_password((password))))
    user_tuple = cursor.fetchall()
    return user_tuple

def add_user(cursor, email, first_name, last_name, user_id, password):
    role = role_parser(email)
    cursor.execute(''' INSERT INTO Users (user_id, email, password, first_name, last_name, role, profile_picture_url, created_at, last_login)
                   VALUE(%s, %s, %s, %s, %s, %s, NULL, %s, NULL) ''', (user_id, email, hash_password(password), first_name, last_name, role, datetime.datetime.now()))