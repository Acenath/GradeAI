from flask import Flask, render_template, url_for, request, session, redirect, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_mysqldb import MySQL
from flask_login import *
from helpers import *
from classes import *
import os
import json
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["SECRET_KEY"] = "CANSU_BÜŞRA_ORHAN_SUPER_SECRET_KEY"  # os.environ.get("SECRET_KEY")
# Login
login_manager = LoginManager()

# Database
app.config['MYSQL_HOST'] = '127.0.0.1'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'GradeAI'

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
        student_csv_file = request.files.get("fileInput")
        if student_csv_file and student_csv_file.filename:
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

@app.route('/get_student_info/<student_id>', methods=["GET"])
@login_required
def get_student_info(student_id):
    cursor = gradeai_db.connection.cursor()
    student_info = fetch_student_info(cursor, student_id)
    cursor.close()
    return jsonify(student_info)

@app.route('/student_dashboard')
@login_required
def student_dashboard():
    return render_template("student_dashboard.html")

@app.route('/teacher_dashboard')
@login_required
def teacher_dashboard():
    cursor = gradeai_db.connection.cursor()
    courses = fetch_classes(cursor, current_user.user_id)
    upcoming_deadlines = fetch_upcoming_deadlines(cursor, current_user.user_id)
    
    recent_feedback = fetch_recent_feedback(cursor, current_user.user_id)
    
    recent_announcements = fetch_recent_announcements(cursor, current_user.user_id)
    
    cursor.close()
    return render_template("teacher_dashboard.html", 
                          courses=courses,
                          upcoming_deadlines=upcoming_deadlines,
                          recent_feedback=recent_feedback,
                          recent_announcements=recent_announcements)

@app.route('/announcement_student')
@login_required
def announcement_student():
    return render_template("announcement_student.html")

@app.route('/announcement_view_student')
@login_required
def announcement_view_student():
    return render_template("announcement_view_student.html")

@app.route('/announcement_teacher/<course_name>/<course_code>')
@login_required
def announcement_teacher(course_name, course_code):
    cursor = gradeai_db.connection.cursor()
    cursor.execute('''
        SELECT announcement_id, content, posted_at
        FROM Announcement
        WHERE class_id = %s
        ORDER BY posted_at DESC
    ''', (course_code,))
    announcements = cursor.fetchall()
    cursor.close()
    for announcement in announcements:
        print(f"Announcement: {announcement}")
    
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
        FROM Announcement
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
        description = request.form.get("description")
        attachments = request.files.get("attachments")
        
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        announcement_id = f"{course_code}_{title}"

        cursor.execute(''' 
            INSERT INTO Announcement (announcement_id, class_id, content, posted_at)
            VALUES (%s, %s, %s, %s)
        ''', (announcement_id, course_code, description, datetime.datetime.now()))

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
        rubric_descs, rubric_vals = request.form.getlist("rubric_descriptions[]"), request.form.getlist("rubric_values[]")
        total_score = sum([int(i) for i in rubric_vals])

        save_files(assignment_files, course_code, assignment_title)
        create_assignment(cursor, assignment_title, assignment_desc, deadline, course_code, total_score)
        zip_to_rubric(cursor, zip(rubric_descs, rubric_vals), current_user.user_id, course_code, assignment_title)

        gradeai_db.connection.commit()
        cursor.close()
        
        flash("Assignment created successfully", "success")
        return redirect(url_for("view_assignments", course_code=course_code))
    
    cursor = gradeai_db.connection.cursor()
    cursor.execute("SELECT name FROM Class WHERE class_id = %s", (course_code,))
    course = cursor.fetchone()
    cursor.close()
    
    if not course:
        flash("Course not found", "error")
        return redirect(url_for("teacher_dashboard"))
    
    return render_template("assignment_creation.html", 
                         course_name=course[0],
                         course_code=course_code)


@app.route('/assignment_feedback_teacher/<course_name>/<course_code>')
@login_required
def assignment_feedback_teacher(course_name, course_code):
    cursor = gradeai_db.connection.cursor()
    feedbacks = fetch_feedbacks_by_teacher(cursor, current_user.user_id)
    cursor.close()
    return render_template("assignment_feedback_teacher.html", feedbacks=feedbacks, course_name=course_name, course_code=course_code)


@app.route('/assignment_grades_student')
@login_required
def assignment_grades_student():
    return render_template("assignment_grades_student.html")


@app.route('/assignment_student')
@login_required
def assignment_student():
    return render_template("assignment_student.html")


@app.route('/assignment_submit_student')
@login_required
def assignment_submit_student():
    return render_template("assignment_submit_student.html")


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


@app.route('/course_grades_student')
@login_required
def course_grades_student():
    return render_template("course_grades_student.html")


@app.route('/edit_email')
@login_required
def edit_email():
    return render_template("edit_email.html")


@app.route('/edit_image')
@login_required
def edit_image():
    return render_template("edit_image.html")


@app.route('/homework_student')
@login_required
def homework_student():
    return render_template("homework_student.html")


@app.route('/homework_teacher')
@login_required
def homework_teacher():
    return render_template("homework_teacher.html")


@app.route('/new_password')
def new_password():
    return render_template("new_password.html")


@app.route('/profile_student')
@login_required
def profile_student():
    return render_template("profile_student.html")


@app.route('/profile_teacher')
@login_required
def profile_teacher():
    return render_template("profile_teacher.html")


@app.route('/create_feedback', methods=["GET", "POST"])
@login_required
def create_feedback():
    if request.method == "POST":
        student_name = request.form.get("studentName")
        assignment_title = request.form.get("assignmentTitle")
        feedback_description = request.form.get("feedbackDescription")
        attachment = request.files.get("attachment")
        filename = None

        if attachment:
            uploads_folder = "static/uploads/"
            os.makedirs(uploads_folder, exist_ok=True)
            filename = secure_filename(attachment.filename)
            attachment.save(os.path.join(uploads_folder, filename))

        return redirect(url_for("assignment_feedback_teacher"))

    return render_template("create_feedback.html")


@app.route('/view_submission/<course_code>/<assignment_id>/<submission_id>')
@login_required
def view_submission(course_code, assignment_id, submission_id):
    cursor = gradeai_db.connection.cursor()
    
    # Get submission details
    submission = get_submission_details(cursor, submission_id, course_code)
    if not submission:
        flash("Submission not found", "error")
        return redirect(url_for("teacher_dashboard"))
    
    cursor.close()
    
    return render_template("view_submission.html",
                         submission=submission,
                         course_code=course_code,
                         assignment_id=assignment_id)

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


if __name__ == "__main__":
    app.run(debug=True)
