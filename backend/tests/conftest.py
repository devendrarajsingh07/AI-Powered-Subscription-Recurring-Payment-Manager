"""Real PostgreSQL integration harness. Never migrates/truncates the application database."""

import os
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from alembic import command
from alembic.config import Config
from app.auth import limiter
from app.clock import today
from app.config import get_settings
from app.db import get_db
from app.main import app
from app.uploads import UploadWorker, get_worker

ROOT = Path(__file__).resolve().parents[1]


def alembic_config(connection=None):
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    if connection is not None:
        config.attributes["connection"] = connection
    return config


@pytest.fixture(scope="session")
def pg_admin():
    url = make_url(os.environ["DATABASE_URL"])
    engine = create_engine(
        url.set(database="postgres"), isolation_level="AUTOCOMMIT", hide_parameters=True
    )
    with engine.connect() as connection:
        assert connection.scalar(text("SHOW server_version_num")).startswith("16")
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def pg_engine(pg_admin):
    name = "subtrack_test_" + uuid.uuid4().hex
    with pg_admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))  # Generated UUID, not user input.
    engine = create_engine(pg_admin.url.set(database=name), hide_parameters=True)
    try:
        with engine.begin() as connection:
            command.upgrade(alembic_config(connection), "head")
        yield engine
    finally:
        engine.dispose()
        with pg_admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))


@pytest.fixture(autouse=True)
def isolated_app(pg_engine, monkeypatch):
    from app.db import Base

    with pg_engine.begin() as connection:
        tables = ", ".join('"' + table.name + '"' for table in Base.metadata.sorted_tables)
        connection.execute(text(f"TRUNCATE {tables} CASCADE"))
    monkeypatch.setenv("BCRYPT_ROUNDS", "4")
    get_settings.cache_clear()
    limiter.clear()
    worker = UploadWorker(pg_engine)

    def session():
        with Session(pg_engine) as db:
            yield db

    app.dependency_overrides[get_db] = session
    app.dependency_overrides[get_worker] = lambda: worker
    yield worker
    worker.close()
    app.dependency_overrides.clear()
    get_settings.cache_clear()


@pytest.fixture
def api_client(isolated_app):
    from datetime import date

    app.dependency_overrides[today] = lambda: date(2026, 10, 18)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def db(pg_engine):
    with Session(pg_engine) as session:
        yield session
