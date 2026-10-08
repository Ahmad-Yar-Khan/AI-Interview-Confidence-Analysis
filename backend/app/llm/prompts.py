"""
prompts.py
----------
Every prompt template used by the LLM layer, isolated from the code that
calls them. Prompt wording changes far more often than the Python logic
around it — this file is what you edit when tuning behavior, without
scrolling past unrelated code to find the string you want.
"""

CATEGORY_PROMPT = """Read this resume and return the 3 to 5 most relevant technical interview categories for this candidate.

Choose categories that are clearly evidenced by skills, projects, or work experience in the resume.
Use specific real interview domain names such as:
Machine Learning, Backend Engineering, Frontend Engineering, System Design,
SQL & Databases, Cloud & DevOps, Data Structures & Algorithms, Computer Networks,
Operating Systems, Distributed Systems, Concurrency, Cybersecurity, Data Engineering, etc.

Return ONLY a valid JSON array of strings, no explanation, no markdown fences.
Example: ["Machine Learning", "Backend Engineering", "System Design"]

RESUME:
{resume_text}
"""

QUESTION_PROMPT = """You are an expert technical interviewer generating questions for a specific candidate.

{job_section}CATEGORIES TO COVER:
{categories_str}
Always include 2 HR & Behavioral questions (open-ended, no model answer needed).

RETRIEVED RESUME CONTEXT — the most relevant sections for each category (retrieved via semantic similarity):
{category_context_str}

RULES:
- Reference the candidate's actual projects, companies, numbers, and technologies shown above
- Do NOT ask generic textbook questions — ask about what THIS candidate specifically has done
- Difficulty: ~25% Easy, 50% Medium, 25% Hard
- For technical questions: write a concise model answer (2-4 sentences)
- For HR & Behavioral: model_answer = null, has_answer = false
- Spread {tech_total} questions across the listed categories + 2 HR & Behavioral

Return ONLY a valid JSON array of exactly {total} questions. Each element:
{{
  "id": "q1",
  "question": "...",
  "category": "...",
  "difficulty": "Easy" | "Medium" | "Hard",
  "model_answer": "..." or null,
  "has_answer": true or false
}}
"""

QUESTION_PROMPT_FALLBACK = """You are an expert technical interviewer.
Generate exactly {total} interview questions tailored specifically to this candidate.
{job_section}
RULES:
- Every question must relate directly to something in the resume
- Mix: technical depth, system design, behavioral, experience-based
- Difficulty: ~25% Easy, 50% Medium, 25% Hard
- For technical questions: write a concise model answer (2-4 sentences)
- For behavioral questions: model_answer = null, has_answer = false
- Include 2 HR & Behavioral questions

Return ONLY a valid JSON array of exactly {total} questions. Each element:
{{
  "id": "q1",
  "question": "...",
  "category": "...",
  "difficulty": "Easy" | "Medium" | "Hard",
  "model_answer": "..." or null,
  "has_answer": true or false
}}

RESUME:
{resume_text}
"""

PERSONALIZE_PROMPT = """You are a technical interviewer preparing a personalized interview for a specific candidate.

Below are {count} template questions retrieved from a question bank. They define the TOPIC and DIFFICULTY to cover — but they are generic. Your job is to rewrite each one so it references something concrete from this candidate's resume: a specific project, technology choice, tool, or experience they actually have.

RULES:
- Keep the core concept of the template question (do not change the topic)
- Reference the candidate's actual work — name their project, the specific library they used, a decision they made
- If no specific resume detail maps cleanly, ask the concept in the context of their most relevant project
- Rewrite the model answer to reflect the candidate's context too (2–3 sentences)
- Preserve the original difficulty and category
- Return exactly {count} questions — one personalized rewrite per template

Return ONLY a valid JSON array of exactly {count} questions. Each element:
{{
  "id": "<keep original id>",
  "question": "<personalized question>",
  "category": "<keep original category>",
  "difficulty": "<keep original difficulty>",
  "model_answer": "<context-aware model answer>",
  "has_answer": true
}}

TEMPLATE QUESTIONS:
{questions_json}

CANDIDATE RESUME:
{resume_text}
"""

COMBINED_QUESTION_PROMPT = """You are a technical interviewer preparing a personalized interview for a specific candidate.

Complete TWO tasks in a single response:

━━━ TASK 1 — Personalize {dataset_count} template questions ━━━
Rewrite each template question to reference something specific from this candidate's resume.
- Keep the core concept, category, and difficulty unchanged
- Reference the candidate's actual project, technology used, or decision made
- Update the model answer to reflect the candidate's context (2–3 sentences)
- Preserve the original id

━━━ TASK 2 — Generate {project_count} new project questions ━━━
Write {project_count} new questions based strictly on the PROJECTS section below.
- Each must target a specific technical decision or implementation detail from a named project
- Do NOT overlap in topic with the template questions above
- Use ids "p1", "p2", etc.
- Assign the most fitting category (e.g. "Backend Engineering", "System Design", "Databases")
- Model answer: 2–3 sentences grounded in the project detail
- has_answer: true for all

Return ONLY a valid JSON object — no explanation, no markdown fences:
{{
  "dataset": [ ],
  "project": [ ]
}}

Each question element (both arrays use the same shape):
{{
  "id": "...",
  "question": "...",
  "category": "...",
  "difficulty": "Easy" | "Medium" | "Hard",
  "model_answer": "...",
  "has_answer": true
}}

TEMPLATE QUESTIONS — Task 1:
{questions_json}

RESUME:
{resume_text}

PROJECTS — Task 2:
{projects_text}
"""

PROJECT_QUESTION_PROMPT = """You are a technical interviewer preparing questions based on a candidate's project work.

Generate exactly {count} interview questions. Each question must target a specific technical decision, implementation detail, or challenge from one of the projects below — not a generic concept.

RULES:
- Reference a concrete detail from the project (a technology chosen, a problem solved, an architectural tradeoff)
- Write a model answer of 2–3 sentences based on what is described in the projects
- Difficulty mix: roughly half Medium, the rest split between Easy and Hard
- Assign the most fitting technical category (e.g. "Machine Learning", "Backend Engineering", "System Design", "Databases")
{avoid_section}
Return ONLY a valid JSON array of exactly {count} questions. Each element:
{{
  "id": "p1",
  "question": "...",
  "category": "...",
  "difficulty": "Easy" | "Medium" | "Hard",
  "model_answer": "...",
  "has_answer": true
}}

PROJECTS:
{projects_text}
"""

SCORE_PROMPT = """You are evaluating a candidate's interview answer. Be fair but rigorous.

Question: {question}
Category: {category}
{answer_context}
Candidate's Answer: {user_answer}

Score the answer and return ONLY a valid JSON object, no explanation, no markdown fences:
{{
  "overall": <integer 0-100>,
  "is_behavioral": <true or false>,
  "angles": {{
    "conceptual": <integer 0-100>,
    "technical": <integer 0-100>,
    "completeness": <integer 0-100>
  }},
  "feedback": "<1-2 sentences of constructive feedback>"
}}

Scoring guide:
- For TECHNICAL questions (has model answer): score conceptual correctness, technical accuracy, and completeness vs the expected answer.
- For BEHAVIORAL questions (no model answer): score on effort/detail (conceptual), use of specific examples (technical), and STAR structure (completeness).
- overall should reflect the weighted combination of the three angles.
"""
