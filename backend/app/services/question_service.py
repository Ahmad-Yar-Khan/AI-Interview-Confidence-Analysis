"""
question_service.py
--------------------
Builds the opening questions for a session: Groq reads the whole resume plus
the role context (job title brief, years of experience) and writes a handful
of questions, each verified against the resume (see
llm.question_generation.generate_interview_questions). Everything after those
opening questions is a follow-up to a weak answer (see followup_service).

The FAISS dataset retrieval, HR sampling, and SBERT dedup helpers, and
init_rag()/rag_status(), are no longer part of the question flow and init_rag()
is no longer called at startup. They are kept here, unwired, in case the dataset
questions come back; rag_status() still backs /api/health (reports not ready).
"""

import asyncio
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


def _resume_sections(resume_text: str) -> dict[str, str]:
    """Resume split into labelled sections (skills, projects, experience, ...); repeated labels are joined."""
    if not _rag_imports_ok:
        return {}
    sections: dict[str, str] = {}
    for label, text in get_chunks(ResumeProfile(raw_text=resume_text)):
        sections[label] = sections[label] + "\n" + text if label in sections else text
    return sections


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


# ════════════════════════════════════════
# ORCHESTRATION — assembles the final question set for a session
# ════════════════════════════════════════

async def get_or_generate_questions(
    session: dict, total: int = 5, role: str = "", years: int | None = None,
) -> list[dict]:
    """
    Generate the opening questions for a session. Groq reads the whole resume
    plus the role context (job title -> cached research brief, years of
    experience) and writes `total` questions; each is checked against the
    resume before it is accepted (see generate_interview_questions). Further
    questions come later as follow-ups to weak answers (followup_service).

    Falls back to the older full-resume generator if grounding leaves nothing.
    Mutates `session` in place (questions / job_role / years_experience / debug
    fields).
    """
    # Local imports to avoid circular imports at module load time.
    from app.llm import generate_interview_questions, generate_questions
    from app.services.role_brief_service import build_role_context

    role = role.strip()
    context_changed = (role != session.get("job_role", "") or years != session.get("years_experience"))

    if session["questions"] and not context_changed:
        return session["questions"]

    session["job_role"]         = role
    session["years_experience"] = years
    session.pop("followups", None)   # a fresh question set starts with fresh follow-up state

    resume_text  = session["resume_text"]
    role_context = await build_role_context(role, years)
    session["role_context"] = role_context.meta()
    has_role = role_context.role_name is not None

    # The grounding checks can reject questions, so ask up to twice and
    # accumulate until there are enough.
    questions: list[dict] = []
    seen: set[str] = set()
    for attempt in range(2):
        try:
            batch = await generate_interview_questions(
                resume_text=resume_text,
                role_context=role_context.text,
                has_role=has_role,
                count=total - len(questions),
            )
        except Exception as e:
            logger.warning(f"Question generation attempt {attempt + 1} failed: {e}")
            continue
        for q in batch:
            key = q["question"][:80].lower().strip()
            if key not in seen:
                seen.add(key)
                questions.append(q)
        if len(questions) >= total:
            break

    if not questions:
        logger.warning("No grounded questions — falling back to full-resume generation.")
        questions = await generate_questions(
            resume_text=resume_text, total=total, job_context=role_context.text,
        )

    for i, q in enumerate(questions):
        q["id"] = f"q{i+1}"
        q["question_id"] = f"q{i+1}"
        q.setdefault("is_followup", False)

    logger.info(f"Questions assembled: {len(questions)} generated (role={role_context.role_name!r}, years={years})")

    session["debug_chunks"]    = await asyncio.to_thread(_resume_sections, resume_text)
    session["debug_retrieval"] = {"questions": questions}
    session["questions"] = questions

    return questions
