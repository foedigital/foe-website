import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional

DB_PATH = Path(__file__).parent.parent / "comedy_images.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database tables if they don't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS venues (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            url TEXT NOT NULL,
            last_scraped TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY,
            venue_id INTEGER NOT NULL,
            source_url TEXT NOT NULL UNIQUE,
            local_path TEXT NOT NULL,
            event_name TEXT,
            event_date TEXT,
            image_hash TEXT NOT NULL,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (venue_id) REFERENCES venues(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sync_log (
            id INTEGER PRIMARY KEY,
            venue_id INTEGER,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            images_found INTEGER,
            images_new INTEGER,
            status TEXT,
            error_message TEXT,
            FOREIGN KEY (venue_id) REFERENCES venues(id)
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_hash ON images(image_hash)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_source ON images(source_url)")

    conn.commit()
    conn.close()


def get_or_create_venue(name: str, url: str) -> int:
    """Get venue ID, creating if it doesn't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM venues WHERE name = ?", (name,))
    row = cursor.fetchone()

    if row:
        venue_id = row["id"]
    else:
        cursor.execute(
            "INSERT INTO venues (name, url) VALUES (?, ?)",
            (name, url)
        )
        venue_id = cursor.lastrowid
        conn.commit()

    conn.close()
    return venue_id


def update_venue_last_scraped(venue_id: int):
    """Update the last_scraped timestamp for a venue."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE venues SET last_scraped = ? WHERE id = ?",
        (datetime.now().isoformat(), venue_id)
    )
    conn.commit()
    conn.close()


def image_exists(source_url: str) -> bool:
    """Check if an image URL has already been scraped."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM images WHERE source_url = ?", (source_url,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists


def hash_exists(image_hash: str) -> Optional[str]:
    """Check if an image hash exists, return local path if so."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT local_path FROM images WHERE image_hash = ?", (image_hash,))
    row = cursor.fetchone()
    conn.close()
    return row["local_path"] if row else None


def add_image(
    venue_id: int,
    source_url: str,
    local_path: str,
    image_hash: str,
    event_name: Optional[str] = None,
    event_date: Optional[str] = None,
    show_time: Optional[str] = None
) -> int:
    """Add a new image record to the database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO images
           (venue_id, source_url, local_path, image_hash, event_name, event_date, show_time)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (venue_id, source_url, local_path, image_hash, event_name, event_date, show_time)
    )
    image_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return image_id


def start_sync_log(venue_id: int) -> int:
    """Start a sync log entry, return log ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO sync_log (venue_id, started_at, status) VALUES (?, ?, ?)",
        (venue_id, datetime.now().isoformat(), "running")
    )
    log_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return log_id


def complete_sync_log(
    log_id: int,
    images_found: int,
    images_new: int,
    status: str = "success",
    error_message: Optional[str] = None
):
    """Complete a sync log entry."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """UPDATE sync_log
           SET completed_at = ?, images_found = ?, images_new = ?,
               status = ?, error_message = ?
           WHERE id = ?""",
        (datetime.now().isoformat(), images_found, images_new, status, error_message, log_id)
    )
    conn.commit()
    conn.close()


def get_recent_syncs(venue_id: Optional[int] = None, limit: int = 10) -> list:
    """Get recent sync logs."""
    conn = get_connection()
    cursor = conn.cursor()

    if venue_id:
        cursor.execute(
            """SELECT s.*, v.name as venue_name
               FROM sync_log s
               JOIN venues v ON s.venue_id = v.id
               WHERE s.venue_id = ?
               ORDER BY s.started_at DESC LIMIT ?""",
            (venue_id, limit)
        )
    else:
        cursor.execute(
            """SELECT s.*, v.name as venue_name
               FROM sync_log s
               JOIN venues v ON s.venue_id = v.id
               ORDER BY s.started_at DESC LIMIT ?""",
            (limit,)
        )

    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
