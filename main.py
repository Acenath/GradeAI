from flask import Flask, render_template, url_for, request, session, redirect, flash
from flask_sqlalchemy import SQLAlchemy
from flask_mysqldb import MySQL
from flask_login import *
from helpers import *
from classes import *
import os
import json
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["SECRET_KEY"] = "CANSU_BÜŞRA_ORHAN_SUPER_SECRET_KEY"#os.environ.get("SECRET_KEY")
#Login
login_manager = LoginManager()

#Database
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

@app.route('/login', methods = ["GET", "POST"])
def login():
    if request.method == "POST":
        cursor = gradeai_db.connection.cursor()
        email = request.form["email"]
        password = request.form["password"]
        user_tuple = fetch_user(cursor, email, password)

        if not user_tuple:
            return render_template("login.html", error_message = "This account doesn't exist!")
        
        update_last_login(cursor, email, password)
        gradeai_db.connection.commit()
        cursor.close()
        curr_user = User(*user_tuple[0][0: 5]) # password should be ignored
        login_user(curr_user)
        if int.from_bytes(user_tuple[0][5]) == 1: # in DB it is stored in bits
            del user_tuple
            return redirect(url_for("teacher_dashboard"))
        
        else:
            del user_tuple
            return redirect(url_for("student_dashboard"))
        
    else:
        return render_template("login.html")


def confirm_login():
    return

@app.route('/signup', methods = ["GET", "POST"])
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
        
        return render_template("signup.html", error_message = "This account already exist!")
    
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
        cursor = gradeai_db.connection.cursor()
        course_name = request.form.get("course_name")
        course_code = request.form.get("course_code")
        student_csv_file = request.files.get("fileInput")
        students_data = request.form.get("studentsData")

        create_class(cursor, course_code, course_name, current_user.user_id)
        
        if student_csv_file:
            uploads_folder = "/home/oran/Desktop/gradeai/csv_files/"
            os.makedirs(uploads_folder, exist_ok=True)  # Make sure folder exists
            filename = secure_filename(student_csv_file.filename)
            csv_path = os.path.join(uploads_folder, filename)
            student_csv_file.save(csv_path)

            enroll_students(cursor, csv_path, course_code)
        elif students_data:
            try:
                students = json.loads(students_data)
                for student in students:
                    cursor.execute(
                        "INSERT INTO student (student_id, name) VALUES (%s, %s) ON DUPLICATE KEY UPDATE name = %s",
                        (student['studentNo'], student['studentName'], student['studentName'])
                    )
                    cursor.execute(
                        "INSERT INTO enrollment (student_id, course_code) VALUES (%s, %s)",
                        (student['studentNo'], course_code)
                    )
            except json.JSONDecodeError:
                flash("Error processing student data", "error")
                return redirect(url_for("blockview_teacher"))
        else:
            flash("No students added!", "error")
            return redirect(url_for("blockview_teacher"))

        gradeai_db.connection.commit()
        cursor.close()

        return redirect(url_for("teacher_dashboard"))

    return render_template("blockview_teacher.html")

@app.route('/student_dashboard')
@login_required
def student_dashboard():
    return render_template("student_dashboard.html")

@app.route('/teacher_dashboard')
@login_required
def teacher_dashboard():
    cursor = gradeai_db.connection.cursor()
    cursor.execute("SELECT * FROM class WHERE teacher_id = %s", (current_user.user_id,))
    courses = cursor.fetchall()
    cursor.close()
    return render_template("teacher_dashboard.html", courses=courses)


@app.route('/announcement_student')
@login_required
def announcement_student():
    return render_template("announcement_student.html")

@app.route('/announcement_teacher')
@login_required
def announcement_teacher():
    return render_template("announcement_teacher.html")

@app.route('/announcement_view_student')
@login_required
def announcement_view_student():
    return render_template("announcement_view_student.html")

@app.route('/announcement_view_teacher')
@login_required
def announcement_view_teacher():
    return render_template("announcement_view_teacher.html")

@app.route('/assignment_creation', methods = ["GET", "POST"])
@login_required
def assignment_creation():
    return render_template("assignment_creation.html")

@app.route('/assignment_feedback_teacher')
@login_required
def assignment_feedback_teacher():
    return render_template("assignment_feedback_teacher.html")

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

@app.route('/assignment_view_teacher')
@login_required
def assignment_view_teacher():
    return render_template("assignment_view_teacher.html")

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

if __name__ == "__main__":
    app.run(debug = True)
