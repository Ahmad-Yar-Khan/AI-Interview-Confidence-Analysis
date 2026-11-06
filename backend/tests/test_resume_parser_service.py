"""
Tests for resume section parsing (skills / projects) used at upload time.
Run from backend/ with:  pytest tests/test_resume_parser_service.py
"""

from app.services.resume_parser_service import extract_skills_and_projects, parse_resume_sections

RESUME = """Jane Doe
jane@example.com

SUMMARY
Backend engineer focused on APIs.

SKILLS
Python, FastAPI, PostgreSQL
Docker, Redis

EXPERIENCE
Acme Corp — Backend Engineer
Built an order service.

PROJECTS
SmartInterview
- Built a FastAPI backend with Groq question generation.

EDUCATION
BSc Computer Science
"""


def test_standalone_sections_are_split_and_bounded():
    sections = parse_resume_sections(RESUME)
    assert "Python, FastAPI" in sections["skills"]
    assert "Docker, Redis" in sections["skills"]
    assert "SmartInterview" in sections["projects"]
    assert "Built an order service" in sections["experience"]
    assert "Docker, Redis" not in sections["projects"]
    assert "BSc Computer Science" in sections["education"]


def test_inline_skills_header_is_kept():
    sections = parse_resume_sections("Jane Doe\nSkills: Python, SQL, Docker\nExperience\nAcme 2023")
    assert sections["skills"] == "Python, SQL, Docker"
    assert sections["experience"] == "Acme 2023"


def test_project_experience_is_treated_as_projects():
    sections = parse_resume_sections("Project Experience\nBuilt a parser.\nEducation\nBSc")
    assert sections["projects"] == "Built a parser."
    assert "projects" in sections and "experience" not in sections


def test_markdown_headers_are_recognised():
    sections = parse_resume_sections("## Technical Skills\nPython, Go\n## Projects\nCLI tool")
    assert sections["skills"] == "Python, Go"
    assert sections["projects"] == "CLI tool"


def test_missing_sections_return_both_keys_empty():
    result = extract_skills_and_projects("Jane Doe\nExperience\nAcme 2023")
    assert result == {"skills": "", "projects": ""}
