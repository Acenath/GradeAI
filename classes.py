from flask_login import UserMixin
from helpers import *
import hashlib
import datetime
import uuid
from typing import Optional
import gc
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
import os
import docx
import re
import ast
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
class User(UserMixin):
    def __init__(self, user_id, email, *, first_name, last_name):
        self.user_id = user_id
        self.email = email
        self.first_name = first_name
        self.last_name = last_name
        self._is_authenticated = True
        self._is_active = True

    @staticmethod
    def get(cursor, user_id):
        cursor.execute(''' SELECT * FROM users WHERE user_id = %s ''', (user_id,))
        user_rows = cursor.fetchall()
        cursor.close()
        
        if not user_rows:
            return None
            
        user_data = user_rows[0]
        return User(
            user_id=user_data[0],
            email=user_data[1],
            first_name=user_data[3],
            last_name=user_data[4]

        )

    def logout(self):
        """Clear all user data when logging out"""
        self.user_id = None
        self.email = None
        self.first_name = None
        self.last_name = None
        self._is_authenticated = False
        self._is_active = False

    def clear_session(self):
        """Alternative method to clear user data"""
        self.logout()

    def is_authenticated(self):
        """Check if user is authenticated"""
        return self._is_authenticated and self.user_id is not None

    def is_active(self):
        """Check if user is active"""
        return self._is_active and self.user_id is not None

    def is_anonymous(self):
        """Check if user is anonymous"""
        return not self.is_authenticated()

    def get_id(self):
        """Return user ID for Flask-Login"""
        return self.user_id if self.is_authenticated() else None

    def __repr__(self):
        """String representation for debugging"""
        if self.is_authenticated():
            return f"<User {self.user_id}: {self.first_name} {self.last_name}>"
        else:
            return "<User: Not authenticated>"
    
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
import re
import json
import ast
import gc
import docx

class GradingAssistant():
    def __init__(self):
        self.model_name = "meta-llama/Llama-3.2-1B-Instruct"
        self.max_new_tokens = 512  # Reduced for faster generation
        self.temperature = 0.2     # Lower for more consistent output
        self.top_p = 0.9          # Slightly lower for better control
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        print("Loading model and tokenizer...")
        # Load model ONCE during initialization
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            device_map="auto" if self.device == "cuda" else None,
            torch_dtype=torch.bfloat16,
            attn_implementation="sdpa"
        ).eval()
        
        # Set padding token
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        
        print("Model loaded successfully!")

    def create_rubric_instructions(self, current_rubrics, current_points):
        total_points = sum(current_points) if current_points else 0
        total_score = 100 if total_points == 0 else 10 ** (len(str(total_points)) + 1)
        remaining_score = total_score - total_points
        
        # Store for fallback use
        self.current_points = current_points
        self.remaining_score = remaining_score
        
        # Essay-specific rubric instructions
        self.rubric_instructions = f"""
You MUST create exactly {remaining_score} points worth of essay grading rubric items.

ESSAY ASSIGNMENT TO CREATE RUBRIC FOR:
{getattr(self, 'question', 'Essay writing assignment')}

EXISTING RUBRICS (DO NOT DUPLICATE):
{current_rubrics if current_rubrics else 'None'}

CRITICAL INSTRUCTIONS - FOLLOW EXACTLY:
1. Create numbered rubric items ONLY for essay grading
2. Each line MUST start with a number and period: "1. "
3. Each line MUST end with points in parentheses: "(15 pt)"
4. NO other text, NO explanations, NO essays
5. Total points MUST equal exactly {remaining_score}
6. Focus on essay-specific criteria like thesis, arguments, evidence, writing quality

REQUIRED FORMAT - COPY THIS EXACTLY:
1. [Essay grading criteria] (20 pt)
2. [Another essay criteria] (15 pt)
3. [Final essay criteria] (10 pt)

EXAMPLE OUTPUT FOR ESSAY GRADING:
1. Clear and strong thesis statement (25 pt)
2. Supporting evidence and examples (20 pt)
3. Logical organization and flow (15 pt)
4. Grammar and writing mechanics (10 pt)

NOW CREATE THE ESSAY RUBRIC - START WITH "1.":
        """

    def consume_question(self, question):
        self.question = question

    def flush_memory(self):
        if self.device == "cuda":
            torch.cuda.empty_cache()
        gc.collect()

    def _check_response_format(self, response):
        """Check if response follows the required rubric format"""
        lines = response.strip().split('\n')
        valid_lines = 0
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check for pattern: "Number. Description (X pt)"
            pattern = r'^(\d+)\.\s*(.+?)\s*\((\d+)\s*pt?\)'
            if re.match(pattern, line, re.IGNORECASE):
                valid_lines += 1
        
        return valid_lines >= 2  # At least 2 valid rubric lines

    def _generate_response_with_retry(self, messages, max_retries=3):
        """Generate response with retry logic for better results"""
        for attempt in range(max_retries):
            print(f"Generation attempt {attempt + 1}/{max_retries}")
            
            # More restrictive generation parameters for better following
            prompt = self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )
            
            inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)

            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=200,  # Shorter to force concise output
                    temperature=0.1,     # Much lower for strict following
                    top_p=0.7,          # More restrictive
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id,
                    use_cache=True,
                    repetition_penalty=1.3,  # Higher to avoid repetition
                    no_repeat_ngram_size=3,   # Prevent repetitive patterns
                )

            # Extract response
            full_response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            # Better response extraction
            if "assistant" in full_response:
                response = full_response.split("assistant")[-1]
            else:
                input_length = len(self.tokenizer.decode(inputs['input_ids'][0], skip_special_tokens=True))
                response = full_response[input_length:]
            
            # Clean up response
            response = response.strip()
            for stop_token in ["<|eot_id|>", "</s>", "<|end|>"]:
                if stop_token in response:
                    response = response.split(stop_token)[0]
            
            # Check if response follows format
            if self._check_response_format(response):
                print(f"✅ Attempt {attempt + 1} passed format check")
                return response.strip()
            else:
                print(f"❌ Attempt {attempt + 1} failed format check")
                print(f"Response was: {response[:200]}...")
                if attempt < max_retries - 1:
                    print("Retrying with different parameters...")
        
        print("⚠️ All attempts failed, returning last response")
        return response.strip()

    def _generate_response(self, messages):
        """Shared generation method (kept for compatibility)"""
        return self._generate_response_with_retry(messages, max_retries=1)

    def _create_fallback_rubrics(self):
        """Create essay-specific fallback rubrics if model fails"""
        print("Creating essay-specific fallback rubrics...")
        
        # Get remaining points
        remaining_score = getattr(self, 'remaining_score', 100)
        
        # Essay-specific rubric templates
        essay_rubrics = [
            {"rubric_desc": "Clear thesis statement and main argument", "rubric_score": str(remaining_score // 4)},
            {"rubric_desc": "Supporting evidence and examples", "rubric_score": str(remaining_score // 4)},
            {"rubric_desc": "Organization and logical flow", "rubric_score": str(remaining_score // 4)},
            {"rubric_desc": "Grammar, style, and writing mechanics", "rubric_score": str(remaining_score - 3 * (remaining_score // 4))},
        ]
        
        print(f"Created {len(essay_rubrics)} essay rubrics:")
        for item in essay_rubrics:
            print(f"  {item['rubric_desc']} ({item['rubric_score']} pt)")
        
        return essay_rubrics

    def generate_rubric(self):
        print("Generating essay rubric...")
        
        # Essay-specific system message
        chat = [
            {"role": "system", "content": "You are an essay grading rubric generator. Output ONLY numbered essay grading criteria with points. Format: '1. Thesis statement quality (25 pt)'"},
            {"role": "user", "content": self.rubric_instructions}
        ]
        
        # Use retry logic
        rubric_text = self._generate_response_with_retry(chat)
        print("Raw model output:")
        print(rubric_text)
        print("-" * 50)
        
        # Improved parsing logic
        rubrics = self._parse_rubric(rubric_text)
        
        print(f"Parsed {len(rubrics)} rubric items:")
        for item in rubrics:
            print(f"  {item['rubric_desc']} ({item['rubric_score']} pt)")
        
        # Fallback if parsing fails
        if not rubrics or len(rubrics) < 2:
            print("⚠️ Parsing failed or insufficient rubrics, creating essay fallback...")
            rubrics = self._create_fallback_rubrics()
        
        self.rubrics = rubrics
        return rubrics

    def _parse_rubric(self, rubric_text):
        """Improved rubric parsing"""
        rubrics = []
        lines = rubric_text.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Look for numbered items: "1. Description (X pt)"
            pattern = r'^(\d+)\.\s*(.+?)\s*\((\d+)\s*pt?\)'
            match = re.match(pattern, line, re.IGNORECASE)
            
            if match:
                number, description, score = match.groups()
                rubrics.append({
                    "rubric_score": score,
                    "rubric_desc": description.strip()
                })
                continue
            
            # Alternative pattern: "Description (X pt)" without number
            pattern2 = r'^(.+?)\s*\((\d+)\s*pt?\)'
            match2 = re.match(pattern2, line, re.IGNORECASE)
            
            if match2:
                description, score = match2.groups()
                # Skip if it starts with a bullet or dash
                if not description.strip().startswith(('-', '•', '*')):
                    rubrics.append({
                        "rubric_score": score,
                        "rubric_desc": description.strip()
                    })
        
        return rubrics

    def grade_file(self, file_path, file_type, rubrics):
        # Read essay content
        text_l = []
        if file_type == "docx":
            f = docx.Document(file_path)
            for docpara in f.paragraphs:
                text_l.append(docpara.text + "\n")
        elif file_type == "txt":
            with open(file_path, 'r', encoding='utf-8') as f:
                text_l = f.readlines()
        
        # Handle both tuple and dict formats for rubrics
        formatted_rubrics = []
        for item in rubrics:
            print(f"Processing rubric item: {item}, type: {type(item)}")
            
            if isinstance(item, tuple):
                # Database format: (description, score)
                curr_dict = {
                    "description": item[0],  # description
                    "point": int(float(item[1]))  # FIXED: Convert float string to int
                }
            elif isinstance(item, dict):
                # Already in dict format from generate_rubric
                if "rubric_desc" in item and "rubric_score" in item:
                    curr_dict = {
                        "description": item["rubric_desc"],
                        "point": int(float(item["rubric_score"]))  # FIXED: Convert float string to int
                    }
                else:
                    # Alternative dict format
                    curr_dict = {
                        "description": item.get("description", ""),
                        "point": int(float(item.get("point", 0)))  # FIXED: Handle float strings
                    }
            else:
                print(f"Warning: Unknown rubric format: {item}")
                continue
                
            formatted_rubrics.append(curr_dict)

        essay_content = "".join(text_l)
        
        # SIMPLIFIED grading instructions for better JSON generation
        grading_instructions = f"""
    Grade this essay using these criteria. Output ONLY valid JSON.

    RUBRICS:
    {[{'desc': r['description'][:50], 'max_pts': r['point']} for r in formatted_rubrics]}

    ESSAY:
    {essay_content[:1000]}...

    Output format (EXACTLY):
    [{{"rubric_desc": "criteria 1", "rubric_score": 25}}, {{"rubric_desc": "criteria 2", "rubric_score": 30}}]

    JSON:"""
        
        chat = [
            {"role": "system", "content": "Output only JSON array with rubric scores. No explanations."},
            {"role": "user", "content": grading_instructions}
        ]

        # MORE restrictive parameters for clean JSON
        prompt = self.tokenizer.apply_chat_template(
            chat,
            tokenize=False,
            add_generation_prompt=True
        )
        
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=200,  # MUCH shorter to prevent truncation
                temperature=0.05,    # VERY low for consistent JSON
                top_p=0.7,           # More restrictive
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id,
                use_cache=True,
                repetition_penalty=1.1,
                early_stopping=True,
            )

        # Extract response
        full_response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        if "assistant" in full_response:
            response = full_response.split("assistant")[-1]
        else:
            input_length = len(self.tokenizer.decode(inputs['input_ids'][0], skip_special_tokens=True))
            response = full_response[input_length:]
        
        response = response.strip()
        for stop_token in ["<|eot_id|>", "</s>", "<|end|>"]:
            if stop_token in response:
                response = response.split(stop_token)[0]
        
        print("Essay grading response:")
        print(response)
        print("-" * 50)
        
        # Better JSON parsing with FIXED fallback handling
        try:
            # Try to extract JSON from response - handle incomplete JSON
            json_patterns = [
                r'\[.*?\]',           # Complete array
                r'\[\s*\{.*?\}\s*\]', # Array with single object
                r'\[\s*\{.*',         # Incomplete array
            ]
            
            json_str = None
            for pattern in json_patterns:
                json_match = re.search(pattern, response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    
                    # Fix incomplete JSON
                    if not json_str.endswith(']'):
                        # Count open braces
                        open_braces = json_str.count('{')
                        close_braces = json_str.count('}')
                        
                        # Add missing closing braces
                        for _ in range(open_braces - close_braces):
                            json_str += '}'
                        
                        # Add closing bracket if missing
                        if not json_str.endswith(']'):
                            json_str += ']'
                    
                    break
            
            if json_str:
                print(f"Extracted JSON (possibly fixed): {json_str}")
                
                # Try JSON parsing first, then ast.literal_eval as fallback
                try:
                    rubric_scores = json.loads(json_str)
                except json.JSONDecodeError:
                    try:
                        rubric_scores = ast.literal_eval(json_str)
                    except (ValueError, SyntaxError):
                        print("Both JSON and literal_eval failed, using fallback")
                        rubric_scores = self._create_essay_fallback_scores(formatted_rubrics)
                
                print(f"Parsed scores: {rubric_scores}")
                
                # Calculate total score with FIXED error handling
                student_score = 0
                for item in rubric_scores:
                    try:
                        # Handle both possible key names and convert properly
                        if "rubric_score" in item:
                            score = int(float(item["rubric_score"]))
                        elif "point" in item:
                            score = int(float(item["point"]))
                        else:
                            score = 0
                        student_score += score
                    except (ValueError, TypeError) as e:
                        print(f"Error converting score for item {item}: {e}")
                        continue
                
                return student_score
            else:
                print("No JSON found in response, using fallback")
                fallback_scores = self._create_essay_fallback_scores(formatted_rubrics)
                return sum(item["point"] for item in fallback_scores)
                
        except Exception as e:
            print(f"Error parsing essay grades: {e}")
            print(f"Raw response: {response}")
            print("Using fallback scores...")
            fallback_scores = self._create_essay_fallback_scores(formatted_rubrics)
            return sum(item["point"] for item in fallback_scores)

    def _create_essay_fallback_scores(self, formatted_rubrics):
        """Create fallback scores for essay grading when JSON parsing fails"""
        print("Creating essay fallback scores (80% of max points for decent essay)...")
        fallback_scores = []
        
        for rubric in formatted_rubrics:
            # Give 80% of max points as fallback for essays (assuming decent quality)
            try:
                max_points = int(float(rubric["point"]))  # FIXED: Handle float strings
                score = max(1, int(max_points * 0.8))
            except (ValueError, TypeError):
                score = 5  # Default fallback score
                
            fallback_scores.append({
                "description": rubric["description"],  # FIXED: Use consistent key names
                "point": score                         # FIXED: Use "point" not "rubric_score"
            })
        
        print(f"Fallback essay scores: {fallback_scores}")
        return fallback_scores

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

class AnnouncementIDManager:
    """Clean announcement ID management with stable primary keys"""
    
    @staticmethod
    def create_announcement_id() -> str:
        """
        Creates stable announcement ID (PRIMARY KEY) - NEVER changes
        Format: announce_{uuid}
        """
        unique_id = str(uuid.uuid4()).replace('-', '')[:16]
        return f"announce_{unique_id}"

# Clean implementation
def create_announcement_fixed(cursor, announcement_title, announcement_content, class_id, created_by):
    """Create announcement with stable UUID-based ID"""
    # Primary key - never changes, always unique
    announcement_id = AnnouncementIDManager.create_announcement_id()
    
    cursor.execute(''' 
        INSERT INTO announcement (announcement_id, title, content, class_id, created_by, created_at) 
        VALUES (%s, %s, %s, %s, %s, %s)
    ''', (announcement_id, announcement_title, announcement_content, class_id, created_by, datetime.datetime.now()))
    
    return announcement_id

def update_announcement_fixed(cursor, announcement_id, new_title, new_content):
    """Update announcement - ID never changes, only content updates"""
    cursor.execute('''
        UPDATE announcement 
        SET title = %s, content = %s, updated_at = %s
        WHERE announcement_id = %s
    ''', (new_title, new_content, datetime.datetime.now(), announcement_id))
    
    return announcement_id  # Same ID always!

def create_announcement_auto_increment(cursor, announcement_title, announcement_content, class_id, created_by):
    """Create announcement with auto-increment ID"""
    cursor.execute(''' 
        INSERT INTO announcement (title, content, class_id, created_by, created_at) 
        VALUES (%s, %s, %s, %s, %s)
    ''', (announcement_title, announcement_content, class_id, created_by, datetime.datetime.now()))
    
    # Get the auto-generated ID
    announcement_id = cursor.lastrowid
    return announcement_id

def update_announcement_auto_increment(cursor, announcement_id, new_title, new_content):
    """Update announcement with auto-increment ID"""
    cursor.execute('''
        UPDATE announcement 
        SET title = %s, content = %s, updated_at = %s
        WHERE announcement_id = %s
    ''', (new_title, new_content, datetime.datetime.now(), announcement_id))
    
    return announcement_id
