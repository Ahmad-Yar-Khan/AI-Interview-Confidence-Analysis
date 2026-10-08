"""
Sanity tests for the resume_parser package. Run from backend/ with:
    pytest tests/test_resume_parser.py

These are deliberately minimal scaffolding — a starting point for the test
coverage this project didn't have before the restructure, not a full suite.
"""

from app.ml.resume_parser import extract_email, extract_phone, extract_name


def test_extract_email_finds_address():
    text = "Contact: jane.doe@example.com for details."
    assert extract_email(text) == "jane.doe@example.com"


def test_extract_email_returns_empty_when_absent():
    assert extract_email("No contact info here.") == ""


def test_extract_phone_finds_number():
    text = "Call me at 555-123-4567 anytime."
    assert "555" in extract_phone(text)


def test_extract_name_prefers_title_case_line():
    text = "John Smith\nSoftware Engineer\njohn@example.com"
    assert extract_name(text) == "John Smith"
