from flask import Flask, render_template, url_for, request, session, redirect, flash, jsonify, send_from_directory, abort
from flask_mysqldb import MySQL
from flask_login import *
from helpers import *
from classes import *
import os
from werkzeug.utils import secure_filename
import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from flask_mail import Mail

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
            # Still show success message for security (don't reveal if email exists)
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


# Define upload directories
ASSIGNMENT_SUBMISSIONS_DIR = os.path.join('static', 'uploads', 'submissions')
ASSIGNMENT_FILES_DIR = os.path.join('static', 'uploads', 'assignments')
PROFILE_PICS_DIR = os.path.join('static', 'uploads', 'profile_pics')

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


@login_manager.user_loader
def load_user(user_id):
    cursor = gradeai_db.connection.cursor()
    return User.get(cursor, user_id)


@app.route("/deneme")
def deneme():
    return render_template("deneme.html")


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
        curr_user = User(*user_tuple[0][0: 5])  # password should be ignored
        login_user(curr_user)
        if int.from_bytes(user_tuple[0][5], byteorder='big') == 1:  # in DB it is stored in bits
            del user_tuple
            return redirect(url_for("teacher_dashboard"))

        else:
            del user_tuple
            return redirect(url_for("student_dashboard"))

    else:
        return render_template("login.html")


def confirm_login():
    return


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


@app.route("/home")
@app.route("/")
def logout():
    logout_user()
    return redirect(url_for("index"))

@app.route('/tutorial')
def tutorial():
    return render_template("tutorial.html")


@app.route('/about')
def about():
    return render_template("aboutus.html")


@app.route('/blockview_teacher', methods=["GET", "POST"])
@login_required
def blockview_teacher():
    if request.method == "POST":
        course_name = request.form.get("course_name")
        course_code = request.form.get("course_code")

        cursor = gradeai_db.connection.cursor()

        handle_class_creation(cursor, course_code, course_name, current_user.user_id)

        student_csv_file = request.files.get("fileInput")
        if student_csv_file:
            result = save_and_process_csv(cursor, student_csv_file, course_code)
            print(result)
            if result['success']:
                flash(f"{result['added']} students added successfully.", "success")
                if result['existing'] > 0:
                    flash(f"{result['existing']} students were already enrolled.", "warning")
                if result['not_found'] > 0:
                    flash(f"{result['not_found']} students not found in system.", "error")
            else:
                flash("Error processing CSV file.", "error")

        students_data = request.form.get("studentsData")
        if students_data:
            handle_student_enrollment(cursor, students_data, course_code)

        deleted_students = request.form.get("deleteStudents")
        if deleted_students:
            removed = handle_student_removal(cursor, deleted_students, course_code)
            if removed:
                flash(f"{len(removed)} students removed from the course.", "success")

        gradeai_db.connection.commit()

        enrolled_students = get_enrolled_students(cursor, course_code)
        cursor.close()

        return render_template("blockview_teacher.html",
                               course_name=course_name,
                               course_code=course_code,
                               enrolled_students=enrolled_students)

    return render_template("blockview_teacher.html")


@app.route('/get_student_info/<student_id>', methods=["GET", "POST"])
@login_required
def get_student_info(student_id):
    cursor = gradeai_db.connection.cursor()
    student = fetch_student_info(cursor, student_id)
    cursor.close()
    print("THIS IS STUDENT: ", student)

    if student["success"]:
        return jsonify({
            "success": True,
            "firstName": student["first_name"],
            "lastName": student["last_name"]
        })
    else:
        return jsonify({
            "success": False,
            "message": student.get("message", "Student not found")
        })


@app.route('/student_dashboard')
@login_required
def student_dashboard():
    cursor = gradeai_db.connection.cursor()
    courses_and_instructors = fetch_enrollments(cursor, current_user.user_id)
    upcoming_deadlines = fetch_upcoming_deadlines(cursor, current_user.user_id, 0)
    recent_feedback = fetch_recent_feedback(cursor, current_user.user_id, 0)
    recent_announcements = fetch_recent_announcements(cursor, current_user.user_id, 0)
    profile_pic = fetch_profile_picture(cursor, current_user.user_id)
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
    profile_pic = fetch_profile_picture(cursor, current_user.user_id)
    cursor.close()
    return render_template("teacher_dashboard.html",
                           courses=courses,
                           upcoming_deadlines=upcoming_deadlines,
                           recent_feedback=recent_feedback,
                           recent_announcements=recent_announcements,
                           total_student_dict=total_student_dict,
                           profile_pic=profile_pic)


@app.route('/announcement_student/<course_code>/<course_name>/<announcement_id>')
@login_required
def announcement_student(course_code, course_name, announcement_id):
    cursor = gradeai_db.connection.cursor()
    attachments = []

    cursor.execute("""
        SELECT announcement_id, content, posted_at
        FROM announcement
        WHERE announcement_id = %s AND class_id = %s
    """, (announcement_id, course_code))
    announcement = cursor.fetchone()

    folder_name = announcement_id.split("_")[1]
    file_dir = os.path.join(app.root_path, "static", "uploads", "announcements", course_code, folder_name)

    if os.path.exists(file_dir):
        for filename in os.listdir(file_dir):
            attachments.append(filename)

    cursor.close()

    return render_template('announcement_student.html',
                           course_code=course_code,
                           course_name=course_name,
                           announcement=announcement,
                           attachments=attachments,
                           folder_name=folder_name)


@app.route('/announcement_view_student/<course_name>/<course_code>')
@login_required
def announcement_view_student(course_name, course_code):
    cursor = gradeai_db.connection.cursor()
    cursor.execute("""
        SELECT announcement_id, class_id, content, posted_at
        FROM announcement
        WHERE class_id = %s
        ORDER BY posted_at DESC
    """, (course_code,))
    announcements = cursor.fetchall()
    print(announcements)
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
    cursor.close()
    return render_template("announcement_teacher.html",
                           course_name=course_name,
                           course_code=course_code,
                           announcements=announcements)


@app.route('/announcement_edit/<course_name>/<course_code>/<announcement_id>', methods=["GET", "POST"])
@login_required
def announcement_edit(course_name, course_code, announcement_id):
    if request.method == "POST":
        cursor = gradeai_db.connection.cursor()
        title = request.form.get("title")
        description = request.form.get("description")
        attachments = request.files.get("attachments")

        cursor.execute('''
            UPDATE Announcement
            SET content = %s
            WHERE announcement_id = %s AND class_id = %s
        ''', (description, announcement_id, course_code))

        gradeai_db.connection.commit()
        cursor.close()

        return redirect(url_for('announcement_teacher', course_name=course_name, course_code=course_code))

    cursor = gradeai_db.connection.cursor()
    cursor.execute('''
        SELECT content
        FROM announcement
        WHERE announcement_id = %s AND class_id = %s
    ''', (announcement_id, course_code))
    announcement = cursor.fetchone()
    cursor.close()

    if not announcement:
        return redirect(url_for('announcement_teacher', course_name=course_name, course_code=course_code))

    return render_template("announcement_edit.html",
                           course_name=course_name,
                           course_code=course_code,
                           announcement_id=announcement_id,
                           content=announcement[0])


@app.route('/announcement_delete/<course_name>/<course_code>/<announcement_id>')
@login_required
def announcement_delete(course_name, course_code, announcement_id):
    cursor = gradeai_db.connection.cursor()
    cursor.execute('''
        DELETE FROM Announcement
        WHERE announcement_id = %s AND class_id = %s
    ''', (announcement_id, course_code))

    gradeai_db.connection.commit()
    cursor.close()

    return redirect(url_for('announcement_teacher', course_name=course_name, course_code=course_code))


@app.route('/announcement_view_teacher/<course_name>/<course_code>', methods=["GET", "POST"])
@login_required
def announcement_view_teacher(course_name, course_code):
    if request.method == "POST":
        cursor = gradeai_db.connection.cursor()
        title = request.form.get("title")
        desc = request.form.get("description")
        attachments = request.files.getlist("attachments")

        create_announcement(cursor, course_code, title, desc)
        save_announcement(attachments, course_code, title)

        # Create notifications for all students
        notify_students_about_announcement(cursor, course_code, title, desc)

        gradeai_db.connection.commit()
        cursor.close()

        return redirect(url_for('announcement_teacher', course_name=course_name, course_code=course_code))

    return render_template("announcement_view_teacher.html", course_name=course_name, course_code=course_code)


@app.route('/assignments/<course_code>')
@login_required
def view_assignments(course_code):
    cursor = gradeai_db.connection.cursor()

    # Get course name
    course = get_course_name(cursor, course_code)
    if not course:
        flash("Course not found", "error")
        return redirect(url_for("teacher_dashboard"))

    # Get all assignments for this course
    assignments = get_course_assignments(cursor, course_code)

    cursor.close()

    return render_template("assignments.html",
                           course_name=course[0],
                           course_code=course_code,
                           assignments=assignments)


@app.route('/assignment_creation/<course_code>', methods=["GET", "POST"])
@login_required
def assignment_creation(course_code):
    if request.method == "POST":
        cursor = gradeai_db.connection.cursor()
        assignment_title = request.form.get("title")
        assignment_desc = request.form.get("description")
        assignment_files = request.files.getlist("attachments")
        deadline = request.form.get("Date")
        rubric_descs, rubric_vals = request.form.getlist("rubric_descriptions[]"), request.form.getlist(
            "rubric_values[]")
        total_score = sum([int(i) for i in rubric_vals])

        save_files(assignment_files, course_code, assignment_title)
        assignment_id = create_assignment(cursor, assignment_title, assignment_desc, deadline, course_code, total_score)
        zip_to_rubric(cursor, zip(rubric_descs, rubric_vals), current_user.user_id, course_code, assignment_title, assignment_id)

        # Create notifications for all students
        #deadline_datetime = datetime.datetime.strptime(deadline, "%Y-%m-%dT%H:%M")
        #notify_students_about_assignment(cursor, course_code, assignment_title, deadline_datetime)

        gradeai_db.connection.commit()
        cursor.close()

        flash("Assignment created successfully", "success")
        return redirect(url_for("view_assignments", course_code=course_code))

    cursor = gradeai_db.connection.cursor()
    cursor.execute("SELECT name FROM class WHERE class_id = %s", (course_code,))
    course = cursor.fetchone()
    cursor.close()

    if not course:
        flash("Course not found", "error")
        return redirect(url_for("teacher_dashboard"))

    return render_template("assignment_creation.html",
                           course_name=course[0],
                           course_code=course_code,
                           today = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M'))

@app.route('/generate_rubric', methods=["POST"])
@login_required
def generate_rubric():
    """
    API endpoint to generate rubric suggestions based on assignment description.
    Expects JSON with 'description' and optional 'course_type' fields.
    Returns JSON array of suggested rubric items.
    """
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
    # Don't generate for very short descriptions
    if len(description.strip()) < 10:
        return jsonify({'error': 'Description too short for meaningful rubric generation'}), 400
    
    # Generate rubric suggestions
    llm_output = grading_assistant.generate_rubric()
    rubric_items = [
        {"description": item["rubric_desc"], "points": int(item["rubric_score"])}
        for item in llm_output
    ]
    return jsonify({
        'success': True,
        'rubric_items': rubric_items
    })


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


@app.route('/assignments_student/<course_code>/<course_name>')
@login_required
def assignments_student(course_code, course_name):
    cursor = gradeai_db.connection.cursor()
    cursor.execute("""
        SELECT a.assignment_id, a.title, a.description, a.deadline,
               CASE WHEN s.submission_id IS NOT NULL THEN 1 ELSE 0 END as is_submitted
        FROM assignment a
        LEFT JOIN submission s ON a.assignment_id = s.assignment_id 
            AND s.student_id = %s
        WHERE a.class_id = %s
        ORDER BY a.deadline ASC
    """, (current_user.user_id, course_code))
    assignments = cursor.fetchall()
    cursor.close()

    return render_template("assignments_student.html",
                           course_name=course_name,
                           course_code=course_code,
                           assignments=assignments)


@app.route('/assignment_submit_student/<course_code>/<course_name>/<assignment_id>', methods = ["GET", "POST"])
@login_required
def assignment_submit_student(course_code, course_name, assignment_id):
    os.makedirs(os.path.join(ASSIGNMENT_SUBMISSIONS_DIR, course_code, assignment_id.split("_")[1], current_user.user_id), exist_ok = 1)
    cursor = gradeai_db.connection.cursor()
    files = []


    # Get assignment details
    cursor.execute("""
        SELECT a.assignment_id, a.title, a.description, a.deadline, 
            a.total_score, c.name as course_name
        FROM assignment a
        JOIN class c ON a.class_id = c.class_id
        WHERE a.assignment_id = %s AND a.class_id = %s
        """, (assignment_id, course_code))
    assignment_data = cursor.fetchone() 
    
    if not assignment_data:
        flash("Assignment not found", "error")
        return redirect(url_for("assignments_student", course_code=course_code, course_name=course_name))

    # Get assignment files
    assignment_files = []
    assignment_dir = os.path.join("static", "uploads", "assignments", course_code, assignment_data[1])
    if os.path.exists(assignment_dir):
        assignment_files = [f for f in os.listdir(assignment_dir) if os.path.isfile(os.path.join(assignment_dir, f))]

    
    submission_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.path.join("static", "uploads", "submissions", course_code, assignment_data[1], current_user.user_id))
    cursor.execute('''
                    DELETE FROM submission WHERE student_id = %s
                       ''', (current_user.user_id, ))
    gradeai_db.connection.commit()

    teacher_id = cursor.execute(''' SELECT teacher_id FROM class WHERE class_id = %s''', (course_code, ))
   
    
    for f in os.listdir(submission_dir):
        filename, _ = f.split(".")
        submission_id = f"{assignment_id}_{filename}"
        files.append(f)
        cursor.execute('''
                    INSERT INTO submission (submission_id, assignment_id, submitted_at, status, student_id)
                    VALUES (%s, %s, %s, %s, %s)
                    ''', (submission_id, assignment_id, datetime.datetime.now(), 0, current_user.user_id))
        
        
    gradeai_db.connection.commit()

    # Check if student has already submitted
    cursor.execute("""
        SELECT s.submission_id, s.submitted_at
        FROM submission s
        WHERE s.student_id = %s AND s.assignment_id = %s
    """, (current_user.user_id, assignment_id))
   
    submission = cursor.fetchone()

    # Format assignment data for template
    assignment = {
        'id': assignment_data[0],
        'title': assignment_data[1],
        'description': assignment_data[2],
        'due_date': assignment_data[3],
        'total_score': assignment_data[4],
        'attachments': [{'filename': f, 'id': i} for i, f in enumerate(assignment_files)],
        'is_submitted': True if submission else False,
        'submission': {
            'files': files,
            'submitted_at': submission[1] if submission else None
        } 
    }
    cursor.close()
    return render_template("assignment_submit_student.html",
                           assignment=assignment,
                           course_code=course_code,
                           course_name=course_name,
                           current_datetime = datetime.datetime.now())

@app.route('/assignment_view_teacher/<course_code>/<assignment_id>')
@login_required
def assignment_view_teacher(course_code, assignment_id):
    cursor = gradeai_db.connection.cursor()

    # Get assignment details
    assignment = get_assignment_details(cursor, assignment_id, course_code)
    if not assignment:
        flash("Assignment not found", "error")
        return redirect(url_for("teacher_dashboard"))

    # Get assignment files
    assignment_files = get_assignment_files(course_code, assignment[0])

    # Get student submissions
    students = get_student_submissions(cursor, assignment_id, course_code)
    cursor.close()
    print(students)
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

            # Generate unique filename
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            unique_filename = f"{current_user.user_id}_{timestamp}_{secure_filename(file.filename)}"
            
            # Save the file
            file_path = os.path.join(PROFILE_PICS_DIR, unique_filename)
            file.save(file_path)
            
            # Verify file was saved
            if not os.path.exists(file_path):
                raise Exception(f"Failed to save file at {file_path}")
            
            app.logger.info(f"File saved successfully at: {file_path}")
            
            # Get relative path for database storage (without 'static/' prefix)
            relative_path = os.path.join('uploads', 'profile_pics', unique_filename).replace('\\', '/')
            app.logger.info(f"Relative path for database: {relative_path}")
            
            # Update database
            cursor = gradeai_db.connection.cursor()
            try:
                # First, get the current profile picture url
                cursor.execute("SELECT profile_picture_url FROM users WHERE user_id = %s", (current_user.user_id,))
                result = cursor.fetchone()
                app.logger.info(f"Current profile picture in database: {result[0] if result else 'None'}")
                
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
                
                # Update the database with new filepath
                cursor.execute("UPDATE users SET profile_picture_url = %s WHERE user_id = %s", (relative_path, current_user.user_id))
                gradeai_db.connection.commit()
                
                # Verify the update
                cursor.execute("SELECT profile_picture_url FROM users WHERE user_id = %s", (current_user.user_id,))
                updated_path = cursor.fetchone()
                app.logger.info(f"Updated profile picture path in database: {updated_path[0] if updated_path else 'None'}")
                
                # Verify the file exists at the new path
                new_full_path = os.path.join(app.root_path, 'static', relative_path)
                app.logger.info(f"Checking if new profile picture exists at: {new_full_path}")
                if os.path.exists(new_full_path):
                    app.logger.info("New profile picture file exists")
                else:
                    app.logger.error("New profile picture file not found!")
                
                flash('Profile picture updated successfully!', 'success')
            except Exception as e:
                gradeai_db.connection.rollback()
                app.logger.error(f"Database error: {str(e)}")
                flash('Database update failed. Please try again.', 'error')
                # Clean up the file if database update failed
                if os.path.exists(file_path):
                    os.remove(file_path)
                return redirect(url_for('edit_image'))
            finally:
                cursor.close()

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

    cursor = gradeai_db.connection.cursor()
    try:
        profile_pic = fetch_profile_picture(cursor, current_user.user_id)
        if profile_pic:
            app.logger.info(f"Current profile picture path: {profile_pic}")
            # Verify the file exists
            full_path = os.path.join(app.root_path, 'static', profile_pic)
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
    finally:
        cursor.close()

@app.route('/profile_student')
@login_required
def profile_student():
    cursor = gradeai_db.connection.cursor()
    courses_and_instructors = fetch_enrollments(cursor, current_user.user_id)
    profile_pic = fetch_profile_picture(cursor, current_user.user_id)
    cursor.close()
    return render_template("profile_student.html", profile_pic=profile_pic, courses_and_instructors=courses_and_instructors)


@app.route('/profile_teacher')
@login_required
def profile_teacher():
    cursor = gradeai_db.connection.cursor()
    courses = fetch_classes(cursor, current_user.user_id)
    profile_pic = fetch_profile_picture(cursor, current_user.user_id)
    cursor.close()
    return render_template("profile_teacher.html", profile_pic=profile_pic, courses=courses)


@app.route('/create_feedback', methods=["GET", "POST"])
@login_required
def create_feedback():
    if request.method == "POST":
        student_name = request.form.get("studentName")
        assignment_title = request.form.get("assignmentTitle")
        feedback_description = request.form.get("feedbackDescription")
        grade = request.form.get("grade")
        attachment = request.files.get("attachment")
        filename = None

        if attachment:
            uploads_folder = "static/uploads/"
            os.makedirs(uploads_folder, exist_ok=True)
            filename = secure_filename(attachment.filename)
            attachment.save(os.path.join(uploads_folder, filename))

        cursor = gradeai_db.connection.cursor()

        # Get student ID from name
        cursor.execute("SELECT user_id FROM users WHERE CONCAT(first_name, ' ', last_name) = %s", (student_name,))
        student = cursor.fetchone()

        if not student:
            flash("Student not found", "error")
            return redirect(url_for("create_feedback"))

        # Get assignment ID and rubric ID from title
        cursor.execute("""
            SELECT a.assignment_id, a.class_id, r.rubric_id 
            FROM assignment a
            JOIN rubric r ON r.rubric_id = CONCAT(a.assignment_id, '_rubric_0')
            WHERE a.title = %s
        """, (assignment_title,))
        assignment = cursor.fetchone()

        if not assignment:
            flash("Assignment not found", "error")
            return redirect(url_for("create_feedback"))

        # Get submission ID
        cursor.execute("SELECT submission_id FROM submission WHERE student_id = %s AND assignment_id = %s",
                       (student[0], assignment[0]))
        submission = cursor.fetchone()

        if not submission:
            flash("No submission found for this student and assignment", "error")
            return redirect(url_for("create_feedback"))

        # Update or insert grade
        cursor.execute("""
            INSERT INTO grade (submission_id, rubric_id, score, feedback, teacher_id, adjusted_at, is_adjusted)
            VALUES (%s, %s, %s, %s, %s, NOW(), 1)
            ON DUPLICATE KEY UPDATE
            score = VALUES(score),
            feedback = VALUES(feedback),
            teacher_id = VALUES(teacher_id),
            adjusted_at = NOW(),
            is_adjusted = 1
        """, (submission[0], assignment[2], grade, feedback_description, current_user.user_id))

        gradeai_db.connection.commit()
        cursor.close()

        flash("Feedback and grade created successfully", "success")
        return redirect(url_for("assignment_feedback_teacher"))

    return render_template("create_feedback.html")


@app.route("/grade")
@login_required
def grade():
    return render_template("grade.html")

@app.route('/grade_submission/<course_code>/<assignment_id>/<submission_id>/<student_id>', methods=['GET', 'POST'])
@login_required
def grade_submission(course_code, assignment_id, submission_id, student_id):
    cursor = gradeai_db.connection.cursor()
    cursor.execute(""" SELECT * FROM users WHERE user_id = %s""", (student_id,))
    student = cursor.fetchone()
    
    student = {'first_name': student[3], 'last_name': student[4], 'user_id': student[0]}
    
    cursor.execute("SELECT * FROM assignment WHERE class_id = %s", (course_code, ))
    assignment = cursor.fetchone()
    assignment = {'title': assignment[1], 'description': assignment[2], 'total_score': assignment[5], 'deadline': assignment[3]}
    
    #submission
    submission_dir = os.path.join(ASSIGNMENT_SUBMISSIONS_DIR, course_code, assignment["title"], student["user_id"])
    submitted_filenames_sizes = [(filename, os.path.getsize(os.path.join(submission_dir, filename))) for filename in os.listdir(submission_dir)]
    cursor.execute("SELECT submitted_at FROM submission ORDER BY submitted_at DESC LIMIT 1")
    last_submitted_at = cursor.fetchone()[0]    
    submission = {"submitted_at": last_submitted_at, "is_on_time": 1 if last_submitted_at <= assignment["deadline"] else 0, "submission_id": submission_id}
    #files
    submission_files = []
    for filename, size in submitted_filenames_sizes:
        submission_files.append({"filename": filename, "size": size})

    #rubrics
    cursor.execute(""" SELECT description FROM rubric WHERE assignment_id = %s""", (assignment_id, ))
    rubric_l = []
    rubrics = cursor.fetchall()
    for rubric_desc in rubrics:
        rubric_l.append({"description": rubric_desc[0]})

    return render_template("grade_submission.html", student = student, assignment = assignment, submission = submission, submission_files = submission_files, rubrics = rubric_l)

# Example error handling in the route
@app.route('/download/<course_code>/<assignment_id>/<user_id>/<filename>')
@login_required
def download_submission(course_code, assignment_id, user_id, filename):
    try:
        submission_dir = os.path.join(
            ASSIGNMENT_SUBMISSIONS_DIR, 
            course_code, 
            assignment_id.split("_")[1], 
            user_id
        )
        print(submission_dir)
        return send_from_directory(submission_dir, filename, as_attachment=True)
    except FileNotFoundError:
        abort(404)

@app.route('/submit_assignment/<course_code>/<course_name>/<assignment_id>', methods=['POST'])
@login_required
def submit_assignment(course_code, course_name, assignment_id):
    cursor = gradeai_db.connection.cursor()

    course_code, assignment_title = assignment_id.split("_")[0], assignment_id.split("_")[1]
    course_name = get_course_name(cursor, course_code)
    delete_file = request.form.get("delete-file")
    delete_all = request.form.get("delete-all")

    submission_dir_student = os.path.join(ASSIGNMENT_SUBMISSIONS_DIR, course_code, assignment_title, current_user.user_id)
    if delete_file:
        submission_id = f"{assignment_id}_{delete_file.split(".")[0]}"
        cursor.execute('''
                        DELETE FROM submission WHERE student_id = %s and assignment_id = %s
                       ''', (current_user.user_id, submission_id, ))
        cursor.execute('''
                        DELETE FROM grade WHERE grade_id = %s
                       ''', (f"{submission_id}_{current_user.user_id}", ))
        
        gradeai_db.connection.commit()
        os.remove(os.path.join(submission_dir_student, delete_file))
        return redirect(url_for("assignment_submit_student", course_code = course_code, course_name = course_name, assignment_id = assignment_id))
    
    if delete_all:
        cursor.execute('''
                        DELETE FROM submission WHERE student_id = %s
                       ''', (current_user.user_id,))
        
        gradeai_db.connection.commit()
        for filename in os.listdir(submission_dir_student):
            os.remove(os.path.join(submission_dir_student, filename))

        return redirect(url_for("assignment_submit_student", course_code = course_code, course_name = course_name, assignment_id = assignment_id))

    #Assignment submit button for student this part
    # Get assignment details including course name
    cursor.execute("""
        SELECT a.title, a.class_id, c.name as course_name
        FROM assignment a
        JOIN class c ON a.class_id = c.class_id
        WHERE a.assignment_id = %s
    """, (assignment_id,))
    assignment = cursor.fetchone()

    if not assignment:
        flash("Assignment not found", "error")
        return redirect(url_for("assignments_student", course_code=course_code, course_name=course_name))

    # Get uploaded files
    files = request.files.getlist('files')
    if not files or not files[0].filename:
        flash("Please select at least one file to submit", "error")
        return redirect(url_for("assignment_submit_student",
                                course_code=assignment[1],
                                course_name=assignment[2],
                                assignment_id=assignment_id,
                                submission_scores = [],
                                ))
    try:
        # Create submission directory with student ID
        submission_dir = os.path.join(ASSIGNMENT_SUBMISSIONS_DIR, assignment[1], assignment[0],
                                      str(current_user.user_id))
        os.makedirs(submission_dir, exist_ok=True)

        # Save each file
        saved_files = []
        for file in files:
            if file and file.filename:
                filename = secure_filename(file.filename)
                file_path = os.path.join(submission_dir, filename)
                file.save(file_path)
                saved_files.append(filename)

        if not saved_files:
            flash("No files were saved", "error")
            return redirect(url_for("assignment_submit_student",
                                    course_code=assignment[1],
                                    course_name=assignment[2],
                                    assignment_id=assignment_id,
                                    submission_scores = []))
        
        # First, try to delete any existing submission
        cursor.execute("""
            DELETE FROM submission 
            WHERE student_id = %s AND assignment_id = %s
        """, (current_user.user_id, assignment_id))

        # Then insert the new submission - let MySQL handle the auto-increment
        cursor.execute("""
            INSERT INTO submission 
            (assignment_id, student_id, submitted_at, status)
            VALUES (%s, %s, NOW(), 1)
        """, (f"{assignment_id}_{filename}", current_user.user_id,))

        gradeai_db.connection.commit()
        flash("Assignment submitted successfully", "success")

    except Exception as e:
        gradeai_db.connection.rollback()
        print(f"Error in submission: {str(e)}")  # For debugging
        flash(f"Error submitting assignment: {str(e)}", "error")

    cursor.execute(''' SELECT description, score FROM rubric WHERE assignment_id = %s''', (assignment_id,))
    rubrics = cursor.fetchall()
    submission_scores = []
    cursor.execute(""" SELECT teacher_id FROM class WHERE class_id = %s""", (course_code, ))
    teacher_id = cursor.fetchone()
    for f in saved_files:
        filename = f.split(".")[1]
        submission_score = grading_assistant.grade_file(os.path.join(submission_dir, f), filename, rubrics)
        cursor.execute(""" 

                        INSERT INTO grade (grade_id, submission_id, score, feedback, teacher_id, adjusted_at, is_adjusted)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)

                    """, (f"{assignment_id}_{current_user.user_id}", f"{assignment_id}_{filename}", submission_score, "This submission is graded by auto grader!", teacher_id, None, int.to_bytes(0)))
        submission_scores.append({"filename": f, submission_score: submission_score})
        gradeai_db.connection.commit()

    cursor.close()
    return redirect(url_for("assignment_submit_student",
                            course_code=assignment[1],
                            course_name=assignment[2], assignment_id = assignment_id,
                            submission_scores = submission_scores),)


@app.route('/upload_profile_pic', methods=['POST'])
@login_required
def upload_profile_pic():
    if 'profile_pic' not in request.files:
        flash('No file selected', 'error')
        return redirect(request.referrer)

    file = request.files['profile_pic']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(request.referrer)

    if file and allowed_file(file.filename):
        # Create uploads directory if it doesn't exist
        upload_dir = os.path.join('static', 'uploads', 'profile_pics')
        os.makedirs(upload_dir, exist_ok=True)

        # Generate unique filename
        filename = secure_filename(f"{current_user.user_id}_{file.filename}")
        file_path = os.path.join(upload_dir, filename)

        # Save the file
        file.save(file_path)

        # Update database with profile picture path
        cursor = gradeai_db.connection.cursor()
        cursor.execute("""
            UPDATE users 
            SET profile_pic = %s 
            WHERE user_id = %s
        """, (filename, current_user.user_id))
        gradeai_db.connection.commit()
        cursor.close()

        flash('Profile picture updated successfully', 'success')
    else:
        flash('Invalid file type. Please upload an image.', 'error')

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
    cursor.execute(""" 
                    UPDATE grade 
                   SET score = %s, feedback = %s, adjusted_at = %s, is_adjusted = %s WHERE submission_id = %s""", (score, feedback, datetime.now(), int.to_bytes(1), submission_id, ))
 
    gradeai_db.connection.commit()
    cursor.close()
    return redirect(url_for("teacher_dashboard"))


def check_upcoming_deadlines():
    with app.app_context():
        cursor = gradeai_db.connection.cursor()
        # Get assignments due in the next 24 hours
        cursor.execute("""
            SELECT a.assignment_id, a.title, a.class_id, a.deadline
            FROM assignment a
            WHERE a.deadline BETWEEN NOW() AND DATE_ADD(NOW(), INTERVAL 24 HOUR)
        """)
        upcoming_assignments = cursor.fetchall()

        for assignment in upcoming_assignments:
            notify_about_deadline(cursor, assignment[2], assignment[1], assignment[3])

        gradeai_db.connection.commit()
        cursor.close()


# Schedule the deadline check to run every hour
scheduler = BackgroundScheduler()
scheduler.add_job(func=check_upcoming_deadlines, trigger="interval", hours=1)
scheduler.start()

@app.route('/get_notifications')
@login_required
def get_notifications():
    try:
        cursor = gradeai_db.connection.cursor()
        notifications = get_student_notifications(cursor, current_user.user_id)
        cursor.close()
        return jsonify([{
            'id': n[0],
            'type': n[1],
            'title': n[2],
            'message': n[3],
            'time': n[4].strftime('%Y-%m-%d %H:%M:%S'),
            'is_read': bool(n[5])  # Convert bit(1) to boolean
        } for n in notifications])
    except Exception as e:
        print(f"Error in get_notifications: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/mark_notification_read/<notification_id>', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    try:
        cursor = gradeai_db.connection.cursor()
        cursor.execute('''
            UPDATE notifications
            SET is_read = TRUE
            WHERE notification_id = %s AND user_id = %s
        ''', (notification_id, current_user.user_id))
        gradeai_db.connection.commit()
        cursor.close()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error in mark_notification_read: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/mark_all_notifications_read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    try:
        cursor = gradeai_db.connection.cursor()
        cursor.execute('''
            UPDATE notifications
            SET is_read = TRUE
            WHERE user_id = %s
        ''', (current_user.user_id,))
        gradeai_db.connection.commit()
        cursor.close()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error in mark_all_notifications_read: {str(e)}")
        return jsonify({'error': str(e)}), 500

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

if __name__ == "__main__":
    app.run(debug=True)
