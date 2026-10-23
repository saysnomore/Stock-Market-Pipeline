import math
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from . import config

SCHEMA_PATH = config.SQL_DIR / "schema.sql"
VIEWS_PATH = config.SQL_DIR / "views.sql"


def _sqrt(value):
    if value is None or value < 0:
        return None
    return math.sqrt(value)


@contextmanager
def connect(db_path):
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.create_function("SQRT", 1, _sqrt, deterministic=True)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_schema(conn):
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.executescript(VIEWS_PATH.read_text(encoding="utf-8"))
