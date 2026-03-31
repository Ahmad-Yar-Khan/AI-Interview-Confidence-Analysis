"""
resume_parser.py
----------------
Parses PDF or DOCX resumes into a structured ResumeProfile.
Works for any resume layout — regex patterns + spaCy NER.
Extracts: name, title, skills, experience, projects, education.
Category weights use canonical names matching preprocess_datasets.py.
"""

import re
import io
import logging
from typing import Optional
from dataclasses import dataclass, field

import pdfplumber
import docx
import spacy

logger = logging.getLogger(__name__)

try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    logger.warning("spaCy model not found. Run: python -m spacy download en_core_web_sm")
    nlp = None


# ════════════════════════════════════════
# DATA MODEL
# ════════════════════════════════════════

@dataclass
class ExperienceEntry:
    role: str
    company: str
    duration: str
    highlights: list[str] = field(default_factory=list)


@dataclass
class ResumeProfile:
    name: str = "Candidate"
    title: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    skills: list[str] = field(default_factory=list)
    experience: list[ExperienceEntry] = field(default_factory=list)
    education: list[str] = field(default_factory=list)
    projects: list[str] = field(default_factory=list)
    raw_text: str = ""
    category_weights: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "title": self.title,
            "email": self.email,
            "phone": self.phone,
            "location": self.location,
            "skills": self.skills,
            "experience": [
                {
                    "role": e.role,
                    "company": e.company,
                    "duration": e.duration,
                    "highlights": e.highlights,
                }
                for e in self.experience
            ],
            "education": self.education,
            "projects": self.projects,
            "category_weights": self.category_weights,
        }


# ════════════════════════════════════════
# SKILL → CATEGORY MAP
# Canonical names must match preprocess_datasets.py CATEGORY_MAP values.
# ════════════════════════════════════════

SKILL_CATEGORY_MAP = {
    "AI & Data Science": [
        "machine learning", "ml", "deep learning", "neural network", "tensorflow",
        "pytorch", "keras", "scikit-learn", "sklearn", "pandas", "numpy",
        "nlp", "natural language processing", "nltk", "spacy", "bert", "gpt",
        "transformer", "computer vision", "opencv", "cnn", "rnn", "lstm",
        "llm", "generative ai", "gan", "random forest", "xgboost",
        "gradient boosting", "k-means", "clustering", "regression",
        "classification", "feature engineering", "data science", "data analysis",
        "statistics", "featuretools", "gridsearchcv", "fairml",
        "anomaly detection", "time series", "recommender", "embedding",
        "hugging face", "langchain", "rag", "vector database", "faiss",
    ],
    "Software Engineering": [
        "python", "java", "javascript", "typescript", "c++", "c#", "go",
        "rust", "react", "angular", "vue", "node", "express", "django",
        "flask", "fastapi", "spring", "rest api", "graphql", "microservices",
        "oop", "design patterns", "solid", "git", "github", "agile", "scrum",
        "data structures", "algorithms", "system design", "object oriented",
        "software development", "programming", "backend", "frontend",
    ],
    "SQL & Databases": [
        "sql", "postgresql", "mysql", "sqlite", "oracle", "mssql",
        "database", "relational database", "query", "joins", "stored procedure",
        "index", "normalization", "nosql", "mongodb", "cassandra", "redis",
        "dynamodb", "data warehouse", "etl", "bigquery", "snowflake", "dbt",
    ],
    "Cloud & Containers": [
        "docker", "kubernetes", "k8s", "container", "aws", "azure", "gcp",
        "google cloud", "amazon web services", "ec2", "s3", "lambda",
        "serverless", "cloud", "terraform", "helm", "service mesh",
        "load balancer", "auto scaling", "cdn",
    ],
    "DevOps": [
        "ci/cd", "jenkins", "github actions", "gitlab ci", "circleci",
        "devops", "infrastructure as code", "iac", "ansible", "monitoring",
        "prometheus", "grafana", "elk", "splunk", "datadog", "sre",
        "site reliability", "pipeline", "deployment", "gitops",
    ],
    "DSA & Algorithms": [
        "data structures", "algorithms", "dsa", "sorting", "searching",
        "binary tree", "graph", "dynamic programming", "recursion",
        "hash map", "hash table", "linked list", "big o", "complexity",
    ],
    "Operating Systems": [
        "operating system", "os", "kernel", "process", "thread",
        "memory management", "virtual memory", "paging", "scheduling",
        "deadlock", "semaphore", "mutex", "file system", "linux", "unix",
    ],
    "Computer Networks": [
        "networking", "tcp", "udp", "ip", "http", "https", "dns",
        "osi model", "network protocol", "socket", "routing", "firewall", "vpn",
    ],
    "Distributed Systems": [
        "distributed system", "distributed computing", "cap theorem",
        "consensus", "replication", "sharding", "partition",
        "eventual consistency", "kafka", "message queue",
    ],
    "Concurrency": [
        "concurrency", "parallel", "parallelism", "thread", "mutex",
        "semaphore", "race condition", "deadlock", "async", "await",
        "coroutine", "lock", "synchronization", "multithreading",
    ],
    "HR & Behavioral": [],   # universal — always 0.50
}

# Flat list of all known skills for chip extraction
KNOWN_SKILLS = sorted({
    kw for kws in SKILL_CATEGORY_MAP.values() for kw in kws
})


# ════════════════════════════════════════
# TEXT EXTRACTION
# ════════════════════════════════════════

def extract_text_from_pdf(file_bytes: bytes) -> str:
    text_parts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            t = page.extract_text(layout=True)
            if t:
                text_parts.append(t)
    return "\n".join(text_parts)


def extract_text_from_docx(file_bytes: bytes) -> str:
    doc = docx.Document(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def extract_text(file_bytes: bytes, filename: str) -> str:
    fname = filename.lower()
    if fname.endswith(".pdf"):
        return extract_text_from_pdf(file_bytes)
    elif fname.endswith(".docx"):
        return extract_text_from_docx(file_bytes)
    elif fname.endswith(".txt"):
        return file_bytes.decode("utf-8", errors="replace")
    else:
        raise ValueError(f"Unsupported file type: {filename}. Use PDF, DOCX, or TXT.")


# ════════════════════════════════════════
# FIELD EXTRACTORS
# ════════════════════════════════════════

def extract_email(text: str) -> str:
    m = re.search(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}", text)
    return m.group(0) if m else ""


def extract_phone(text: str) -> str:
    m = re.search(r"(\+?\d{1,3}[\s.-]?)?(\(?\d{3}\)?[\s.-]?)?\d{3}[\s.-]?\d{4}", text)
    return m.group(0).strip() if m else ""


def extract_name(text: str) -> str:
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for line in lines[:8]:
        if re.search(r"[@|/\\<>]", line):
            continue
        if len(line.split()) <= 4 and re.match(r"^[A-Z][a-z]+([ \-][A-Z][a-z]+)+$", line):
            return line
    if nlp:
        doc = nlp(text[:500])
        for ent in doc.ents:
            if ent.label_ == "PERSON" and len(ent.text.split()) >= 2:
                return ent.text
    return lines[0] if lines else "Candidate"


def extract_title(text: str, name: str) -> str:
    TITLE_KW = [
        "engineer", "developer", "architect", "scientist", "analyst",
        "manager", "lead", "director", "consultant", "specialist",
        "designer", "researcher", "intern", "officer", "head",
        "full stack", "backend", "frontend", "devops", "ml", "ai",
        "data", "software", "cloud", "security", "qa", "product",
    ]
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for line in lines[:20]:
        if line == name:
            continue
        if any(kw in line.lower() for kw in TITLE_KW) and len(line.split()) <= 8:
            return line
    return ""


def extract_skills(text: str) -> list[str]:
    found = set()
    lower_text = text.lower()

    # Strategy 1: Skills section block
    skills_section = re.search(
        r"(skills?|technical skills?|core competencies|technologies)[:\s\n]+(.*?)(\n\n|\Z)",
        lower_text,
        re.IGNORECASE | re.DOTALL,
    )
    if skills_section:
        block = skills_section.group(2)
        tokens = re.split(r"[,|\n•·▪▸\-\t]+", block)
        for tok in tokens:
            tok = tok.strip()
            if 2 <= len(tok) <= 40 and not tok.isdigit():
                found.add(tok.title())

    # Strategy 2: Keyword scan
    for kw in KNOWN_SKILLS:
        if re.search(r"\b" + re.escape(kw) + r"\b", lower_text, re.IGNORECASE):
            found.add(kw.title())

    noise = {"And", "Or", "The", "With", "For", "A", "An", "In", "Of"}
    found = {s for s in found if s not in noise and len(s) > 1}
    return sorted(found)


def extract_experience(text: str) -> list[ExperienceEntry]:
    entries = []
    exp_match = re.search(
        r"(work\s+)?experience[:\s\n]+(.*?)(?=\n(education|projects?|skills?|certif|awards?|publications?)\b|\Z)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    block = exp_match.group(2) if exp_match else text
    job_splits = re.split(r"\n(?=[A-Z][^\n]{5,60}\n)", block)

    date_pattern = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|\d{4})"

    for chunk in job_splits:
        lines = [l.strip() for l in chunk.split("\n") if l.strip()]
        if not lines:
            continue
        role = lines[0]
        company = ""
        duration = ""

        for line in lines[1:4]:
            if re.search(date_pattern, line, re.IGNORECASE):
                duration = line
                continue
            if not line.startswith(("•", "-", "·", "▪")) and len(line.split()) <= 6:
                company = line

        highlights = []
        for line in lines:
            if re.match(r"^[•\-·▪▸]\s*", line):
                clean = re.sub(r"^[•\-·▪▸]\s*", "", line).strip()
                if len(clean) > 20:
                    highlights.append(clean)

        if role and len(role) > 3 and not role.startswith(("•", "-")):
            entries.append(ExperienceEntry(
                role=role,
                company=company,
                duration=duration,
                highlights=highlights[:6],
            ))

    return entries[:6]


def extract_education(text: str) -> list[str]:
    edu_match = re.search(
        r"education[:\s\n]+(.*?)(?=\n(experience|projects?|skills?|certif|awards?)\b|\Z)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if not edu_match:
        return []
    block = edu_match.group(1)
    lines = [l.strip() for l in block.split("\n") if l.strip()]
    degree_kw = ["bachelor", "master", "phd", "b.s", "m.s", "b.e", "m.e", "mba", "bsc", "msc"]
    return [
        line for line in lines
        if any(kw in line.lower() for kw in degree_kw) or re.search(r"\d{4}", line)
    ][:4]


def extract_projects(text: str) -> list[str]:
    proj_match = re.search(
        r"projects?[:\s\n]+(.*?)(?=\n(experience|education|skills?|certif|awards?)\b|\Z)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if not proj_match:
        return []
    block = proj_match.group(1)
    return [
        l.strip() for l in block.split("\n")
        if l.strip() and len(l.strip()) > 10
    ][:8]


# ════════════════════════════════════════
# CATEGORY WEIGHT CALCULATOR
# ════════════════════════════════════════

def compute_category_weights(profile: "ResumeProfile") -> dict:
    full_text = (
        " ".join(profile.skills)
        + " " + " ".join(
            e.role + " " + e.company + " " + " ".join(e.highlights)
            for e in profile.experience
        )
        + " " + " ".join(profile.projects)
        + " " + " ".join(profile.education)
        + " " + profile.title
    ).lower()

    weights = {}
    for category, keywords in SKILL_CATEGORY_MAP.items():
        if category == "HR & Behavioral":
            weights[category] = 0.50   # universal
            continue
        if not keywords:
            weights[category] = 0.10
            continue
        matches = sum(
            1 for kw in keywords
            if re.search(r"\b" + re.escape(kw) + r"\b", full_text)
        )
        weight = min(1.0, 0.10 + (matches / max(len(keywords) * 0.3, 1)) * 0.90)
        weights[category] = round(weight, 3)

    return weights


# ════════════════════════════════════════
# MAIN ENTRY POINT
# ════════════════════════════════════════

def parse_resume(file_bytes: bytes, filename: str) -> ResumeProfile:
    """
    Full pipeline: file bytes → ResumeProfile.
    Call this from the FastAPI /api/parse-resume route.
    """
    raw_text = extract_text(file_bytes, filename)

    profile = ResumeProfile(raw_text=raw_text)
    profile.email      = extract_email(raw_text)
    profile.phone      = extract_phone(raw_text)
    profile.name       = extract_name(raw_text)
    profile.title      = extract_title(raw_text, profile.name)
    profile.skills     = extract_skills(raw_text)
    profile.experience = extract_experience(raw_text)
    profile.education  = extract_education(raw_text)
    profile.projects   = extract_projects(raw_text)
    profile.category_weights = compute_category_weights(profile)

    logger.info(
        f"Parsed resume: '{profile.name}' | {len(profile.skills)} skills | "
        f"{len(profile.experience)} roles | weights={profile.category_weights}"
    )
    return profile
