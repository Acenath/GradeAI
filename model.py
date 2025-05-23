#!/usr/bin/env python
# make_rubric.py
# ---------------------------------------------------------------------
# Generates a detailed 1-point-per-check grading rubric for the
# rock-paper-scissors Java assignment, using Llama-3-8B-Instruct.
# ---------------------------------------------------------------------

import gc
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

# ── Settings ─────────────────────────────────────────────────────────
MODEL_NAME      = "meta-llama/Meta-Llama-3-8B-Instruct"  # Verified correct # Qwen/Qwen2.5-0.5B-Instruct
MAX_NEW_TOKENS  = 768
TEMPERATURE     = 0.3                        # Lower for strict formatting
TOP_P           = 0.95
DEVICE          = "cuda" if torch.cuda.is_available() else "cpu"

# ── Original assignment ─────────────────────────────────────────────
coding_question = """Write a Java program that implements the rock-paper-scissors game..."""  # (keep your full question)

# ── Rubric instructions ──────────────────────────────────────────────
rubric_instructions = """
You are grading student solutions to the task described above.

Design a **detailed grading rubric** that:

• Awards **exactly 1 point per check**  
• Breaks every concern into a **single, atomic, objectively verifiable step**  
• Covers **input validation**, **case normalization**, **invalid-choice handling**, **random opponent move**, **game-logic checks**, and **clear output**  
• Is comprehensive but granular: no bundled checks, no missing edge cases  
• Uses this exact format:

1. [Task description] (1pt)  
2. [Task description] (1pt)  
...

Additional requirements:
• Numbers must be in plain text format (1. not 1))  
• Points must use exactly "(1pt)" suffix  
• No markdown/bold formatting in items  
• No section headers or titles  

Example of CORRECT format:
1. Reads user input using Scanner (1pt)
2. Converts input to lowercase (1pt)

Example of INCORRECT format:
**Input Handling**  
1) Normalizes case  
(2 points) Input validation
"""

# ── Memory management ────────────────────────────────────────────────
def flush_memory():
    if DEVICE == "cuda":
        torch.cuda.empty_cache()
    gc.collect()

# ── Main function ────────────────────────────────────────────────────
def generate_rubric():
    flush_memory()

    # Load model with correct config
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        device_map="auto" if DEVICE == "cuda" else None,
        torch_dtype=torch.bfloat16,
        attn_implementation="sdpa"
    ).eval()

    # Official Llama-3 chat template
    tokenizer.chat_template = """{% for message in messages %}<|begin_of_text|><|start_header_id|>{{ message['role'] }}<|end_header_id|>\n\n{{ message['content'] | trim }}<|eot_id|>{% endfor %}{% if add_generation_prompt %}<|start_header_id|>assistant<|end_header_id|>\n\n{% endif %}"""

    # Build chat prompt
    chat = [
        {"role": "system", "content": "You are an expert CS rubric designer."},
        {"role": "user", "content": coding_question + "\n\n" + rubric_instructions}
    ]
    
    # Apply template and tokenize
    prompt = tokenizer.apply_chat_template(
        chat,
        tokenize=False,
        add_generation_prompt=True
    )
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

    # Generate response
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            temperature=TEMPERATURE,
            top_p=TOP_P,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id
        )

    # Extract clean rubric
    full_response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    rubric = full_response.split("assistant<|end_header_id|>")[-1]  # Split after last prompt
    rubric = rubric.split("<|eot_id|>")[0].strip()  # Remove any trailing artifacts
    
    return rubric

# ── Execution ────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\nGenerating rubric…\n")
    try:
        print(generate_rubric())
    except KeyboardInterrupt:
        print("\nInterrupted by user.")