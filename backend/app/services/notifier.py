"""Private dev outbox and bounded SMTP transport. No body/recipient logging."""

import os
import shutil
import smtplib
import ssl
import tempfile
import uuid
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import format_datetime
from pathlib import Path
from typing import Protocol

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from pydantic import EmailStr, TypeAdapter, ValidationError

from app.config import get_settings


class DeliveryError(Exception):
    def __init__(self, *, permanent=False):
        super().__init__("Email delivery could not be confirmed")
        self.permanent = permanent


def address(value: str) -> str:
    if not isinstance(value, str) or any(char in value for char in "\r\n"):
        raise DeliveryError(permanent=True)
    try:
        return str(TypeAdapter(EmailStr).validate_python(value))
    except ValidationError:
        raise DeliveryError(permanent=True) from None


@dataclass(frozen=True)
class Mail:
    user_id: uuid.UUID
    alert_id: uuid.UUID
    recipient: str
    message: EmailMessage


class Notifier(Protocol):
    def send(self, mail: Mail) -> None: ...


def render(alert, *, settings=None) -> Mail:
    from datetime import datetime

    settings = settings or get_settings()
    environment = Environment(
        loader=FileSystemLoader(Path(__file__).resolve().parents[1] / "templates"),
        autoescape=True,
        undefined=StrictUndefined,
    )
    context = dict(
        kind=alert.kind,
        payload=alert.payload,
        settings_url=settings.web_origin.rstrip("/") + "/settings",
    )
    message = EmailMessage()
    message["From"] = address(settings.smtp_from or "subtrack@example.org")
    message["To"] = address(alert.recipient)
    message["Subject"] = (
        "SubTrack renewal reminder" if alert.kind == "renewal" else "SubTrack budget reminder"
    )
    message["Message-ID"] = f"<{alert.id}@subtrack.local>"
    message["Date"] = format_datetime(datetime.fromisoformat(alert.payload["generated_at"]))
    message.set_content(environment.get_template("alert.txt").render(**context))
    message.add_alternative(
        environment.get_template("alert.html").render(**context), subtype="html"
    )
    return Mail(
        uuid.UUID(str(alert.user_id)), uuid.UUID(str(alert.id)), address(alert.recipient), message
    )


class ConsoleNotifier:
    """Atomic hard-link publication: never overwrite or partially publish an .eml."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def user_directory(self, user_id):
        # UUID coercion prevents user-controlled path traversal, including during purge.
        target = self.root.resolve() / str(uuid.UUID(str(user_id)))
        if target.parent != self.root.resolve() or target.is_symlink():
            raise DeliveryError(permanent=True)
        return target

    def send(self, mail: Mail):
        address(mail.recipient)
        folder = self.user_directory(mail.user_id)
        final = folder / (str(uuid.UUID(str(mail.alert_id))) + ".eml")
        temporary = None
        try:
            folder.mkdir(parents=True, exist_ok=True, mode=0o700)
            if final.exists():
                return
            with tempfile.NamedTemporaryFile(dir=folder, prefix=".pending-", delete=False) as file:
                temporary = Path(file.name)
                file.write(mail.message.as_bytes())
                file.flush()
                os.fsync(file.fileno())
            try:
                os.link(temporary, final)
                if os.name == "posix":
                    directory = os.open(folder, os.O_RDONLY)
                    try:
                        os.fsync(directory)
                    finally:
                        os.close(directory)
            except FileExistsError:
                pass  # An identical alert key was already published; the original wins.
        except OSError:
            raise DeliveryError() from None
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)

    def delivered(self, user_id, alert_id):
        file = self.user_directory(user_id) / (str(uuid.UUID(str(alert_id))) + ".eml")
        return not file.is_symlink() and file.is_file()

    def purge(self, user_id):
        target = self.user_directory(user_id)
        if target.exists():
            shutil.rmtree(target)


class SmtpNotifier:
    def __init__(self, settings):
        self.settings = settings

    def send(self, mail: Mail):
        address(mail.recipient)
        cfg = self.settings
        if not cfg.smtp_host:
            raise DeliveryError()
        try:
            connection = smtplib.SMTP_SSL if cfg.smtp_security == "tls" else smtplib.SMTP
            options = {"timeout": cfg.smtp_timeout_seconds}
            if cfg.smtp_security == "tls":
                options["context"] = ssl.create_default_context()
            with connection(cfg.smtp_host, cfg.smtp_port, **options) as smtp:
                if cfg.smtp_security == "starttls":
                    smtp.starttls(context=ssl.create_default_context())
                if cfg.smtp_username:
                    smtp.login(cfg.smtp_username, cfg.smtp_password.get_secret_value())
                smtp.send_message(mail.message)
        except (OSError, smtplib.SMTPException):
            raise DeliveryError() from None


def get_notifier(settings=None) -> Notifier:
    cfg = settings or get_settings()
    return (
        ConsoleNotifier(cfg.outbox_dir) if cfg.notifier_provider == "console" else SmtpNotifier(cfg)
    )
