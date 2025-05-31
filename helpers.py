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
from classes import (
    SubmissionIDManager, GradeIDManager, AssignmentIDManager, 
    RubricIDManager, AnnouncementIDManager
)


#VARIABLES
ENROLLMENTS_FILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads", "enrollments")
ASSIGNMENT_FILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "uploads", "assignments")
ANNOUNCEMENT_FILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "uploads", "announcements")
ASSIGNMENT_SUBMISSIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "uploads", "submissions")
PROFILE_PICS_DIR = os.path.join('static', 'uploads', 'profile_pics')
ALLOWED_EXTENSIONS = ['png', 'jpg', 'jpeg']

#FUNCTIONS

def calculate_total_sum(array):
    return sum([int(i) for i in array])

def change_password(cursor, user_id, new_password):
    hashed_password = hash_password(new_password)
    cursor.execute("UPDATE users SET password = %s WHERE user_id = %s", (hashed_password, user_id))

def save_files(given_files, section, course_code, title: None):
    intended_dir = ''
    if section == 'announcements':
        intended_dir = os.path.join(ANNOUNCEMENT_FILES_DIR, str(course_code), title)
    elif section == 'assignments':
        intended_dir = os.path.join(ASSIGNMENT_FILES_DIR, str(course_code), title)
    elif section == 'submissions':
        intended_dir = os.path.join(ASSIGNMENT_SUBMISSIONS_DIR, str(course_code), title)
    elif section == 'enrollments':
        intended_dir = os.path.join(ENROLLMENTS_FILES_DIR, str(course_code))

    else:
        return

    os.makedirs(intended_dir, exist_ok=True)

    for f in given_files:
        if f and f.filename:
            filename = secure_filename(f.filename)
            file_path = os.path.join(intended_dir, filename)
            f.save(file_path)

def process_csv(csv_path, course_code):
    student_list = set()
    try:
        with open(os.path.join(ENROLLMENTS_FILES_DIR, course_code), 'r+') as f:
            csv_reader = csv.reader(f)
            for row in csv_reader:
                if not row or not row[0].strip():  # skip empty rows
                    continue
            
                student_id = row[0].strip()
                student_list.add(student_id)
        
        if os.path.exists(csv_path):
            os.remove(csv_path)

        return student_list
    
    except Exception as e:
        print(f"Error processing CSV: {e}")
        if os.path.exists(csv_path):
            os.remove(csv_path)
        return {'success': False}

def handle_class_creation(cursor, course_code, course_name, teacher_id):
    cursor.execute("SELECT * FROM class WHERE class_id = %s", (course_code,))
    existing_class = cursor.fetchone()
    
    if not existing_class:
        create_class(cursor, course_code, course_name, teacher_id)
        return True
    return False

def handle_student_removal(cursor, students_to_remove, course_code):
    """
    Remove students from a course
    
    Args:
        cursor: Database cursor
        students_to_remove: Either a single student ID (string) or list of student IDs
        course_code: Course code string
    
    Returns:
        List of successfully removed student IDs
    """
    removed_students = []
    
    # Convert single student to list for uniform processing
    if isinstance(students_to_remove, str):
        students_list = [students_to_remove]
    elif isinstance(students_to_remove, list):
        students_list = students_to_remove
    else:
        # Handle JSON string from frontend (if any legacy code sends it)
        try:
            students_list = json.loads(students_to_remove)
        except:
            return removed_students
    
    for student_id in students_list:
        if not student_id or not student_id.strip():
            continue
            
        try:
            # Remove student from enrollment table
            cursor.execute("""
                DELETE FROM enrollments 
                WHERE student_id = %s AND course_code = %s
            """, (student_id.strip(), course_code))
            
            # Check if the deletion was successful
            if cursor.rowcount > 0:
                removed_students.append(student_id.strip())
                
        except Exception as e:
            print(f"Error removing student {student_id}: {e}")
            # Continue with other students even if one fails
            continue
    
    return removed_students


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

def create_rubric(cursor, score, description, created_by, assignment_id, fold):
    """Updated create_rubric with proper ID generation"""
    rubric_id = RubricIDManager.create_rubric_id(assignment_id, fold)
    cursor.execute('''
        INSERT INTO rubric (rubric_id, assignment_id, score, description, created_at, created_by)
        VALUES (%s, %s, %s, %s, %s, %s)
    ''', (rubric_id, assignment_id, score, description, datetime.datetime.now(), created_by))

    return rubric_id

def create_assignment(cursor, assignment_title, assignment_desc, assignment_deadline, class_id, total_score):
    """Updated create_assignment with proper ID generation"""
    flag = False
    assignment_id = AssignmentIDManager.create_assignment_id(class_id, assignment_title)
    
    # Check for uniqueness and add timestamp if needed
    cursor.execute("SELECT assignment_id FROM assignment WHERE assignment_id = %s", (assignment_id,))
    if cursor.fetchone():
        timestamp = datetime.datetime.now().strftime("%H%M%S")
        assignment_id = f"{assignment_id}_{timestamp}"
        flag = True
    
    cursor.execute(''' 
        INSERT INTO assignment (assignment_id, title, description, deadline, class_id, total_score) 
        VALUES (%s, %s, %s, %s, %s, %s)
    ''', (assignment_id, assignment_title, assignment_desc, assignment_deadline, class_id, total_score))
    
    return assignment_id, flag

def create_grade_with_proper_id(cursor, submission_id, score, feedback, teacher_id):
    """Helper function to create grade with proper ID"""
    grade_id = GradeIDManager.create_grade_id(submission_id)
    
    cursor.execute("""
        INSERT INTO grade (grade_id, submission_id, score, feedback, teacher_id, adjusted_at, is_adjusted)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (grade_id, submission_id, score, feedback, teacher_id, None, 0))
    
    return grade_id

def create_submission_with_proper_id(cursor, assignment_id, student_id, filename):
    """Helper function to create submission with proper ID"""
    submission_id = SubmissionIDManager.create_submission_id(assignment_id, student_id, filename)
    
    cursor.execute("""
        INSERT INTO submission (submission_id, assignment_id, student_id, submitted_at, status)
        VALUES (%s, %s, %s, NOW(), 1)
    """, (submission_id, assignment_id, student_id))
    
    return submission_id

def fetch_classes(cursor, user_id):
    cursor.execute("SELECT * FROM class WHERE teacher_id = %s", (user_id,))
    courses = cursor.fetchall()
    return courses

def fetch_profile_picture(cursor, user_id):
    # Look for profile picture in the uploads directory
    profile_pics_dir = os.path.join('static', 'uploads', 'profile_pics')
    if os.path.exists(profile_pics_dir):
        # Get all files that start with the user_id
        for filename in os.listdir(profile_pics_dir):
            if filename.startswith(str(user_id)):
                # Return the path relative to the static directory
                return os.path.join('uploads', 'profile_pics', filename).replace('\\', '/')
    return None

def enroll_student(cursor, student_id, class_id):
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
    cursor.execute(''' INSERT INTO users (user_id, email, password, first_name, last_name, role, created_at, last_login)
                   VALUE(%s, %s, %s, %s, %s, %s, %s, NULL) ''', (user_id, email, hash_password(password), first_name, last_name, role, datetime.datetime.now()))

def fetch_feedbacks_by_teacher(cursor, teacher_id):
    query = """
        SELECT 
            a.title AS assignment_title,
            CONCAT(u.first_name, ' ', u.last_name) AS student_name,
            s.submitted_at AS submission_date,
            g.feedback,
            a.assignment_id,
            s.submission_id,
            u.user_id
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

def get_student_submissions(cursor, user_id, assignment_id):
    cursor.execute(""" 
                    SELECT submission_id FROM submission 
                    WHERE student_id = %s AND assignment_id = %s
                    """, (user_id, assignment_id,))
    
    return cursor.fetchall()

def get_assignment_details(cursor, assignment_id, course_code: None):
    if not course_code:
        cursor.execute(""" 
        SELECT *
        FROM assignment a
        WHERE a.assignment_id = %s
                    """, (assignment_id, ))
    else:
        cursor.execute("""
            SELECT a.title, a.description, a.deadline, a.total_score, c.name as course_name
            FROM assignment a
            JOIN class c ON a.class_id = c.class_id
            WHERE a.assignment_id = %s AND a.class_id = %s
        """, (assignment_id, course_code))

    return cursor.fetchone()

def get_files(section, course_code, title):
    attachments = []
    intended_dir = ''
    if section == 'assingment':
        intended_dir = os.path.join(ASSIGNMENT_FILES_DIR, course_code, title)
    elif section == 'submission':
        intended_dir = os.path.join(ASSIGNMENT_SUBMISSIONS_DIR, course_code, title)
    elif section == 'announcement':
        intended_dir = os.path.join(ASSIGNMENT_FILES_DIR, 'announcements', course_code, title)
        # Create directory if it doesn't exist
        os.makedirs(intended_dir, exist_ok=True)

    if os.path.exists(intended_dir):
        attachments = [f for f in os.listdir(intended_dir) if os.path.isfile(os.path.join(intended_dir, f))]
    return attachments

def get_students_submissions(cursor, assignment_id, course_code):
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

def get_user_info(cursor, user_id):
    cursor.execute(""" SELECT * FROM users WHERE user_id = %s""", (user_id,))
    return cursor.fetchone()



def get_grade_details(cursor, submission_id, course_code):
    cursor.execute("""
        SELECT * 
        FROM grade 
        WHERE submission_id = %s
    """, (submission_id,))
    return cursor.fetchone()


def get_rubrics(cursor, assignment_id):
    cursor.execute(""" SELECT * FROM rubric WHERE assignment_id = %s""", (assignment_id,))
    return cursor.fetchall()

def get_submission_details(cursor, submission_id):
    cursor.execute("""
    SELECT
        s.submitted_at,
        g.score,
        g.feedback,
        u.first_name,
        u.last_name,
        u.user_id,
        a.title as assignment_title,
        c.class_id,
        a.assignment_id
    FROM submission s
    JOIN users u ON s.student_id = u.user_id
    JOIN assignment a ON s.assignment_id = a.assignment_id
    LEFT JOIN grade g ON s.submission_id = g.submission_id
    LEFT JOIN enrollment e ON e.student_id = u.user_id
    LEFT JOIN class c ON e.class_id = c.class_id
    WHERE s.submission_id = %s
    """, (submission_id,))
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

def update_grade_db(cursor, submission_id, score, feedback):
    cursor.execute("""
        UPDATE grade
        SET score = %s, feedback = %s, adjusted_at = %s, is_adjusted = %s
        WHERE submission_id = %s
    """, (score, feedback, datetime.datetime.now(), 1, submission_id))


def delete_grade(cursor, grade_id):
        cursor.execute('''
                    DELETE FROM grade
                   WHERE grade_id = %s
                   ''', (grade_id, ))
 

def delete_submissions(cursor, user_id, assignment_id):
    cursor.execute('''
        DELETE FROM submission 
        WHERE student_id = %s AND assignment_id = %s
    ''', (user_id, assignment_id, ))

def delete_submission(cursor, submission_id):
    cursor.execute('''
                DELETE FROM submission 
                   WHERE submission_id = %s
                   ''', (submission_id, ))

def delete_announcement(cursor, announcement_id):
    try:
        cursor.execute('''
        DELETE FROM announcement
        WHERE announcement_id = %s
        ''', (announcement_id, ))
        return True
    
    except:
        return False

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
                s.submitted_at,
                c.class_id,
                c.name AS class_name
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
        cursor.execute('''
            SELECT 
                g.grade_id, 
                g.feedback, 
                g.score, 
                u.first_name, 
                u.last_name, 
                a.title AS assignment_title, 
                s.submitted_at,
                c.class_id,
                c.name AS class_name
            FROM submission as s 
            NATURAL JOIN grade as g
            JOIN assignment as a ON a.assignment_id = s.assignment_id
            JOIN class as c ON c.class_id = a.class_id
            JOIN users as u ON u.user_id = s.student_id 
            WHERE s.student_id = %s
            ORDER BY s.submitted_at DESC
            LIMIT %s
        ''', (user_id, limit))
        
    return cursor.fetchall()

def fetch_announcement_details(cursor, announcement_id):
    cursor.execute("""
        SELECT announcement_id, content, posted_at, title
        FROM announcement
        WHERE announcement_id = %s
    """, (announcement_id,))
    return cursor.fetchone()

def fetch_recent_announcements(cursor, user_id, is_teacher, limit=5):
    """Fetch recent announcements made by the teacher"""
    if is_teacher:
        cursor.execute("""
            SELECT 
                a.announcement_id,
                a.content,
                a.posted_at,
                c.class_id,
                c.name AS course_name,
                a.title
            FROM announcement a
            JOIN class c ON a.class_id = c.class_id
            WHERE c.teacher_id = %s
            ORDER BY a.posted_at DESC
            LIMIT %s
        """, (user_id, limit))

    elif not is_teacher:
        cursor.execute(''' SELECT c.class_id, a.content, a.title, a.posted_at, c.name
                       FROM enrollment as e NATURAL JOIN announcement as a NATURAL JOIN class as c
                       WHERE e.student_id = %s
                       ORDER BY a.posted_at DESC
                       LIMIT %s''', (user_id, limit, ))
        
    return cursor.fetchall()


def get_course_teacher_id(cursor, course_code):
    cursor.execute(""" 
                    SELECT teacher_id FROM class c
                   WHERE c.class_id = %s                
                    """, (course_code, ))
    return cursor.fetchone()
def fetch_recent_class_announcements(cursor, course_code):
    cursor.execute('''
        SELECT announcement_id, content, posted_at, title
        FROM announcement
        WHERE class_id = %s
        ORDER BY posted_at DESC
    ''', (course_code,))
    return cursor.fetchall()

def create_announcement(cursor, course_code, title, desc):
    """Create announcement with stable UUID-based ID"""

    announcement_id = AnnouncementIDManager.create_announcement_id()
    
    cursor.execute('''
    INSERT INTO announcement (announcement_id, class_id, title, content, posted_at)
    VALUES (%s, %s, %s, %s, %s)
    ''', (announcement_id, course_code, title, desc, datetime.datetime.now()))
    
    return announcement_id      
    
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
    

def allowed_file(filename):
    
    # Check if the file has an allowed extension
    if '.' not in filename:
        return False
    
    extension = filename.rsplit('.', 1)[1].lower()
    return extension in ALLOWED_EXTENSIONS

def delete_assignment(cursor, assignment_id):
    """
    Deletes an assignment and all related rubrics, submissions, and grades from the database.
    """
    # Delete grades related to submissions of this assignment
    cursor.execute('''
        DELETE g FROM grade g
        JOIN submission s ON g.submission_id = s.submission_id
        WHERE s.assignment_id = %s
    ''', (assignment_id,))

    # Delete submissions for this assignment
    cursor.execute('''
        DELETE FROM submission WHERE assignment_id = %s
    ''', (assignment_id,))

    # Delete rubrics for this assignment
    cursor.execute('''
        DELETE FROM rubric WHERE assignment_id = %s
    ''', (assignment_id,))

    # Delete the assignment itself
    cursor.execute('''
        DELETE FROM assignment WHERE assignment_id = %s
    ''', (assignment_id,))
