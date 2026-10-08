"""
question_service.py
--------------------
The RAG + question-assembly business logic, pulled out of main.py's
get_questions() route and its private helpers. This is the piece we spent a
lot of review time on: 3-source assembly (dataset retrieval via FAISS,
project-question generation via Groq, HR questions via random sampling),
SBERT-cosine dedup, and the full-LLM-generation fallback.

Behavior is unchanged from the original main.py — this is a relocation, not a
rewrite of the logic itself. The RAG readiness globals (_rag_ready / _rag_engine
/ _rag_bank) that used to live at main.py module scope now live here, since
this is the module that actually consumes them; `init_rag()` is called once
from the app's lifespan startup, and `rag_status()` is what the /api/health
route reads.
"""

import random
import logging

logger = logging.getLogger(__name__)

try:
    from app.ml.embedding_engine import EmbeddingEngine
    from app.ml.data_loader import init_question_bank
    from app.ml.resume_parser import ResumeProfile, get_chunks
    _rag_imports_ok = True
except Exception as _re:
    _rag_imports_ok = False
    logger.warning(f"RAG imports unavailable: {_re}")

_rag_ready  = False
_rag_engine = None
_rag_bank   = None


def init_rag() -> None:
    """Called once from the app's lifespan startup."""
    global _rag_ready, _rag_engine, _rag_bank
    if not _rag_imports_ok:
        logger.warning("RAG pipeline skipped — imports unavailable.")
        return
    try:
        _rag_engine = EmbeddingEngine()
        _rag_bank   = init_question_bank(_rag_engine)
        _rag_ready  = True
        logger.info(f"RAG pipeline ready — {len(_rag_bank.questions)} questions indexed in FAISS.")
    except Exception as _e:
        logger.warning(f"RAG pipeline failed to initialise: {_e}. Falling back to resume-only generation.")


def rag_status() -> dict:
    return {
        "rag_ready": _rag_ready,
        "rag_questions_indexed": len(_rag_bank.questions) if _rag_ready else 0,
    }


# ════════════════════════════════════════
# QUESTION ASSEMBLY HELPERS
# ════════════════════════════════════════

def _normalize_dataset_question(q, id_prefix: str = "ds") -> dict:
    """Convert a QuestionBank Question to the frontend-compatible dict format."""
    d = q.to_dict()
    qid = f"{id_prefix}_{d['id']}"
    return {
        "id":           qid,
        "question_id":  qid,
        "question":     d["question"],
        "category":     d["category"],
        "difficulty":   d["difficulty"],
        "model_answer": d.get("answer"),   # dataset stores it as "answer"
        "has_answer":   d["has_answer"],
    }


def _retrieve_dataset_questions(resume_text: str, count: int = 5) -> list[dict]:
    """
    Global SBERT retrieval: embed resume, search FAISS across all tech questions,
    cap per-category to 2 for diversity, return top `count` results.
    """
    if not _rag_ready or not _rag_imports_ok:
        return []
    try:
        resume_vec = _rag_engine.embed(resume_text[:3000])
        search_k   = min(len(_rag_bank.questions), count * 10)
        _, indices = _rag_engine.search(resume_vec, top_k=search_k)

        MAX_PER_CAT = 2
        cat_counts: dict[str, int] = {}
        selected: list[dict] = []
        seen: set[str] = set()

        for idx in indices:
            if len(selected) >= count:
                break
            q = _rag_bank.questions[idx]
            if q.category == "HR & Behavioral":
                continue
            if q.question in seen:
                continue
            if cat_counts.get(q.category, 0) >= MAX_PER_CAT:
                continue
            selected.append(_normalize_dataset_question(q, id_prefix="ds"))
            seen.add(q.question)
            cat_counts[q.category] = cat_counts.get(q.category, 0) + 1

        # Backfill: relax cap if short
        if len(selected) < count:
            for idx in indices:
                if len(selected) >= count:
                    break
                q = _rag_bank.questions[idx]
                if q.category == "HR & Behavioral" or q.question in seen:
                    continue
                selected.append(_normalize_dataset_question(q, id_prefix="ds"))
                seen.add(q.question)

        logger.info(
            f"Global SBERT retrieval: {len(selected)} questions "
            f"from categories {list(dict.fromkeys(q['category'] for q in selected))}"
        )
        return selected
    except Exception as e:
        logger.warning(f"Dataset retrieval failed: {e}")
        return []


def _get_hr_questions(count: int = 3) -> list[dict]:
    """Randomly sample HR & Behavioral questions from the dataset."""
    if not _rag_ready:
        return []
    try:
        hr_pool = _rag_bank.get_by_category("HR & Behavioral")
        if not hr_pool:
            return []
        sampled = random.sample(hr_pool, min(count, len(hr_pool)))
        return [_normalize_dataset_question(q, id_prefix="hr") for q in sampled]
    except Exception as e:
        logger.warning(f"HR question retrieval failed: {e}")
        return []


def _extract_projects_section(resume_text: str) -> str:
    """Return the raw projects section text from the resume, or empty string if not found."""
    if not _rag_imports_ok:
        return ""
    profile = ResumeProfile(raw_text=resume_text)
    for label, text in get_chunks(profile):
        if label == "projects":
            return text
    return ""


def _dedup_questions(questions: list[dict], sim_threshold: float = 0.70) -> list[dict]:
    """
    Remove duplicate questions using SBERT cosine similarity when the RAG engine
    is available, falling back to string-prefix matching otherwise.
    Two questions are considered duplicates when their cosine similarity exceeds
    sim_threshold — the later one (lower priority source) is dropped.
    """
    if not questions:
        return []

    if _rag_ready:
        texts = [q["question"] for q in questions]
        vecs  = _rag_engine.embed_batch(texts)       # (N, dim), L2-normalised
        sim   = vecs @ vecs.T                        # (N, N) cosine similarities

        to_drop: set[int] = set()
        for i in range(len(questions)):
            if i in to_drop:
                continue
            for j in range(i + 1, len(questions)):
                if j not in to_drop and sim[i, j] >= sim_threshold:
                    to_drop.add(j)

        return [q for i, q in enumerate(questions) if i not in to_drop]

    # Fallback: string prefix
    seen:   set[str]  = set()
    result: list[dict] = []
    for q in questions:
        key = q["question"][:80].lower().strip()
        if key not in seen:
            seen.add(key)
            result.append(q)
    return result


def get_debug_chunks(resume_text: str) -> dict:
    """Used by the /api/debug/chunks route."""
    if not _rag_imports_ok:
        return {}
    return {label: text for label, text in get_chunks(ResumeProfile(raw_text=resume_text))}


# ════════════════════════════════════════
# ORCHESTRATION — assembles the final question set for a session
# ════════════════════════════════════════

def get_or_generate_questions(session: dict, total: int = 12, role: str = "", jd: str = "") -> list[dict]:
    """
    Assemble interview questions from three sources:
      - 5 technical questions retrieved from the dataset via FAISS (resume-matched)
      - 4 project-specific questions generated by Gemini/Groq from the projects section
      - 3 HR & Behavioral questions randomly sampled from the dataset
    Falls back to full LLM generation if all three sources fail.

    Mutates `session` in place (questions / job_role / job_description / debug
    fields), same as the original main.py route body did directly on the
    `sessions[session_id]` dict.
    """
    # Local import to avoid a circular import at module load time
    # (app.llm -> ... -> nothing that imports this module, but kept local
    # for clarity about why question_service depends on the llm layer).
    from app.llm import generate_dataset_and_project_questions, generate_questions

    prev_role = session.get("job_role", "")
    prev_jd   = session.get("job_description", "")
    context_changed = (role.strip() != prev_role or jd.strip() != prev_jd)

    if session["questions"] and not context_changed:
        return session["questions"]

    session["job_role"]        = role.strip()
    session["job_description"] = jd.strip()

    resume_text = session["resume_text"]

    # ── Sources 1 & 2: personalized dataset + project questions ──
    # Single Groq call handles both tasks to halve quota usage.
    raw_dataset_qs = _retrieve_dataset_questions(resume_text, count=5)
    projects_text  = _extract_projects_section(resume_text)
    dataset_qs: list[dict] = []
    project_qs: list[dict] = []
    try:
        dataset_qs, project_qs = generate_dataset_and_project_questions(
            dataset_qs=raw_dataset_qs,
            projects_text=projects_text,
            resume_text=resume_text,
            project_count=4,
        )
    except Exception as e:
        logger.warning(f"Combined question generation failed: {e}")
        dataset_qs = raw_dataset_qs  # fall back to raw unmodified questions

    # ── Source 3: HR questions from dataset ───────────────────
    hr_qs = _get_hr_questions(count=3)

    # ── Combine, deduplicate, re-index ────────────────────────
    questions = _dedup_questions(dataset_qs + project_qs + hr_qs)

    # Full LLM fallback if every source returned nothing
    if not questions:
        logger.warning("All sources empty — falling back to full LLM generation.")
        questions = generate_questions(resume_text=resume_text, total=total)

    for i, q in enumerate(questions):
        q["id"] = f"q{i+1}"
        q["question_id"] = f"q{i+1}"

    logger.info(
        f"Questions assembled: {len(dataset_qs)} dataset + "
        f"{len(project_qs)} project + {len(hr_qs)} HR = {len(questions)} total"
    )

    # Store for debug endpoint
    session["debug_chunks"]    = get_debug_chunks(resume_text)
    session["debug_retrieval"] = {"dataset": dataset_qs, "project": project_qs, "hr": hr_qs}
    session["questions"] = questions

    return questions
