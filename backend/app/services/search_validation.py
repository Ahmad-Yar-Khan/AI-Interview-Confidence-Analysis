"""
search_validation.py
---------------------
Pure (no network, no LLM) validation of web-search output before and after it
is condensed into a role brief. Two stages:

  1. filter_results()  — drops search hits that are low-score, off-topic, spam,
     duplicate, stale, too short, or that look like prompt-injection attempts,
     and trims what survives so the condensing prompt stays small.
  2. validate_brief()  — checks the LLM's condensed output: schema + hard length
     caps, then a grounding check that drops any skill/theme not supported by
     the surviving snippets. Confidence is computed here from evidence, never
     taken from the model's own claim.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlparse

# ── Stage 1 tunables ─────────────────────────────────────────
MIN_SCORE          = 0.30     # Tavily relevance score below this is dropped
MIN_CONTENT_CHARS  = 150
MAX_CONTENT_CHARS  = 1200     # per-snippet cap fed to the condensing prompt
MAX_SOURCES        = 6
MIN_SOURCES        = 2        # fewer survivors than this -> brief rejected
MAX_AGE_DAYS       = 365 * 3  # only enforced when the hit carries a date

BLOCKED_DOMAINS = {
    "pinterest.com", "facebook.com", "instagram.com", "tiktok.com",
    "quora.com", "twitter.com", "x.com",
}

_INJECTION = re.compile(
    r"ignore\s+(all\s+|any\s+|the\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?)"
    r"|disregard\s+(all\s+|the\s+)?(previous|prior|above)"
    r"|system\s+prompt"
    r"|you\s+are\s+(now\s+)?an?\s+(ai|assistant|language\s+model)",
    re.IGNORECASE,
)

_STOPWORDS = {"a", "an", "and", "the", "of", "in", "for", "to", "at", "or"}

# ── Stage 2 caps ─────────────────────────────────────────────
CAPS = {"core_skills": 8, "tools_and_tech": 8, "responsibilities": 5, "interview_themes": 6}
MAX_ITEM_CHARS = 80
GROUNDING_THRESHOLD = {"core_skills": 0.75, "tools_and_tech": 0.75,
                       "responsibilities": 0.6, "interview_themes": 0.6}
MIN_GROUNDED_SKILLS = 3       # core_skills + tools_and_tech surviving grounding
MIN_GROUNDED_TOTAL = 5


class BriefRejected(Exception):
    """The search/condense output failed validation — keep the previous brief."""


@dataclass
class FilterStats:
    kept: int = 0
    rejected: dict[str, int] = field(default_factory=dict)

    def reject(self, reason: str) -> None:
        self.rejected[reason] = self.rejected.get(reason, 0) + 1


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9+#.]+", text.lower()) if t not in _STOPWORDS]


def _domain(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _is_blocked(domain: str) -> bool:
    return any(domain == d or domain.endswith("." + d) for d in BLOCKED_DOMAINS)


def _is_stale(published: str | None) -> bool:
    if not published:
        return False
    try:
        dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
    except ValueError:
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).days > MAX_AGE_DAYS


def _relevant(text: str, role_search_name: str) -> bool:
    """At least half of the role name's meaningful tokens must appear in the hit."""
    wanted = set(_tokens(role_search_name))
    if not wanted:
        return True
    present = set(_tokens(text))
    return len(wanted & present) / len(wanted) >= 0.5


def filter_results(results: list[dict], role_search_name: str) -> tuple[list[dict], FilterStats]:
    """
    Keep only usable hits. Each returned dict has url / title / content (trimmed).
    Highest-score hits win when there are more than MAX_SOURCES survivors; only
    one hit per domain is kept so a single site can't dominate the brief.
    """
    stats = FilterStats()
    kept: list[dict] = []
    seen_domains: set[str] = set()
    seen_content: set[str] = set()

    for r in sorted(results, key=lambda r: r.get("score") or 0, reverse=True):
        url     = r.get("url") or ""
        title   = r.get("title") or ""
        content = (r.get("content") or "").strip()
        domain  = _domain(url)

        if _is_blocked(domain):
            stats.reject("blocked_domain"); continue
        if (r.get("score") or 0) < MIN_SCORE:
            stats.reject("low_score"); continue
        if len(content) < MIN_CONTENT_CHARS:
            stats.reject("too_short"); continue
        if _INJECTION.search(content) or _INJECTION.search(title):
            stats.reject("injection_pattern"); continue
        if _is_stale(r.get("published_date")):
            stats.reject("stale"); continue
        if not _relevant(f"{title} {content}", role_search_name):
            stats.reject("off_topic"); continue
        if domain in seen_domains:
            stats.reject("duplicate_domain"); continue
        fingerprint = re.sub(r"\W+", "", content.lower())[:200]
        if fingerprint in seen_content:
            stats.reject("duplicate_content"); continue

        seen_domains.add(domain)
        seen_content.add(fingerprint)
        kept.append({"url": url, "title": title[:150], "content": content[:MAX_CONTENT_CHARS]})
        if len(kept) >= MAX_SOURCES:
            break

    stats.kept = len(kept)
    return kept, stats


# ── Stage 2 ──────────────────────────────────────────────────

def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9+#]+", " ", text.lower()).strip()


def _grounded(item: str, corpus_norm: str, corpus_tokens: set[str], threshold: float) -> bool:
    """Item appears verbatim in the sources, or enough of its words do."""
    item_norm = _norm(item)
    if not item_norm:
        return False
    if item_norm in corpus_norm:
        return True
    # A single word must match verbatim; a phrase may match on its longer words
    # (so "API design best practices" is supported by "best practices for API design").
    words = [w for w in item_norm.split() if len(w) > 3]
    if len(item_norm.split()) < 2 or not words:
        return False
    return sum(w in corpus_tokens for w in words) / len(words) >= threshold


def validate_brief(raw: object, sources: list[dict]) -> dict:
    """
    Returns {core_skills, tools_and_tech, responsibilities, interview_themes,
    confidence, source_count} or raises BriefRejected. `raw` is the parsed JSON
    from the condensing call; `sources` are the snippets that call was shown.
    """
    if not isinstance(raw, dict):
        raise BriefRejected("condensed output is not a JSON object")

    corpus_norm = _norm(" ".join(f"{s['title']} {s['content']}" for s in sources))
    corpus_tokens = set(corpus_norm.split())

    cleaned: dict[str, list[str]] = {}
    proposed = dropped = 0
    for key, cap in CAPS.items():
        items = raw.get(key)
        if not isinstance(items, list):
            items = []
        out: list[str] = []
        for it in items:
            if not isinstance(it, str):
                continue
            it = re.sub(r"\s+", " ", it).strip()[:MAX_ITEM_CHARS]
            if not it or it.lower() in {o.lower() for o in out}:
                continue
            proposed += 1
            if _grounded(it, corpus_norm, corpus_tokens, GROUNDING_THRESHOLD[key]):
                out.append(it)
            else:
                dropped += 1
            if len(out) >= cap:
                break
        cleaned[key] = out

    skills = len(cleaned["core_skills"]) + len(cleaned["tools_and_tech"])
    total = sum(len(v) for v in cleaned.values())
    if skills < MIN_GROUNDED_SKILLS or total < MIN_GROUNDED_TOTAL:
        raise BriefRejected(
            f"too little grounded content (skills={skills}, total={total}, dropped={dropped}/{proposed})"
        )

    drop_ratio = dropped / proposed if proposed else 1.0
    if len(sources) >= 4 and drop_ratio <= 0.2:
        confidence = "high"
    elif len(sources) >= 2 and drop_ratio <= 0.5:
        confidence = "medium"
    else:
        confidence = "low"

    return {**cleaned, "confidence": confidence, "source_count": len(sources)}
