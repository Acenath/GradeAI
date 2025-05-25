from flask_login import UserMixin
from helpers import *

import gc
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
import os
import docx
import re
import ast
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

class User(UserMixin):
    def __init__(self, user_id, email, _, first_name, last_name):
        self.user_id = user_id
        self.email = email
        self.first_name = first_name
        self.last_name = last_name

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
            _=None,
            first_name=user_data[3],
            last_name=user_data[4]
        )


    def is_authenticated(self, cursor):
        return True
    
    def is_active(self):
        return True
    
    def is_anonymous(self):
        return False
    
    def get_id(self):
        return self.user_id
    

class GradingAssistant():
    def __init__(self):
        self.model_name = "meta-llama/Meta-Llama-3-8B-Instruct"
        self.max_new_tokens = 512
        self.temperature = 0.2
        self.top_p = 0.64
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # Load model and tokenizer ONCE during initialization
        print("Loading model and tokenizer...")
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            device_map="auto" if self.device == "cuda" else None,
            torch_dtype=torch.bfloat16,
            attn_implementation="sdpa",  # Use Flash Attention if available
            low_cpu_mem_usage=False,  # Reduce CPU memory usage during loading
        ).eval()
        
        # Set chat template once
        self.tokenizer.chat_template = """{% for message in messages %}<|begin_of_text|><|start_header_id|>{{ message['role'] }}<|end_header_id|>\n\n{{ message['content'] | trim }}<|eot_id|>{% endfor %}{% if add_generation_prompt %}<|start_header_id|>assistant<|end_header_id|>\n\n{% endif %}"""
        
        # Set padding token
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        
        print("Model loaded successfully!")

    def _generate_response(self, messages):
        """Shared generation method to avoid code duplication"""
        # Apply template and tokenize
        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)

        # Generate response with optimized settings
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                temperature=self.temperature,
                top_p=self.top_p,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id,
                use_cache=True,  # Enable KV cache for faster generation
            )

        # Extract clean response
        full_response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        response = full_response.split("assistant<|end_header_id|>")[-1]
        response = response.split("<|eot_id|>")[0].strip()
        return response

    def generate_rubric(self):
        # No need to flush memory or reload model
        chat = [
            {"role": "system", "content": "You are an expert grading assistant responsible for writing grading rubrics for student essays."},
            {"role": "user", "content": self.question + "\n\n" + self.rubric_instructions}
        ]
        
        rubric = self._generate_response(chat)
        
        # Parse rubric (your existing parsing code)
        lines = rubric.strip().split('\n')
        rubrics = []
        for line in lines:
            if not line or not line[0].isdigit():
                continue
            try:
                first, last = -5, -6
                while line[first:last:-1].isdigit():
                    last += -1        
                last += 1 if last != -6 else 0
                rubric_score = line[first:last:-1][::-1]
                rubric_desc = line[3:len(line) - 7]
                rubric_info = {"rubric_score": rubric_score, "rubric_desc": rubric_desc}
                rubrics.append(rubric_info)
            except Exception as e:
                print(f"Error parsing rubric line: {line}, error: {e}")
        
        self.rubrics = rubrics
        return rubrics

    def grade_file(self, file_path, file_type, rubrics):
        # Read file content (your existing code)
        text_l = []
        if file_type == "docx":
            f = docx.Document(file_path)
            for docpara in f.paragraphs:
                text_l.append(docpara.text + "\n")

        formatted_rubrics = []
        for item in rubrics:
            curr_dict = {"description": item[0], "point": item[1]}
            formatted_rubrics.append(curr_dict)

        context = "".join(text_l)
        grading_instructions = f"""
            ### Rubric
            Each rubric item consists of a description and a point value. Grade the essay only using these rubric items:

            {formatted_rubrics}

            ### Instructions
            - Read the content of the essay provided (DOCX or PDF).
            - For each rubric item, give a score between 0 and the maximum defined in the rubric.
            - Do NOT give any explanations or feedback.
            - Output should be a **JSON list of objects**, where each object has:
                - "rubric_desc": the description of the rubric item
                - "rubric_score": the numeric score (integer)

            ### Output Format (JSON):
            [
            {{"rubric_desc": "Rubric description 1", "rubric_score": X}},
            ...
            ]

            Now grade the following essay based on the rubric.
            """
        
        chat = [
            {"role": "system", "content": "You are an expert academic grader. Your task is to evaluate an essay **strictly based on the rubric** provided."},
            {"role": "user", "content": context + "\n\n" + grading_instructions}
        ]

        rubric = self._generate_response(chat)
        
        print("THIS IS RUBRIC ITSELF ")
        print(rubric)
        
        # Parse JSON response (your existing code)
        match = re.search(r'\[\s*{.*?}\s*]', rubric, re.DOTALL)
        json_str = match.group(0)
        print("this is json_str")
        print(json_str)
        rubric_scores = ast.literal_eval(json_str)
        print("this is rubric_scores")
        print(rubric_scores)
        
        student_score = 0
        for item in rubric_scores:
            student_score += item["point"]
        return student_score

    def flush_memory(self):
        """Optional: call this if you need to free up memory"""
        if self.device == "cuda":
            torch.cuda.empty_cache()
        gc.collect()

    # Your other methods remain the same
    def create_rubric_instructions(self, current_rubrics, current_points):
        total_points = sum(current_points)
        total_score = 10 ** (len(str(total_points)) + 1)
        remaining_score = total_score - total_points
        self.rubric_instructions = f"""
        You are grading student solutions to the task described above.

        Design a **detailed grading rubric** that:

        • Total awards summed created by you need to equal to {remaining_score} **discrete, integer ** 
        • Breaks every concern into a **single, atomic, objectively verifiable step**  
        • Covers **input validation**, **case normalization**, **invalid-choice handling**, **random opponent move**, **game-logic checks**, and **clear output**  
        • Is comprehensive but granular: no bundled checks, no missing edge cases  
        • In below format x and y values can be any values that is correlated with inital teacher given rubrics and the other rublics related to question as well.
        • Uses this exact format:

        1. [Task description] (x pt)  
        2. [Task description] (y pt)  
        ...
        

        Additional requirements:
        • Numbers must be in plain text format (1. not 1))  
        • Points must use exactly "(x pt)" suffix  
        • No markdown/bold formatting in items  
        • No section headers or titles  

        Example of CORRECT format:
        1. Reads user input using Scanner (1pt)
        2. Converts input to lowercase (1pt)

        Example of INCORRECT format:
        **Input Handling**  
        1) Normalizes case  
        (2 points) Input validation

        Immutable rubrics given by creator:
        In this part you are not allowed to change any of the given inputs
        Rubrics and related points given by creator must remain same.
        You need to take account of these rubrics so that don't duplicate them
        Here are the immutable rubrics:
        {current_rubrics}

        """

    def consume_question(self, question):
        self.question = question
        