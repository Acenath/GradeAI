import hashlib
import datetime
import uuid
from typing import Optional

class IDGenerator:
    """Centralized unique identifier generator for all entities"""
    
    @staticmethod
    def generate_hash_id(*components) -> str:
        """Generate a hash-based ID from components"""
        combined = "_".join(str(comp) for comp in components)
        return hashlib.md5(combined.encode()).hexdigest()[:16]
    
    @staticmethod
    def generate_timestamp_id(prefix: str = "") -> str:
        """Generate timestamp-based unique ID"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]  # microseconds to milliseconds
        return f"{prefix}_{timestamp}" if prefix else timestamp
    
    @staticmethod
    def generate_uuid(prefix: str = "") -> str:
        """Generate UUID-based ID"""
        unique_id = str(uuid.uuid4()).replace('-', '')[:16]
        return f"{prefix}_{unique_id}" if prefix else unique_id

class SubmissionIDManager:
    """Manages submission IDs consistently"""
    
    @staticmethod
    def create_submission_id(assignment_id: str, student_id: str, filename: str) -> str:
        """
        Creates unique submission ID
        Format: {assignment_id}_{student_id}_{filename_hash}
        """
        filename_base = filename.split('.')[0] if '.' in filename else filename
        # Use hash to handle long filenames and special characters
        filename_hash = hashlib.md5(filename_base.encode()).hexdigest()[:8]
        return f"{assignment_id}_{student_id}_{filename_hash}"
    
    @staticmethod
    def create_submission_id_simple(assignment_id: str, student_id: str) -> str:
        """
        Creates simple submission ID for single file submissions
        Format: {assignment_id}_{student_id}
        """
        return f"{assignment_id}_{student_id}"
    
    @staticmethod
    def extract_components(submission_id: str) -> dict:
        """Extract components from submission ID"""
        parts = submission_id.split('_')
        if len(parts) >= 3:
            return {
                'assignment_id': '_'.join(parts[:-2]),
                'student_id': parts[-2],
                'filename_hash': parts[-1]
            }
        elif len(parts) == 2:
            return {
                'assignment_id': parts[0],
                'student_id': parts[1],
                'filename_hash': None
            }
        else:
            return {}

class GradeIDManager:
    """Manages grade IDs consistently"""
    
    @staticmethod
    def create_grade_id(submission_id: str) -> str:
        """
        Creates unique grade ID based on submission
        Format: grade_{submission_id}
        """
        return f"grade_{submission_id}"
    
    @staticmethod
    def create_grade_id_with_rubric(submission_id: str, rubric_id: str) -> str:
        """
        Creates grade ID with rubric reference
        Format: grade_{submission_id}_{rubric_hash}
        """
        rubric_hash = hashlib.md5(rubric_id.encode()).hexdigest()[:8]
        return f"grade_{submission_id}_{rubric_hash}"

class AssignmentIDManager:
    """Manages assignment IDs consistently"""
    
    @staticmethod
    def create_assignment_id(class_id: str, assignment_title: str) -> str:
        """
        Creates unique assignment ID
        Format: {class_id}_{title_hash}
        """
        # Clean title and create hash to handle special characters and length
        title_clean = assignment_title.replace(' ', '_').replace('/', '_')
        title_hash = hashlib.md5(assignment_title.encode()).hexdigest()[:12]
        return f"{class_id}_{title_hash}"

class RubricIDManager:
    """Manages rubric IDs consistently"""
    
    @staticmethod
    def create_rubric_id(assignment_id: str, rubric_index: int) -> str:
        """
        Creates unique rubric ID
        Format: rubric_{assignment_id}_{index}
        """
        return f"rubric_{assignment_id}_{rubric_index:03d}"

class NotificationIDManager:
    """Manages notification IDs consistently"""
    
    @staticmethod
    def create_notification_id(user_id: str, notification_type: str) -> str:
        """
        Creates unique notification ID
        Format: notif_{user_id}_{type}_{timestamp}
        """
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        return f"notif_{user_id}_{notification_type}_{timestamp}"

# Updated helper functions for your existing code
def create_assignment_fixed(cursor, assignment_title, assignment_desc, assignment_deadline, class_id, total_score):
    """Updated create_assignment function with proper ID generation"""
    assignment_id = AssignmentIDManager.create_assignment_id(class_id, assignment_title)
    
    # Check if assignment already exists
    cursor.execute("SELECT assignment_id FROM assignment WHERE assignment_id = %s", (assignment_id,))
    if cursor.fetchone():
        # If exists, append timestamp to make it unique
        timestamp = datetime.datetime.now().strftime("%H%M%S")
        assignment_id = f"{assignment_id}_{timestamp}"
    
    cursor.execute(''' 
        INSERT INTO assignment (assignment_id, title, description, deadline, class_id, total_score) 
        VALUES (%s, %s, %s, %s, %s, %s)
    ''', (assignment_id, assignment_title, assignment_desc, assignment_deadline, class_id, total_score))
    
    return assignment_id

def create_rubric_fixed(cursor, score, description, created_by, assignment_id, rubric_index):
    """Updated create_rubric function with proper ID generation"""
    rubric_id = RubricIDManager.create_rubric_id(assignment_id, rubric_index)
    
    # Check if rubric exists and update or insert
    cursor.execute('SELECT rubric_id FROM rubric WHERE rubric_id = %s', (rubric_id,))
    existing_rubric = cursor.fetchone()
    
    if existing_rubric:
        cursor.execute('''
            UPDATE rubric 
            SET score = %s, description = %s, created_at = %s, created_by = %s
            WHERE rubric_id = %s
        ''', (score, description, datetime.datetime.now(), created_by, rubric_id))
    else:
        cursor.execute('''
            INSERT INTO rubric (rubric_id, assignment_id, score, description, created_at, created_by)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (rubric_id, assignment_id, score, description, datetime.datetime.now(), created_by))
    
    return rubric_id

def create_notification_fixed(cursor, user_id, notification_type, title, message):
    """Updated create_notification function with proper ID generation"""
    notification_id = NotificationIDManager.create_notification_id(user_id, notification_type)
    
    cursor.execute('''
        INSERT INTO notifications (notification_id, user_id, type, title, message, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
    ''', (notification_id, user_id, notification_type, title, message, datetime.datetime.now()))
    
    return notification_id

# Example usage and testing
def test_id_generation():
    """Test the ID generation system"""
    print("=== Testing ID Generation System ===")
    
    # Test submission IDs
    sub_id1 = SubmissionIDManager.create_submission_id("CS101_assignment1", "student123", "homework.pdf")
    sub_id2 = SubmissionIDManager.create_submission_id("CS101_assignment1", "student456", "homework.pdf")
    print(f"Submission ID 1: {sub_id1}")
    print(f"Submission ID 2: {sub_id2}")
    print(f"Components: {SubmissionIDManager.extract_components(sub_id1)}")
    
    # Test grade IDs
    grade_id1 = GradeIDManager.create_grade_id(sub_id1)
    grade_id2 = GradeIDManager.create_grade_id(sub_id2)
    print(f"Grade ID 1: {grade_id1}")
    print(f"Grade ID 2: {grade_id2}")
    
    # Test assignment IDs
    assign_id = AssignmentIDManager.create_assignment_id("CS101", "Programming Assignment #1")
    print(f"Assignment ID: {assign_id}")
    
    # Test rubric IDs
    rubric_id = RubricIDManager.create_rubric_id(assign_id, 0)
    print(f"Rubric ID: {rubric_id}")
    
    # Test notification IDs
    notif_id = NotificationIDManager.create_notification_id("student123", "assignment")
    print(f"Notification ID: {notif_id}")
    
    print("\n=== ID Uniqueness Test ===")
    # Test uniqueness
    import time
    ids = set()
    for i in range(1000):
        new_id = IDGenerator.generate_timestamp_id("test")
        if new_id in ids:
            print(f"Duplicate found at iteration {i}: {new_id}")
            break
        ids.add(new_id)
        time.sleep(0.001)  # Small delay
    else:
        print("All 1000 IDs were unique!")

if __name__ == "__main__":
    test_id_generation()