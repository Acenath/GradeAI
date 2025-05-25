import datetime
from hashlib import sha256
import csv
import os
import json
from collections import defaultdict
from flask_mail import Mail
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename
from flask import flash, jsonify

from main import gradeai_db, app

#VARIABLES
STUDENT_LIST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "csv_files", "student_list.csv")
ASSIGNMENT_FILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "uploads", "assignments")
ANNOUNCEMENT_FILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "uploads", "announcements")
ASSIGNMENT_SUBMISSIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "uploads", "submissions")
#FUNCTIONS

def change_password(cursor, user_id, new_password):
    hashed_password = hash_password(new_password)
    cursor.execute("UPDATE users SET password = %s WHERE user_id = %s", (hashed_password, user_id))


def save_files(assignment_files, course_id, assignment_title):
    # Create the directory path
    assignment_dir = os.path.join(ASSIGNMENT_FILES_DIR, course_id, assignment_title)
    os.makedirs(assignment_dir, exist_ok=True)
    
    # Save each file
    for course_file in assignment_files:
        if course_file and course_file.filename:
            filename = secure_filename(course_file.filename)
            file_path = os.path.join(assignment_dir, filename)
            course_file.save(file_path)

def save_announcement(announcement_files, course_id, announcement_title):
    announcement_dir = os.path.join(ANNOUNCEMENT_FILES_DIR, str(course_id), announcement_title)
    os.makedirs(announcement_dir, exist_ok=True)

    for f in announcement_files:
        if f and f.filename:
            filename = secure_filename(f.filename)
            file_path = os.path.join(announcement_dir, filename)
            f.save(file_path)


def save_submissions(assignment_files, course_id, assignment_title):
    assignment_dir = os.path.join(ASSIGNMENT_SUBMISSIONS_DIR, course_id, assignment_title)
    os.makedirs(assignment_dir, exist_ok=True)
    for course_file in assignment_files:
        if course_file and course_file.filename:
            filename = secure_filename(course_file.filename)
            file_path = os.path.join(assignment_dir, filename)
            course_file.save(file_path)

def handle_class_creation(cursor, course_code, course_name, teacher_id):
    cursor.execute("SELECT * FROM class WHERE class_id = %s", (course_code,))
    existing_class = cursor.fetchone()
    
    if not existing_class:
        create_class(cursor, course_code, course_name, teacher_id)
        return True
    return False

def handle_student_enrollment(cursor, students_data, course_code):
    try:
        students_list = json.loads(students_data)
    except json.JSONDecodeError:
        flash("Invalid student data format", "error")
        return {'success': False}
    
    results = {
        'success': [],
        'already_enrolled': [],
        'not_found': []
    }
    
    for student_id in students_list:
        if not student_id.strip():
            continue
            
        # First check if student exists in the system
        cursor.execute(''' SELECT * FROM users WHERE user_id = %s ''', (student_id,))
        student_exists = cursor.fetchone()
        
        if not student_exists:
            results['not_found'].append(student_id)
            continue
            
        # Then check if already enrolled
        if is_student_enrolled(cursor, student_id, course_code):
            results['already_enrolled'].append(student_id)
        else:
            enroll_students(cursor, student_id, course_code)
            results['success'].append(student_id)
    
    # Flash messages based on results
    if results['success']:
        flash(f"{len(results['success'])} students added successfully.", "success")
    if results['already_enrolled']:
        flash(f"{len(results['already_enrolled'])} students were already enrolled.", "warning")
    if results['not_found']:
        flash(f"{len(results['not_found'])} students not found in system.", "error")
    
    return results


def handle_student_removal(cursor, deleted_students, course_code):
    try:
        deleted_list = json.loads(deleted_students)
    except json.JSONDecodeError:
        return []
    
    removed_students = []
    
    for student_id in deleted_list:
        if is_student_enrolled(cursor, student_id, course_code):
            remove_student(cursor, student_id, course_code)
            removed_students.append(student_id)
    
    return removed_students

def save_and_process_csv(cursor, csv_file, class_id):

    csv_dir = os.path.dirname(STUDENT_LIST_DIR)
    os.makedirs(csv_dir, exist_ok=True)
    filename = secure_filename(csv_file.filename)
    save_path = os.path.join(csv_dir, filename)
    csv_file.save(save_path)
    
    result = {
        'success': False,
        'added': 0,
        'existing': 0,
        'not_found': 0,
        'students': []  # List to store student info for display
    }
    
    try:
        with open(save_path, 'r+') as f:
            csv_reader = csv.reader(f)
            for row in csv_reader:
                print(row)
                if not row or not row[0].strip():  # skip empty rows
                    continue
                
                student_id = row[0].strip()
                print(student_id)
                # First check if student exists in the system
                cursor.execute(''' 
                    SELECT user_id, first_name, last_name 
                    FROM users 
                    WHERE user_id = %s
                ''', (student_id,))
                student = cursor.fetchone()
                
                if not student:
                    result['not_found'] += 1
                    result['students'].append({
                        'id': student_id,
                        'name': 'Not in system',
                        'status': 'not_found'
                    })
                    continue
                
                # Then check if student is already enrolled
                if is_student_enrolled(cursor, student_id, class_id):
                    result['existing'] += 1
                    result['students'].append({
                        'id': student_id,
                        'name': f"{student[1]} {student[2]}",
                        'status': 'existing'
                    })
                else:
                    enroll_students(cursor, student_id, class_id)
                    result['added'] += 1
                    result['success'] = True
                    result['students'].append({
                        'id': student_id,
                        'name': f"{student[1]} {student[2]}",
                        'status': 'added'
                    })
        
        if os.path.exists(save_path):
            os.remove(save_path)
        return result
    except Exception as e:
        print(f"Error processing CSV: {e}")
        if os.path.exists(save_path):
            os.remove(save_path)
        return {'success': False}

def is_student_enrolled(cursor, student_id, class_id):
    cursor.execute(''' SELECT * FROM enrollment WHERE student_id = %s AND class_id = %s ''', (student_id, class_id))
    enrollment_tuple = cursor.fetchall()
    if enrollment_tuple:
        return True
    return False

def remove_student(cursor, student_id, class_id):
    cursor.execute(''' DELETE FROM enrollment WHERE student_id = %s AND class_id = %s ''', (student_id, class_id))

def zip_to_rubric(cursor, zip_rubric, user_id, class_id, assignment_title, assignment_id):
    for fold, (rubric_desc, rubric_val) in enumerate(zip_rubric):
        create_rubric(cursor, rubric_val, rubric_desc, user_id, class_id, assignment_id, assignment_title, fold)

def create_rubric(cursor, score, description, created_by, class_id, assignment_id, assignment_title, fold):
    # First check if rubric exists
    cursor.execute('''SELECT rubric_id FROM rubric WHERE rubric_id = %s''', (f"{class_id}_{assignment_title}_{fold}",))
    existing_rubric = cursor.fetchone()
    
    if existing_rubric:
        # Update existing rubric
        cursor.execute('''
            UPDATE rubric 
            SET name = %s, score = %s, description = %s, created_at = %s, created_by = %s
            WHERE rubric_id = %s
        ''', ( f"{class_id}_{assignment_title}_{fold}", assignment_id, score, description, datetime.datetime.now(), created_by, ))
    else:
        # Insert new rubric
        cursor.execute('''
            INSERT INTO rubric (rubric_id, assignment_id, score, description, created_at, created_by)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (f"{class_id}_{assignment_title}_{fold}", assignment_id, score, description, datetime.datetime.now(), created_by, ))

def create_assignment(cursor, assignment_title, assignment_desc, assignment_deadline, class_id, total_score):
    assignment_id = f"{class_id}_{assignment_title}"
    cursor.execute(''' INSERT INTO assignment (assignment_id, title, description, deadline, class_id, total_score) 
                   VALUES (%s, %s, %s, %s, %s, %s)''', (assignment_id, assignment_title, assignment_desc, assignment_deadline, class_id, total_score))
    return assignment_id

def fetch_classes(cursor, user_id):
    cursor.execute("SELECT * FROM class WHERE teacher_id = %s", (user_id,))
    courses = cursor.fetchall()
    return courses

def fetch_profile_picture(cursor, user_id):
    cursor.execute("SELECT profile_picture_url FROM users WHERE user_id = %s", (user_id,))
    result = cursor.fetchone()
    return result[0] if result else None

def enroll_students(cursor, student_id, class_id):
    cursor.execute(''' INSERT INTO enrollment (enrollment_id, enrolled_at, class_id, student_id)
                           VALUES (%s, %s, %s, %s)''', (f"{class_id}_{student_id}",datetime.datetime.now(), class_id, student_id))     

def create_class(cursor, course_code, course_name, teacher_id):
    cursor.execute('''INSERT INTO class (class_id, name, created_at, teacher_id) 
                   VALUES (%s, %s, %s, %s)''', (course_code, course_name, datetime.datetime.now(), teacher_id))
    
def hash_password(password):
    return sha256(password.encode("utf-8")).hexdigest()

def role_parser(email): 
    return email.split("@")[1].split(".")[0][-1: -3: -1] == "nu" # its "un" actually but in reverse you can add [::-1] to make it normal
    
def register_positive(cursor, email, user_id):
    cursor.execute(''' SELECT * FROM users WHERE email = %s OR user_id = %s ''', (email, user_id))
    user_tuple = cursor.fetchall()

    if user_tuple:
        return False
    
    return True

def update_last_login(cursor, email, password):
    cursor.execute(''' UPDATE users SET last_login = %s WHERE email = %s and password = %s ''', (datetime.datetime.now(), email, hash_password(password)))

def fetch_user(cursor, email, password):
    cursor.execute(''' SELECT * FROM users WHERE email = %s and password = %s''', (email, hash_password((password))))
    user_tuple = cursor.fetchall()
    return user_tuple

def add_user(cursor, email, first_name, last_name, user_id, password):
    role = role_parser(email)
    cursor.execute(''' INSERT INTO users (user_id, email, password, first_name, last_name, role, profile_picture_url, created_at, last_login)
                   VALUE(%s, %s, %s, %s, %s, %s, NULL, %s, NULL) ''', (user_id, email, hash_password(password), first_name, last_name, role, datetime.datetime.now()))

def fetch_feedbacks_by_teacher(cursor, teacher_id):
        query = """
            SELECT 
                a.title AS assignment_title,
                CONCAT(u.first_name, ' ', u.last_name) AS student_name,
                s.submitted_at AS submission_date,
                g.feedback
            FROM grade g
            INNER JOIN submission s ON g.submission_id = s.submission_id
            INNER JOIN assignment a ON s.assignment_id = a.assignment_id
            INNER JOIN users u ON s.student_id = u.user_id
            WHERE a.class_id IN (
                SELECT class_id FROM class WHERE teacher_id = %s
            )
            ORDER BY s.submitted_at DESC
        """
        cursor.execute(query, (teacher_id,))
        return cursor.fetchall()

def fetch_student_info(cursor, student_id):
    cursor.execute("""SELECT first_name, last_name FROM users WHERE user_id = %s""", (student_id.split(",")[0],))
    student = cursor.fetchone()
    print(student)
    if student:
        return {
            'success': True,
            'first_name': student[0],
            'last_name': student[1]
        }
    return {
        'success': False,
        'first_name': None,
        'last_name': None,
        'message': 'Student not found'
    }

def get_enrolled_students(cursor, class_id):
    cursor.execute("""
        SELECT u.user_id, u.first_name, u.last_name 
        FROM users u 
        INNER JOIN enrollment e ON u.user_id = e.student_id 
        WHERE e.class_id = %s
        ORDER BY u.first_name, u.last_name
    """, (class_id,))
    return cursor.fetchall()

def get_course_name(cursor, course_code):
    cursor.execute("SELECT name FROM class WHERE class_id = %s", (course_code,))
    return cursor.fetchone()

def get_course_assignments(cursor, course_code):
    cursor.execute("""
        SELECT 
            a.assignment_id,
            a.title,
            a.description,
            a.deadline,
            a.total_score,
            COUNT(DISTINCT s.submission_id) as submission_count,
            COUNT(DISTINCT g.grade_id) as graded_count
        FROM assignment a
        LEFT JOIN submission s ON a.assignment_id = s.assignment_id
        LEFT JOIN grade g ON s.submission_id = g.grade_id
        WHERE a.class_id = %s
        GROUP BY a.assignment_id
        ORDER BY a.deadline DESC
    """, (course_code,))
    return cursor.fetchall()

def get_assignment_details(cursor, assignment_id, course_code):
    cursor.execute("""
        SELECT a.title, a.description, a.deadline, a.total_score, c.name as course_name
        FROM assignment a
        JOIN class c ON a.class_id = c.class_id
        WHERE a.assignment_id = %s AND a.class_id = %s
    """, (assignment_id, course_code))
    return cursor.fetchone()

def get_assignment_files(course_code, assignment_title):
    assignment_files = []
    assignment_dir = os.path.join(ASSIGNMENT_FILES_DIR, course_code, assignment_title)
    if os.path.exists(assignment_dir):
        assignment_files = [f for f in os.listdir(assignment_dir) if os.path.isfile(os.path.join(assignment_dir, f))]
    return assignment_files

def get_student_submissions(cursor, assignment_id, course_code):
    cursor.execute("""
        SELECT 
            u.first_name, u.last_name, u.user_id,
            s.submission_id, s.submitted_at,
            g.score, g.feedback
        FROM users u
        LEFT JOIN submission s ON u.user_id = s.student_id AND s.assignment_id = %s
        LEFT JOIN grade g ON s.submission_id = g.submission_id
        WHERE u.user_id IN (
            SELECT student_id FROM enrollment WHERE class_id = %s
        )
        GROUP BY u.user_id
        ORDER BY u.first_name, u.last_name
    """, (assignment_id, course_code))
    return cursor.fetchall()

def get_submission_details(cursor, submission_id, course_code):
    cursor.execute("""
        SELECT 
            s.submitted_at,
            g.score,
            g.feedback,
            u.first_name,
            u.last_name,
            u.user_id,
            a.title as assignment_title,
            c.name as course_name
        FROM submission s
        JOIN users u ON s.student_id = u.user_id
        JOIN assignment a ON s.assignment_id = a.assignment_id
        JOIN class c ON a.class_id = c.class_id
        LEFT JOIN grade g ON s.submission_id = g.submission_id
        WHERE s.submission_id = %s AND a.class_id = %s
    """, (submission_id, course_code))
    return cursor.fetchone()

def get_submission_for_grading(cursor, submission_id, course_code):
    cursor.execute("""
        SELECT 
            s.submitted_at,
            g.score,
            g.feedback,
            u.first_name,
            u.last_name,
            u.user_id,
            a.title as assignment_title,
            a.total_score,
            c.name as course_name
        FROM submission s
        JOIN users u ON s.student_id = u.user_id
        JOIN assignment a ON s.assignment_id = a.assignment_id
        JOIN class c ON a.class_id = c.class_id
        LEFT JOIN grade g ON s.submission_id = g.submission_id
        WHERE s.submission_id = %s AND a.class_id = %s
    """, (submission_id, course_code))
    return cursor.fetchone()

def get_assignment_total_score(cursor, assignment_id):
    cursor.execute("""
        SELECT total_score
        FROM assignment
        WHERE assignment_id = %s
    """, (assignment_id,))
    return cursor.fetchone()[0]

def check_existing_grade(cursor, submission_id):
    cursor.execute("""
        SELECT grade_id
        FROM grade
        WHERE submission_id = %s
    """, (submission_id,))
    return cursor.fetchone()

def update_grade(cursor, submission_id, score, feedback):
    cursor.execute("""
        UPDATE Grade
        SET score = %s, feedback = %s
        WHERE submission_id = %s
    """, (score, feedback, submission_id))

def insert_grade(cursor, submission_id, score, feedback):
    cursor.execute("""
        INSERT INTO grade (submission_id, score, feedback, created_at)
        VALUES (%s, %s, %s, %s)
    """, (submission_id, score, feedback, datetime.datetime.now()))

'''def ensure_grade_created_at_exists(cursor):
    """Ensure the Grade table has a created_at column"""
    try:
        # Check if the column exists
        cursor.execute("SHOW COLUMNS FROM Grade LIKE 'created_at'")
        result = cursor.fetchone()
        
        if not result:
            # Add the column if it doesn't exist
            cursor.execute("""
                ALTER TABLE Grade 
                ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            """)
            return True
        return False
    except Exception as e:
        print(f"Error checking/adding created_at column: {e}")
        return False'''


def fetch_upcoming_deadlines(cursor, user_id, is_teacher, limit=5):
    """Fetch upcoming assignment deadlines for the teacher's courses"""
    if is_teacher:
        cursor.execute("""
            SELECT 
                a.assignment_id,
                a.title,
                a.deadline,
                c.class_id,
                c.name AS course_name
            FROM assignment a
            JOIN class c ON a.class_id = c.class_id
            WHERE c.teacher_id = %s
            AND a.deadline >= CURDATE()
            ORDER BY a.deadline ASC
            LIMIT %s
        """, (user_id, limit))

    elif not is_teacher:
        cursor.execute('''SELECT a.assignment_id, a.title, a.deadline, a.class_id, c.name
                       FROM enrollment as e NATURAL JOIN assignment as a NATURAL JOIN class as c  
                       WHERE e.student_id = %s AND a.deadline >= CURDATE()
                       ORDER BY a.deadline ASC
                       LIMIT %s''', (user_id, limit))
        
    return cursor.fetchall()

def fetch_recent_feedback(cursor, user_id, is_teacher, limit=5):
    """Fetch recent feedback given by the teacher"""
    if is_teacher:
        cursor.execute("""
            SELECT 
                g.grade_id,
                g.feedback,
                g.score,
                u.first_name,
                u.last_name,
                a.title AS assignment_title,
                s.submitted_at
            FROM grade g
            JOIN submission s ON g.submission_id = s.submission_id
            JOIN assignment a ON s.assignment_id = a.assignment_id
            JOIN class c ON a.class_id = c.class_id
            JOIN users u ON s.student_id = u.user_id
            WHERE c.teacher_id = %s
            ORDER BY s.submitted_at DESC
            LIMIT %s
        """, (user_id, limit))

    elif not is_teacher:
        cursor.execute(''' SELECT g.grade_id, g.feedback, g.score, u.first_name, u.last_name, a.title, s.submitted_at 
                       FROM submission as s NATURAL JOIN grade as g
                       JOIN assignment as a ON a.assignment_id = s.assignment_id
                       JOIN class as c ON c.class_id = a.class_id
                       JOIN users as u ON u.user_id = s.student_id 
                       WHERE s.student_id = %s
                       ORDER BY s.submitted_at DESC
                       LIMIT %s ''', (user_id, limit))
    return cursor.fetchall()

def fetch_recent_announcements(cursor, user_id, is_teacher, limit=5):
    """Fetch recent announcements made by the teacher"""
    if is_teacher:
        cursor.execute("""
            SELECT 
                a.announcement_id,
                a.content,
                a.posted_at,
                c.class_id,
                c.name AS course_name
            FROM announcement a
            JOIN class c ON a.class_id = c.class_id
            WHERE c.teacher_id = %s
            ORDER BY a.posted_at DESC
            LIMIT %s
        """, (user_id, limit))

    elif not is_teacher:
        cursor.execute(''' SELECT * 
                       FROM enrollment as e NATURAL JOIN announcement as a NATURAL JOIN class as c
                       WHERE e.student_id = %s
                       ORDER BY a.posted_at DESC
                       LIMIT %s''', (user_id, limit, ))
        
    return cursor.fetchall()

def fetch_recent_class_announcements(cursor, course_code):
    cursor.execute('''
        SELECT announcement_id, content, posted_at
        FROM announcement
        WHERE class_id = %s
        ORDER BY posted_at DESC
    ''', (course_code,))
    return cursor.fetchall()

def create_announcement(cursor, course_code, title, desc):
    cursor.execute(''' 
            INSERT INTO announcement (announcement_id, class_id, content, posted_at)
            VALUES (%s, %s, %s, %s)
        ''', ("{}_{}".format(course_code, title), course_code, desc, datetime.datetime.now()))      
    
def fetch_enrollments(cursor, user_id):
    cursor.execute(''' SELECT e.class_id, c.teacher_id, c.name  
                   FROM enrollment as e LEFT JOIN class as c ON e.class_id = c.class_id 
                   WHERE e.student_id = %s''', (user_id,))
    return cursor.fetchall()

def total_number_of_students(cursor, course_codes):
    total_student_dict = defaultdict(int)

    for course_code in course_codes:
        cursor.execute(''' SELECT COUNT(DISTINCT(student_id)), class_id FROM enrollment WHERE class_id = %s ''', (course_code, ))
        total_student_tuple = cursor.fetchone()
        total_student_dict[course_code] = total_student_dict.get(course_code, 0) + total_student_tuple[0]

    return total_student_dict
    


def create_notifications_table():
    with app.app_context():
        cursor = gradeai_db.connection.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                notification_id varchar(255) NOT NULL,
                user_id varchar(255) NOT NULL,
                type varchar(50) NOT NULL,
                title varchar(255) NOT NULL,
                message varchar(1000) NOT NULL,
                created_at datetime NOT NULL,
                is_read bit(1) NOT NULL DEFAULT b'0',
                PRIMARY KEY (notification_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=latin1 COLLATE=latin1_swedish_ci
        ''')
        gradeai_db.connection.commit()
        cursor.close()

def create_notification(cursor, user_id, type, title, message):
    notification_id = f"{user_id}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    cursor.execute('''
        INSERT INTO notifications (notification_id, user_id, type, title, message, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
    ''', (notification_id, user_id, type, title, message, datetime.datetime.now()))

def get_student_notifications(cursor, user_id):
    cursor.execute('''
        SELECT notification_id, type, title, message, created_at, is_read
        FROM notifications
        WHERE user_id = %s
        ORDER BY created_at DESC
    ''', (user_id,))
    return cursor.fetchall()

def notify_students_about_announcement(cursor, course_code, title, content):
    # Get all students enrolled in the course
    cursor.execute('''
        SELECT student_id 
        FROM enrollment 
        WHERE class_id = %s
    ''', (course_code,))
    students = cursor.fetchall()
    
    # Create notification for each student
    for student in students:
        create_notification(
            cursor,
            student[0],
            'announcement',
            f'New Announcement: {title}',
            f'A new announcement has been posted in {course_code}: {content[:100]}...'
        )

def notify_students_about_assignment(cursor, course_code, title, deadline):
    # Get all students enrolled in the course
    cursor.execute('''
        SELECT student_id 
        FROM enrollment 
        WHERE class_id = %s
    ''', (course_code,))
    students = cursor.fetchall()
    
    # Create notification for each student
    for student in students:
        create_notification(
            cursor,
            student[0],
            'assignment',
            f'New Assignment: {title}',
            f'A new assignment has been posted in {course_code}. Deadline: {deadline.strftime("%Y-%m-%d %H:%M")}'
        )

def notify_student_about_feedback(cursor, student_id, assignment_title, course_code):
    create_notification(
        cursor,
        student_id,
        'feedback',
        f'Feedback Received: {assignment_title}',
        f'You have received feedback on your submission for {assignment_title} in {course_code}'
    )

def notify_about_deadline(cursor, course_code, assignment_title, deadline):
    # Get all students enrolled in the course
    cursor.execute('''
        SELECT student_id 
        FROM enrollment 
        WHERE class_id = %s
    ''', (course_code,))
    students = cursor.fetchall()
    
    # Create notification for each student
    for student in students:
        create_notification(
            cursor,
            student[0],
            'deadline',
            f'Assignment Deadline: {assignment_title}',
            f'Reminder: {assignment_title} in {course_code} is due in 24 hours'
        )

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
    # Check if the file has an allowed extension
    if '.' not in filename:
        return False
    
    extension = filename.rsplit('.', 1)[1].lower()
    return extension in ALLOWED_EXTENSIONS

def save_profile_picture(cursor, filepath, user_id):
    try:
        # First, get the current profile picture url
        cursor.execute("SELECT profile_picture_url FROM users WHERE user_id = %s", (user_id,))
        result = cursor.fetchone()
        
        if result and result[0]:
            old_filepath = result[0]
            # Delete old file if it exists
            try:
                old_full_path = os.path.join(app.root_path, 'static', old_filepath)
                app.logger.info(f"Attempting to delete old profile picture at: {old_full_path}")
                if os.path.exists(old_full_path):
                    os.remove(old_full_path)
                    app.logger.info(f"Successfully deleted old profile picture")
                else:
                    app.logger.warning(f"Old profile picture not found at: {old_full_path}")
            except Exception as e:
                app.logger.warning(f"Could not delete old profile picture: {str(e)}")
        
        # Verify the new file exists before updating database
        new_full_path = os.path.join(app.root_path, 'static', filepath)
        app.logger.info(f"Checking new profile picture at: {new_full_path}")
        if not os.path.exists(new_full_path):
            app.logger.error(f"New profile picture file not found at: {new_full_path}")
            raise Exception(f"New profile picture file not found at: {new_full_path}")
        
        # Update the database with new filepath
        cursor.execute("UPDATE users SET profile_picture_url = %s WHERE user_id = %s", (filepath, user_id))
        app.logger.info(f"Updated profile picture path in database to: {filepath}")
        
        # Verify the update was successful
        cursor.execute("SELECT profile_picture_url FROM users WHERE user_id = %s", (user_id,))
        updated_path = cursor.fetchone()
        if not updated_path or updated_path[0] != filepath:
            app.logger.error(f"Database update verification failed. Expected: {filepath}, Got: {updated_path[0] if updated_path else 'None'}")
            raise Exception("Database update failed - path mismatch")
            
        app.logger.info("Profile picture update completed successfully")
        return True
    except Exception as e:
        app.logger.error(f"Error saving profile picture: {str(e)}")
        raise e

