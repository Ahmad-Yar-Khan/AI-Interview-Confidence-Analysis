"""
session_store.py
-----------------
Wraps the in-memory interview-session state behind a small interface instead
of exposing a raw dict to every route. Today this is still just a Python
dict in one process's memory — the underlying storage hasn't changed, and the
"one worker only" limitation that implies is unchanged too.

What this buys you: if/when that limitation needs fixing (e.g. swapping to
Redis or a database so multiple worker processes can share session state),
only this one file needs to change — no route or service that calls
`session_store.get(...)` / `.create(...)` / `.delete(...)` needs to know or
care where the data actually lives.
"""

from typing import Any, Optional


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, dict] = {}

    def create(self, session_id: str, data: dict) -> None:
        self._sessions[session_id] = data

    def get(self, session_id: str) -> Optional[dict]:
        return self._sessions.get(session_id)

    def exists(self, session_id: str) -> bool:
        return session_id in self._sessions

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def count(self) -> int:
        return len(self._sessions)

    # Convenience passthroughs used by a couple of call sites that need to
    # mutate a session dict in place (e.g. appending an answer).
    def set_field(self, session_id: str, key: str, value: Any) -> None:
        session = self._sessions.get(session_id)
        if session is not None:
            session[key] = value


# Module-level singleton — one shared store for the whole process, same
# lifetime/scope as the old module-level `sessions = {}` dict in main.py.
session_store = SessionStore()
