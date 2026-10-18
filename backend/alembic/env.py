from alembic import context
from app import models  # noqa: F401
from app.db import Base, get_engine

target_metadata = Base.metadata


def run_migrations():
    existing = context.config.attributes.get("connection")
    if existing is not None:
        context.configure(connection=existing, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
        return
    with get_engine().connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


run_migrations()
