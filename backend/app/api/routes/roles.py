"""
roles.py (route)
------------------
GET /api/roles — the dropdown's job titles grouped by category, plus the
"Other" option. Served from the backend so the weekly research job, the
question route's validation, and the UI all share one list.
"""

from fastapi import APIRouter

from app.core.roles import OTHER_SLUG, grouped_roles

router = APIRouter()


@router.get("/api/roles")
def list_roles():
    return {
        "categories": grouped_roles(),
        "other": {"slug": OTHER_SLUG, "name": "Other (not listed)"},
    }
