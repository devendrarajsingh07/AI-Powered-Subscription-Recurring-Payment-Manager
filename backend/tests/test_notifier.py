import socket
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email import policy
from email.parser import BytesParser

import pytest
from aiosmtpd.controller import Controller
from phase5_helpers import DAY, owner, plan

from app import models as m
from app import repositories as repo
from app.config import get_settings
from app.jobs import run_jobs
from app.services.notifier import ConsoleNotifier, DeliveryError, SmtpNotifier, address, render


@pytest.mark.parametrize(
    "value", ["name@example.org\r\nBcc: other@example.org", "name\n@example.org", "invalid"]
)
def test_header_injection_and_bad_addresses_rejected(value):
    with pytest.raises(DeliveryError):
        address(value)


def test_html_and_text_escaped_and_atomic_outbox_publish(db, pg_engine, tmp_path):
    user = owner(db)
    plan(db, user.id, merchant='<img src=x onerror="alert(1)">')
    db.commit()
    run_jobs(pg_engine, as_of=DAY, notifier=ConsoleNotifier(tmp_path))
    path = next(tmp_path.rglob("*.eml"))
    email = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
    for part in email.iter_parts():
        assert "<img" not in part.get_content()
        assert "&lt;img" in part.get_content()
    alert = repo.list_owned(db, user.id, m.Alert)[0]
    mail = render(alert)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: ConsoleNotifier(tmp_path).send(mail), range(2)))
    assert len(list(tmp_path.rglob("*.eml"))) == 1
    ConsoleNotifier(tmp_path).purge(user.id)
    assert not list(tmp_path.rglob("*.eml"))
    with pytest.raises(ValueError):
        ConsoleNotifier(tmp_path).purge("../../outside")


@pytest.mark.parametrize("crash", [False, True])
def test_smtp_sends_to_real_local_test_server(db, pg_engine, monkeypatch, crash):
    class Sink:
        messages = []

        async def handle_DATA(self, server, session, envelope):
            self.messages.append(envelope.original_content)
            return "250 Accepted"

    with socket.socket() as reserve:
        reserve.bind(("127.0.0.1", 0))
        port = reserve.getsockname()[1]
    sink = Sink()
    controller = Controller(sink, hostname="127.0.0.1", port=port)
    controller.start()
    try:
        user = owner(db)
        plan(db, user.id)
        db.commit()
        settings = get_settings().model_copy(
            update={"smtp_host": "127.0.0.1", "smtp_port": port, "smtp_security": "none"}
        )

        class ProcessCrash(BaseException):
            pass

        class Crashing(SmtpNotifier):
            def send(self, mail):
                super().send(mail)
                raise ProcessCrash()

        monkeypatch.setattr(get_settings(), "alert_retry_seconds", 1)
        now = datetime(2026, 10, 18, 3, 30, tzinfo=timezone.utc)
        if crash:
            with pytest.raises(ProcessCrash):
                run_jobs(pg_engine, as_of=DAY, now=now, notifier=Crashing(settings))
        else:
            run_jobs(pg_engine, as_of=DAY, now=now, notifier=SmtpNotifier(settings))
        run_jobs(
            pg_engine, as_of=DAY, now=now + timedelta(seconds=1), notifier=SmtpNotifier(settings)
        )
        run_jobs(
            pg_engine, as_of=DAY, now=now + timedelta(seconds=2), notifier=SmtpNotifier(settings)
        )
        assert len(sink.messages) == (2 if crash else 1)
        assert (
            len(
                {
                    BytesParser(policy=policy.default).parsebytes(msg)["Message-ID"]
                    for msg in sink.messages
                }
            )
            == 1
        )
        message = BytesParser(policy=policy.default).parsebytes(sink.messages[0])
        assert message["To"] == "notify@example.org"
        assert message.get_body(preferencelist=("html",)) is not None
        assert message.get_body(preferencelist=("plain",)) is not None
        assert repo.list_owned(db, user.id, m.Alert)[0].sent_at is not None
    finally:
        controller.stop()
