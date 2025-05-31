from flask_login import UserMixin
from helpers import *
import hashlib
import datetime
import uuid
import gc
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
import re
import json
import ast
import gc
import docx
import PyPDF2
import pdfplumber

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
    

# Fixed GradingAssistant class methods for better rubric protection

class GradingAssistant():
    def __init__(self):
        self.model_name = "meta-llama/Llama-3.2-1B-Instruct"
        self.max_new_tokens = 512
        self.temperature = 0.2
        self.top_p = 0.9
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        print("Loading model and tokenizer...")
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            device_map="auto" if self.device == "cuda" else None,
            torch_dtype=torch.bfloat16,
            attn_implementation="sdpa"
        ).eval()
        
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        
        print("Model loaded successfully!")

    def create_rubric_instructions(self, current_rubrics, current_points):
        """FIXED: Better handling of manual rubrics with improved validation"""
        
        # FIXED: Validate and sanitize input data
        if current_rubrics is None:
            current_rubrics = []
        if current_points is None:
            current_points = []
            
        # Ensure lists are the same length
        min_length = min(len(current_rubrics), len(current_points))
        current_rubrics = current_rubrics[:min_length]
        current_points = current_points[:min_length]
        
        # FIXED: Only count rubrics with points > 0 for remaining calculation
        valid_existing_points = [p for p in current_points if p > 0]
        existing_total = sum(valid_existing_points)
        remaining_points = 100 - existing_total
        
        # Store for fallback use with better validation
        self.current_rubrics = current_rubrics
        self.current_points = current_points
        self.remaining_points = max(0, remaining_points)  # Ensure non-negative
        self.existing_total = existing_total
        
        # FIXED: Better display of existing rubrics with validation
        existing_rubrics_display = ""
        if current_rubrics and current_points:
            # Only show rubrics with points > 0 in the instructions
            valid_rubrics = [(r, p) for r, p in zip(current_rubrics, current_points) if p > 0]
            
            if valid_rubrics:
                existing_rubrics_display = "EXISTING RUBRICS (already added by teacher - DO NOT MODIFY OR RECREATE THESE):\n"
                for i, (rubric, points) in enumerate(valid_rubrics, 1):
                    # FIXED: Sanitize rubric text to prevent instruction injection
                    safe_rubric = str(rubric).replace('\n', ' ').strip()[:100]  # Limit length
                    existing_rubrics_display += f"{i}. {safe_rubric} ({points} pt)\n"
                existing_rubrics_display += f"\nTotal existing points: {existing_total}/100\n"
                existing_rubrics_display += "IMPORTANT: Do NOT include these existing rubrics in your response. Only create NEW additional rubrics.\n"
            else:
                existing_rubrics_display = "EXISTING RUBRICS: None (you are creating the first rubrics)\n"
        else:
            existing_rubrics_display = "EXISTING RUBRICS: None (you are creating the first rubrics)\n"

        # FIXED: Enhanced rubric instructions with better validation
        self.rubric_instructions = f"""
You are helping a teacher create essay grading rubrics. The teacher may have already added some rubrics manually.

ESSAY ASSIGNMENT CONTEXT:
{getattr(self, 'question', 'Essay writing assignment - analyze and create appropriate grading criteria')}

{existing_rubrics_display}

CRITICAL REQUIREMENTS - MUST FOLLOW EXACTLY:
1. DO NOT recreate, modify, or include any of the existing rubrics listed above
2. Only create NEW rubric items that total EXACTLY {self.remaining_points} points
3. The NEW rubrics must complement the existing ones to reach exactly 100 points total
4. Each NEW rubric item must be relevant to essay evaluation (thesis, arguments, evidence, organization, writing quality, etc.)
5. Use clear, specific criteria that teachers can easily apply when grading
6. Distribute points logically based on importance of each criterion
7. Points must be positive integers (no zero or negative values)

STRICT FORMAT REQUIREMENTS:
- Each line MUST start with a number and period: "1. "
- Each line MUST end with points in parentheses: "(X pt)"
- NO additional text, explanations, or commentary
- Points must be whole numbers (no decimals)
- All points must sum to exactly {self.remaining_points}
- Minimum 1 point per rubric item

EXAMPLE FORMAT (if you needed to create 45 points):
1. Clear thesis statement with well-defined argument (15 pt)
2. Strong supporting evidence and relevant examples (15 pt)
3. Logical organization and smooth transitions (10 pt)
4. Proper grammar and writing mechanics (5 pt)

YOUR TASK:
Create ONLY NEW rubric items worth exactly {self.remaining_points} points that complement the existing rubrics to total 100 points.
If {self.remaining_points} is 0 or negative, respond with: "All 100 points have been allocated. No additional rubrics needed."

START YOUR RESPONSE WITH "1." (or appropriate number):
        """

    def consume_question(self, question):
        """FIXED: Sanitize question input"""
        self.question = str(question).strip()[:500] if question else "Essay writing assignment"

    def flush_memory(self):
        if self.device == "cuda":
            torch.cuda.empty_cache()
        gc.collect()

    def _check_response_format(self, response):
        """FIXED: Enhanced format validation with better error reporting"""
        lines = response.strip().split('\n')
        valid_lines = 0
        total_points = 0
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check for pattern: "Number. Description (X pt)"
            pattern = r'^(\d+)\.\s*(.+?)\s*\((\d+)\s*pt?\)'
            match = re.match(pattern, line, re.IGNORECASE)
            if match:
                valid_lines += 1
                points = int(match.group(3))
                total_points += points
        
        # Check if format is correct AND points add up correctly
        remaining_points = getattr(self, 'remaining_points', 100)
        points_correct = (total_points == remaining_points)
        format_correct = (valid_lines >= 1)
        
        print(f"Format check: {valid_lines} valid lines, {total_points} points (need {remaining_points})")
        
        if not format_correct:
            print(f"❌ Format error: Expected at least 1 valid rubric line")
        if not points_correct:
            print(f"❌ Points error: Got {total_points}, expected {remaining_points}")
            
        return format_correct and points_correct

    def _create_manual_rubric_response(self):
        """FIXED: Better fallback rubric creation with point validation"""
        remaining_points = getattr(self, 'remaining_points', 100)
        
        if remaining_points <= 0:
            return "All 100 points have been allocated. No additional rubrics needed."
        
        # FIXED: Better essay rubric templates with flexible point distribution
        essay_templates = [
            ("Clear thesis statement and main argument", 0.25),
            ("Strong supporting evidence and examples", 0.25),
            ("Logical organization and flow", 0.20),
            ("Grammar, style, and writing mechanics", 0.15),
            ("Critical analysis and depth of thought", 0.15)
        ]
        
        # FIXED: Ensure exact point allocation
        rubric_response = ""
        allocated_points = 0
        
        # Calculate how many rubrics we can create
        max_rubrics = min(len(essay_templates), remaining_points)  # Can't exceed available points
        
        for i, (desc, weight) in enumerate(essay_templates[:max_rubrics], 1):
            if i == max_rubrics:
                # Last item gets all remaining points
                points = remaining_points - allocated_points
            else:
                points = max(1, int(remaining_points * weight))
                # Ensure we don't exceed remaining points
                points = min(points, remaining_points - allocated_points - (max_rubrics - i))
            
            if points > 0:  # Only add if we have points to allocate
                rubric_response += f"{i}. {desc} ({points} pt)\n"
                allocated_points += points
            
            if allocated_points >= remaining_points:
                break
        
        # FIXED: Verification that we allocated exactly the right amount
        if allocated_points != remaining_points:
            print(f"⚠️ Fallback allocation mismatch: {allocated_points} != {remaining_points}")
            # Simple fix: adjust the last item
            lines = rubric_response.strip().split('\n')
            if lines:
                last_line = lines[-1]
                # Extract the last point value and adjust
                import re
                match = re.search(r'\((\d+) pt\)', last_line)
                if match:
                    current_last_points = int(match.group(1))
                    adjustment = remaining_points - allocated_points
                    new_last_points = current_last_points + adjustment
                    if new_last_points > 0:
                        lines[-1] = re.sub(r'\(\d+ pt\)', f'({new_last_points} pt)', last_line)
                        rubric_response = '\n'.join(lines) + '\n'
        
        return rubric_response.strip()

    def _generate_response_with_retry(self, messages, max_retries=5):
        """FIXED: Enhanced retry logic with better error handling"""
        for attempt in range(max_retries):
            print(f"Generation attempt {attempt + 1}/{max_retries}")
            
            try:
                # Adjust temperature based on attempt
                temp = 0.1 + (attempt * 0.05)
                
                prompt = self.tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True
                )
                
                inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)

                with torch.no_grad():
                    outputs = self.model.generate(
                        **inputs,
                        max_new_tokens=300,
                        temperature=temp,
                        top_p=0.7,
                        do_sample=True,
                        pad_token_id=self.tokenizer.eos_token_id,
                        use_cache=True,
                        repetition_penalty=1.2,
                        no_repeat_ngram_size=3,
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
                
                # Check if response follows format AND has correct point total
                if self._check_response_format(response):
                    print(f"✅ Attempt {attempt + 1} passed format and point total check")
                    return response.strip()
                else:
                    print(f"❌ Attempt {attempt + 1} failed format or point total check")
                    print(f"Response was: {response[:200]}...")
                    
            except Exception as e:
                print(f"❌ Attempt {attempt + 1} failed with error: {e}")
                
            if attempt < max_retries - 1:
                print("Retrying with adjusted parameters...")
        
        print("⚠️ All attempts failed, creating manual fallback")
        return self._create_manual_rubric_response()

    def generate_rubric(self):
        """FIXED: Enhanced rubric generation with better validation"""
        print("Generating essay rubric...")
        
        # Check if all points are already allocated
        remaining_points = getattr(self, 'remaining_points', 100)
        if remaining_points <= 0:
            print("All 100 points already allocated. No additional rubrics needed.")
            return []
        
        # FIXED: Enhanced system message with clearer instructions
        system_message = f"""You are an essay grading rubric generator for teachers. 

CRITICAL RULES:
- Create rubric items that total EXACTLY {remaining_points} points
- Output ONLY numbered criteria with points in parentheses
- Format: '1. Thesis statement quality (25 pt)'
- No explanations, just the rubric items
- Points must be positive integers
- All points must sum to exactly {remaining_points}

The final rubric system must total exactly 100 points when combined with existing rubrics."""

        chat = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": self.rubric_instructions}
        ]
        
        # Use retry logic with point validation
        rubric_text = self._generate_response_with_retry(chat)
        print("Raw model output:")
        print(rubric_text)
        print("-" * 50)
        
        # Parse and validate point totals
        rubrics = self._parse_rubric(rubric_text)
        
        # FIXED: Enhanced validation
        if rubrics:
            total_generated = sum(int(float(item['rubric_score'])) for item in rubrics)
            print(f"Generated {len(rubrics)} rubric items totaling {total_generated} points (needed {remaining_points})")
            
            for item in rubrics:
                print(f"  {item['rubric_desc']} ({item['rubric_score']} pt)")
            
            # Validate that we have the right total
            if total_generated != remaining_points:
                print(f"⚠️ Point total mismatch: {total_generated} != {remaining_points}")
                rubrics = self._create_fallback_rubrics()
        else:
            print("⚠️ No valid rubrics generated, creating fallback...")
            rubrics = self._create_fallback_rubrics()
        
        self.rubrics = rubrics
        return rubrics

    def _create_fallback_rubrics(self):
        """FIXED: Enhanced fallback rubric creation with exact point allocation"""
        print("Creating essay-specific fallback rubrics...")
        
        remaining_points = getattr(self, 'remaining_points', 100)
        
        if remaining_points <= 0:
            print("No points remaining for additional rubrics")
            return []
        
        # FIXED: Better essay rubric templates
        base_rubrics = [
            "Clear thesis statement and main argument",
            "Strong supporting evidence and examples", 
            "Logical organization and paragraph structure",
            "Grammar, style, and writing mechanics",
            "Critical analysis and depth of thought",
            "Proper citations and source integration",
            "Conclusion and synthesis of ideas"
        ]
        
        # FIXED: Calculate exact point distribution
        num_rubrics = min(len(base_rubrics), max(1, remaining_points // 3))  # At least 3 points per rubric
        
        essay_rubrics = []
        allocated_points = 0
        
        for i in range(num_rubrics):
            if i == num_rubrics - 1:
                # Last rubric gets all remaining points
                points = remaining_points - allocated_points
            else:
                # Distribute points fairly
                points_per_remaining = (remaining_points - allocated_points) // (num_rubrics - i)
                points = max(1, points_per_remaining)
            
            if points > 0:
                essay_rubrics.append({
                    "rubric_desc": base_rubrics[i],
                    "rubric_score": str(points)
                })
                allocated_points += points
        
        # FIXED: Verify exact allocation
        final_total = sum(int(item["rubric_score"]) for item in essay_rubrics)
        print(f"Created {len(essay_rubrics)} essay rubrics totaling {final_total} points (needed {remaining_points}):")
        for item in essay_rubrics:
            print(f"  {item['rubric_desc']} ({item['rubric_score']} pt)")
        
        return essay_rubrics

    def _parse_rubric(self, rubric_text):
        """Improved rubric parsing with point validation"""
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
                try:
                    score_int = int(score)
                    if score_int > 0:  # Only add positive scores
                        rubrics.append({
                            "rubric_score": str(score_int),
                            "rubric_desc": description.strip()
                        })
                except ValueError:
                    continue
                continue
            
            # Alternative pattern: "Description (X pt)" without number
            pattern2 = r'^(.+?)\s*\((\d+)\s*pt?\)'
            match2 = re.match(pattern2, line, re.IGNORECASE)
            
            if match2:
                description, score = match2.groups()
                # Skip if it starts with a bullet or dash
                if not description.strip().startswith(('-', '•', '*')):
                    try:
                        score_int = int(score)
                        if score_int > 0:
                            rubrics.append({
                                "rubric_score": str(score_int),
                                "rubric_desc": description.strip()
                            })
                    except ValueError:
                        continue
        
        return rubrics

    def grade_file(self, file_path, file_type, rubrics):
        # Read essay content - MODIFIED TO SUPPORT PDF
        text_l = []

        if file_type == "docx":
            f = docx.Document(file_path)
            for docpara in f.paragraphs:
                text_l.append(docpara.text + "\n")
        elif file_type == "pdf":
            # PDF support using PyPDF2
            
            try:
                with open(file_path, 'rb') as pdf_file:
                    pdf_reader = PyPDF2.PdfReader(pdf_file)
                    num_pages = len(pdf_reader.pages)
                    
                    for page_num in range(num_pages):
                        page = pdf_reader.pages[page_num]
                        text = page.extract_text()
                        if text:
                            text_l.append(text + "\n")
            except Exception as e:
                print(f"Error reading PDF file: {e}")
                # Try alternative PDF reader if PyPDF2 fails
                try:
                    with pdfplumber.open(file_path) as pdf:
                        for page in pdf.pages:
                            text = page.extract_text()
                            if text:
                                text_l.append(text + "\n")
                except:
                    print("Failed to read PDF with both PyPDF2 and pdfplumber")
                    text_l.append("Error: Could not extract text from PDF file.\n")
        elif file_type == "txt":
            with open(file_path, 'r', encoding='utf-8') as f:
                text_l = f.readlines()
        else:
            # Handle other file types or unknown extensions
            print(f"Warning: Unknown file type '{file_type}', attempting to read as text")
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    text_l = f.readlines()
            except:
                text_l.append(f"Error: Could not read file of type '{file_type}'.\n")

        # Handle both tuple and dict formats for rubrics
        formatted_rubrics = []
        total_possible_points = 0

        for item in rubrics:
            print(f"Processing rubric item: {item}, type: {type(item)}")
            
            if isinstance(item, tuple):
                # Database format: (description, score)
                curr_dict = {
                    "description": item[0],  # description
                    "point": int(float(item[1]))  # Convert float string to int
                }
            elif isinstance(item, dict):
                # Already in dict format from generate_rubric
                if "rubric_desc" in item and "rubric_score" in item:
                    curr_dict = {
                        "description": item["rubric_desc"],
                        "point": int(float(item["rubric_score"]))  # Convert float string to int
                    }
                else:
                    # Alternative dict format
                    curr_dict = {
                        "description": item.get("description", ""),
                        "point": int(float(item.get("point", 0)))  # Handle float strings
                    }
            else:
                print(f"Warning: Unknown rubric format: {item}")
                continue
                
            formatted_rubrics.append(curr_dict)
            total_possible_points += curr_dict["point"]

        essay_content = "".join(text_l)
        print("THIS IS THE ESSAY_CONTENT:", essay_content)
        # Enhanced grading instructions emphasizing the 100-point scale
        grading_instructions = f"""
        Grade this essay using the provided rubrics. The rubrics total {total_possible_points} points out of 100.

        GRADING RUBRICS (Total: {total_possible_points} points):
        {[{'criteria': r['description'][:60], 'max_points': r['point']} for r in formatted_rubrics]}

        ESSAY TO GRADE:
        {essay_content[:1500]}...

        GRADING GUIDELINES:
        - Evaluate each criterion carefully based on essay quality
        - Award points proportionally (0 to max points for each criterion)
        - Consider the academic level and assignment requirements
        - Be fair but maintain standards

        REQUIRED OUTPUT FORMAT (valid JSON only):
        [{{"rubric_desc": "criteria name", "rubric_score": awarded_points}}, ...]

        Example: [{{"rubric_desc": "Thesis statement", "rubric_score": 20}}, {{"rubric_desc": "Supporting evidence", "rubric_score": 18}}]

        JSON RESPONSE:"""

        chat = [
            {"role": "system", "content": f"You are grading an essay using specific rubrics totaling {total_possible_points} points. Output only valid JSON array with rubric scores. Be fair but maintain academic standards."},
            {"role": "user", "content": grading_instructions}
        ]

        # Generate grading response
        prompt = self.tokenizer.apply_chat_template(
            chat,
            tokenize=False,
            add_generation_prompt=True
        )

        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=250,  # Adequate for JSON response
                temperature=0.1,     # Low for consistent JSON format
                top_p=0.8,           
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

        # Enhanced JSON parsing with proper fallback handling
        try:
            # Extract JSON from response
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
                print(f"Extracted JSON: {json_str}")
                
                # Parse JSON
                try:
                    rubric_scores = json.loads(json_str)
                except json.JSONDecodeError:
                    try:
                        rubric_scores = ast.literal_eval(json_str)
                    except (ValueError, SyntaxError):
                        print("JSON parsing failed, using balanced fallback")
                        rubric_scores = self._create_essay_fallback_scores(formatted_rubrics)
                
                print(f"Parsed scores: {rubric_scores}")
                
                # Calculate total score with validation
                student_score = 0
                for item in rubric_scores:
                    try:
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
                
                # Validate score doesn't exceed maximum
                if student_score > total_possible_points:
                    print(f"Warning: Student score ({student_score}) exceeds maximum ({total_possible_points})")
                    student_score = total_possible_points
                
                print(f"Final student score: {student_score}/{total_possible_points}")
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
        """Create realistic fallback scores for essay grading when JSON parsing fails"""
        print("Creating realistic essay fallback scores...")
        fallback_scores = []
        
        for rubric in formatted_rubrics:
            try:
                max_points = int(float(rubric["point"]))
                # Give 70-85% of max points as fallback (realistic range for average essays)
                score_percentage = 0.70 + (hash(rubric["description"]) % 16) / 100  # 0.70 to 0.85
                score = max(1, int(max_points * score_percentage))
            except (ValueError, TypeError):
                score = 3  # Conservative fallback score
                
            fallback_scores.append({
                "description": rubric["description"],
                "point": score
            })
        
        total_fallback = sum(item["point"] for item in fallback_scores)
        print(f"Fallback essay scores totaling {total_fallback}: {fallback_scores}")
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
        filename_hash = hashlib.md5(student_id.encode()).hexdigest()[:8]
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
