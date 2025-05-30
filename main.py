from flask import Flask, render_template, url_for, request, session, redirect, flash, jsonify, send_from_directory, abort
from flask_mysqldb import MySQL
from flask_login import *
from itsdangerous import URLSafeTimedSerializer
from helpers import *
from classes import *
import os
from werkzeug.utils import secure_filename
import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from flask_mail import Mail, Message

app = Flask(__name__)
app.config["SECRET_KEY"] = "CANSU_BÜŞRA_ORHAN_SUPER_SECRET_KEY"  # os.environ.get("SECRET_KEY")
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'gradia.website@gmail.com'
app.config['MAIL_PASSWORD'] = 'ivln hvqr pfnm zudw'
app.config['MAIL_DEFAULT_SENDER'] = 'gradia.website@gmail.com'
app.config['SECUIRTY_PASSWORD_SALT'] = 'gradia_salt'
mail = Mail(app)
grading_assistant = GradingAssistant()

# Create directories if they don't exist
os.makedirs(ASSIGNMENT_SUBMISSIONS_DIR, exist_ok=True)
os.makedirs(ASSIGNMENT_FILES_DIR, exist_ok=True)
os.makedirs(PROFILE_PICS_DIR, exist_ok=True)

# Login
login_manager = LoginManager()

# Database
app.config['MYSQL_HOST'] = '127.0.0.1'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'gradeai'

gradeai_db = MySQL(app)
login_manager.init_app(app)



def generate_reset_token(email):
    serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    return serializer.dumps(email, salt=app.config['SECUIRTY_PASSWORD_SALT'])

def verify_reset_token(token, max_age=3600):
    serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    try:
        email = serializer.loads(token, salt=app.config['SECUIRTY_PASSWORD_SALT'], max_age=max_age) #expireas after 1 hour
    except Exception as e:
        app.logger.error(f"Token verification failed: {str(e)}")
        return None
    return email

@app.route('/forgot_password', methods=["GET", "POST"])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')

        if not email:
            flash('Please enter your email address.', 'error')
            return render_template('forgot_password.html')
        cursor = gradeai_db.connection.cursor()
        cursor.execute("SELECT user_id, first_name FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        if user:
            try:
                token = generate_reset_token(email)
                reset_url = url_for('new_password', token=token, _external=True)
                send_password_reset_email(email, user[1], reset_url)
                flash('If the email is registered, a password reset link has been sent to your email address.', 'info')
            except Exception as e:
                app.logger.error(f"Error sending email: {str(e)}")
                flash('There was an error sending the email. Please try again later.', 'error')
                return render_template('forgot_password.html')
        else:
            flash('If the email is registered, a password reset link has been sent to your email address.', 'info')
        
        cursor.close()
        return redirect(url_for('login'))
    
    return render_template('forgot_password.html')

@app.route('/new_password/<token>', methods=["GET", "POST"])
def new_password(token):
    email = verify_reset_token(token)
    if not email:
        flash('The password reset link is invalid or has expired.', 'error')
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if new_password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template("new_password.html", token=token)

        cursor = gradeai_db.connection.cursor()
        try:
            change_password(cursor, email, new_password)
            gradeai_db.connection.commit()
            flash('Your password has been reset successfully.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            app.logger.error(f"Error resetting password: {str(e)}")
            flash('An error occurred while resetting your password. Please try again.', 'error')
            return render_template("new_password.html", token=token)
        finally:
            cursor.close()

    return render_template("new_password.html", token=token)

def send_password_reset_email(to_email, first_name, reset_url):
    msg = Message(
        "Gradia - Password Reset Request",
        sender=app.config['MAIL_DEFAULT_SENDER'],
        recipients=[to_email]
    )
    
    msg.html = f"""
    <html>
    <body>
        <h2>Password Reset</h2>
        <p>
        Hello {first_name},</p>
        <p>You requested to reset your Gradia password. Click the link below:</p>
        <a href="{reset_url}">Reset Password</a>
        <p>This link expires in 1 hour.</p>
        <p>If you didn't request this, please ignore this email.</p>
    </body>
    </html>
    """
    
    mail.send(msg)


@login_manager.user_loader
def load_user(user_id):
    cursor = gradeai_db.connection.cursor()
    return User.get(cursor, user_id)

@app.route('/')
@app.route('/home')
def index():
    return render_template("homepage.html")


@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "POST":
        cursor = gradeai_db.connection.cursor()
        email = request.form["email"]
        password = request.form["password"]
        user_tuple = fetch_user(cursor, email, password)
        if not user_tuple:
            return render_template("login.html", error_message="This account doesn't exist!")

        update_last_login(cursor, email, password)
        gradeai_db.connection.commit()
        cursor.close()
        temp_infos = user_tuple[0]
        curr_user = User(user_id= temp_infos[0], email = temp_infos[1], first_name = temp_infos[3], last_name = temp_infos[4])  # password should be ignored 
        login_user(curr_user)

        if int.from_bytes(user_tuple[0][5], byteorder='big') == 1:  # in DB it is stored in bits
            del user_tuple
            return redirect(url_for("teacher_dashboard"))

        else:
            del user_tuple
            return redirect(url_for("student_dashboard"))

    else:
        return render_template("login.html")


@app.route('/signup', methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form["email"]
        first_name = request.form["first_name"]
        last_name = request.form["last_name"]
        user_id = request.form["user_id"]
        password = request.form["password"]

        cursor = gradeai_db.connection.cursor()

        if register_positive(cursor, email, user_id):
            add_user(cursor, email, first_name, last_name, user_id, password)
            gradeai_db.connection.commit()
            cursor.close()
            return redirect(url_for("login"))

        return render_template("signup.html", error_message="This account already exists!")

    else:
        return render_template("signup.html")


@app.route("/logout")
@login_required
def logout():
    if current_user.is_authenticated():
        current_user.logout()
    
    # Flask-Login logout
    logout_user()
    
    flash("You have been logged out successfully", "info")
    return redirect(url_for("index"))

@app.route('/tutorial')
def tutorial():
    return render_template("tutorial.html")


@app.route('/about')
def about():
    return render_template("aboutus.html")


@app.route('/blockview_teacher', methods=['GET', 'POST'])
@login_required
def blockview_teacher():
    """Handle class creation with student management functionality"""
    
    if request.method == 'GET':
        # Initialize empty form for new class creation
        return render_template('blockview_teacher.html', 
                             course_name='', 
                             course_code='', 
                             enrolled_students=[],
                             temp_students_json='')
    
    # Handle POST requests
    cursor = gradeai_db.connection.cursor()
    
    try:
        # Get form data
        course_name = request.form.get('course_name', '').strip()
        course_code = request.form.get('course_code', '').strip()
        action = request.form.get('action', '')
        temp_students_json = request.form.get('temp_students_json', '')
        
        # Parse existing temporary students from form
        temp_students = []
        if temp_students_json:
            try:
                import json
                temp_students = json.loads(temp_students_json)
            except:
                temp_students = []
        
        # Get current enrolled students
        enrolled_students = get_current_students_list(cursor, course_code, temp_students)
        
        # Handle different actions
        if action == 'add_student':
            return handle_add_student(cursor, course_name, course_code, enrolled_students, temp_students)
            
        elif action == 'upload_csv':
            return handle_csv_upload(cursor, course_name, course_code, enrolled_students, temp_students)
            
        elif action == 'remove_student':
            return handle_remove_student(cursor, course_name, course_code, enrolled_students, temp_students)
            
        elif action == 'create_course':
            return handle_create_course(cursor, course_name, course_code, enrolled_students)
        
        else:
            flash('Invalid action', 'danger')
            return render_template('blockview_teacher.html', 
                                 course_name=course_name, 
                                 course_code=course_code, 
                                 enrolled_students=enrolled_students,
                                 temp_students_json=temp_students_json)
    
    except Exception as e:
        flash(f'An error occurred: {str(e)}', 'danger')
        return render_template('blockview_teacher.html', 
                             course_name=course_name or '', 
                             course_code=course_code or '', 
                             enrolled_students=[],
                             temp_students_json='')
    finally:
        if cursor:
            cursor.close()

def get_current_students_list(cursor, course_code, temp_students):
    """Get current students - either from database (if course exists) or from temp list"""
    if course_code:
        # Check if course actually exists in database
        try:
            cursor.execute("SELECT * FROM class WHERE class_id = %s", (course_code,))
            course_exists = cursor.fetchone() is not None
            
            if course_exists:
                # Course exists, get from database
                return get_enrolled_students(cursor, course_code)
            else:
                # Course code provided but doesn't exist yet, use temp students
                return temp_students
        except:
            return temp_students
    else:
        # No course code provided, use temp students
        return temp_students

def create_temp_students_json(temp_students):
    """Convert temp students list to JSON string for form persistence"""
    import json
    return json.dumps(temp_students)

def handle_add_student(cursor, course_name, course_code, current_students, temp_students):
    """Handle adding a single student manually"""
    student_id = request.form.get('studentNo', '').strip()
    
    # Convert temp_students to JSON for persistence
    temp_students_json = create_temp_students_json(temp_students)
    
    if not student_id:
        flash('Please enter a student number', 'warning')
        return render_template('blockview_teacher.html', 
                             course_name=course_name, 
                             course_code=course_code, 
                             enrolled_students=current_students,
                             temp_students_json=temp_students_json)
    
    # Check if student exists in users table
    student_info = fetch_student_info(cursor, student_id)
    if not student_info['success']:
        flash(f'Student {student_id} not found in the system', 'danger')
        return render_template('blockview_teacher.html', 
                             course_name=course_name, 
                             course_code=course_code, 
                             enrolled_students=current_students,
                             temp_students_json=temp_students_json)
    
    # Check if student is already in the list
    student_already_exists = any(student[0] == student_id for student in current_students)
    if student_already_exists:
        flash(f'Student {student_id} is already in the list', 'warning')
        return render_template('blockview_teacher.html', 
                             course_name=course_name, 
                             course_code=course_code, 
                             enrolled_students=current_students,
                             temp_students_json=temp_students_json)
    
    # Check if course exists in database
    cursor.execute("SELECT * FROM class WHERE class_id = %s", (course_code,))
    course_exists = cursor.fetchone() is not None
    
    if course_exists:
        # Course exists in database, enroll immediately
        enroll_student(cursor, student_id, course_code)
        gradeai_db.connection.commit()  # Commit the transaction
        flash(f'Student {student_id} ({student_info["first_name"]} {student_info["last_name"]}) added successfully', 'success')
        # Refresh enrolled students list from database
        current_students = get_enrolled_students(cursor, course_code)
        temp_students_json = create_temp_students_json([])  # Clear temp list for existing course
    else:
        # Course doesn't exist yet, add to temporary list
        flash(f'Student {student_id} ({student_info["first_name"]} {student_info["last_name"]}) added to list', 'success')
        temp_student = [student_id, student_info['first_name'], student_info['last_name']]
        temp_students.append(temp_student)
        current_students = temp_students
        temp_students_json = create_temp_students_json(temp_students)
        del temp_students_json
    
    return render_template('blockview_teacher.html', 
                         course_name=course_name, 
                         course_code=course_code, 
                         enrolled_students=current_students,
                         temp_students_json=temp_students_json)

def handle_csv_upload(cursor, course_name, course_code, current_students, temp_students):
    """Handle CSV file upload for bulk student enrollment"""
    
    # Convert temp_students to JSON for persistence
    temp_students_json = create_temp_students_json(temp_students)
    
    if 'fileInput' not in request.files:
        flash('No file selected', 'danger')
        return render_template('blockview_teacher.html', 
                             course_name=course_name, 
                             course_code=course_code, 
                             enrolled_students=current_students,
                             temp_students_json=temp_students_json)
    
    file = request.files['fileInput']
    
    if file.filename == '':
        flash('No file selected', 'danger')
        return render_template('blockview_teacher.html', 
                             course_name=course_name, 
                             course_code=course_code, 
                             enrolled_students=current_students,
                             temp_students_json=temp_students_json)
    
    if not file.filename.lower().endswith('.csv'):
        flash('Please upload a CSV file', 'danger')
        return render_template('blockview_teacher.html', 
                             course_name=course_name, 
                             course_code=course_code, 
                             enrolled_students=current_students,
                             temp_students_json=temp_students_json)
    
    try:
        # Save the uploaded file temporarily
        filename = secure_filename(file.filename)
        temp_path = os.path.join(ENROLLMENTS_FILES_DIR, filename)
        os.makedirs(ENROLLMENTS_FILES_DIR, exist_ok=True)
        file.save(temp_path)
        
        # Process CSV file
        added_students = []
        failed_students = []
        current_student_ids = [student[0] for student in current_students]
        
        with open(temp_path, 'r', newline='', encoding='utf-8') as csvfile:
            csv_reader = csv.reader(csvfile)
            
            for row_num, row in enumerate(csv_reader, 1):
                if not row or not row[0].strip():  # Skip empty rows
                    continue
                
                student_id = row[0].strip()
                
                # Check if student already in current list
                if student_id in current_student_ids:
                    failed_students.append(f"Row {row_num}: Student {student_id} already in list")
                    continue
                
                # Check if student exists
                student_info = fetch_student_info(cursor, student_id)
                if not student_info['success']:
                    failed_students.append(f"Row {row_num}: Student {student_id} not found")
                    continue
                
                # Check if course exists in database
                course_exists = False
                if course_code:
                    cursor.execute("SELECT * FROM class WHERE class_id = %s", (course_code,))
                    course_exists = cursor.fetchone() is not None
                
                if course_exists:
                    # Course exists, enroll immediately
                    enroll_student(cursor, student_id, course_code)
                    added_students.append(f"{student_id} ({student_info['first_name']} {student_info['last_name']})")
                else:
                    # Course doesn't exist yet, add to temporary list
                    added_students.append(f"{student_id} ({student_info['first_name']} {student_info['last_name']})")
                    temp_student = [student_id, student_info['first_name'], student_info['last_name']]
                    temp_students.append(temp_student)
        
        # Commit database changes if course exists
        course_exists = False
        if course_code:
            cursor.execute("SELECT * FROM class WHERE class_id = %s", (course_code,))
            course_exists = cursor.fetchone() is not None
            
        if course_exists:
            gradeai_db.connection.commit()
            # Refresh from database
            current_students = get_enrolled_students(cursor, course_code)
            temp_students_json = create_temp_students_json([])
        else:
            # Update current list and JSON
            current_students = temp_students
            temp_students_json = create_temp_students_json(temp_students)
        
        # Clean up temporary file
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        # Show results
        if added_students:
            flash(f'Successfully processed {len(added_students)} students', 'success')
        
        if failed_students:
            flash(f'{len(failed_students)} students failed: {"; ".join(failed_students[:3])}{"..." if len(failed_students) > 3 else ""}', 'warning')
    
    except Exception as e:
        flash(f'Error processing CSV file: {str(e)}', 'danger')
        # Clean up temporary file on error
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)
    
    return render_template('blockview_teacher.html', 
                         course_name=course_name, 
                         course_code=course_code, 
                         enrolled_students=current_students,
                         temp_students_json=temp_students_json)

def handle_remove_student(cursor, course_name, course_code, current_students, temp_students):
    """Handle removing a student from the course"""
    student_to_remove = request.form.get('student_to_remove', '').strip()
    
    if not student_to_remove:
        flash('No student specified for removal', 'danger')
        temp_students_json = create_temp_students_json(temp_students)
        return render_template('blockview_teacher.html', 
                             course_name=course_name, 
                             course_code=course_code, 
                             enrolled_students=current_students,
                             temp_students_json=temp_students_json)
    
    try:
        # Check if course exists in database
        course_exists = False
        if course_code:
            cursor.execute("SELECT * FROM class WHERE class_id = %s", (course_code,))
            course_exists = cursor.fetchone() is not None
            
        if course_exists:
            # Course exists, remove from database
            removed_students = handle_student_removal(cursor, student_to_remove, course_code)
            
            if removed_students:
                gradeai_db.connection.commit()  # Commit the transaction
                flash(f'Student {student_to_remove} removed successfully', 'success')
                # Refresh enrolled students list from database
                current_students = get_enrolled_students(cursor, course_code)
                temp_students_json = create_temp_students_json([])
            else:
                flash(f'Failed to remove student {student_to_remove}', 'danger')
                temp_students_json = create_temp_students_json([])
        else:
            # Course doesn't exist yet, remove from temporary list
            temp_students = [student for student in temp_students if student[0] != student_to_remove]
            current_students = temp_students
            temp_students_json = create_temp_students_json(temp_students)
            flash(f'Student {student_to_remove} removed from list', 'success')
    
    except Exception as e:
        flash(f'Error removing student: {str(e)}', 'danger')
        temp_students_json = create_temp_students_json(temp_students)
    
    return render_template('blockview_teacher.html', 
                         course_name=course_name, 
                         course_code=course_code, 
                         enrolled_students=current_students,
                         temp_students_json=temp_students_json)

def handle_create_course(cursor, course_name, course_code, current_students):
    """Handle creating the course/class"""
    
    # Validate required fields
    if not course_name or not course_code:
        flash('Course name and code are required', 'danger')
        temp_students_json = create_temp_students_json(current_students if not course_code else [])
        return render_template('blockview_teacher.html', 
                             course_name=course_name, 
                             course_code=course_code, 
                             enrolled_students=current_students,
                             temp_students_json=temp_students_json)
    
    try:
        # Check if class already exists
        cursor.execute("SELECT * FROM class WHERE class_id = %s", (course_code,))
        existing_class = cursor.fetchone()
        
        if existing_class:
            flash(f'A class with code {course_code} already exists', 'danger')
            temp_students_json = create_temp_students_json(current_students if not course_code else [])
            return render_template('blockview_teacher.html', 
                                 course_name=course_name, 
                                 course_code=course_code, 
                                 enrolled_students=current_students,
                                 temp_students_json=temp_students_json)
        
        # Create the class
        teacher_id = current_user.user_id
        create_class(cursor, course_code, course_name, teacher_id)
        
        # If there are students in the temporary list, enroll them
        enrolled_count = 0
        if current_students:
            for student in current_students:
                student_id = student[0]
                try:
                    if not is_student_enrolled(cursor, student_id, course_code):
                        enroll_student(cursor, student_id, course_code)
                        enrolled_count += 1
                except Exception as e:
                    print(f"Error enrolling student {student_id}: {e}")
                    continue
        
        # Commit all changes
        gradeai_db.connection.commit()
        
        # Success message
        success_msg = f'Class "{course_name}" ({course_code}) created successfully'
        if enrolled_count > 0:
            success_msg += f' with {enrolled_count} students enrolled'
        
        flash(success_msg, 'success')
        
        # Redirect to course management or dashboard
        return redirect(url_for('teacher_dashboard'))  # or wherever you want to redirect
        
    except Exception as e:
        flash(f'Error creating class: {str(e)}', 'danger')
        # Rollback on error
        gradeai_db.connection.rollback()
        temp_students_json = create_temp_students_json(current_students if not course_code else [])
        return render_template('blockview_teacher.html', 
                             course_name=course_name, 
                             course_code=course_code, 
                             enrolled_students=current_students,
                             temp_students_json=temp_students_json) 
@app.route('/student_dashboard')
@login_required
def student_dashboard():
    cursor = gradeai_db.connection.cursor()
    courses_and_instructors = fetch_enrollments(cursor, current_user.user_id)
    upcoming_deadlines = fetch_upcoming_deadlines(cursor, current_user.user_id, 0)
    recent_feedback = fetch_recent_feedback(cursor, current_user.user_id, 0)
    recent_announcements = fetch_recent_announcements(cursor, current_user.user_id, 0)
    profile_pic = fetch_profile_picture(None, current_user.user_id)
    cursor.close()

    return render_template("student_dashboard.html",
                         courses_and_instructors=courses_and_instructors,
                         upcoming_deadlines=upcoming_deadlines,
                         recent_feedback=recent_feedback,
                         recent_announcements=recent_announcements,
                         profile_pic=profile_pic)


@app.route('/teacher_dashboard')
@login_required
def teacher_dashboard():
    cursor = gradeai_db.connection.cursor()
    courses = fetch_classes(cursor, current_user.user_id)
    total_student_dict = total_number_of_students(cursor, [course[0] for course in courses])
    upcoming_deadlines = fetch_upcoming_deadlines(cursor, current_user.user_id, 1)
    recent_feedback = fetch_recent_feedback(cursor, current_user.user_id, 1)
    recent_announcements = fetch_recent_announcements(cursor, current_user.user_id, 1)
    profile_pic = fetch_profile_picture(None, current_user.user_id)
    cursor.close()

    return render_template("teacher_dashboard.html",
                         courses=courses,
                         upcoming_deadlines=upcoming_deadlines,
                         recent_feedback=recent_feedback,
                         recent_announcements=recent_announcements,
                         total_student_dict=total_student_dict,
                         profile_pic=profile_pic)

#DONE
@app.route('/announcement_student/<course_code>/<course_name>/<announcement_id>/<title>')
@login_required
def announcement_student(course_code, course_name, announcement_id, title):
    cursor = gradeai_db.connection.cursor()
    attachments = []

    announcement = fetch_announcement_details(cursor, announcement_id)
    attachments =  get_files('announcement', course_code, title)

    cursor.close()

    return render_template('announcement_student.html',
                           course_code=course_code,
                           course_name=course_name,
                           announcement=announcement,
                           attachments=attachments,
                           folder_name=title)

#DONE
@app.route('/announcement_view_student/<course_name>/<course_code>')
@login_required
def announcement_view_student(course_name, course_code):
    cursor = gradeai_db.connection.cursor()
    announcements = fetch_recent_class_announcements(cursor, course_code)
    cursor.close()

    return render_template("announcement_view_student.html",
                           course_name=course_name,
                           course_code=course_code,
                           announcements=announcements)

#DONE
@app.route('/announcement_teacher/<course_name>/<course_code>')
@login_required
def announcement_teacher(course_name, course_code):
    cursor = gradeai_db.connection.cursor()
    announcements = fetch_recent_class_announcements(cursor, course_code)
    cursor.close()
    return render_template("announcement_teacher.html",
                           course_name=course_name,
                           course_code=course_code,
                           announcements=announcements)


@app.route('/announcement_edit/<course_name>/<course_code>/<announcement_id>', methods=["GET", "POST"])
@login_required
def announcement_edit(course_name, course_code, announcement_id):
    cursor = gradeai_db.connection.cursor()
    #TODO
    # Change the whole function
    if request.method == "POST":
        title = request.form.get("title")
        content = request.form.get("description")
        attachments = request.files.get("attachments")
        _ = edit_announcement(announcement_id, title, content)
        gradeai_db.connection.commit()
        cursor.close()

        return redirect(url_for('announcement_teacher', course_name=course_name, course_code=course_code))

    else:
        fetch_announcement_details(cursor, announcement_id)
        announcement = cursor.fetchone()
        
        cursor.close()
        if not announcement:
            return redirect(url_for('announcement_teacher', course_name=course_name, course_code=course_code))
        
        
        return render_template("announcement_edit.html",
                            course_name=course_name,
                            course_code=course_code,
                            announcement=announcement)

#DONE
@app.route('/announcement_delete/<course_name>/<course_code>/<announcement_id>')
@login_required
def announcement_delete(course_name, course_code, announcement_id):
    cursor = gradeai_db.connection.cursor()
    _ = delete_announcement(cursor, announcement_id)
    gradeai_db.connection.commit()
    cursor.close()

    return redirect(url_for('announcement_teacher', course_name=course_name, course_code=course_code))

#DONE
@app.route('/announcement_view_teacher/<course_name>/<course_code>', methods=["GET", "POST"])
@login_required
def announcement_view_teacher(course_name, course_code):
    if request.method == "POST":
        cursor = gradeai_db.connection.cursor()
        title = request.form.get("title")
        desc = request.form.get("description")
        attachments = request.files.getlist("attachments")

        create_announcement(cursor, course_code, title, desc)
        save_files(attachments, "announcements", course_code, title)

        gradeai_db.connection.commit()
        cursor.close()

        return redirect(url_for('announcement_teacher', course_name=course_name, course_code=course_code))

    return render_template("announcement_view_teacher.html", course_name=course_name, course_code=course_code)

#DONE
@app.route('/assignments/<course_code>')
@login_required
def view_assignments(course_code):
    cursor = gradeai_db.connection.cursor()

    course = get_course_name(cursor, course_code)
    if not course:
        flash("Course not found", "error")
        return redirect(url_for("teacher_dashboard"))

    assignments = get_course_assignments(cursor, course_code)

    cursor.close()

    return render_template("assignments.html",
                           course_name=course[0],
                           course_code=course_code,
                           assignments=assignments)

#DONE
@app.route('/assignment_creation/<course_code>', methods=["GET", "POST"])
@login_required
def assignment_creation(course_code):
    cursor = gradeai_db.connection.cursor()
    if request.method == "POST":
        assignment_title = request.form.get("title")
        assignment_desc = request.form.get("description")
        assignment_files = request.files.getlist("attachments")
        deadline = request.form.get("Date")
        rubric_descs, rubric_vals = request.form.getlist("rubric_descriptions[]"), request.form.getlist("rubric_values[]")
        
        total_score = calculate_total_sum(rubric_vals)

        save_files(assignment_files, 'assignments', course_code, assignment_title)
        assignment_id = create_assignment(cursor, assignment_title, assignment_desc, deadline, course_code, total_score)
        zip_to_rubric(cursor, zip(rubric_descs, rubric_vals), current_user.user_id, course_code, assignment_title, assignment_id)

        gradeai_db.connection.commit()
        cursor.close()

        flash("Assignment created successfully", "success")
        return redirect(url_for("view_assignments", course_code=course_code))

  
    course = get_course_name(cursor, course_code)
    cursor.close()

    if not course:
        flash("Course not found", "error")
        return redirect(url_for("teacher_dashboard"))

    return render_template("assignment_creation.html",
                           course_name=course[0],
                           course_code=course_code,
                           today = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M'))

#DONE
@app.route('/generate_rubric', methods=["POST"])
@login_required
def generate_rubric():
    data = request.get_json()
    if not data or 'description' not in data:
        return jsonify({'error': 'Missing assignment description'}), 400
        
    description = data.get('description', '')
    existing_rubrics = data.get('existing_rubrics', [])

    if existing_rubrics:
        current_rubrics, current_points = [], []
        for entry in existing_rubrics:
            current_rubrics.append(entry["description"])
            current_points.append(entry["points"])

    grading_assistant.create_rubric_instructions(current_rubrics, current_points)
    grading_assistant.consume_question(description)

    if len(description.strip()) < 10:
        return jsonify({'error': 'Description too short for meaningful rubric generation'}), 400
    
    llm_output = grading_assistant.generate_rubric()

    rubric_items = [
        {"description": item["rubric_desc"], "points": int(item["rubric_score"])}
        for item in llm_output
    ]
    return jsonify({
        'success': True,
        'rubric_items': rubric_items
    })

#DONE
@app.route('/assignment_feedback_teacher/<course_name>/<course_code>')
@login_required
def assignment_feedback_teacher(course_name, course_code):
    cursor = gradeai_db.connection.cursor()
    feedbacks = fetch_feedbacks_by_teacher(cursor, current_user.user_id)
    cursor.close()
    return render_template("assignment_feedback_teacher.html", feedbacks=feedbacks, course_name=course_name,
                           course_code=course_code)

@app.route('/assignment_grades_student/<course_name>/<course_code>')
@login_required
def assignment_grades_student(course_name, course_code):
    cursor = gradeai_db.connection.cursor()
    cursor.execute("""
        SELECT a.title as assignment_title, g.score, g.feedback, 
               g.adjusted_at as graded_at, c.name as course_name, 
               c.class_id as course_code
        FROM grade g 
        JOIN submission s ON g.submission_id = s.submission_id 
        JOIN assignment a ON s.assignment_id = a.assignment_id 
        JOIN class c ON a.class_id = c.class_id 
        WHERE s.student_id = %s AND c.class_id = %s
        ORDER BY g.adjusted_at DESC
    """, (current_user.user_id, course_code))
    grades = cursor.fetchall()
    cursor.close()
    return render_template("assignment_grades_student.html",
                           grades=grades,
                           course_name=course_name,
                           course_code=course_code)

#DONE
@app.route('/assignments_student/<course_code>/<course_name>')
@login_required
def assignments_student(course_code, course_name):
    cursor = gradeai_db.connection.cursor()
    assignments = get_course_assignments(cursor, course_code)
    cursor.close()

    return render_template("assignments_student.html",
                           course_name=course_name,
                           course_code=course_code,
                           assignments=assignments)
#DONE
@app.route('/assignment_submit_student/<course_code>/<course_name>/<assignment_id>', methods=["GET", "POST"])
@login_required
def assignment_submit_student(course_code, course_name, assignment_id):
    cursor = gradeai_db.connection.cursor()
    
    assignment_data = get_assignment_details(cursor, assignment_id, course_code)
    
    if not assignment_data:
        flash("Assignment not found", "error")
        cursor.close()
        return redirect(url_for("assignments_student", course_code=course_code, course_name=course_name))

    submission_dir = os.path.join(ASSIGNMENT_SUBMISSIONS_DIR, course_code, assignment_data[0], current_user.user_id)
    
    os.makedirs(submission_dir, exist_ok=True)

    assignment_files = []
    assignment_dir = os.path.join(ASSIGNMENT_FILES_DIR, course_code, assignment_data[0])
    
    if os.path.exists(assignment_dir):
        assignment_files = [f for f in os.listdir(assignment_dir) if os.path.isfile(os.path.join(assignment_dir, f))]

    delete_submissions(cursor, current_user.user_id, assignment_id)
    gradeai_db.connection.commit()

    files = []
    current_time = ''
    if os.path.exists(submission_dir):
        try:
            for f in os.listdir(submission_dir):
                if os.path.isfile(os.path.join(submission_dir, f)):
                    files.append(f)
                    current_time = datetime.datetime.now()
                    create_submission_with_proper_id(cursor, assignment_id, current_user.user_id, f)
                    
        except Exception as e:
            print(f"Error processing submission directory: {e}")

    gradeai_db.connection.commit()

    # Format assignment data for template
    assignment = {
        'id': assignment_id,
        'title': assignment_data[0],
        'description': assignment_data[1],
        'due_date': assignment_data[2],
        'total_score': assignment_data[3],
        'attachments': [{'filename': f, 'id': i} for i, f in enumerate(assignment_files)],
        'is_submitted': True if files else False,
        'submission': {
            'files': files,
            'submitted_at': current_time if files else None
        } 
    }
    
    cursor.close()
    return render_template("assignment_submit_student.html",
                           assignment=assignment,
                           course_code=course_code,
                           course_name=course_name,
                           current_datetime=datetime.datetime.now())

#DONE
@app.route('/assignment_view_teacher/<course_code>/<assignment_id>')
@login_required
def assignment_view_teacher(course_code, assignment_id):
    cursor = gradeai_db.connection.cursor()

    # Get assignment details
    assignment = get_assignment_details(cursor, assignment_id, course_code)
    if not assignment:
        flash("Assignment not found", "error")
        cursor.close()
        return redirect(url_for("teacher_dashboard"))

    # Get assignment files using the actual assignment title
    assignment_title = assignment[0]  # assignment[0] is the title
    assignment_files = []
    
    assignment_dir = os.path.join(ASSIGNMENT_FILES_DIR, course_code, assignment_title)
    
    if os.path.exists(assignment_dir):
        assignment_files = [f for f in os.listdir(assignment_dir) if os.path.isfile(os.path.join(assignment_dir, f))]

    students = get_students_submissions(cursor, assignment_id, course_code)
    cursor.close()
    
    print(f"Debug - Students with submissions: {len(students) if students else 0}")
    
    return render_template("assignment_view_teacher.html",
                           course_name=assignment[4],
                           assignment_title=assignment[0],
                           description=assignment[1],
                           deadline=assignment[2],
                           total_score=assignment[3],
                           assignment_files=assignment_files,
                           students=students,
                           course_code=course_code,
                           assignment_id=assignment_id)

@app.route('/edit_image', methods=["GET", "POST"])
@login_required
def edit_image():
    if request.method == 'POST':
        if 'profile_image' not in request.files:
            flash('No file part', 'error')
            return redirect(url_for('edit_image'))
        
        file = request.files['profile_image']

        if file.filename == '':
            flash('No selected file', 'error')
            return redirect(url_for('edit_image'))
        
        # Check file extension
        if not allowed_file(file.filename):
            flash('Invalid file type. Please upload a PNG, JPG, or JPEG image.', 'error')
            return redirect(url_for('edit_image'))
        
        if file.content_type not in ['image/png', 'image/jpeg', 'image/jpg']:
            app.logger.warning(f"Invalid MIME type: {file.content_type}")
            flash('Invalid file type. Please upload a PNG, JPG, or JPEG image.', 'error')
            return redirect(url_for('edit_image'))
        
        try:
            # Read file content to check size
            file_content = file.read()
            file.seek(0)  # Reset file pointer
            
            # Check file size (limit 5MB = 5*1024*1024 bytes)
            if len(file_content) > 5*1024*1024:
                flash('File size exceeds the limit of 5MB. Please upload a smaller file.', 'error')
                return redirect(url_for('edit_image'))

            # Get old profile picture path before generating new filename
            old_pic = fetch_profile_picture(None, current_user.user_id)
            old_path = None
            if old_pic:
                old_path = os.path.join('static', old_pic.replace('/', os.path.sep))
                app.logger.info(f"Found old profile picture at: {old_path}")

            # Generate unique filename
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            unique_filename = f"{current_user.user_id}_{timestamp}_{secure_filename(file.filename)}"
            
            # Create uploads directory if it doesn't exist
            upload_dir = os.path.join('static', 'uploads', 'profile_pics')
            os.makedirs(upload_dir, exist_ok=True)
            
            # Save the file using OS path for filesystem operations
            file_path = os.path.join(upload_dir, unique_filename)
            
            # Save the file
            app.logger.info(f"Attempting to save file to: {file_path}")
            file.save(file_path)
            
            # Verify file was saved and is readable
            if not os.path.exists(file_path):
                raise Exception(f"Failed to save file at {file_path}")
            
            app.logger.info(f"File saved successfully at: {file_path}")
            
            # Try to open the file to verify it's a valid image
            try:
                from PIL import Image
                with Image.open(file_path) as img:
                    img.verify()
                app.logger.info("Image verification successful")
            except Exception as e:
                app.logger.error(f"Image verification failed: {str(e)}")
                if os.path.exists(file_path):
                    os.remove(file_path)
                raise Exception(f"Invalid image file: {str(e)}")
            
            # Only delete old profile picture after new one is verified
            if old_path and os.path.exists(old_path) and old_path != file_path:
                try:
                    os.remove(old_path)
                    app.logger.info(f"Deleted old profile picture at {old_path}")
                except Exception as e:
                    app.logger.warning(f"Failed to delete old profile picture: {str(e)}")
            
            # Final verification that the new file exists
            if not os.path.exists(file_path):
                app.logger.error(f"File not found at final verification: {file_path}")
                raise Exception("File was not saved properly")
            
            app.logger.info("Profile picture update completed successfully")
            flash('Profile picture updated successfully!', 'success')
            
            # Redirect based on user role
            user_role = role_parser(current_user.email)
            if isinstance(user_role, bytes):
                user_role = int.from_bytes(user_role, byteorder='big')
            
            if user_role == 1:
                return redirect(url_for('profile_teacher'))
            else:
                return redirect(url_for('profile_student'))

        except Exception as e:
            app.logger.error(f"Error in profile picture upload: {str(e)}")
            # Clean up any partially saved file
            if 'file_path' in locals() and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    app.logger.info(f"Cleaned up partially saved file: {file_path}")
                except Exception as cleanup_error:
                    app.logger.error(f"Failed to clean up file: {str(cleanup_error)}")
            flash(f'Failed to update profile picture: {str(e)}', 'error')
            return redirect(url_for('edit_image'))
    
    # If GET request, render the edit image page
    user_role = role_parser(current_user.email)
    if isinstance(user_role, bytes):
        user_role = int.from_bytes(user_role, byteorder='big')

    try:
        profile_pic = fetch_profile_picture(None, current_user.user_id)
        if profile_pic:
            app.logger.info(f"Current profile picture path: {profile_pic}")
            # Verify the file exists using OS path
            full_path = os.path.join('static', profile_pic.replace('/', os.path.sep))
            app.logger.info(f"Checking profile picture at: {full_path}")
            if not os.path.exists(full_path):
                app.logger.warning(f"Profile picture file not found at: {full_path}")
                profile_pic = None
            else:
                app.logger.info("Profile picture file exists")
                # Log the URL that will be used
                url = url_for('static', filename=profile_pic)
                app.logger.info(f"Profile picture URL will be: {url}")
        return render_template("edit_image.html", user_role=user_role, profile_pic=profile_pic)
    except Exception as e:
        app.logger.error(f"Error fetching profile picture: {str(e)}")
        return render_template("edit_image.html", user_role=user_role, profile_pic=None)

@app.route('/profile_student')
@login_required
def profile_student():
    cursor = gradeai_db.connection.cursor()
    courses_and_instructors = fetch_enrollments(cursor, current_user.user_id)
    profile_pic = fetch_profile_picture(None, current_user.user_id)
    cursor.close()
    return render_template("profile_student.html", 
                         courses_and_instructors=courses_and_instructors,
                         profile_pic=profile_pic)

@app.route('/profile_teacher')
@login_required
def profile_teacher():
    cursor = gradeai_db.connection.cursor()
    courses = fetch_classes(cursor, current_user.user_id)
    profile_pic = fetch_profile_picture(None, current_user.user_id)
    cursor.close()
    return render_template("profile_teacher.html", 
                         courses=courses,
                         profile_pic=profile_pic)

#DONE
@app.route('/grade_submission/<course_code>/<assignment_id>/<submission_id>/<student_id>', methods=['GET', 'POST'])
@login_required
def grade_submission(course_code, assignment_id, submission_id, student_id):
    cursor = gradeai_db.connection.cursor()
    
    # Get student info
    student = get_user_info(cursor, student_id)
    student = {'first_name': student[3], 'last_name': student[4], 'user_id': student[0]}
    
    # Get assignment info
    assignment = get_assignment_details(cursor, assignment_id, course_code)
    assignment = {'title': assignment[0], 'description': assignment[1], 'total_score': assignment[3], 'deadline': assignment[2], 'assignment_id': assignment_id}
    
    # Get submission info
    submission = get_submission_details(cursor, submission_id)
    last_submitted_at = submission[0] if submission else None
    
    # Get existing grade and feedback
    
    grade = get_grade_details(cursor, submission_id, course_code)
    current_score = grade[2] if grade else 0
    current_feedback = grade[3] if grade else ""
    
    submission = {
        "submitted_at": last_submitted_at, 
        "is_on_time": 1 if last_submitted_at <= assignment["deadline"] else 0, 
        "submission_id": submission_id,
        "score": current_score,
        "feedback": current_feedback
    }
    
    # Get submission directory using actual assignment title
    submission_dir = os.path.join(ASSIGNMENT_SUBMISSIONS_DIR, course_code, assignment["title"], student["user_id"])
    
    # Get files
    submission_files = []
    if os.path.exists(submission_dir):
        for filename in os.listdir(submission_dir):
            if os.path.isfile(os.path.join(submission_dir, filename)):
                file_size = os.path.getsize(os.path.join(submission_dir, filename))
                submission_files.append({"filename": filename, "size": file_size})
    
    # Get rubrics
    rubric_l = []
    rubrics = get_rubrics(cursor, assignment_id)
    for rubric_desc in rubrics:
        rubric_l.append({"description": rubric_desc[2]})

    cursor.close()
    return render_template("grade_submission.html", 
                         student=student, 
                         assignment=assignment, 
                         submission=submission, 
                         submission_files=submission_files, 
                         rubrics=rubric_l,
                         course_code=course_code)

#DONE
@app.route('/download/<course_code>/<assignment_id>/<user_id>/<filename>')
@login_required
def download_submission(course_code, assignment_id, user_id, filename):
    try:
        cursor = gradeai_db.connection.cursor()

        assignment = get_assignment_details(cursor, assignment_id)
        cursor.close()
        
        if not assignment:
            abort(404)
        
        submission_dir = os.path.join(ASSIGNMENT_SUBMISSIONS_DIR, course_code, assignment[1], user_id)
        
        print(f"Download path: {submission_dir}")
        return send_from_directory(submission_dir, filename, as_attachment=True)
    except FileNotFoundError:
        abort(404)

#DONE
@app.route('/submit_assignment/<course_code>/<course_name>/<assignment_id>', methods=['POST'])
@login_required
def submit_assignment(course_code, course_name, assignment_id):
    cursor = gradeai_db.connection.cursor()
    assignment = get_assignment_details(cursor, assignment_id, None)
    print(assignment)
    if not assignment:
        flash("Assignment not found", "error")
        cursor.close()
        return redirect(url_for("assignments_student", course_code=course_code, course_name=course_name))

    assignment_title = assignment[1]

    submission_dir_student = os.path.join(ASSIGNMENT_SUBMISSIONS_DIR, course_code, assignment_title, current_user.user_id)
    print(submission_dir_student)
    delete_file = request.form.get("delete-file")
    delete_all = request.form.get("delete-all")
    
    # Handle file deletion
    if delete_file:    
        submission_id = SubmissionIDManager.create_submission_id(assignment_id, current_user.user_id, delete_file)
        grade_id = GradeIDManager.create_grade_id(submission_id)
                
        delete_grade(cursor, grade_id)
        delete_submission(cursor, submission_id)
        file_path = os.path.join(submission_dir_student, delete_file)
        if os.path.exists(file_path):
            os.remove(file_path)
        
        gradeai_db.connection.commit()
        cursor.close()
        return redirect(url_for("assignment_submit_student", 
                               course_code=course_code, 
                               course_name=course_name, 
                               assignment_id=assignment_id))
    
    # Handle delete all
    if delete_all:
        # Get all submissions for this student and assignment
        submissions = get_student_submissions(cursor, current_user.user_id, assignment_id)
        # Delete grades and submissions
        print("Debug - submit_assignment: ", submissions)
        for submission in submissions:
            cursor.execute("DELETE FROM grade WHERE submission_id = %s", (submission[0], ))
        
        delete_submissions(cursor, current_user.user_id, assignment_id)
        gradeai_db.connection.commit()
        print(submission_dir_student)
        if os.path.exists(submission_dir_student):
            try:
                for filename in os.listdir(submission_dir_student):
                    file_path = os.path.join(submission_dir_student, filename)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
            except Exception as e:
                print(f"Error deleting files: {e}")

        gradeai_db.connection.commit()
        cursor.close()
        return redirect(url_for("assignment_submit_student", 
                               course_code=course_code, 
                               course_name=course_name, 
                               assignment_id=assignment_id))

    # Handle new submission
    files = request.files.getlist('files')
    if not files or not files[0].filename:
        flash("Please select at least one file to submit", "error")
        cursor.close()
        return redirect(url_for("assignment_submit_student",
                                course_code=course_code,
                                course_name=assignment[2],
                                assignment_id=assignment_id))
    
    try:
        # Create submission directory using correct path
        submission_dir = os.path.join(ASSIGNMENT_SUBMISSIONS_DIR, course_code, assignment_title, str(current_user.user_id))
        os.makedirs(submission_dir, exist_ok=True)

        # Save files and create submissions
        saved_files = []
        submission_records = []
        
        for f in files:
            if f and f.filename:
                filename = secure_filename(f.filename)
                file_path = os.path.join(submission_dir, filename)
                f.save(file_path)
                saved_files.append(filename)                
                submission_id = SubmissionIDManager.create_submission_id(
                    assignment_id, current_user.user_id, filename
                )
                submission_records.append((submission_id, filename))

        if not saved_files:
            flash("No files were saved", "error")
            cursor.close()
            return redirect(url_for("assignment_submit_student",
                                    course_code=course_code,
                                    course_name=assignment[2],
                                    assignment_id=assignment_id))
        
        # Delete any existing submissions for this assignment and student
        cursor.execute("""
            SELECT submission_id FROM submission 
            WHERE student_id = %s AND assignment_id = %s
        """, (current_user.user_id, assignment_id))
        existing_submissions = cursor.fetchall()
        
        # Delete grades for existing submissions
        for existing_sub in existing_submissions:
            cursor.execute(""" DELETE FROM grade WHERE submission_id = %s""", (existing_sub[0], ))
        
        delete_submissions(cursor, current_user.user_id, assignment_id)

        for submission_id, filename in submission_records:
            create_submission_with_proper_id(cursor, assignment_id, current_user.user_id, filename)

        gradeai_db.connection.commit()

        # AUTO-GRADING PROCESS
        print("Debug - Starting auto-grading process")
        
        # Get rubrics for this assignment
        db_rubrics = get_rubrics(cursor, assignment_id)
        if not db_rubrics:
            print("Debug - No rubrics found for assignment")
            flash("Warning: No grading rubrics found for this assignment", "warning")
        else:
            print(f"Debug - Found {len(db_rubrics)} rubrics")
            # Convert tuples to expected format
            rubrics = []
            for rubric_tuple in db_rubrics:
                rubric_dict = {
                    "rubric_desc": rubric_tuple[0],
                    "rubric_score": str(rubric_tuple[1])
                }
                rubrics.append(rubric_dict)
            
            print(f"Debug - Formatted rubrics: {rubrics}")
            
            # Get teacher ID
            teacher_result = get_course_teacher_id(cursor, course_code)
            
            teacher_id = teacher_result[0] if teacher_result else None
            submission_scores = []
            
            # Grade each file
            for filename, (submission_id, _) in zip(saved_files, submission_records):
                file_extension = filename.split(".")[-1] if "." in filename else "docx"
                file_path = os.path.join(submission_dir, filename)
            
                try:
                    # Grade the file using the grading assistant
                    submission_score = grading_assistant.grade_file(file_path, file_extension, rubrics)
                    print(f"Debug - Grading result: {submission_score}")
                    # Add grade into DB
                    create_grade_with_proper_id(cursor, submission_id, submission_score, "This submission is graded by system!", teacher_id)
                    
                    submission_scores.append({
                        "filename": filename, 
                        "submission_score": submission_score,
                        "submission_id": submission_id
                    })
                    
                except Exception as grading_error:
                    print(f"Error grading file {filename}: {grading_error}")
                    flash(f"Error grading {filename}: {str(grading_error)}", "warning")
                    
                    # Create grade entry with score value of 
                    create_grade_with_proper_id(cursor, submission_id, 0, "This submission is graded by system!", teacher_id)
            
            gradeai_db.connection.commit()
            print(f"Debug - Auto-grading completed. Scores: {submission_scores}")
            
            if submission_scores:
                total_score = sum(item["submission_score"] for item in submission_scores)
                flash(f"Assignment graded automatically! Total score: {total_score}/{assignment[3]}", "success")
        
    except Exception as e:
        gradeai_db.connection.rollback()
        print(f"Error in submission: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f"Error submitting assignment: {str(e)}", "error")

    cursor.close()
    return redirect(url_for("assignment_submit_student",
                            course_code=course_code,
                            course_name=assignment[2], 
                            assignment_id=assignment_id))




@app.route('/edit_email', methods=['GET', 'POST'])
@login_required
def edit_email():
    if request.method == 'POST':
        new_email = request.form.get('new_email')
        cursor = gradeai_db.connection.cursor()
        try:
            # Check if email already exists
            cursor.execute("SELECT user_id FROM users WHERE email = %s AND user_id != %s", 
                         (new_email, current_user.user_id))
            if cursor.fetchone():
                flash('Email already in use by another account', 'error')
                return redirect(url_for('edit_email'))
            
            # Update email
            cursor.execute("UPDATE users SET email = %s WHERE user_id = %s",
                         (new_email, current_user.user_id))
            gradeai_db.connection.commit()
            flash('Email updated successfully', 'success')
            
            # Redirect based on user role
            user_role = role_parser(current_user.email)
            if isinstance(user_role, bytes):
                user_role = int.from_bytes(user_role, byteorder='big')
            
            if user_role == 1:
                return redirect(url_for('profile_teacher'))
            else:
                return redirect(url_for('profile_student'))
                
        except Exception as e:
            gradeai_db.connection.rollback()
            flash('Error updating email', 'error')
            return redirect(url_for('edit_email'))
        finally:
            cursor.close()
            
    return render_template('edit_email.html')

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

#LOOK AGAIN
@app.route('/course_grades_student/<course_name>/<course_code>')
@login_required
def course_grades_student(course_name, course_code):
    cursor = gradeai_db.connection.cursor()
    cursor.execute("""
        SELECT a.title, g.score, g.feedback, 
               g.adjusted_at , c.name , 
               c.class_id 
        FROM grade g 
        JOIN submission s ON g.submission_id = s.submission_id 
        JOIN assignment a ON s.assignment_id = a.assignment_id 
        JOIN class c ON a.class_id = c.class_id 
        WHERE s.student_id = %s
        ORDER BY g.adjusted_at DESC
    """, (current_user.user_id,))
    grades = cursor.fetchall()
    cursor.close()
    return render_template("course_grades_student.html",
                           grades=grades,
                           course_name=course_name,
                           course_code=course_code)


if __name__ == "__main__":
    app.run(debug=True)

