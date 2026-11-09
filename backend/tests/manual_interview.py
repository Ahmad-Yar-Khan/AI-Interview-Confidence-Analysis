"""
manual_interview.py
-------------------
Interactive CLI that walks the *live* backend flow against a resume file:

    upload resume -> generate opening questions (question agent)
                  -> you pick one question and answer it
                  -> score that answer (evaluation agent)
                  -> show any follow-up the follow-up agent generated

It talks to the real FastAPI app through TestClient, so it exercises the same
routes, agents, and follow-up eligibility rules the frontend uses — no server
needs to be running.

Usage (from backend/):
    python -m tests.manual_interview "data/AhmadYar_Resume (4).pdf"
    python -m tests.manual_interview resume.pdf --role back-end-developer --years 3 --total 7

When prompted, type the number of the question you want to answer, then type
your answer.
"""

import argparse
import os
import sys

# Allow `python tests/manual_interview.py` as well as `python -m tests.manual_interview`.
_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from fastapi.testclient import TestClient  # noqa: E402

from app.core.roles import OTHER_SLUG, get_role  # noqa: E402
from app.main import app  # noqa: E402

_ALLOWED_EXT = {".pdf", ".docx", ".txt"}
_MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
}

def _separator(char: str = "─", width: int = 78) -> None:
    print(char * width)


def _print_questions(questions: list[dict]) -> None:
    _separator()
    print(f"GENERATED QUESTIONS ({len(questions)})")
    _separator()
    for i, q in enumerate(questions, 1):
        meta = " · ".join(
            part for part in (q.get("category"), q.get("difficulty")) if part
        )
        print(f"\n{i}) {q['question']}")
        if meta:
            print(f"   [{meta}]")
    _separator()


def _print_score(index: int, question: dict, result: dict) -> None:
    print(f"\n{index}) {question['question']}")
    print(f"   Score: {result.get('overall', 0)}/100  (rubric {result.get('evaluation_score')}/10)")
    criteria = result.get("criteria") or {}
    if criteria:
        print("   Criteria: " + ", ".join(f"{k}={v}" for k, v in criteria.items()))
    feedback = (result.get("feedback") or "").strip()
    if feedback:
        print(f"   Feedback: {feedback}")
    followup = result.get("followup")
    if followup:
        print(f"   ↳ Follow-up ({followup.get('id')}): {followup.get('question')}")
    else:
        print("   ↳ No follow-up (answer scored >= 6 or follow-up not allowed).")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an interactive interview through the live backend flow.")
    parser.add_argument("resume", help="Path to the resume file (.pdf, .docx or .txt)")
    parser.add_argument("--role", default=OTHER_SLUG, help="Role slug from GET /api/roles (default: other)")
    parser.add_argument("--years", type=int, default=None, help="Candidate years of experience")
    parser.add_argument("--total", type=int, default=7, help="Number of opening questions (3-8)")
    args = parser.parse_args()

    if not os.path.isfile(args.resume):
        print(f"error: resume not found: {args.resume}", file=sys.stderr)
        return 2

    ext = os.path.splitext(args.resume)[1].lower()
    if ext not in _ALLOWED_EXT:
        print(f"error: unsupported file type '{ext}'. Use .pdf, .docx or .txt.", file=sys.stderr)
        return 2

    if args.role != OTHER_SLUG and get_role(args.role) is None:
        print(f"error: unknown role slug '{args.role}'. Use 'other' or a slug from GET /api/roles.", file=sys.stderr)
        return 2

    if not 3 <= args.total <= 8:
        print("error: --total must be between 3 and 8.", file=sys.stderr)
        return 2

    with open(args.resume, "rb") as fh:
        resume_bytes = fh.read()

    with TestClient(app) as client:
        # ── 1. Upload / parse the resume ────────────────────────
        print(f"Uploading {os.path.basename(args.resume)} ({len(resume_bytes)} bytes)…")
        resp = client.post(
            "/api/upload-resume",
            files={"file": (os.path.basename(args.resume), resume_bytes, _MEDIA_TYPES.get(ext, "application/octet-stream"))},
        )
        if resp.status_code != 200:
            print(f"error: upload failed ({resp.status_code}): {resp.text}", file=sys.stderr)
            return 1

        upload = resp.json()
        session_id = upload["session_id"]
        profile = upload.get("profile") or {}
        print(f"Session: {session_id}")
        print(f"Candidate: {profile.get('name') or 'Candidate'} ({profile.get('char_count', 0)} chars)")
        for warning in upload.get("warnings") or []:
            print(f"warning: {warning}")

        # ── 2. Generate the opening questions ───────────────────
        params = {"total": args.total, "role": args.role}
        if args.years is not None:
            params["years"] = args.years
        print("\nGenerating questions (question agent)…")
        resp = client.get(f"/api/questions/{session_id}", params=params)
        if resp.status_code != 200:
            print(f"error: question generation failed ({resp.status_code}): {resp.text}", file=sys.stderr)
            return 1

        payload = resp.json()
        questions = payload.get("questions") or []
        if not questions:
            print("error: the question agent returned no questions.", file=sys.stderr)
            return 1

        role_context = payload.get("role_context") or {}
        if isinstance(role_context, dict):
            role_label = role_context.get("role") or args.role
            role_years = role_context.get("years")
        else:
            role_label, role_years = str(role_context), args.years
        years_label = f", {role_years} yrs" if role_years is not None else ""
        print(f"Role: {role_label}{years_label}   Bank relevance: {payload.get('relevance')}/10")
        _print_questions(questions)

        # ── 3. Pick one question and answer it ──────────────────
        print("\nPick one of the questions above and answer it.\n")
        selected = None
        while selected is None:
            try:
                raw = input(f"Question number to answer (1-{len(questions)}): ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return 1
            if raw.isdigit() and 1 <= int(raw) <= len(questions):
                selected = int(raw)
            else:
                print(f"  Please enter a number between 1 and {len(questions)}.")

        question = questions[selected - 1]
        try:
            answer = input("\nYour answer: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 1
        if not answer:
            print("error: answer cannot be empty.", file=sys.stderr)
            return 1

        # ── 4. Evaluate the answer + generate a follow-up ───────
        print("\nEvaluating answer (evaluation agent)…")
        body = {
            "session_id": session_id,
            "question_id": question.get("question_id") or question.get("id"),
            "question_text": question["question"],
            "model_answer": question.get("model_answer"),
            "user_answer": answer,
            "category": question.get("category") or "General",
            "difficulty": question.get("difficulty") or "Medium",
            "has_answer": question.get("has_answer", True),
            "queue_length": len(questions),
            "question_position": selected - 1,
        }
        resp = client.post("/api/score", json=body)
        if resp.status_code != 200:
            print(f"\nerror: scoring failed ({resp.status_code}): {resp.text}", file=sys.stderr)
            return 1

        result = resp.json()
        _print_score(selected, question, result)

        # ── 5. Follow-up summary ────────────────────────────────
        print()
        _separator("═")
        followup = result.get("followup")
        if followup:
            print("FOLLOW-UP GENERATED")
            _separator("═")
            print(followup.get("question"))
        else:
            print("No follow-up was generated (answer scored >= 6 or follow-up not allowed).")
        _separator("═")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
