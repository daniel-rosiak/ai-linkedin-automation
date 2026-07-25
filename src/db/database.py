import sqlite3
from datetime import datetime
from typing import List, Optional

from src.config import DATABASE_PATH
from src.db.models import Proposal


def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_db():
    """Creates the tables if they don't already exist and runs migrations to support 'posted' status and 'updated_at'."""
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE,
                title TEXT,
                source TEXT,
                summary TEXT,
                proposed_title TEXT,
                proposed_angle TEXT,
                status TEXT CHECK(status IN ('pending', 'approved', 'rejected', 'skipped', 'posted')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Check and migrate existing schema for 'posted' and 'updated_at' column addition
        cursor = conn.execute("PRAGMA table_info(proposals)")
        columns = [row["name"] for row in cursor.fetchall()]

        cursor = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='proposals'")
        table_sql_row = cursor.fetchone()
        if table_sql_row:
            table_sql = table_sql_row["sql"]
            if "'posted'" not in table_sql or "updated_at" not in table_sql:
                print("Migrating SQLite proposals table for 'posted' status and 'updated_at' timestamps...")
                conn.execute("ALTER TABLE proposals RENAME TO proposals_old")
                conn.execute("""
                    CREATE TABLE proposals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        url TEXT UNIQUE,
                        title TEXT,
                        source TEXT,
                        summary TEXT,
                        proposed_title TEXT,
                        proposed_angle TEXT,
                        status TEXT CHECK(status IN ('pending', 'approved', 'rejected', 'skipped', 'posted')),
                        feedback TEXT,
                        completed_copy TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                # Copy all existing columns safely
                cols_to_copy = [
                    "url",
                    "title",
                    "source",
                    "summary",
                    "proposed_title",
                    "proposed_angle",
                    "status",
                    "created_at",
                ]
                if "feedback" in columns:
                    cols_to_copy.append("feedback")
                if "completed_copy" in columns:
                    cols_to_copy.append("completed_copy")

                cols_str = ", ".join(cols_to_copy)
                conn.execute(f"INSERT INTO proposals ({cols_str}) SELECT {cols_str} FROM proposals_old")
                conn.execute("DROP TABLE proposals_old")
                print("Migration complete!")

        # Create key-value preferences table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS preferences (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        # Create style examples table for mimic training posts
        conn.execute("""
            CREATE TABLE IF NOT EXISTS style_examples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                type TEXT DEFAULT 'manual',
                proposal_id INTEGER
            )
        """)

        # Add feedback column if not exists dynamically (safeguard)
        try:
            conn.execute("ALTER TABLE proposals ADD COLUMN feedback TEXT")
        except sqlite3.OperationalError:
            pass
        # Add completed_copy column if not exists dynamically (safeguard)
        try:
            conn.execute("ALTER TABLE proposals ADD COLUMN completed_copy TEXT")
        except sqlite3.OperationalError:
            pass
        # Add updated_at column if not exists dynamically (safeguard)
        try:
            conn.execute("ALTER TABLE proposals ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        except sqlite3.OperationalError:
            pass
        # Add type and proposal_id columns to style_examples dynamically (safeguard)
        try:
            conn.execute("ALTER TABLE style_examples ADD COLUMN type TEXT DEFAULT 'manual'")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE style_examples ADD COLUMN proposal_id INTEGER")
        except sqlite3.OperationalError:
            pass
        conn.commit()


def update_proposal_completed_copy(proposal_id: int, completed_copy: str):
    """Saves the finalized expanded LinkedIn copywriting text for a proposal and advances updated_at."""
    with get_db_connection() as conn:
        conn.execute(
            """
            UPDATE proposals
            SET completed_copy = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """,
            (completed_copy, proposal_id),
        )
        conn.commit()


def add_style_example(content: str, type: str = "manual", proposal_id: Optional[int] = None):
    """Saves a writing example (either manually pasted or automatically cataloged approved copy) to train the mimic model."""
    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO style_examples (content, type, proposal_id) VALUES (?, ?, ?)",
            (content, type, proposal_id),
        )
        conn.commit()


def get_style_examples(limit: int = 3) -> List[str]:
    """Retrieves recent raw manual style training post examples."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT content FROM style_examples WHERE type = 'manual' ORDER BY created_at DESC, id DESC LIMIT ?",
            (limit,),
        )
        rows = cursor.fetchall()
        return [row["content"] for row in rows]


def remove_style_example_by_proposal(proposal_id: int):
    """Removes an approved style example associated with a specific proposal ID (used during refinements)."""
    with get_db_connection() as conn:
        conn.execute("DELETE FROM style_examples WHERE proposal_id = ? AND type = 'approved'", (proposal_id,))
        conn.commit()


def get_style_examples_detailed(limit: int = 10) -> List[dict]:
    """Retrieves detailed records of recent manual style training post examples (including id, content, type)."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT id, content, type, created_at FROM style_examples WHERE type = 'manual' ORDER BY created_at DESC, id DESC LIMIT ?",
            (limit,),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def delete_style_example(example_id: int) -> bool:
    """Deletes a specific style example by its unique database ID. Returns True if deleted, otherwise False."""
    with get_db_connection() as conn:
        cursor = conn.execute("DELETE FROM style_examples WHERE id = ?", (example_id,))
        conn.commit()
        return cursor.rowcount > 0


def clear_style_examples():
    """Clears all manual style training post examples (or everything)."""
    with get_db_connection() as conn:
        conn.execute("DELETE FROM style_examples")
        conn.commit()


def set_preference(key: str, value: str):
    """Sets a global user preference key-value pair."""
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO preferences (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
            (key, value),
        )
        conn.commit()


def get_preference(key: str) -> Optional[str]:
    """Retrieves a global user preference value by key."""
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT value FROM preferences WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row["value"] if row else None


def url_exists(url: str) -> bool:
    """Checks if a URL has already been processed or proposed."""
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT 1 FROM proposals WHERE url = ?", (url,))
        return cursor.fetchone() is not None


def save_proposal(proposal: Proposal) -> int:
    """Saves a new proposal into the database. Returns its assigned row ID."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO proposals (url, title, source, summary, proposed_title, proposed_angle, status, feedback, completed_copy)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                proposed_title=excluded.proposed_title,
                proposed_angle=excluded.proposed_angle,
                status=excluded.status,
                feedback=excluded.feedback,
                completed_copy=excluded.completed_copy
        """,
            (
                proposal.url,
                proposal.title,
                proposal.source,
                proposal.summary,
                proposal.proposed_title,
                proposal.proposed_angle,
                proposal.status,
                proposal.feedback,
                proposal.completed_copy,
            ),
        )
        conn.commit()
        return cursor.lastrowid if cursor.lastrowid else proposal.id


def update_proposal_status(proposal_id: int, status: str):
    """Updates the status of an existing proposal and advances updated_at."""
    with get_db_connection() as conn:
        conn.execute(
            """
            UPDATE proposals
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """,
            (status, proposal_id),
        )
        conn.commit()


def get_proposal(proposal_id: int) -> Optional[Proposal]:
    """Retrieves a single proposal by its database ID."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT id, url, title, source, summary, proposed_title, proposed_angle, status, created_at, feedback, completed_copy
            FROM proposals
            WHERE id = ?
        """,
            (proposal_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        # Parse timestamp
        created_at = datetime.fromisoformat(row["created_at"]) if row["created_at"] else None

        return Proposal(
            id=row["id"],
            url=row["url"],
            title=row["title"],
            source=row["source"],
            summary=row["summary"],
            proposed_title=row["proposed_title"],
            proposed_angle=row["proposed_angle"],
            status=row["status"],
            created_at=created_at,
            feedback=row["feedback"],
            completed_copy=row["completed_copy"],
        )


def update_proposal_feedback(proposal_id: int, feedback: str):
    """Saves written user feedback critiques for a specific proposal and advances updated_at."""
    with get_db_connection() as conn:
        conn.execute(
            """
            UPDATE proposals
            SET feedback = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """,
            (feedback, proposal_id),
        )
        conn.commit()


def get_history(status: str, limit: int = 10) -> List[Proposal]:
    """Retrieves recent proposals with a given status to build context for LLM learning."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT id, url, title, source, summary, proposed_title, proposed_angle, status, created_at, feedback, completed_copy
            FROM proposals
            WHERE status = ?
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
        """,
            (status, limit),
        )
        rows = cursor.fetchall()

        proposals = []
        for row in rows:
            created_at = datetime.fromisoformat(row["created_at"]) if row["created_at"] else None
            proposals.append(
                Proposal(
                    id=row["id"],
                    url=row["url"],
                    title=row["title"],
                    source=row["source"],
                    summary=row["summary"],
                    proposed_title=row["proposed_title"],
                    proposed_angle=row["proposed_angle"],
                    status=row["status"],
                    created_at=created_at,
                    feedback=row["feedback"],
                    completed_copy=row["completed_copy"],
                )
            )
        return proposals


def get_positive_history(limit: int = 10) -> List[Proposal]:
    """Retrieves recent proposals that are either approved or posted (positive indicators) for style learning."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT id, url, title, source, summary, proposed_title, proposed_angle, status, created_at, feedback, completed_copy
            FROM proposals
            WHERE status IN ('approved', 'posted')
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
        """,
            (limit,),
        )
        rows = cursor.fetchall()

        proposals = []
        for row in rows:
            created_at = datetime.fromisoformat(row["created_at"]) if row["created_at"] else None
            proposals.append(
                Proposal(
                    id=row["id"],
                    url=row["url"],
                    title=row["title"],
                    source=row["source"],
                    summary=row["summary"],
                    proposed_title=row["proposed_title"],
                    proposed_angle=row["proposed_angle"],
                    status=row["status"],
                    created_at=created_at,
                    feedback=row["feedback"],
                    completed_copy=row["completed_copy"],
                )
            )
        return proposals


def get_all_history(limit: int = 10) -> List[Proposal]:
    """Retrieves the most recent proposals across all statuses, grouped by status priority and ordered chronologically."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT id, url, title, source, summary, proposed_title, proposed_angle, status, created_at, feedback, completed_copy
            FROM proposals
            ORDER BY
                CASE status
                    WHEN 'approved' THEN 1
                    WHEN 'posted' THEN 2
                    WHEN 'rejected' THEN 3
                    WHEN 'skipped' THEN 4
                    ELSE 5
                END ASC,
                updated_at DESC,
                id DESC
            LIMIT ?
        """,
            (limit,),
        )
        rows = cursor.fetchall()

        proposals = []
        for row in rows:
            created_at = datetime.fromisoformat(row["created_at"]) if row["created_at"] else None
            proposals.append(
                Proposal(
                    id=row["id"],
                    url=row["url"],
                    title=row["title"],
                    source=row["source"],
                    summary=row["summary"],
                    proposed_title=row["proposed_title"],
                    proposed_angle=row["proposed_angle"],
                    status=row["status"],
                    created_at=created_at,
                    feedback=row["feedback"],
                    completed_copy=row["completed_copy"],
                )
            )
        return proposals
