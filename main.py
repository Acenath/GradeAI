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


@app.route('/stıdent_dashboard')
def student_dashboard():
    return render_template("student_dashboard.html")


@app.route('/teacher_dashboard')
def teacher_dashboard():
    return render_template("teacher_dashboard.html")

if __name__ == "__main__":
    app.run(debug = True)
