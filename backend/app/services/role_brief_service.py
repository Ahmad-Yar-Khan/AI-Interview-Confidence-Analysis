"""
role_brief_service.py
----------------------
Weekly, background web research per dropdown job title, cached in SQLite, so
no user ever waits on a search.

  scheduler  ->  Tavily (2 queries/role)  ->  search_validation.filter_results
             ->  Groq condense            ->  search_validation.validate_brief
             ->  role_brief_store (served for ROLE_BRIEF_TTL_DAYS)

A failed or rejected refresh never overwrites the previous brief, and an
expired/missing brief simply means the interview is generated from the resume
alone. Request-time code only calls build_role_context().
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from app.core.config import settings
from app.core.roles import ROLES, OTHER_SLUG, Role, get_role
from app.llm.groq_client import chat, parse_json
from app.llm.validation import neutralize
from app.llm.prompts import ROLE_BRIEF_PROMPT, ROLE_BRIEF_SYSTEM_PROMPT
from app.services.role_brief_store import RoleBriefStore
from app.services.search_validation import BriefRejected, MIN_SOURCES, filter_results, validate_brief

logger = logging.getLogger(__name__)

store = RoleBriefStore(settings.ROLE_BRIEF_DB_PATH)

_DAY = 86400
TTL_SECONDS     = settings.ROLE_BRIEF_TTL_DAYS * _DAY
REFRESH_AFTER   = TTL_SECONDS * 6 / 7     # refresh a "day" before expiry so briefs never lapse
CHECK_INTERVAL  = 6 * 3600                # how often the scheduler looks for due roles
RETRY_GAP       = 5 * 3600                # min gap between attempts on the same role
PAUSE_BETWEEN   = 1.5                     # seconds between roles, to stay under rate limits
TAVILY_URL      = "https://api.tavily.com/search"

# Two queries per role keeps a weekly run to ~170 Tavily credits.
_QUERIES = (
    "{name} key skills tools technologies responsibilities",
    "{name} technical interview topics what interviewers ask",
)


# ════════════════════════════════════════
# RESEARCH (background only)
# ════════════════════════════════════════

async def _tavily_search(client: httpx.AsyncClient, query: str) -> list[dict]:
    resp = await client.post(
        TAVILY_URL,
        headers={"Authorization": f"Bearer {settings.TAVILY_API_KEY}"},
        json={
            "query": query,
            "search_depth": "basic",
            "max_results": 5,
            "include_answer": False,
            "time_range": "year",
        },
    )
    resp.raise_for_status()
    return resp.json().get("results", [])


def _sources_block(sources: list[dict]) -> str:
    return "\n\n".join(
        f"<source id=\"{i}\">\n{neutralize(s['title'], 'source')}\n{neutralize(s['content'], 'source')}\n</source>"
        for i, s in enumerate(sources, 1)
    )


async def refresh_role(role: Role) -> None:
    """Research one role and store the validated brief. Raises on any failure."""
    results: list[dict] = []
    async with httpx.AsyncClient(timeout=20) as client:
        for q in _QUERIES:
            results += await _tavily_search(client, q.format(name=role.search_name))

    sources, stats = filter_results(results, role.search_name)
    if len(sources) < MIN_SOURCES:
        raise BriefRejected(f"only {len(sources)} usable sources of {len(results)} (rejected: {stats.rejected})")

    prompt = ROLE_BRIEF_PROMPT.format(role_name=role.name, sources_block=_sources_block(sources))
    raw = parse_json(await chat(prompt, system=ROLE_BRIEF_SYSTEM_PROMPT, temperature=0.2))
    brief = validate_brief(raw, sources)

    await asyncio.to_thread(
        store.save_brief, role.slug, brief,
        [{"url": s["url"], "title": s["title"]} for s in sources], time.time(),
    )
    logger.info(f"Role brief refreshed: {role.slug} ({brief['confidence']}, {brief['source_count']} sources)")


def _is_due(row: dict | None, now: float) -> bool:
    if row is None or row["brief"] is None or row["refreshed_at"] is None:
        return True
    return now - row["refreshed_at"] >= REFRESH_AFTER


async def refresh_stale_roles() -> None:
    """One scheduler pass: refresh every role whose brief is missing or nearly expired."""
    for role in ROLES:
        now = time.time()
        row = await asyncio.to_thread(store.get, role.slug)
        if not _is_due(row, now):
            continue
        if not await asyncio.to_thread(store.claim, role.slug, now, RETRY_GAP):
            continue
        try:
            await refresh_role(role)
        except Exception as e:  # one bad role must not stop the pass
            logger.warning(f"Role brief refresh failed for {role.slug}: {e}")
            await asyncio.to_thread(store.record_failure, role.slug, f"{type(e).__name__}: {e}")
        await asyncio.sleep(PAUSE_BETWEEN)


async def _scheduler_loop() -> None:
    while True:
        try:
            await refresh_stale_roles()
        except Exception:
            logger.exception("Role brief scheduler pass crashed")
        await asyncio.sleep(CHECK_INTERVAL)


_task: asyncio.Task | None = None


def start_scheduler() -> None:
    """Called from the app lifespan. Checks on boot, then every few hours."""
    global _task
    store.init()
    if not settings.ROLE_BRIEF_SCHEDULER:
        logger.info("Role brief scheduler disabled (ROLE_BRIEF_SCHEDULER=0).")
        return
    if not settings.TAVILY_API_KEY:
        logger.warning("TAVILY_API_KEY is not set — role briefs won't refresh; questions use the resume only.")
        return
    _task = asyncio.create_task(_scheduler_loop())


def stop_scheduler() -> None:
    if _task:
        _task.cancel()


# ════════════════════════════════════════
# REQUEST-TIME: build the prompt's role context
# ════════════════════════════════════════

@dataclass
class RoleContext:
    text: str                       # block inserted into the prompt
    role_name: str | None = None    # None for "Other"
    years: int | None = None
    brief_used: bool = False
    brief_updated: str | None = None  # ISO date of the brief's last refresh

    def meta(self) -> dict:
        return {"role": self.role_name, "years": self.years,
                "brief_used": self.brief_used, "brief_updated": self.brief_updated}


def _experience_guidance(years: int) -> str:
    if years < 1:
        return "Entry level (under 1 year). Test fundamentals; mostly Easy and Medium; no system-design leadership."
    if years < 3:
        return "Junior (1–2 years). Solid fundamentals and hands-on implementation; mostly Easy and Medium, one Hard at most."
    if years < 6:
        return "Mid level (3–5 years). Implementation depth, trade-offs, debugging; mostly Medium, some Hard."
    if years < 10:
        return "Senior (6–9 years). Design decisions, scale, ownership, mentoring; Medium and Hard."
    return "Staff/lead level (10+ years). Architecture, org-level trade-offs, ambiguity; mostly Hard."


def _render_brief(brief: dict) -> str:
    labels = (("core_skills", "Core skills"), ("tools_and_tech", "Tools & tech"),
              ("responsibilities", "Responsibilities"), ("interview_themes", "Interview themes"))
    lines = [f"- {label}: {'; '.join(brief[k])}" for k, label in labels if brief.get(k)]
    return "\n".join(lines)


async def build_role_context(role_slug: str | None, years: int | None) -> RoleContext:
    """
    "Other" (or an unknown/empty slug) deliberately yields NO job title in the
    prompt — questions then come from the resume and experience level only.
    """
    role = get_role(role_slug) if role_slug and role_slug != OTHER_SLUG else None
    parts: list[str] = []

    if role:
        parts.append(f"TARGET ROLE: {role.name}")
    else:
        parts.append("TARGET ROLE: none specified. Base every question on the candidate's own material.")

    if years is not None:
        parts.append(f"CANDIDATE EXPERIENCE: {years} year{'s' if years != 1 else ''}. {_experience_guidance(years)}")

    ctx = RoleContext(text="", role_name=role.name if role else None, years=years)

    if role:
        try:
            row = await asyncio.to_thread(store.get, role.slug)
        except Exception as e:  # a broken cache must never block an interview
            logger.warning(f"Role brief lookup failed for {role.slug}: {e}")
            row = None
        fresh = (row and row["brief"] and row["refreshed_at"]
                 and time.time() - row["refreshed_at"] <= TTL_SECONDS)
        # A low-confidence brief is weak signal — better to leave it out than to steer on it.
        if fresh and row["brief"].get("confidence") != "low":
            updated = datetime.fromtimestamp(row["refreshed_at"], timezone.utc).date().isoformat()
            parts.append(
                f"<role_brief researched=\"{updated}\" confidence=\"{row['brief']['confidence']}\">\n"
                f"{_render_brief(row['brief'])}\n</role_brief>\n"
                "The role brief is background on what this role usually involves. It is not a statement about the candidate."
            )
            ctx.brief_used = True
            ctx.brief_updated = updated

    ctx.text = "\n".join(parts)
    return ctx
