import re
import json
import ast
full_text = """THIS IS RUBRIC ITSELF 
system

You are an expert academic grader. Your task is to evaluate an essay **strictly based on the rubric** provided.user

Confronting Climate Change: A Global Imperative
Climate change represents one of the most pressing challenges facing humanity today. Driven largely by human activity, particularly the burning of fossil fuels and deforestation, climate change has led to rising global temperatures, extreme weather events, melting ice caps, and sea level rise. Its impact reaches every corner of the globe, affecting ecosystems, economies, and societies in profound ways.
At the heart of climate change is the enhanced greenhouse effect. Human actions, especially the combustion of coal, oil, and natural gas, have significantly increased the concentration of greenhouse gases such as carbon dioxide (CO₂) and methane (CH₄) in the atmosphere. These gases trap heat, leading to global warming. According to the Intergovernmental Panel on Climate Change (IPCC), the Earth's average surface temperature has risen by about 1.1°C since the late 19th century, with most of the warming occurring in the past 40 years.
The consequences of climate change are already visible. Glaciers and polar ice sheets are melting at alarming rates, contributing to rising sea levels that threaten coastal communities. More frequent and intense hurricanes, wildfires, droughts, and heatwaves are disrupting natural systems and human life. Biodiversity is declining as species struggle to adapt to rapidly changing habitats, and food and water security are increasingly at risk in vulnerable regions.
Addressing climate change requires a coordinated global response. This includes transitioning to renewable energy sources, improving energy efficiency, conserving forests, and promoting sustainable agricultural practices. International agreements such as the Paris Agreement aim to limit global warming to well below 2°C, with an ideal target of 1.5°C. Success hinges on the commitment of governments, businesses, and individuals alike.
In conclusion, climate change is not a distant threat—it is a current reality. Immediate and sustained action is essential to mitigate its effects and build a more resilient and sustainable future. The choices we make today will determine the world that future generations inherit.



            ### Rubric
            Each rubric item consists of a description and a point value. Grade the essay only using these rubric items:

            [{'description': 'Clearly states the thesis statement and provides a concise overview of the essay', 'point': 5.0}, {'description': 'Provides a well-organized and logical structure to the essay, with a clear introduction, body, and conclusion ', 'point': 10.0}, {'description': 'Effectively argues the causes and effects of climate change, using credible sources and evidence ', 'point': 20.0}, {'description': 'Discusses potential solutions to mitigate the effects of climate change, including personal actions and policy changes ', 'point': 15.0}, {'description': 'Uses proper grammar, spelling, and punctuation throughout the essay', 'point': 5.0}, {'description': 'Demonstrates a clear and concise writing style, avoiding jargon and technical terms', 'point': 5.0}, {'description': 'Addresses potential counterarguments and provides a thoughtful conclusion that summarizes the main points ', 'point': 10.0}, {'description': 'Includes a bibliography or references page with at least 3 credible sources', 'point': 5.0}, {'description': 'Adheres to the required word count and formatting guidelines', 'point': 5.0}, {'description':'Demonstrates a clear understanding of the topic and its significance, with a thoughtful and well-supported argument ', 'point': 20.0}]

            ### Instructions
            - Read the content of the essay provided (DOCX or PDF).
            - For each rubric item, give a score between 0 and the maximum defined in the rubric.
            - Do NOT give any explanations or feedback.
            - Output should be a **JSON list of objects**, where each object has:
                - "rubric_desc": the description of the rubric item
                - "rubric_score": the numeric score (integer)

            ### Output Format (JSON):
            [
            {"rubric_desc": "Rubric description 1", "rubric_score": X},
           ...
            ]

            Now grade the following essay based on the rubric.assistant

Here is the graded essay in JSON format:

[
  {"rubric_desc": "Clearly states the thesis statement and provides a concise overview of the essay", "rubric_score": 5.0},
  {"rubric_desc": "Provides a well-organized and logical structure to the essay, with a clear introduction, body, and conclusion", "rubric_score": 9.0},
  {"rubric_desc": "Effectively argues the causes and effects of climate change, using credible sources and evidence", "rubric_score": 19.0},
  {"rubric_desc": "Discusses potential solutions to mitigate the effects of climate change, including personal actions and policy changes", "rubric_score": 14.0},
  {"rubric_desc": "Uses proper grammar, spelling, and punctuation throughout the essay", "rubric_score": 5.0},
  {"rubric_desc": "Demonstrates a clear and concise writing style, avoiding jargon and technical terms", "rubric_score": 5.0},
  {"rubric_desc": "Addresses potential counterarguments and provides a thoughtful conclusion that summarizes the main points", "rubric_score": 9.0},
  {"rubric_desc": "Includes a bibliography or references page with at least 3 credible sources", "rubric_score": 0.0},
  {"rubric_desc": "Adheres to the required word count and formatting guidelines", "rubric_score": 5.0},
  {"rubric_desc": "Demonstrates a clear understanding of the topic and its significance, with a thoughtful and well-supported argument", "rubric_score": 19.0}
]"""

# This regex finds the first full JSON array in the text
match = re.search(r'\[\s*{.*?}\s*]', full_text, re.DOTALL)

if match:
    json_str = match.group(0)

    # OPTION 1: Using ast (recommended)
    rubric_scores = ast.literal_eval(json_str)

    # OPTION 2: Using JSON (if needed)
    # json_str = json_str.replace("'", '"')
    # rubric_scores = json.loads(json_str)

    print(rubric_scores)
else:
    print("No JSON found.")
