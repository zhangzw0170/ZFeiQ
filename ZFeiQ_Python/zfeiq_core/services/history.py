import sqlite3
from typing import List, Dict
from ..entities.message import Message


class HistoryService:
    def __init__(self, db_path: str = ":memory:"):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._ensure_tables()

    def _ensure_tables(self):
        cur = self._conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user TEXT,
                to_user TEXT,
                text TEXT,
                ts REAL
            )
            """
        )
        self._conn.commit()

    def add_message(self, msg: Message) -> int:
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO messages (from_user, to_user, text, ts) VALUES (?, ?, ?, ?)",
            (msg.from_user, msg.to, msg.text, msg.ts),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_messages(self, limit: int = 100) -> List[Dict]:
        cur = self._conn.cursor()
        cur.execute("SELECT id, from_user, to_user, text, ts FROM messages ORDER BY id DESC LIMIT ?", (limit,))
        rows = cur.fetchall()
        return [
            {"id": r[0], "from_user": r[1], "to": r[2], "text": r[3], "ts": r[4]} for r in rows
        ]
