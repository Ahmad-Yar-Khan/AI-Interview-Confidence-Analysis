"""
Manually run the role-brief research (the same code the weekly scheduler runs).

From backend/:
    python -m scripts.refresh_role_briefs                    # every role that is missing/nearly expired
    python -m scripts.refresh_role_briefs --role data-engineer   # one role, regardless of age
    python -m scripts.refresh_role_briefs --status           # what's cached
"""

import argparse
import asyncio
import logging
import time

from dotenv import load_dotenv

load_dotenv(override=True)

from app.core.roles import get_role  # noqa: E402
from app.services import role_brief_service as svc  # noqa: E402


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", help="role slug to force-refresh")
    ap.add_argument("--status", action="store_true", help="print cache status and exit")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO)
    svc.store.init()

    if args.status:
        for row in sorted(svc.store.status(), key=lambda r: r["slug"]):
            age = f"{(time.time() - row['refreshed_at']) / 86400:.1f}d" if row["refreshed_at"] else "never"
            print(f"{row['slug']:<55} {row['confidence'] or '-':<7} refreshed {age:<7} {row['last_error'] or ''}")
        return

    if args.role:
        role = get_role(args.role)
        if role is None:
            raise SystemExit(f"Unknown role slug: {args.role}")
        await svc.refresh_role(role)
    else:
        await svc.refresh_stale_roles()


if __name__ == "__main__":
    asyncio.run(main())
