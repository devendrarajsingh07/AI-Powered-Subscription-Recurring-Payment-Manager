"""Only explicitly disposable demo accounts expire; real/local accounts are never selected."""

import json
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app import repositories as repo
from app.auth import DEV_DEMO_EMAIL
from app.config import get_settings
from app.models import User
from app.services.notifier import ConsoleNotifier


def purge_demo_accounts(engine, *, now=None):
    cfg = get_settings()
    if not cfg.public_demo_only:
        return 0
    now = now or datetime.now(timezone.utc)
    count = 0
    with Session(engine) as db:
        targets = list(
            db.execute(
                select(User.id, (User.email == DEV_DEMO_EMAIL).label("shared")).where(
                    or_(
                        User.demo_expires_at <= now,
                        User.email == DEV_DEMO_EMAIL,
                    )
                )
            )
        )
    shared_before = sum(int(row.shared) for row in targets)
    for user_id, _ in targets:
        with Session(engine) as db, db.begin():
            user = repo.get_user(db, user_id, lock=True)
            if user is None:
                continue
            ConsoleNotifier(cfg.outbox_dir).purge(user_id)
            repo.delete_data(db, user_id)
            count += 1
    # Content-free deployment evidence, never an email, password, transaction or amount.
    print(
        json.dumps(
            {"event": "public_demo_purge", "shared_before": shared_before, "removed": count}
        ),
        flush=True,
    )
    return count
