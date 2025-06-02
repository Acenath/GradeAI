# GradeAI - Automated Essay Grading System 🎓

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8+-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/Flask-2.0+-green.svg" alt="Flask Version">
  <img src="https://img.shields.io/badge/LLM-Llama--3.2-orange.svg" alt="LLM Model">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
</p>

## 📖 Table of Contents

- [About The Project](#about-the-project)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Configuration](#configuration)
- [Usage](#usage)
  - [For Teachers](#for-teachers)
  - [For Students](#for-students)
- [Project Structure](#project-structure)
- [API Documentation](#api-documentation)
- [How It Works](#how-it-works)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)
- [Acknowledgments](#acknowledgments)

## 🌟 About The Project

GradeAI is an innovative automated essay grading system designed to revolutionize the way educators assess student essays. Built as a final graduation project, this platform leverages the power of Large Language Models (LLMs) to provide intelligent, consistent, and timely feedback on essay assignments.

### 🎯 Project Goals

- **Reduce grading workload** for teachers by automating the essay evaluation process
- **Provide instant feedback** to students upon submission
- **Ensure consistent grading** using AI-powered rubric evaluation
- **Support multiple file formats** including PDF, DOCX, and TXT
- **Generate intelligent rubrics** based on assignment descriptions

### 🔍 What Makes GradeAI Stand Out?

1. **AI-Powered Grading**: Uses Meta's Llama 3.2 model for intelligent essay evaluation
2. **Dynamic Rubric Generation**: Automatically creates grading rubrics from assignment descriptions
3. **Real-time Processing**: Students receive grades immediately after submission
4. **Comprehensive Dashboard**: Intuitive interfaces for both teachers and students
5. **Secure Authentication**: Email-based authentication with password reset functionality

## ✨ Features

### For Teachers
- 📝 **Create and manage classes** with student enrollment
- 📋 **Design assignments** with custom rubrics or AI-generated ones
- 🤖 **Automatic grading** of essay submissions using LLM
- 📊 **Grade overview dashboard** with submission tracking
- 📢 **Post announcements** to classes with file attachments
- 👥 **Bulk student enrollment** via CSV upload
- ✏️ **Manual grade adjustment** capabilities

### For Students
- 📚 **View enrolled courses** and assignments
- 📤 **Submit essays** in PDF, DOCX, or TXT format
- ⚡ **Instant grading** with AI-powered feedback
- 📈 **Track grades** across all courses
- 📅 **Deadline management** with upcoming assignment views
- 🔔 **View announcements** from teachers
- 👤 **Profile management** with picture upload

## 🛠️ Tech Stack

### Backend
- **Framework**: Flask (Python)
- **Database**: MySQL
- **Authentication**: Flask-Login
- **Email Service**: Flask-Mail (SMTP)
- **AI/ML**: 
  - Transformers (Hugging Face)
  - Meta Llama 3.2 1B Instruct
  - PyTorch

### Frontend
- **Templates**: Jinja2
- **Styling**: CSS3
- **JavaScript**: Vanilla JS
- **UI Components**: Custom design

### File Processing
- **PDF**: PyPDF2, pdfplumber
- **DOCX**: python-docx
- **Security**: Werkzeug secure filename

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher
- MySQL Server
- CUDA-capable GPU (recommended for faster AI processing)
- 8GB+ RAM
- Git

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/gradeai.git
   cd gradeai
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   
   # On Windows
   venv\Scripts\activate
   
   # On macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up MySQL database**
   ```sql
   CREATE DATABASE gradeai;
   USE gradeai;
   
   -- Run the schema creation script
   source database/schema.sql 
   ```

5. **Configure environment variables**
   Create a `.env` file in the root directory:
   ```env
   SECRET_KEY=your_secret_key_here
   MYSQL_HOST=127.0.0.1
   MYSQL_USER=root
   MYSQL_PASSWORD=your_mysql_password
   MYSQL_DB=gradeai
   MAIL_USERNAME=your_email@gmail.com
   MAIL_PASSWORD=your_app_password
   ```

### Configuration

1. **Email Configuration**
   - Enable 2-factor authentication on your Gmail account
   - Generate an app-specific password
   - Update the email configuration in `main.py`

2. **Model Configuration**
   - The system will automatically download the Llama 3.2 model on first run
   - Ensure you have sufficient disk space (~2GB for model files)

3. **Directory Structure**
   The application will automatically create necessary directories:
   ```
   static/
   ├── uploads/
   │   ├── assignments/
   │   ├── submissions/
   │   ├── announcements/
   │   ├── enrollments/
   │   └── profile_pics/
   ```

## 📘 Usage

### Starting the Application

```bash
python main.py
```

Navigate to `http://localhost:5000` in your web browser.

### For Teachers

1. **Sign Up/Login**
   - Register with a university email (e.g., `teacher@university.edu`)
   - The system automatically assigns teacher role based on email domain

2. **Create a Class**
   - Navigate to "Create Class"
   - Enter course code and name
   - Add students manually or via CSV upload

3. **Create Assignments**
   - Go to your class → "Assignments" → "Create Assignment"
   - Enter assignment details
   - Either manually create rubrics or use AI generation
   - Rubrics must total exactly 100 points

4. **View Submissions**
   - Access submissions through the assignment view
   - Download student files
   - View AI-generated grades
   - Adjust grades if needed

### For Students

1. **Sign Up/Login**
   - Register with a student email
   - Login to access your dashboard

2. **View Assignments**
   - Check enrolled courses
   - View assignment details and deadlines

3. **Submit Essays**
   - Upload your essay (PDF, DOCX, or TXT)
   - Receive instant AI-powered grading
   - View detailed feedback

4. **Track Progress**
   - Monitor grades across all courses
   - Check upcoming deadlines
   - Read announcements

## 📁 Project Structure

```
gradeai/
├── main.py                 # Main Flask application
├── classes.py              # Core classes (User, GradingAssistant, ID Managers)
├── helpers.py              # Utility functions
├── requirements.txt        # Python dependencies
├── static/                 # Static files
│   ├── css/               # Stylesheets
│   ├── js/                # JavaScript files
│   └── uploads/           # User uploads
├── templates/             # HTML templates
│   ├── homepage.html
│   ├── login.html
│   ├── signup.html
│   ├── student_dashboard.html
│   ├── teacher_dashboard.html
│   └── ...
└── database/
    └── schema.sql         # Database schema
```

## 🔌 API Documentation

### Key Routes

#### Authentication
- `POST /login` - User login
- `POST /signup` - User registration
- `GET /logout` - User logout
- `POST /forgot_password` - Password reset request
- `POST /new_password/<token>` - Reset password

#### Teacher Routes
- `GET /teacher_dashboard` - Teacher home page
- `POST /blockview_teacher` - Create class and manage enrollment
- `GET /assignments/<course_code>` - View course assignments
- `POST /assignment_creation/<course_code>` - Create new assignment
- `POST /generate_rubric` - AI rubric generation
- `GET /grade_submission/<course_code>/<assignment_id>/<submission_id>/<student_id>` - Grade interface

#### Student Routes
- `GET /student_dashboard` - Student home page
- `GET /assignments_student/<course_code>/<course_name>` - View assignments
- `POST /submit_assignment/<course_code>/<course_name>/<assignment_id>` - Submit essay
- `GET /course_grades_student/<course_name>/<course_code>` - View grades

## 🧠 How It Works

### AI Grading Process

1. **Rubric Creation**
   - Teacher provides assignment description
   - AI analyzes description and generates relevant rubrics
   - Each rubric has specific point values totaling 100

2. **Essay Submission**
   - Student uploads essay file
   - System extracts text from PDF/DOCX/TXT

3. **AI Evaluation**
   - Essay content is processed by Llama 3.2 model
   - Model evaluates essay against each rubric criterion
   - Points are awarded based on quality assessment

4. **Grade Generation**
   - System calculates total score
   - Generates feedback (currently system-generated message)
   - Stores grade in database

### Security Features

- Password hashing using SHA-256
- Session management with Flask-Login
- Secure file upload with filename sanitization
- CSRF protection
- Email verification for password resets

## 🤝 Contributing

We welcome contributions to GradeAI! Please follow these steps:

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### Contribution Guidelines

- Follow PEP 8 style guide for Python code
- Add comments for complex logic
- Update documentation for new features
- Write unit tests for new functionality
- Ensure all tests pass before submitting PR

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📧 Contact

Project Team:
- Cansu - [GitHub Profile](https://github.com/cansu)
- Büşra - [GitHub Profile](https://github.com/busra)
- Orhan - [GitHub Profile](https://github.com/orhan)

Project Link: [https://github.com/yourusername/gradeai](https://github.com/yourusername/gradeai)

## 🙏 Acknowledgments

- [Meta AI](https://ai.meta.com/) for the Llama 3.2 model
- [Hugging Face](https://huggingface.co/) for the Transformers library
- [Flask](https://flask.palletsprojects.com/) for the web framework
- Our university professors for guidance and support
- All contributors who helped shape this project

---

<p align="center">Made with ❤️ by the GradeAI Team</p>
