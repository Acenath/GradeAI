from flask import Flask, render_template, url_for, request
from flask_sqlalchemy import SQLAlchemy
from flask_mysqldb import MySQL
from helpers import *
import os

app = Flask(__name__)
#Database
app.config['MYSQL_HOST'] = '127.0.0.1'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'GradeAI'  

gradeai_db = MySQL(app)

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
        if check_user_exist(cursor, email, password):
            if is_teacher(cursor, email):
                return render_template("teacher_dashboard.html")
            
            return render_template("student_dashboard.html")
        return render_template("login.html", error_message = "This account doesn't exist!")
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
            return render_template("login.html")
        
        return render_template("signup.html", error_message = "This account already exist!")
    
    else:
        return render_template("signup.html")


@app.route("/home")
@app.route("/")
def logout():
    return render_template("homepage.html")

@app.route('/forgot_password')
def forgot_password():
    return render_template("forgot_password.html")

@app.route('/tutorial')
def tutorial():
    return render_template("tutorial.html")

@app.route('/about')
def about():
    return render_template("aboutus.html")

@app.route('/blockview_teacher')
def blockview_teacher():
    return render_template("blockview_teacher.html")

@app.route('/student_dashboard')
def student_dashboard():
    return render_template("student_dashboard.html")

@app.route('/teacher_dashboard')
def teacher_dashboard():
    return render_template("teacher_dashboard.html")

@app.route('/announcement_student')
def announcement_student():
    return render_template("announcement_student.html")

@app.route('/announcement_teacher')
def announcement_teacher():
    return render_template("announcement_teacher.html")

@app.route('/announcement_view_student')
def announcement_view_student():
    return render_template("announcement_view_student.html")

@app.route('/announcement_view_teacher')
def announcement_view_teacher():
    return render_template("announcement_view_teacher.html")

@app.route('/assignment_creation')
def assignment_creation():
    return render_template("assignment_creation.html")

@app.route('/assignment_feedback_teacher')
def assignment_feedback_teacher():
    return render_template("assignment_feedback_teacher.html")

@app.route('/assignment_grades_student')
def assignment_grades_student():
    return render_template("assignment_grades_student.html")

@app.route('/assignment_student')
def assignment_student():
    return render_template("assignment_student.html")

@app.route('/assignment_submit_student')
def assignment_submit_student():
    return render_template("assignment_submit_student.html")

@app.route('/assignment_view_teacher')
def assignment_view_teacher():
    return render_template("assignment_view_teacher.html")

@app.route('/course_grades_student')
def course_grades_student():
    return render_template("course_grades_student.html")

@app.route('/edit_email')
def edit_email():
    return render_template("edit_email.html")

@app.route('/edit_image')
def edit_image():
    return render_template("edit_image.html")

@app.route('/homework_student')
def homework_student():
    return render_template("homework_student.html")

@app.route('/homework_teacher')
def homework_teacher():
    return render_template("homework_teacher.html")

@app.route('/login')
def login():
    return render_template("login.html")

@app.route('/new_password')
def new_password():
    return render_template("new_password.html")

@app.route('/profile_student')
def profile_student():
    return render_template("profile_student.html")

@app.route('/profile_teacher')
def profile_teacher():
    return render_template("profile_teacher.html")

@app.route('/signup')
def signup():
    return render_template("signup.html")

if __name__ == "__main__":
    app.run(debug = True)
