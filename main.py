from flask import Flask, render_template, url_for, request, session, redirect, flash, jsonify
from flask_mysqldb import MySQL
from flask_login import *
from helpers import *
from classes import *
import os
import json
from werkzeug.utils import secure_filename
import datetime
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
app.config["SECRET_KEY"] = "CANSU_BÜŞRA_ORHAN_SUPER_SECRET_KEY"  # os.environ.get("SECRET_KEY")
grading_assistant = GradingAssistant()

# Define upload directories
ASSIGNMENT_SUBMISSIONS_DIR = os.path.join('static', 'uploads', 'submissions')
ASSIGNMENT_FILES_DIR = os.path.join('static', 'uploads', 'assignments')

# Create directories if they don't exist
os.makedirs(ASSIGNMENT_SUBMISSIONS_DIR, exist_ok=True)
os.makedirs(ASSIGNMENT_FILES_DIR, exist_ok=True)

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


@app.route('/forgot_password')
def forgot_password():
    return render_template("forgot_password.html")


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

        # Process CSV file
        # TODO:
        # Save csv file first
        # 
        student_csv_file = request.files.get("fileInput")
        if student_csv_file:
            result = save_and_process_csv(cursor, student_csv_file, course_code)
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
    print(student)

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

        grading_assistant.create_rubric_instructions(rubric_descs, rubric_vals)
        grading_assistant.consume_question(assignment_desc)

        save_files(assignment_files, course_code, assignment_title)
        create_assignment(cursor, assignment_title, assignment_desc, deadline, course_code, total_score)
        zip_to_rubric(cursor, zip(rubric_descs, rubric_vals), current_user.user_id, course_code, assignment_title)

        # Create notifications for all students
        deadline_datetime = datetime.datetime.strptime(deadline, "%Y-%m-%dT%H:%M")
        notify_students_about_assignment(cursor, course_code, assignment_title, deadline_datetime)

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
                           course_code=course_code)

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
    rubric_items = grading_assistant.generate_rubric()
    print(rubric_items)
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


@app.route('/assignment_submit_student/<course_code>/<course_name>/<assignment_id>')
@login_required
def assignment_submit_student(course_code, course_name, assignment_id):
    os.makedirs(os.path.join(ASSIGNMENT_SUBMISSIONS_DIR, course_code, assignment_id.split("_")[1], current_user.user_id), exist_ok = 1)
    cursor = gradeai_db.connection.cursor()

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
    
    files = []
    for f in os.listdir(submission_dir):
        submission_id = f"{f.split(".")[0]}_{assignment_data[1]}"
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
                           course_name=course_name)


def delete_submitted_file(course_code, course_name, assignment_id, submitted_filename):
    cursor = gradeai_db.connection.cursor()
        # Get assignment details
    cursor.execute("""
        SELECT a.assignment_id, a.title, a.description, a.deadline, 
               a.total_score, c.name as course_name
        FROM assignment a
        JOIN class c ON a.class_id = c.class_id
        WHERE a.assignment_id = %s AND a.class_id = %s
    """, (assignment_id, course_code))
    assignment_data = cursor.fetchone()

    submission_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.path.join("static", "uploads", "submissions", course_code, assignment_data[1], current_user.user_id))
    os.remove(os.path.join(submission_dir, submitted_filename))
    cursor.execute('''
                    DELETE FROM submission WHERE submission_id = %s 
                   ''', (f"{f.split(".")[0]}_{assignment_data[1]}"))

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
    print(students)
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
            
            # Ensure the directory exists
            os.makedirs(PROFILE_PICS_DIR, exist_ok=True)
            
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
                save_profile_picture(cursor, relative_path, current_user.user_id)
                gradeai_db.connection.commit()
                
                # Verify the update
                cursor.execute("SELECT profile_picture_url FROM users WHERE user_id = %s", (current_user.user_id,))
                updated_path = cursor.fetchone()
                app.logger.info(f"Updated profile picture path in database: {updated_path[0] if updated_path else 'None'}")
                
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


@app.route('/new_password')
def new_password():
    return render_template("new_password.html")


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

@app.route('/grade_submission/<course_code>/<assignment_id>/<submission_id>', methods=['GET', 'POST'])
@login_required
def grade_submission(course_code, assignment_id, submission_id):
    cursor = gradeai_db.connection.cursor()

    if request.method == 'POST':
        score = request.form.get('score')
        feedback = request.form.get('feedback')

        # Get assignment total score
        total_score = get_assignment_total_score(cursor, assignment_id)

        # Validate score
        try:
            score = float(score)
            if score < 0 or score > total_score:
                flash("Score must be between 0 and " + str(total_score), "error")
                return redirect(url_for("grade_submission",
                                        course_code=course_code,
                                        assignment_id=assignment_id,
                                        submission_id=submission_id))
        except ValueError:
            flash("Invalid score format", "error")
            return redirect(url_for("grade_submission",
                                    course_code=course_code,
                                    assignment_id=assignment_id,
                                    submission_id=submission_id))

        # Check if grade already exists
        existing_grade = check_existing_grade(cursor, submission_id)

        if existing_grade:
            # Update existing grade
            update_grade(cursor, submission_id, score, feedback)
        else:
            # Insert new grade
            insert_grade(cursor, submission_id, score, feedback)

        gradeai_db.connection.commit()
        flash("Grade submitted successfully", "success")
        return redirect(url_for("assignment_view_teacher",
                                course_code=course_code,
                                assignment_id=assignment_id))

    # Get submission details for grading
    submission = get_submission_for_grading(cursor, submission_id, course_code)
    if not submission:
        flash("Submission not found", "error")
        return redirect(url_for("teacher_dashboard"))

    cursor.close()

    return render_template("grade_submission.html",
                           submission=submission,
                           course_code=course_code,
                           assignment_id=assignment_id)


@app.route('/submit_assignment/<assignment_id>', methods=['POST'])
@login_required
def submit_assignment(assignment_id):
    cursor = gradeai_db.connection.cursor()

    course_code, assignment_title = assignment_id.split("_")[0], assignment_id.split("_")[1]
    course_name = get_course_name(cursor, course_code)
    delete_file = request.form.get("delete-file")
    delete_all = request.form.get("delete-all")

    submission_dir_student = os.path.join(ASSIGNMENT_SUBMISSIONS_DIR, course_code, assignment_title, current_user.user_id)
    if delete_file:
        cursor.execute('''
                        DELETE FROM submission WHERE assignment_id = %s
                       ''', (f"{delete_file.split("_")[0]}_{assignment_id}", ))
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
                                assignment_id=assignment_id))

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
                                    assignment_id=assignment_id))

        # Get the relative path for database storage
        relative_path = os.path.join('uploads', 'submissions', assignment[1], assignment[0], str(current_user.user_id),
                                     saved_files[0])

        # First, try to delete any existing submission
        cursor.execute("""
            DELETE FROM submission 
            WHERE student_id = %s AND assignment_id = %s
        """, (current_user.user_id, assignment_id))

        # Then insert the new submission - let MySQL handle the auto-increment
        cursor.execute("""
            INSERT INTO submission 
            (assignment_id, student_id, submitted_at, file_url, status)
            VALUES (%s, %s, NOW(), %s, 1)
        """, (assignment_id, current_user.user_id, relative_path))

        gradeai_db.connection.commit()
        flash("Assignment submitted successfully", "success")

    except Exception as e:
        gradeai_db.connection.rollback()
        print(f"Error in submission: {str(e)}")  # For debugging
        flash(f"Error submitting assignment: {str(e)}", "error")
    finally:
        cursor.close()

    return redirect(url_for("assignment_submit_student",
                            course_code=assignment[1],
                            course_name=assignment[2], assignment_id = assignment_id))


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

    # Get assignment and student details
    cursor.execute("""
        SELECT a.title, a.class_id, s.student_id
        FROM submission s
        JOIN assignment a ON s.assignment_id = a.assignment_id
        WHERE s.submission_id = %s
    """, (submission_id,))
    details = cursor.fetchone()

    if details:
        update_grade(cursor, submission_id, score, feedback)
        # Create notification for the student
        notify_student_about_feedback(cursor, details[2], details[0], details[1])

    gradeai_db.connection.commit()
    cursor.close()
    return jsonify({'success': True})


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

if __name__ == "__main__":
    app.run(debug=True)
