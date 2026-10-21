import uuid
from datetime import date
from decimal import Decimal

import pytest
from conftest import alembic_config
from sqlalchemy import Float, Numeric, create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from app import models as m
from app import repositories as repo


def test_migrations_roundtrip_from_empty(pg_admin):
    name = "subtrack_migration_" + uuid.uuid4().hex
    with pg_admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    engine = create_engine(pg_admin.url.set(database=name), hide_parameters=True)
    try:
        with engine.begin() as connection:
            config = alembic_config(connection)
            command.upgrade(config, "head")
            assert set(inspect(connection).get_table_names()) >= set(m.Base.metadata.tables)
            assert not compare_metadata(MigrationContext.configure(connection), m.Base.metadata)
            command.downgrade(config, "base")
            assert not (set(inspect(connection).get_table_names()) & set(m.Base.metadata.tables))
            command.upgrade(config, "head")
            assert not compare_metadata(MigrationContext.configure(connection), m.Base.metadata)
    finally:
        engine.dispose()
        with pg_admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))


def test_model_schema_has_no_drift_and_money_is_numeric(pg_engine):
    with pg_engine.connect() as connection:
        assert not compare_metadata(MigrationContext.configure(connection), m.Base.metadata)
    system_tables = {"users", "llm_switch", "llm_usage"}  # Global, content-free, no owner.
    for table in m.Base.metadata.sorted_tables:
        if table.name not in system_tables:
            assert "user_id" in table.c
            assert any(index.columns.keys() == ["user_id"] for index in table.indexes)
        for column in table.columns:
            assert not isinstance(column.type, Float)
            if "amount" in column.name or column.name in ("monthly_limit", "est_monthly_saving"):
                if column.name == "amount_cv":
                    continue
                assert isinstance(column.type, Numeric)
                # Duplicate estimates aggregate multiple individually valid monetary records.
                expected_precision = 24 if column.name == "est_monthly_saving" else 12
                assert column.type.precision == expected_precision and column.type.scale == 2


def test_provider_migration_revokes_previous_recipient_consent(pg_admin):
    name = "subtrack_consent_" + uuid.uuid4().hex
    with pg_admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    engine = create_engine(pg_admin.url.set(database=name), hide_parameters=True)
    try:
        with engine.begin() as connection:
            config = alembic_config(connection)
            command.upgrade(config, "0005_chat")
            connection.execute(
                text(
                    "INSERT INTO users (id,email,password_hash,live_opt_in) "
                    "VALUES (:id,:email,:hash,true)"
                ),
                {"id": uuid.uuid4(), "email": "consent@example.org", "hash": "unused-fixture"},
            )
            command.upgrade(config, "head")
            assert connection.scalar(text("SELECT live_opt_in FROM users")) is False
            command.downgrade(config, "0006_demo")
            assert connection.scalar(text("SELECT live_opt_in FROM users")) is False
    finally:
        engine.dispose()
        with pg_admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))


def test_budget_alert_null_subscription_dedupe_and_cascades(db):
    user = m.User(email="schema@example.org", password_hash="synthetic-unused-test-hash")
    db.add(user)
    db.flush()
    repo.create_owned(
        db, user.id, m.Alert, kind="budget", send_on=date(2026, 10, 1), channel="email", payload={}
    )
    db.commit()
    with pytest.raises(IntegrityError):
        repo.create_owned(
            db,
            user.id,
            m.Alert,
            kind="budget",
            send_on=date(2026, 10, 1),
            channel="email",
            payload={},
        )
    db.rollback()


def test_cross_user_charge_link_rejected_by_database(db):
    users = [
        m.User(email=f"schema-{i}@example.org", password_hash="synthetic-unused") for i in range(2)
    ]
    db.add_all(users)
    db.flush()
    first, second = users
    upload = repo.create_owned(db, first.id, m.Upload, filename="synthetic.csv")
    tx = repo.create_owned(
        db,
        first.id,
        m.Transaction,
        upload_id=upload.id,
        date=date(2026, 1, 1),
        raw_description="Synthetic",
        merchant_normalized="synthetic",
        amount=Decimal("100"),
        type="debit",
        currency="INR",
    )
    sub = repo.create_owned(
        db,
        second.id,
        m.Subscription,
        identity_key="test-cross-user",
        merchant="synthetic",
        category="unknown",
        kind="subscription",
        currency="INR",
        cadence="monthly",
        avg_amount=Decimal("100"),
        confidence=Decimal("0.9"),
        regularity=Decimal(1),
        amount_cv=Decimal(0),
        occurrences=3,
        last_charge=date(2026, 1, 1),
        next_expected=date(2026, 1, 31),
    )
    db.commit()
    db.add(m.SubscriptionCharge(user_id=second.id, subscription_id=sub.id, transaction_id=tx.id))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()
