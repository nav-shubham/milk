import sqlite3
import logging
from contextlib import contextmanager
from app.config import DATABASE_PATH

logger = logging.getLogger(__name__)

def get_connection() -> sqlite3.Connection:
    """Returns a SQLite connection. Ensures database parent directory exists."""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON;")
    # Return rows as dictionaries
    conn.row_factory = sqlite3.Row
    return conn

@contextmanager
def get_db_cursor():
    """Context manager for SQLite cursor with automatic commit/rollback."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        yield cursor
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database transaction error: {e}", exc_info=True)
        raise
    finally:
        cursor.close()
        conn.close()
