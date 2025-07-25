from flask import Flask, render_template, url_for, request, redirect, flash, jsonify, send_from_directory, abort, get_flashed_messages
from flask_mysqldb import MySQL
from flask_login import *
from helpers import *
from classes import *
import os
from werkzeug.utils import secure_filename
import datetime
from flask_mail import Mail, Message
import json
import shutil

app = Flask(__name__)
app.config["SECRET_KEY"] = "CANSU_BÜŞRA_ORHAN_SUPER_SECRET_KEY"  # os.environ.get("SECRET_KEY")
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'gradia.website@gmail.com'
app.config['MAIL_PASSWORD'] = 'ivln hvqr pfnm zudw'
app.config['MAIL_DEFAULT_SENDER'] = 'gradia.website@gmail.com'
app.config['SECUIRTY_PASSWORD_SALT'] = 'gradia_salt'

# Database
app.config['MYSQL_HOST'] = '127.0.0.1'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'gradeai'

# Login
login_manager = LoginManager()

gradeai_db = MySQL(app)
login_manager.init_app(app)
grading_assistant = GradingAssistant()
mail = Mail(app)


# Create directories if they don't exist
os.makedirs(ASSIGNMENT_SUBMISSIONS_DIR, exist_ok=True)
os.makedirs(ASSIGNMENT_FILES_DIR, exist_ok=True)
os.makedirs(PROFILE_PICS_DIR, exist_ok=True)
os.makedirs(ANNOUNCEMENT_FILES_DIR, exist_ok=True)
os.makedirs(ENROLLMENTS_FILES_DIR, exist_ok=True)

@app.route('/forgot_password', methods=["GET", "POST"])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')

        if not email:
            print('Please enter your email address.', 'error')
            return render_template('forgot_password.html')
        cursor = gradeai_db.connection.cursor()
        cursor.execute("SELECT user_id, first_name FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        if user:
            try:
                token = generate_reset_token(app, email)
                reset_url = url_for('new_password', token=token, _external=True)
                send_password_reset_email(email, user[1], reset_url)
                print('If the email is registered, a password reset link has been sent to your email address.', 'info')
            except Exception as e:
                app.logger.error(f"Error sending email: {str(e)}")
                print('There was an error sending the email. Please try again later.', 'error')
                return render_template('forgot_password.html')
        else:
            print('If the email is registered, a password reset link has been sent to your email address.', 'info')
        
        cursor.close()
        return redirect(url_for('login'))
    
    return render_template('forgot_password.html')

@app.route('/new_password/<token>', methods=["GET", "POST"])
def new_password(token):
    email = verify_reset_token(app, token)
    if not email:
        print('The password reset link is invalid or has expired.', 'error')
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if new_password != confirm_password:
            print('Passwords do not match.', 'error')
            return render_template("new_password.html", token=token)

        cursor = gradeai_db.connection.cursor()
        try:
            change_password(cursor, email, new_password)
            gradeai_db.connection.commit()
            print('Your password has been reset successfully.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            app.logger.error(f"Error resetting password: {str(e)}")
            print('An error occurred while resetting your password. Please try again.', 'error')
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

@app.route('/edit_email', methods=["GET", "POST"])
@login_required
def edit_email():
    if request.method == 'POST':
        new_email = request.form.get('new_email')
        if not new_email:
            flash('Please enter a new email address.', 'error')
            return render_template('edit_email.html')
        
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, new_email):
            flash('Please enter a valid email address.', 'error')
            return render_template('edit_email.html')
        
        # Check if the new email is the same as current email
        if new_email == current_user.email:
            flash('This is already your current email address.', 'info')
            return render_template('edit_email.html')
        
        cursor = gradeai_db.connection.cursor()
        
        # Check if email is already registered
        cursor.execute("SELECT user_id FROM users WHERE email = %s AND user_id != %s", (new_email, current_user.user_id))
        existing_user = cursor.fetchone()
        
        if existing_user:
            flash('This email address is already registered. Please use a different email address.', 'error')
            cursor.close()
            return render_template('edit_email.html')
        
        try:
            # Generate confirmation token
            token = generate_email_change_token(app, current_user.user_id, new_email)
            confirmation_url = url_for('confirm_email_change', token=token, _external=True)
            
            # Send confirmation email to new email address
            send_email_change_confirmation(new_email, current_user.first_name, confirmation_url)
            
            flash(f'A confirmation email has been sent to {new_email}. Please check your email and click the confirmation link to complete the email change.', 'info')
            
        except Exception as e:
            app.logger.error(f"Error sending confirmation email: {str(e)}")
            flash('There was an error sending the confirmation email. Please try again later.', 'error')
            return render_template('edit_email.html')
        finally:
            cursor.close()
        
        # Redirect to profile page based on user role
        user_role = role_parser(current_user.email)
        if isinstance(user_role, bytes):
            user_role = int.from_bytes(user_role, byteorder='big')
        
        if user_role == 1:
            return redirect(url_for('profile_teacher'))
        else:
            return redirect(url_for('profile_student'))
    
    return render_template('edit_email.html')

@app.route('/confirm_email_change/<token>')
def confirm_email_change(token):
    email_change_data = verify_email_change_token(app, token)
    
    if not email_change_data:
        flash('The email confirmation link is invalid or has expired (24 hours).', 'error')
        return redirect(url_for('login'))
    
    user_id, new_email = email_change_data
    
    cursor = gradeai_db.connection.cursor()
    
    try:
        # Double-check that the email is still not taken
        cursor.execute("SELECT user_id FROM users WHERE email = %s AND user_id != %s", (new_email, user_id))
        existing_user = cursor.fetchone()
        
        if existing_user:
            flash('This email address is already registered. Email change cancelled.', 'error')
            return redirect(url_for('login'))
        
        # Update the user's email
        cursor.execute("UPDATE users SET email = %s WHERE user_id = %s", (new_email, user_id))
        gradeai_db.connection.commit()
        
        flash('Your email address has been successfully updated!', 'success')
        
        # If user is logged in, redirect to their profile
        if current_user.is_authenticated and current_user.user_id == user_id:
            user_role = role_parser(new_email)  # Use new email for role check
            if isinstance(user_role, bytes):
                user_role = int.from_bytes(user_role, byteorder='big')
            
            if user_role == 1:
                return redirect(url_for('profile_teacher'))
            else:
                return redirect(url_for('profile_student'))
        else:
            return redirect(url_for('login'))
            
    except Exception as e:
        app.logger.error(f"Error updating email: {str(e)}")
        gradeai_db.connection.rollback()
        flash('An error occurred while updating your email. Please try again.', 'error')
        return redirect(url_for('login'))
    finally:
        cursor.close()

def send_email_change_confirmation(to_email, first_name, confirmation_url):
    """Send email change confirmation email"""
    msg = Message(
        "Gradia - Email Change Confirmation",
        sender=app.config['MAIL_DEFAULT_SENDER'],
        recipients=[to_email]
    )
    
    msg.html = f"""
    <html>
    <body>
        <h2>Email Change Confirmation</h2>
        <p>Hello {first_name},</p>
        <p>You requested to change your Gradia email address to this email. Click the link below to confirm:</p>
        <a href="{confirmation_url}" style="background-color: #1a73e8; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px;">Confirm Email Change</a>
        <p><strong>This link expires in 24 hours.</strong></p>
        <p>If you didn't request this change, please ignore this email and contact support if you have concerns.</p>
        <br>
        <p>Best regards,<br>The Gradia Team</p>
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
        _ = get_flashed_messages()
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
    
    f = request.files['fileInput']
    
    if f.filename == '':
        flash('No file selected', 'danger')
        return render_template('blockview_teacher.html', 
                             course_name=course_name, 
                             course_code=course_code, 
                             enrolled_students=current_students,
                             temp_students_json=temp_students_json)
    
    if not f.filename.lower().endswith('.csv'):
        flash('Please upload a CSV file', 'danger')
        return render_template('blockview_teacher.html', 
                             course_name=course_name, 
                             course_code=course_code, 
                             enrolled_students=current_students,
                             temp_students_json=temp_students_json)
    
    try:
        # Save the uploaded file temporarily
        filename = secure_filename(f.filename)
        temp_path = os.path.join(ENROLLMENTS_FILES_DIR, filename)
        os.makedirs(ENROLLMENTS_FILES_DIR, exist_ok=True)
        f.save(temp_path)
        
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
                print(f'Failed to remove student {student_to_remove}', 'danger')
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


@app.route('/announcement_teacher/<course_name>/<course_code>')
@login_required
def announcement_teacher(course_name, course_code):
    cursor = gradeai_db.connection.cursor()
    announcements = fetch_recent_class_announcements(cursor, course_code)
    
    announcements_with_files = []
    for announcement in announcements:
        announcement_dict = {
            'id': announcement[0],
            'content': announcement[1], 
            'date': announcement[2],
            'title': announcement[3],
            'files': get_files('announcement', course_code, announcement[3])
        }
        announcements_with_files.append(announcement_dict)
    
    cursor.close()
    return render_template("announcement_teacher.html",
                         course_name=course_name,
                         course_code=course_code,
                         announcements=announcements_with_files)

@app.route('/announcement_delete/<course_name>/<course_code>/<announcement_id>/<title>')
@login_required
def announcement_delete(course_name, course_code, announcement_id, title):
    cursor = gradeai_db.connection.cursor()
    _ = delete_announcement(cursor, announcement_id)
    shutil.rmtree(os.path.join(ANNOUNCEMENT_FILES_DIR, course_code, title))
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

        existing_announcement = create_announcement(cursor, course_code, title, desc)
        if existing_announcement == "THERE IS SOMETHING":
            flash("This announcement is already exist!")
            return redirect(url_for("announcement_teacher", course_name = course_name, course_code = course_code))
        save_files(attachments, "announcements", course_code, title)

        gradeai_db.connection.commit()
        cursor.close()

        return redirect(url_for('announcement_teacher', course_name=course_name, course_code=course_code))

    return render_template("announcement_view_teacher.html", course_name=course_name, course_code=course_code)


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

@app.route('/assignment_creation/<course_code>', methods=['GET', 'POST'])
@login_required
def assignment_creation(course_code):
    cursor = gradeai_db.connection.cursor()
    
    # Get course name
    course_name = get_course_name(cursor, course_code)
    if not course_name:
        print("Course not found", "error")
        cursor.close()
        return redirect(url_for('teacher_dashboard'))
    
    # Initialize form data
    form_data = {
        'title': '',
        'description': '',
        'due_date': '',
        'file_type': 'Any',
        'rubrics': [{'description': '', 'points': 0}],
        'uploaded_files': []
    }
    
    # Get today's date for min datetime
    today = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M')
    
    if request.method == 'POST':
        action = request.form.get('action', 'create_assignment')
        
        # Preserve form data
        form_data.update({
            'title': request.form.get('title', ''),
            'description': request.form.get('description', ''),
            'due_date': request.form.get('Date', ''),
            'file_type': request.form.get('file_type', 'Any')
        })
        
        # Get rubric data
        rubric_descriptions = request.form.getlist('rubric_descriptions[]')
        rubric_values = request.form.getlist('rubric_values[]')
        
        # Build rubrics list
        form_data['rubrics'] = []
        for i, (desc, val) in enumerate(zip(rubric_descriptions, rubric_values)):
            try:
                points = int(val) if val else 0
            except ValueError:
                points = 0
            form_data['rubrics'].append({
                'description': desc.strip(),
                'points': points
            })
        
        # Handle different actions
        if action == 'add_rubric':
            form_data['rubrics'].append({'description': '', 'points': 0})
            
        elif action.startswith('remove_rubric_'):
            try:
                index = int(action.split('_')[-1])
                if 0 <= index < len(form_data['rubrics']) and len(form_data['rubrics']) > 1:
                    form_data['rubrics'].pop(index)
            except (ValueError, IndexError):
                flash("Error removing rubric", "error")
                
        elif action == 'generate_rubric':
            description = form_data['description'].strip()
            
            if len(description) < 10:
                flash("Please enter a more detailed assignment description for meaningful rubric generation.", "error")
            else:
                try:
                    # Prepare existing rubrics for the grading assistant
                    current_rubrics = []
                    current_points = []
                    
                    for rubric in form_data['rubrics']:
                        if rubric['description'].strip() and rubric['points'] > 0:
                            current_rubrics.append(rubric['description'].strip())
                            current_points.append(rubric['points'])
                    
                    total_existing = sum(current_points)
                    
                    if total_existing >= 100:
                        flash("All 100 points have been allocated. No additional rubrics needed.", "info")
                    else:
                        # Generate rubrics using the grading assistant
                        grading_assistant.create_rubric_instructions(current_rubrics, current_points)
                        grading_assistant.consume_question(description)
                        
                        llm_output = grading_assistant.generate_rubric()
                        
                        if llm_output:
                            # Clear existing rubrics and rebuild with existing + new
                            new_rubrics = []
                            
                            # Add existing rubrics back
                            for desc, points in zip(current_rubrics, current_points):
                                new_rubrics.append({'description': desc, 'points': points})
                            
                            # Add generated rubrics
                            generated_count = 0
                            for item in llm_output:
                                try:
                                    points = int(item["rubric_score"])
                                    new_rubrics.append({
                                        'description': item["rubric_desc"],
                                        'points': points
                                    })
                                    generated_count += 1
                                except (ValueError, KeyError) as e:
                                    print(f"Error processing rubric item: {e}")
                                    continue
                            
                            form_data['rubrics'] = new_rubrics
                            
                            if generated_count > 0:
                                total_new_points = sum(int(item["rubric_score"]) for item in llm_output)
                                flash(f"Successfully generated {generated_count} new rubric(s) worth {total_new_points} points.", "success")
                            else:
                                flash("Could not generate rubric suggestions. Please try again.", "warning")
                        else:
                            flash("Could not generate rubric suggestions. Please try again.", "warning")
                            
                except Exception as e:
                    print(f"Error generating rubrics: {e}")
                    flash("An error occurred while generating rubrics. Please try again.", "error")
        
        elif action == 'create_assignment':
            # Validate form data
            errors = []
            
            if not form_data['title'].strip():
                errors.append("Assignment title is required")
            
            if not form_data['description'].strip():
                errors.append("Assignment description is required")
            
            if not form_data['due_date']:
                errors.append("Due date is required")
            
            # Validate rubrics
            valid_rubrics = []
            total_points = 0
            
            for rubric in form_data['rubrics']:
                if rubric['description'].strip():
                    if rubric['points'] <= 0:
                        errors.append(f"Rubric '{rubric['description'][:30]}...' must have points greater than 0")
                    else:
                        valid_rubrics.append(rubric)
                        total_points += rubric['points']
            
            if not valid_rubrics:
                errors.append("At least one rubric is required")
            
            if total_points != 100:
                errors.append(f"Total rubric points must equal 100. Currently: {total_points} points")
            
            # Validate due date
            try:
                due_date = datetime.datetime.strptime(form_data['due_date'], '%Y-%m-%dT%H:%M')
                if due_date <= datetime.datetime.now():
                    errors.append("Due date must be in the future")
            except ValueError:
                errors.append("Invalid due date format")
            
            if errors:
                for error in errors:
                    print(error, "error")
            else:
                try:
                    # Create assignment in database
                    teacher_id = current_user.user_id
                    
                    # Handle file uploads
                    uploaded_files = []
                    if 'attachments' in request.files:
                        files = request.files.getlist('attachments')
                        if files and files[0].filename:
                            assignment_dir = os.path.join(ASSIGNMENT_FILES_DIR, course_code, form_data['title'])
                            os.makedirs(assignment_dir, exist_ok=True)
                            
                            for f in files:
                                if f and f.filename:
                                    filename = secure_filename(f.filename)
                                    file_path = os.path.join(assignment_dir, filename)
                                    f.save(file_path)
                                    uploaded_files.append(filename)

                    # Create assignment
                    assignment_id, existing_assignment = create_assignment(
                        cursor, 
                        form_data['title'], 
                        form_data['description'], 
                        form_data['due_date'],
                        course_code,
                        total_points,
                        form_data['file_type']                
                        )
                    if existing_assignment:
                        flash(f"You cannot create an assignment with this title. An assignment titled '{form_data['title']}' already exists in this course.", "error")
                        return redirect(url_for('assignment_creation', course_code=course_code))
                    
                    # Create rubrics
                    for fold, rubric in enumerate(valid_rubrics):
                        rubric_id = RubricIDManager.create_rubric_id(assignment_id, fold)
                        cursor.execute(""" INSERT INTO rubric (rubric_id, assignment_id, score, description, created_at, created_by)
                                       VALUES (%s, %s, %s, %s, %s, %s)""", (rubric_id, assignment_id, rubric["points"], rubric["description"], datetime.datetime.now(), teacher_id))
                    
                    gradeai_db.connection.commit()
                    cursor.close()
                    
                    print(f"Assignment '{form_data['title']}' created successfully with {len(valid_rubrics)} rubrics totaling {total_points} points!", "success")
                    return redirect(url_for('view_assignments', course_code=course_code))
                    
                except Exception as e:
                    gradeai_db.connection.rollback()
                    print(f"Error creating assignment: {e}")
                    flash("An error occurred while creating the assignment. Please try again.", "error")
                    return redirect(url_for("assignment_creation", course_code = course_code))
    
    # Ensure at least one rubric entry exists
    if not form_data['rubrics'] or all(not r['description'].strip() and r['points'] == 0 for r in form_data['rubrics']):
        form_data['rubrics'] = [{'description': '', 'points': 0}]
    
    cursor.close()
    
    return render_template('assignment_creation.html',
                         course_code=course_code,
                         course_name=course_name,
                         today=today,
                         **form_data)

# Helper route for the original generate_rubric endpoint (for API compatibility)
@app.route('/generate_rubric', methods=["POST"])
@login_required
def generate_rubric():
    current_rubrics, current_points = [], []
    data = request.get_json()
    
    if not data or 'description' not in data:
        return jsonify({'error': 'Missing assignment description'}), 400
    
    description = data.get('description', '')
    existing_rubrics = data.get('existing_rubrics', [])
    
    if existing_rubrics:
        for entry in existing_rubrics:
            current_rubrics.append(entry["description"])
            current_points.append(entry["points"])
    
    grading_assistant.create_rubric_instructions(current_rubrics, current_points)
    grading_assistant.consume_question(description)
    
    if len(description.strip()) < 10:
        return jsonify({'error': 'Description too short for meaningful rubric generation'}), 400
    
    try:
        llm_output = grading_assistant.generate_rubric()
        rubric_items = [
            {"description": item["rubric_desc"], "points": int(item["rubric_score"])}
            for item in llm_output
        ]
        
        return jsonify({
            'success': True,
            'rubric_items': rubric_items
        })
    except Exception as e:
        return jsonify({'error': f'Error generating rubric: {str(e)}'}), 500


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
               c.class_id as course_code, a.deadline
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
                           course_code=course_code,
                           current_time = datetime.datetime.now())


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
                    create_submission(cursor, assignment_id, current_user.user_id, f)
                    
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
        }, 
        'file_type': assignment_data[-1]
    }
    
    cursor.close()
    return render_template("assignment_submit_student.html",
                           assignment=assignment,
                           course_code=course_code,
                           course_name=course_name,
                           current_datetime=datetime.datetime.now())


@app.route('/assignment_view_teacher/<course_code>/<assignment_id>')
@login_required
def assignment_view_teacher(course_code, assignment_id):
    cursor = gradeai_db.connection.cursor()

    # Get assignment details
    assignment = get_assignment_details(cursor, assignment_id, course_code)
    if not assignment:
        print("Assignment not found", "error")
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
            print('No file part', 'error')
            return redirect(url_for('edit_image'))
        
        f = request.files['profile_image']

        if f.filename == '':
            print('No selected file', 'error')
            return redirect(url_for('edit_image'))
        
        # Check file extension
        if not allowed_file(f.filename):
            print('Invalid file type. Please upload a PNG, JPG, or JPEG image.', 'error')
            return redirect(url_for('edit_image'))
        
        if f.content_type not in ['image/png', 'image/jpeg', 'image/jpg']:
            app.logger.warning(f"Invalid MIME type: {f.content_type}")
            print('Invalid file type. Please upload a PNG, JPG, or JPEG image.', 'error')
            return redirect(url_for('edit_image'))
        
        try:
            # Read file content to check size
            file_content = f.read()
            f.seek(0)  # Reset file pointer
            
            # Check file size (limit 5MB = 5*1024*1024 bytes)
            if len(file_content) > 5*1024*1024:
                print('File size exceeds the limit of 5MB. Please upload a smaller file.', 'error')
                return redirect(url_for('edit_image'))

            # Generate unique filename
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            unique_filename = f"{current_user.user_id}_{timestamp}_{secure_filename(f.filename)}"
            
            # Create the profile pics directory if it doesn't exist
            os.makedirs(PROFILE_PICS_DIR, exist_ok=True)
            
            # Delete old profile picture if it exists
            old_pic = fetch_profile_picture(None, current_user.user_id)
            if old_pic:
                old_path = os.path.join('static', old_pic)
                if os.path.exists(old_path):
                    try:
                        os.remove(old_path)
                        app.logger.info(f"Successfully deleted old profile picture at: {old_path}")
                    except Exception as e:
                        app.logger.warning(f"Could not delete old profile picture: {str(e)}")
            
            # Save the new file
            file_path = os.path.join(PROFILE_PICS_DIR, unique_filename)
            f.save(file_path)
            
            # Verify file was saved
            if not os.path.exists(file_path):
                raise Exception(f"Failed to save file at {file_path}")
            
            app.logger.info(f"File saved successfully at: {file_path}")
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
            flash('Failed to update profile picture. Please try again.', 'error')
            return redirect(url_for('edit_image'))
    
    # If GET request, render the edit image page
    user_role = role_parser(current_user.email)
    if isinstance(user_role, bytes):
        user_role = int.from_bytes(user_role, byteorder='big')

    profile_pic = fetch_profile_picture(None, current_user.user_id)
    return render_template("edit_image.html", user_role=user_role, profile_pic=profile_pic)

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


@app.route('/download/<course_code>/<assignment_id>/<user_id>/<filename>')
@login_required
def download_submission(course_code, assignment_id, user_id, filename):
    try:
        cursor = gradeai_db.connection.cursor()

        assignment = get_assignment_details(cursor, assignment_id, None) # PLEASE DON'T DELETE NONE PART
        cursor.close()
        
        if not assignment:
            abort(404)
        
        submission_dir = os.path.join(ASSIGNMENT_SUBMISSIONS_DIR, course_code, assignment[1], user_id)
        return send_from_directory(submission_dir, filename, as_attachment=True)
    except FileNotFoundError:
        abort(404)
        

@app.route('/submit_assignment/<course_code>/<course_name>/<assignment_id>', methods=['POST'])
@login_required
def submit_assignment(course_code, course_name, assignment_id):
    cursor = gradeai_db.connection.cursor()
    assignment = get_assignment_details(cursor, assignment_id, None)
    if not assignment:
        flash("Assignment not found", "error")
        cursor.close()
        return redirect(url_for("assignments_student", course_code=course_code, course_name=course_name))

    assignment_title = assignment[1]
    # Get file type requirement (assuming it's the last element in assignment tuple)
    file_type_requirement = assignment[-1] if len(assignment) > 4 else None

    submission_dir_student = os.path.join(ASSIGNMENT_SUBMISSIONS_DIR, course_code, assignment[1], current_user.user_id)
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
        if os.path.exists(os.path.join(ASSIGNMENT_SUBMISSIONS_DIR, course_code, assignment_title, current_user.user_id, delete_file)):
            shutil.rmtree(os.path.join(ASSIGNMENT_SUBMISSIONS_DIR, course_code, assignment_title, current_user.user_id, delete_file))
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
        for submission in submissions:
            cursor.execute("DELETE FROM grade WHERE submission_id = %s", (submission[0], ))
        
        delete_submissions(cursor, current_user.user_id, assignment_id)
        gradeai_db.connection.commit()
        if os.path.exists(submission_dir_student):
            try:
                for filename in os.listdir(submission_dir_student):
                    file_path = os.path.join(submission_dir_student, filename)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
            except Exception as e:
                print(f"Error deleting files: {e}")

        gradeai_db.connection.commit()
        shutil.rmtree(os.path.join(ASSIGNMENT_SUBMISSIONS_DIR, course_code, assignment_title, current_user.user_id))
        cursor.close()
        return redirect(url_for("assignment_submit_student", 
                               course_code=course_code, 
                               course_name=course_name, 
                               assignment_id=assignment_id))

    # Handle new submission 
    f = request.files.get('file')  # Changed from getlist to get single file
    if not f or not f.filename:
        flash("Please select a file to submit", "error")
        cursor.close()
        return redirect(url_for("assignment_submit_student",
                                course_code=course_code,
                                course_name=assignment[2],
                                assignment_id=assignment_id))
    
    # VALIDATE FILE TYPE
    filename = secure_filename(f.filename)
    file_extension = filename.split(".")[-1].lower() if "." in filename else ""
    
    # Check if file type matches requirement
    if file_type_requirement:
        if file_type_requirement.upper() == 'PDF' and file_extension != 'pdf':
            flash("Only PDF files are allowed for this assignment", "error")
            cursor.close()
            return redirect(url_for("assignment_submit_student",
                                    course_code=course_code,
                                    course_name=assignment[2],
                                    assignment_id=assignment_id))
        elif file_type_requirement.upper() == 'DOCX' and file_extension != 'docx':
            flash("Only DOCX files are allowed for this assignment", "error")
            cursor.close()
            return redirect(url_for("assignment_submit_student",
                                    course_code=course_code,
                                    course_name=assignment[2],
                                    assignment_id=assignment_id))
        elif file_type_requirement.upper() not in ['PDF', 'DOCX'] and file_extension not in ['pdf', 'docx']:
            flash("Only PDF or DOCX files are allowed for this assignment", "error")
            cursor.close()
            return redirect(url_for("assignment_submit_student",
                                    course_code=course_code,
                                    course_name=assignment[2],
                                    assignment_id=assignment_id))
    
    try:
        # Create submission directory using correct path
        submission_dir = os.path.join(ASSIGNMENT_SUBMISSIONS_DIR, course_code, assignment_title, str(current_user.user_id))
        os.makedirs(submission_dir, exist_ok=True)

        # Delete any existing files in the submission directory before saving new one
        if os.path.exists(submission_dir):
            try:
                for existing_file in os.listdir(submission_dir):
                    file_path = os.path.join(submission_dir, existing_file)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
            except Exception as e:
                print(f"Error deleting existing files: {e}")

        # Save the single file
        file_path = os.path.join(submission_dir, filename)
        f.save(file_path)
        
        submission_id = SubmissionIDManager.create_submission_id(
            assignment_id, current_user.user_id, filename
        )

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

        # Create new submission
        create_submission(cursor, assignment_id, current_user.user_id, filename)

        gradeai_db.connection.commit()

        # AUTO-GRADING PROCESS
        print("Debug - Starting auto-grading process")
        
        # Get rubrics for this assignment
        db_rubrics = get_rubrics(cursor, assignment_id)
        if not db_rubrics:
            print("Debug - No rubrics found for assignment")
            print("Warning: No grading rubrics found for this assignment", "warning")
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
            
            # Grade the single file
            try:
                # Grade the file using the grading assistant
                submission_score = grading_assistant.grade_file(file_path, file_extension, rubrics)
                print(f"Debug - Grading result: {submission_score}")
                # Add grade into DB
                create_grade(cursor, submission_id, submission_score, "This submission is graded by system!", teacher_id)
                
                gradeai_db.connection.commit()
                print(f"Debug - Auto-grading completed. Score: {submission_score}")
                
                print(f"Assignment graded automatically! Score: {submission_score}/{assignment[3]}", "success")
                
            except Exception as grading_error:
                print(f"Error grading file {filename}: {grading_error}")
                print(f"Error grading {filename}: {str(grading_error)}", "warning")
                
                # Create grade entry with score value of 0
                create_grade(cursor, submission_id, 0, "This submission is graded by system!", teacher_id)
                gradeai_db.connection.commit()
        
    except Exception as e:
        gradeai_db.connection.rollback()
        print(f"Error in submission: {str(e)}")
        import traceback
        traceback.print_exc()
        print(f"Error submitting assignment: {str(e)}", "error")

    cursor.close()
    return redirect(url_for("assignment_submit_student",
                            course_code=course_code,
                            course_name=assignment[2], 
                            assignment_id=assignment_id))




@app.route('/upload_profile_pic', methods=['POST'])
@login_required
def upload_profile_pic():
    if 'profile_pic' not in request.files:
        print('No file selected', 'error')
        return redirect(request.referrer)

    f = request.files['profile_pic']
    if f.filename == '':
        print('No file selected', 'error')
        return redirect(request.referrer)

    if f and allowed_file(f.filename):
        # Create uploads directory if it doesn't exist
        upload_dir = os.path.join('static', 'uploads', 'profile_pics')
        os.makedirs(upload_dir, exist_ok=True)

        # Delete old profile picture if it exists
        old_pic = fetch_profile_picture(None, current_user.user_id)
        if old_pic:
            old_path = os.path.join('static', old_pic)
            if os.path.exists(old_path):
                try:
                    os.remove(old_path)
                    app.logger.info(f"Successfully deleted old profile picture at: {old_path}")
                except Exception as e:
                    app.logger.warning(f"Could not delete old profile picture: {str(e)}")

        # Generate unique filename
        filename = secure_filename(f"{current_user.user_id}_{f.filename}")
        file_path = os.path.join(upload_dir, filename)

        # Save the file
        f.save(file_path)

        # Update database with profile picture path
        cursor = gradeai_db.connection.cursor()
        cursor.execute("""
            UPDATE users 
            SET profile_pic = %s 
            WHERE user_id = %s
        """, (filename, current_user.user_id))
        gradeai_db.connection.commit()
        cursor.close()

        print('Profile picture updated successfully', 'success')
    else:
        print('Invalid file type. Please upload an image.', 'error')

    return redirect(request.referrer)


def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/update_grade/<submission_id>', methods=['POST'])
@login_required
def update_grade(submission_id):
    cursor = gradeai_db.connection.cursor()
    score = request.form.get('score')
    feedback = request.form.get('feedback')
    
    update_grade_db(cursor, submission_id, score, feedback)
    gradeai_db.connection.commit()
    print("Grade and feedback updated successfully!", "success")
    
    result = get_submission_details(cursor, submission_id)
    
    if result:
        course_code, assignment_id, student_id = result[-2], result[-1], result[5] # not sure tho changed get_submission_details
        cursor.close()
        return redirect(url_for('grade_submission', 
                                course_code=course_code, 
                                assignment_id=assignment_id, 
                                submission_id=submission_id, 
                                student_id=student_id))
    else:
        cursor.close()
        return redirect(url_for("teacher_dashboard"))
            



@app.route('/course_grades_student/<course_name>/<course_code>')
@login_required
def course_grades_student(course_name, course_code):
    cursor = gradeai_db.connection.cursor()
    cursor.execute("""
    SELECT a.title, g.score, g.feedback,
    g.adjusted_at , c.name ,
    c.class_id, s.submitted_at
    FROM grade g
    JOIN submission s ON g.submission_id = s.submission_id
    JOIN assignment a ON s.assignment_id = a.assignment_id
    JOIN class c ON a.class_id = c.class_id
    WHERE s.student_id = %s AND a.deadline <= %s
    ORDER BY g.adjusted_at DESC
    """, (current_user.user_id, datetime.datetime.now(), ))
    grades = cursor.fetchall()
    cursor.close()
    return render_template("course_grades_student.html",
                           grades=grades,
                           course_name=course_name,
                           course_code=course_code)

@app.route('/delete_assignment/<course_code>/<assignment_id>/<title>', methods=['POST'])
@login_required
def delete_assignment_route(course_code, assignment_id, title):
    # Only allow teachers (role == 1)
    user_role = role_parser(current_user.email)
    if isinstance(user_role, bytes):
        user_role = int.from_bytes(user_role, byteorder='big')
    if user_role != 1:
        flash('You are not authorized to delete assignments.', 'error')
        return redirect(url_for('view_assignments', course_code=course_code))

    cursor = gradeai_db.connection.cursor()
    try:
        delete_assignment(cursor, assignment_id)
        gradeai_db.connection.commit()
        shutil.rmtree(os.path.join(ASSIGNMENT_FILES_DIR, course_code, title))
        flash('Assignment deleted successfully.', 'success')
    except Exception as e:
        gradeai_db.connection.rollback()
        print(f'Error deleting assignment: {str(e)}', 'error')
    finally:
        cursor.close()
    return redirect(url_for('view_assignments', course_code=course_code))

if __name__ == "__main__":
    app.run(debug=True)

