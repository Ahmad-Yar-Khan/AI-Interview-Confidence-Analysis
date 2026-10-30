"""
roles.py
--------
The fixed job-title list behind the frontend dropdown. Single source of truth:
the frontend fetches it from GET /api/roles, the weekly job researches every
entry, and the question route validates the incoming slug against it.

Each entry is (display name, search name). The display name is what the user
sees; the search name is the single primary term used in web queries, so a
combined row like "Cloud Engineer / Cloud Architect" doesn't produce a muddled
query. Slugs are derived from the display name and are stable cache keys.
"""

import re
from dataclasses import dataclass

OTHER_SLUG = "other"


@dataclass(frozen=True)
class Role:
    slug: str
    name: str
    search_name: str
    category: str


_RAW: dict[str, list[tuple[str, str]]] = {
    "Software Development": [
        ("Software Engineer / Software Developer", "software engineer"),
        ("Front-End Developer", "front-end developer"),
        ("Back-End Developer", "back-end developer"),
        ("Full-Stack Developer", "full-stack developer"),
        ("Mobile Developer (iOS / Android)", "mobile app developer iOS Android"),
        ("Embedded Systems Engineer", "embedded systems engineer"),
        ("Game Developer", "game developer"),
        ("Application Developer", "application developer"),
        ("Senior / Staff / Principal Engineer", "senior staff principal software engineer"),
        ("Software Architect", "software architect"),
        ("Engineering Manager", "engineering manager"),
        ("Director of Engineering / VP of Engineering / CTO", "director of engineering"),
    ],
    "DevOps, Cloud & Infrastructure": [
        ("DevOps Engineer", "devops engineer"),
        ("Site Reliability Engineer (SRE)", "site reliability engineer SRE"),
        ("Cloud Engineer / Cloud Architect", "cloud engineer"),
        ("Platform Engineer", "platform engineer"),
        ("Systems Administrator", "systems administrator"),
        ("Infrastructure Engineer", "infrastructure engineer"),
        ("Release Engineer", "release engineer"),
        ("Build Engineer", "build engineer"),
    ],
    "Quality & Testing": [
        ("QA Engineer", "QA engineer"),
        ("Software Development Engineer in Test (SDET)", "SDET software development engineer in test"),
        ("Test Automation Engineer", "test automation engineer"),
        ("Performance Engineer", "performance engineer"),
    ],
    "Data Science & Analytics": [
        ("Data Scientist", "data scientist"),
        ("Data Analyst", "data analyst"),
        ("Business Intelligence (BI) Analyst / Developer", "business intelligence analyst"),
        ("Analytics Engineer", "analytics engineer"),
        ("Quantitative Analyst", "quantitative analyst"),
        ("Statistician", "statistician"),
        ("Decision Scientist", "decision scientist"),
        ("Product Analyst", "product analyst"),
    ],
    "Data Engineering": [
        ("Data Engineer", "data engineer"),
        ("Big Data Engineer", "big data engineer"),
        ("ETL Developer", "ETL developer"),
        ("Data Architect", "data architect"),
        ("Database Administrator (DBA)", "database administrator DBA"),
        ("Database Developer", "database developer"),
        ("Data Warehouse Engineer", "data warehouse engineer"),
    ],
    "Machine Learning & AI": [
        ("Machine Learning Engineer", "machine learning engineer"),
        ("AI Engineer", "AI engineer"),
        ("Research Scientist", "machine learning research scientist"),
        ("Applied Scientist", "applied scientist"),
        ("MLOps Engineer", "MLOps engineer"),
        ("NLP Engineer", "NLP engineer"),
        ("Computer Vision Engineer", "computer vision engineer"),
        ("Prompt Engineer", "prompt engineer"),
        ("AI Product Manager", "AI product manager"),
    ],
    "Cybersecurity": [
        ("Security Engineer", "security engineer"),
        ("Security Analyst", "security analyst"),
        ("Penetration Tester", "penetration tester"),
        ("Application Security Engineer", "application security engineer"),
        ("Cloud Security Engineer", "cloud security engineer"),
        ("Security Architect", "security architect"),
        ("Incident Responder", "incident responder"),
        ("CISO", "chief information security officer CISO"),
    ],
    "Product, Design & Management": [
        ("Product Manager", "product manager"),
        ("Technical Program Manager", "technical program manager"),
        ("Project Manager", "project manager"),
        ("Scrum Master", "scrum master"),
        ("UX/UI Designer", "UX UI designer"),
        ("UX Researcher", "UX researcher"),
        ("Technical Product Owner", "technical product owner"),
    ],
    "Support, Sales & Specialized Roles": [
        ("Solutions Architect", "solutions architect"),
        ("Sales Engineer", "sales engineer"),
        ("Technical Support Engineer", "technical support engineer"),
        ("Developer Advocate / Developer Relations Engineer", "developer advocate"),
        ("Technical Writer", "technical writer"),
        ("IT Consultant", "IT consultant"),
        ("Business Analyst / Systems Analyst", "business analyst"),
        ("Blockchain Developer", "blockchain developer"),
        ("Robotics Engineer", "robotics engineer"),
        ("Bioinformatics Scientist", "bioinformatics scientist"),
    ],
}


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


ROLES: list[Role] = [
    Role(slug=_slugify(name), name=name, search_name=search, category=category)
    for category, entries in _RAW.items()
    for name, search in entries
]
_BY_SLUG: dict[str, Role] = {r.slug: r for r in ROLES}

# Guard against two display names collapsing to one slug (the cache key).
assert len(_BY_SLUG) == len(ROLES), "duplicate role slug in roles.py"


def get_role(slug: str) -> Role | None:
    return _BY_SLUG.get(slug)


def grouped_roles() -> list[dict]:
    """Shape served to the frontend: [{category, roles: [{slug, name}]}, ...]."""
    groups: dict[str, list[dict]] = {}
    for r in ROLES:
        groups.setdefault(r.category, []).append({"slug": r.slug, "name": r.name})
    return [{"category": cat, "roles": roles} for cat, roles in groups.items()]
