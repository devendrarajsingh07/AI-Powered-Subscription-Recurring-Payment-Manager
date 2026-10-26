"""OAuth/Gmail protocol foundation. No live construction or runtime route is enabled.

An injected local test transport is mandatory. No default socket transport, ambient proxy,
credential environment lookup, redirect following or provider-response logging is permitted.
"""

import base64
import hashlib
import json
import re
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlsplit

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select

from app import models as m
from app import repositories as repo
from app.config import get_settings

SCOPE = "https://www.googleapis.com/auth/gmail.readonly"


class ProtocolError(Exception):
    """Safe fixed messages only; never include an exception, response or token."""


class HistoryExpired(ProtocolError):
    pass


def cipher():
    try:
        return Fernet(get_settings().mailbox_token_key.get_secret_value().encode("ascii"))
    except (ValueError, UnicodeError):
        raise ProtocolError("Mailbox encryption key is not configured") from None


def begin(db, user_id, client_id, redirect_uri, *, now=None):
    uri = urlsplit(redirect_uri)
    if uri.scheme != "https" or uri.query or uri.fragment or uri.username or not uri.hostname:
        raise ProtocolError("OAuth callback must be a fixed HTTPS URL")
    instant = now or datetime.now(timezone.utc)
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=")
    repo.create_owned(
        db,
        user_id,
        m.MailboxOAuthState,
        digest=hashlib.sha256(state.encode()).hexdigest(),
        verifier_cipher=cipher().encrypt(verifier.encode()),
        expires_at=instant + timedelta(minutes=5),
    )
    db.commit()
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": SCOPE,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
            "code_challenge": challenge.decode(),
            "code_challenge_method": "S256",
        }
    )


def consume(db, user_id, state, *, now=None):
    if not isinstance(state, str) or not 32 <= len(state) <= 128:
        raise ProtocolError("OAuth request is invalid or expired")
    row = db.scalar(
        select(m.MailboxOAuthState)
        .where(
            m.MailboxOAuthState.user_id == user_id,
            m.MailboxOAuthState.digest == hashlib.sha256(state.encode()).hexdigest(),
        )
        .with_for_update()
    )
    instant = now or datetime.now(timezone.utc)
    if row is None or row.consumed_at or row.expires_at <= instant:
        raise ProtocolError("OAuth request is invalid or expired")
    try:
        verifier = cipher().decrypt(row.verifier_cipher).decode("ascii")
    except (InvalidToken, UnicodeError):
        raise ProtocolError("Reconnect the mailbox after key rotation") from None
    row.consumed_at, row.verifier_cipher = instant, b""
    db.commit()  # Consume before any exchange; errors require a fresh authorization.
    return verifier


def save_tokens(db, user_id, connection_id, tokens):
    """Protocol test seam only; no enabled route can create a Gmail connection.

    Refresh responses may omit a refresh token; preserve its encrypted previous value.
    The independent key is mandatory and rotating it requires reconnection.
    """
    row = db.scalar(
        select(m.MailboxConnection)
        .where(
            m.MailboxConnection.user_id == user_id,
            m.MailboxConnection.id == connection_id,
            m.MailboxConnection.mode == "gmail",
            m.MailboxConnection.consented_at.is_not(None),
        )
        .with_for_update()
    )
    if row is None:
        raise ProtocolError("Mailbox consent is unavailable")
    values = {k: tokens[k] for k in ("access_token", "refresh_token", "expires_in") if k in tokens}
    if "refresh_token" not in values and row.token_cipher:
        try:
            values["refresh_token"] = json.loads(cipher().decrypt(row.token_cipher))[
                "refresh_token"
            ]
        except (InvalidToken, ValueError, KeyError):
            raise ProtocolError("Reconnect the mailbox after key rotation") from None
    GmailProtocol._tokens({**values, "scope": SCOPE, "token_type": "Bearer"}, require_refresh=True)
    row.token_cipher = cipher().encrypt(json.dumps(values).encode())
    db.commit()


class GmailProtocol:
    def __init__(self, *, test_transport=None):
        if test_transport is None:
            raise ProtocolError("Live Gmail is disabled; only local protocol tests are permitted")
        self.client = httpx.Client(
            transport=test_transport, timeout=5, trust_env=False, follow_redirects=False
        )

    def close(self):
        self.client.close()

    def _request(self, method, url, *, limit=65536, **kwargs):
        try:
            with self.client.stream(method, url, **kwargs) as response:
                if response.status_code == 404 and "/history" in url:
                    raise HistoryExpired("Mailbox cursor expired; bounded full resync required")
                if response.status_code not in (200, 204):
                    raise ProtocolError("Mailbox provider request failed; reconnect or retry later")
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > limit:
                        raise ProtocolError("Mailbox provider response exceeded its limit")
                return json.loads(data) if data else {}
        except (httpx.HTTPError, ValueError):
            raise ProtocolError(
                "Mailbox provider is unavailable or returned invalid data"
            ) from None

    def exchange(self, *, code, verifier, client_id, client_secret, redirect_uri):
        value = self._request(
            "POST",
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "code_verifier": verifier,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        return self._tokens(value, require_refresh=True)

    def refresh(self, *, refresh_token, client_id, client_secret):
        value = self._request(
            "POST",
            "https://oauth2.googleapis.com/token",
            data={
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
            },
        )
        return self._tokens(value, require_refresh=False)

    @staticmethod
    def _tokens(value, *, require_refresh):
        if not isinstance(value, dict) or value.get("token_type", "").lower() != "bearer":
            raise ProtocolError("Mailbox authorization response is invalid")
        if not isinstance(value.get("scope"), str) or set(value["scope"].split()) != {SCOPE}:
            raise ProtocolError("Mailbox authorization must grant only the read-only Gmail scope")
        for field in ("access_token", "refresh_token") if require_refresh else ("access_token",):
            if not isinstance(value.get(field), str) or not 16 <= len(value[field]) <= 4096:
                raise ProtocolError("Mailbox authorization response is incomplete")
        if type(value.get("expires_in")) is not int or not 1 <= value["expires_in"] <= 86400:
            raise ProtocolError("Mailbox authorization lifetime is invalid")
        return {k: value[k] for k in ("access_token", "refresh_token", "expires_in") if k in value}

    def revoke(self, token):
        self._request("POST", "https://oauth2.googleapis.com/revoke", data={"token": token})

    def messages(self, token, *, history_id=None):
        route = "history" if history_id else "messages"
        params = {"maxResults": 16}
        if history_id:
            if not re.fullmatch(r"\d{1,30}", history_id):
                raise ProtocolError("Mailbox cursor is invalid")
            params.update(startHistoryId=history_id, historyTypes="messageAdded")
        else:
            params["q"] = 'newer_than:90d -in:spam -in:trash (receipt OR "payment successful")'
        return self._request(
            "GET",
            "https://gmail.googleapis.com/gmail/v1/users/me/" + route,
            headers={"Authorization": "Bearer " + token},
            params=params,
        )

    def raw_message(self, token, message_id):
        if not re.fullmatch(r"[a-fA-F0-9]{1,32}", message_id):
            raise ProtocolError("Mailbox message identity is invalid")
        value = self._request(
            "GET",
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/" + message_id,
            limit=1_500_000,
            headers={"Authorization": "Bearer " + token},
            params={"format": "raw"},
        )
        try:
            raw = value["raw"]
            if not isinstance(raw, str) or len(raw) > 1_400_000:
                raise ValueError
            result = base64.b64decode(raw + "=" * (-len(raw) % 4), altchars=b"-_", validate=True)
            if len(result) > 1024 * 1024:
                raise ValueError
            return result
        except (KeyError, TypeError, ValueError):
            raise ProtocolError("Mailbox message exceeded limits or was invalid") from None
