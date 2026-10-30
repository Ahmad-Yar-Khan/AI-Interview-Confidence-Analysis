"""
validation.py
--------------
Deterministic (no LLM, no network) guards around untrusted text going into
prompts and LLM output coming back. Four jobs:

  1. neutralize()           — stop untrusted text closing the <tag> it is wrapped in.
  2. has_injection() /
     strip_injection_lines() — catch common "ignore previous instructions" phrasing
                              in resumes and spoken answers.
  3. unsupported_details()  — find names, technologies, acronyms and numbers in a
                              generated question that the source text never mentions
                              (the fabricated-detail check).
  4. output_problem()       — basic hygiene on generated text (length, URLs, code
                              fences, injection phrasing).

These catch common failures, not every one: a paraphrased injection or a
factually wrong model answer can still get through, which is why the prompts
also tag untrusted data and the generators also demand verbatim evidence.
"""

import re

# ── 1. Delimiter escape ───────────────────────────────────────

def neutralize(text: str, *tags: str) -> str:
    """Remove any <tag> / </tag> the untrusted text contains, so it can't break out of its wrapper."""
    for tag in tags:
        text = re.sub(rf"</?\s*{re.escape(tag)}\b[^>]*>", "", text, flags=re.IGNORECASE)
    return text


# ── 2. Prompt-injection phrasing ──────────────────────────────

# Deliberately narrower than the web-snippet filter in search_validation: a
# resume for an AI role may legitimately say "system prompt", so only
# instruction-override phrasing is matched here.
_OVERRIDE = re.compile(
    r"ignore\s+(all\s+|any\s+|the\s+|your\s+)?(previous|prior|above|earlier|preceding)\s+(instructions?|prompts?|rules?)"
    r"|disregard\s+(all\s+|the\s+|any\s+)?(previous|prior|above|earlier|your)\b"
    r"|forget\s+(all\s+|everything\s+)?(previous|prior|above|your)\s+(instructions?|rules?)"
    r"|new\s+instructions?\s*:"
    r"|you\s+are\s+now\s+(a|an|the)\b"
    r"|(reveal|show|print|repeat)\s+(your|the)\s+(system\s+)?(prompt|instructions)"
    r"|(give|award|assign)\s+(me|this\s+candidate|the\s+candidate)\s+(a\s+)?(full|perfect|top|maximum|100)"
    r"|(score|rate|grade)\s+(me|this\s+(answer|candidate)|it)\s+(as\s+)?(100|10/10|full|perfect|highest)",
    re.IGNORECASE,
)


def has_injection(text: str) -> bool:
    return bool(_OVERRIDE.search(text))


def strip_injection_lines(text: str) -> tuple[str, list[str]]:
    """
    Drop every line that carries override phrasing (also when it is split across
    two adjacent lines). Returns (clean_text, removed_lines).
    """
    lines = text.splitlines()
    drop: set[int] = set()
    for i, line in enumerate(lines):
        if _OVERRIDE.search(line):
            drop.add(i)
        elif (i + 1 < len(lines) and not _OVERRIDE.search(lines[i + 1])
              and _OVERRIDE.search(f"{line} {lines[i + 1]}")):
            # Only a phrase genuinely split across two lines; a clean line that merely
            # sits above an injected one must survive.
            drop.update((i, i + 1))
    removed = [lines[i].strip() for i in sorted(drop)]
    clean = "\n".join(l for i, l in enumerate(lines) if i not in drop)
    return clean, removed


# ── 3. Fabricated-detail check ────────────────────────────────

# Generic terms a question may use even when the source never names them.
_GENERIC = {
    "api", "apis", "rest", "restful", "http", "https", "sql", "nosql", "json", "xml", "html", "css", "url",
    "uri", "cpu", "gpu", "ram", "os", "ui", "ux", "ci", "cd", "tcp", "udp", "ip", "dns", "tls", "ssl",
    "oop", "solid", "dry", "crud", "orm", "sdk", "ide", "etl", "elt", "ml", "ai", "nlp", "llm", "kpi",
    "sla", "slo", "sli", "e.g", "i.e", "vs", "etc", "qa", "tdd", "bdd", "mvc", "jwt", "oauth", "acid", "cap", "big", "agile", "scrum",
    "kanban", "star", "devops", "sre", "it", "id", "ok", "ssh", "cli", "gui", "io", "db", "dba", "bi", "ide",
}

_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9+#]*(?:[.\-'][A-Za-z0-9+#]+)*")
_SENTENCE_SPLIT = re.compile(r"(?<=[.?!:])\s+|\n+")


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9+#]+", " ", text.lower()).strip()


def _needs_support(token: str, sentence_initial: bool) -> bool:
    """Does this token look like a name, technology, acronym or number (vs. an ordinary word)?"""
    if len(token) < 2 or token.lower() in _GENERIC or token.startswith(("I'", "I’")):
        return False
    if any(c.isdigit() for c in token):
        return True
    if re.search(r"[a-z][A-Z]", token) or "+" in token or "#" in token or "." in token:
        return True                                   # FastAPI, iOS, C++, Node.js
    if token.isupper():
        return True                                   # FAISS, ETL, AWS
    return token[0].isupper() and not sentence_initial  # Python, Acme, Java mid-sentence


def unsupported_details(text: str, source: str) -> list[str]:
    """
    Names / technologies / acronyms / numbers in `text` that never appear in
    `source`. An empty list means every specific detail in the question is
    traceable to the source.
    """
    source_tokens = set(_norm(source).split())
    flagged: list[str] = []
    for sentence in _SENTENCE_SPLIT.split(text):
        for i, raw in enumerate(_WORD.findall(sentence)):
            token = re.sub(r"'s$", "", raw)
            if not _needs_support(token, sentence_initial=(i == 0)):
                continue
            parts = _norm(token).split()
            if parts and not all(p in source_tokens for p in parts) and token not in flagged:
                flagged.append(token)
    return flagged


# ── 4. Generated-text hygiene ─────────────────────────────────

_URL = re.compile(r"https?://|www\.", re.IGNORECASE)

# A "role" question is general; these phrasings claim something about the candidate.
CLAIMS_ABOUT_CANDIDATE = re.compile(
    r"\byour\s+(project|projects|experience|resume|previous|past|work|team|company|role)\b"
    r"|\bat\s+your\b|\bin\s+your\s+(last|previous|current)\b"
    r"|\byou(?:'ve|\s+have)?\s+(built|used|worked|scaled|implemented|designed|developed|led|managed|created|wrote|"
    r"deployed|reduced|improved|increased|optimi[sz]ed|handled|did|made|mentioned|said)\b"
    r"|\b(when|as|since)\s+you\b|\bearlier\s+you\b",
    re.IGNORECASE,
)


def output_problem(question: str, model_answer: str | None = None, max_question_chars: int = 500) -> str | None:
    """A short reason if generated text is unfit to show or store, else None."""
    for label, text in (("question", question), ("model_answer", model_answer or "")):
        if _URL.search(text):
            return f"{label} contains a URL"
        if "```" in text:
            return f"{label} contains a code fence"
        if has_injection(text):
            return f"{label} contains instruction-override phrasing"
    if len(question) > max_question_chars:
        return "question is too long"
    return None


class FollowupRejected(Exception):
    """The generated follow-up failed validation; no follow-up is asked."""
