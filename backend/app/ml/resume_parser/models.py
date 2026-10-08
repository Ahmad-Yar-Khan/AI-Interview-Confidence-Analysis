"""
models.py (resume_parser)
---------------------------
Data classes for a parsed resume.
"""

from dataclasses import dataclass, field


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
