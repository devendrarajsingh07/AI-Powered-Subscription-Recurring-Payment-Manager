"""Development-only account loader through the real upload worker."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app import auth  # noqa: E402
from app import models as m
from app import repositories as repo
from app.clock import today  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import get_engine  # noqa: E402
from app.services import demo  # noqa: E402
from app.uploads import UploadWorker  # noqa: E402

EMAIL = auth.DEV_DEMO_EMAIL
PASSWORD = "SubTrackDemo2026!"


def seed(engine=None, *, as_of=None):
    if get_settings().environment != "development" or get_settings().public_demo_only:
        raise RuntimeError("Shared demo seed is permitted only in local development")
    demo.ensure_enabled()
    engine = engine or get_engine()
    as_of = as_of or today()
    with Session(engine) as db:
        user = db.scalar(select(m.User).where(m.User.email == EMAIL))
        if user is None:
            user = auth.register_user(db, EMAIL, PASSWORD)
        elif auth.credentials_user(db, EMAIL, PASSWORD) is None:
            raise RuntimeError("Demo email exists with another credential")
        upload, created = demo.prepare(db, user.id, as_of=as_of)
        user_id, upload_id = user.id, upload.id
        if created and get_settings().job_mode == "postgres":
            from app.services.durable_queue import enqueue

            data, _ = demo.dataset(as_of)
            enqueue(
                db,
                user_id,
                kind="csv",
                subject_id=upload_id,
                data=data,
                mapping=demo.MAPPING,
                as_of=as_of,
            )
        db.commit()
    if created and get_settings().job_mode == "inline":
        data, _ = demo.dataset(as_of)
        worker = UploadWorker(engine)
        try:
            if not worker.reserve():
                raise RuntimeError("Demo worker unavailable")
            worker.submit(user_id, upload_id, data, demo.MAPPING, as_of=as_of).result()
        finally:
            worker.close()
    deadline = time.monotonic() + 90
    while True:
        with Session(engine) as db:
            upload = repo.get_owned(db, user_id, m.Upload, upload_id)
            if upload is None:
                raise RuntimeError("Demo account was removed while processing")
            status = upload.status
        if status == "done":
            break
        if status == "failed" or time.monotonic() >= deadline:
            raise RuntimeError("Demo processing did not finish; check the worker and retry safely")
        time.sleep(0.1)
    return upload_id


if __name__ == "__main__":
    seed()
    print("Development demo ready. Sign in at the configured WEB_ORIGIN.")
    print(f"Demo-only email: {EMAIL}\nDemo-only password: {PASSWORD}")
