from transformers import AutoTokenizer, AutoModelForCausalLM, AutoTokenizer, Gemma3ForCausalLM
import torch
import gc

torch.cuda.empty_cache()
gc.collect()


model_name = "meta-llama/Llama-3.2-1B"
#model_name = "meta-llama/Llama-3.2-3B"  # Or another local/custom model
#model_name = "meta-llama/Llama-3.1-8B"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name, device_map="auto")


#model = Gemma3ForCausalLM.from_pretrained("google/gemma-2-9b")
#tokenizer = AutoTokenizer.from_pretrained("google/gemma-2-9b")

questions_l = []

coding_question = """
Rock-paper-scissors is a game where two opponents select one of rock, paper or scissors. Based on the following rules, one of the players beats the other one:
    • Rock beats Scissors.
    • Scissors beats Paper.
    • Paper beats Rock.

Given the following programming task, break it down into a detailed grading rubric with the following constraints:

- Each grading task must be worth exactly **1 point**.
- Each task must represent a **single, atomic skill or check** (e.g., normalize input to lowercase, validate against allowed choices, print computer’s choice).
- Tasks must be **clearly numbered**, **labeled**, and phrased as **objective checks** a grader can verify in student code.
- Do not combine multiple tasks into one.
- Subdivide larger ideas (like “input handling” or “comparison logic”) into their smallest meaningful steps.
- The rubric should comprehensively cover input validation, normalization, game logic, randomness, and output clarity.
- Use this format exactly:

1. [Task description] (1pt)
2. [Task description] (1pt)
...

Only generate the rubric list. Do not include explanations or code.
Write a Java program that implements the rock-paper-scissors game. You have only one player (the user) playing against the computer. 
You will take the choice of the user as a String. User might use a mix of capital or lowercase letters to enter their choice. 
User might also enter something unexpected/invalid as well (e.g. 1 instead of rock or cat instead of paper). 
Your code must handle these inputs. Then, the computer will randomly select one of rock, paper or scissors. 
Print the computer's choice. Compare user's choice against the computer's choice based on the rules of the game given above. 
Print who wins. You are not allowed to use switch-case in this question.
"""

prompt = f"""
You are an experienced computer science instructor and rubric designer.

Programming Task:
\"\"\"
{coding_question.strip()}
\"\"\"

Rubric:
TASKS:
"""


inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

with torch.no_grad():
    outputs = model.generate(
        **inputs,
        max_new_tokens=1000,
        temperature=0.5,
        top_p=0.3,
    )

generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)

generated_rubric = generated_text[len(prompt):].strip()

print("\n===== GENERATED RUBRIC =====\n")
print(generated_rubric)
