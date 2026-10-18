from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from alembic.script import ScriptDirectory


def database_at_head(db: Session) -> bool:
    scripts = ScriptDirectory(str(Path(__file__).resolve().parents[1] / "alembic"))
    expected = set(scripts.get_heads())
    actual = set(db.execute(text("SELECT version_num FROM alembic_version")).scalars().all())
    return bool(expected) and actual == expected
