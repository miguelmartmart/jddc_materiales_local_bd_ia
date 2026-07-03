"""
session_store.py — Almacén de sesiones y mensajes del Analista BD.

Similar a ChatHistoryService pero guarda la procedencia completa
(SQL, resultados brutos, índice SIUO usado) en la columna `provenance_json`.
Usa un fichero SQLite propio, independiente del chat general.
"""

import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.modules.db_analyst.models import Provenance, SessionInfo, SessionMessage

logger = logging.getLogger(__name__)

_DB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "db_analyst_sessions.db"
)


class AnalystSessionStore:

    def __init__(self, db_path: str = _DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")  # habilitar cascade delete
        return conn

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id         TEXT PRIMARY KEY,
                    title      TEXT    NOT NULL,
                    model_id   TEXT,
                    created_at TEXT    DEFAULT (datetime('now')),
                    updated_at TEXT    DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id      TEXT    NOT NULL,
                    role            TEXT    NOT NULL,
                    content         TEXT    NOT NULL,
                    provenance_json TEXT,
                    created_at      TEXT    DEFAULT (datetime('now')),
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );
            """)

    # ── Sessions ──────────────────────────────────────────────────────────────

    def create_session(self, model_id: str = "jddcia-qwen3-30b", title: str = "Nueva conversación") -> str:
        session_id = str(uuid.uuid4())
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO sessions (id, title, model_id) VALUES (?, ?, ?)",
                (session_id, title, model_id),
            )
        return session_id

    def update_title(self, session_id: str, title: str):
        with self._conn() as conn:
            conn.execute(
                "UPDATE sessions SET title = ?, updated_at = datetime('now') WHERE id = ?",
                (title, session_id),
            )

    def list_sessions(self, limit: int = 50) -> List[SessionInfo]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, title, created_at, updated_at FROM sessions ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [SessionInfo(id=r["id"], title=r["title"], created_at=r["created_at"], updated_at=r["updated_at"]) for r in rows]

    def delete_session(self, session_id: str):
        with self._conn() as conn:
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

    # ── Messages ──────────────────────────────────────────────────────────────

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        provenance: Optional[Provenance] = None,
    ) -> int:
        prov_json = provenance.model_dump_json() if provenance else None
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO messages (session_id, role, content, provenance_json) VALUES (?, ?, ?, ?)",
                (session_id, role, content, prov_json),
            )
            conn.execute(
                "UPDATE sessions SET updated_at = datetime('now') WHERE id = ?",
                (session_id,),
            )
            return cur.lastrowid

    def get_messages(self, session_id: str) -> List[SessionMessage]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, session_id, role, content, provenance_json, created_at FROM messages WHERE session_id = ? ORDER BY id",
                (session_id,),
            ).fetchall()
        result = []
        for r in rows:
            prov = None
            if r["provenance_json"]:
                try:
                    prov = Provenance.model_validate_json(r["provenance_json"])
                except Exception:
                    pass
            result.append(SessionMessage(
                id=r["id"],
                session_id=r["session_id"],
                role=r["role"],
                content=r["content"],
                provenance=prov,
                created_at=r["created_at"],
            ))
        return result

    def get_last_assistant_message(self, session_id: str) -> Optional[SessionMessage]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id, session_id, role, content, provenance_json, created_at FROM messages WHERE session_id = ? AND role = 'assistant' ORDER BY id DESC LIMIT 1",
                (session_id,),
            ).fetchone()
        if not row:
            return None
        prov = None
        if row["provenance_json"]:
            try:
                prov = Provenance.model_validate_json(row["provenance_json"])
            except Exception:
                pass
        return SessionMessage(
            id=row["id"],
            session_id=row["session_id"],
            role=row["role"],
            content=row["content"],
            provenance=prov,
            created_at=row["created_at"],
        )
