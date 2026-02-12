import sqlite3
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import os

logger = logging.getLogger(__name__)

class ChatHistoryService:
    def __init__(self, db_path: str = "backend/data/chat_history.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize the SQLite database with necessary tables."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Sessions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    model_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Messages table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    role TEXT,
                    content TEXT,
                    meta TEXT, -- JSON string for extra data like images, db_params usage etc
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE
                )
            ''')
            conn.commit()

    def create_session(self, model_id: str, title: str = "New Chat") -> str:
        """Create a new chat session."""
        import uuid
        session_id = str(uuid.uuid4())
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO sessions (id, title, model_id, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                (session_id, title, model_id)
            )
            conn.commit()
            
        return session_id

    def update_session_title(self, session_id: str, title: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE sessions SET title = ? WHERE id = ?", (title, session_id))
            conn.commit()

    def update_session_model(self, session_id: str, model_id: str):
        """Update the model ID for a session (e.g. after fallback or successful response)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE sessions SET model_id = ? WHERE id = ?", (model_id, session_id))
            conn.commit()

    def add_message(self, session_id: str, role: str, content: str, meta: Dict = None):
        """Add a message to a session."""
        if meta is None:
            meta = {}
            
        meta_json = json.dumps(meta)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO messages (session_id, role, content, meta) VALUES (?, ?, ?, ?)",
                (session_id, role, content, meta_json)
            )
            # Update session timestamp
            cursor.execute(
                "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (session_id,)
            )
            conn.commit()

    def get_recent_sessions(self, limit: int = 50) -> List[Dict]:
        """Get list of recent chat sessions."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?",
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_session_messages(self, session_id: str) -> List[Dict]:
        """Get all messages for a specific session."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY id ASC",
                (session_id,)
            )
            
            messages = []
            for row in cursor.fetchall():
                msg = dict(row)
                if msg['meta']:
                    try:
                        msg['meta'] = json.loads(msg['meta'])
                    except:
                        msg['meta'] = {}
                messages.append(msg)
                
            return messages

    def delete_session(self, session_id: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()
