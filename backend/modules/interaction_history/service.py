import sqlite3
import json
import logging
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class InteractionHistoryService:
    def __init__(self, db_path: str = "backend/data/interaction_history.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize the SQLite database."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    module TEXT NOT NULL,         -- 'OUTLOOK', 'CHAT', 'SIMULATION'
                    action TEXT NOT NULL,         -- 'ANALYSIS', 'REPLY', 'SQL_GEN'
                    model_id TEXT,
                    input_context TEXT,           -- User input | content being analyzed
                    output_result TEXT,           -- AI Response
                    metadata TEXT,                -- JSON: {subject, sender, email_id...}
                    status TEXT DEFAULT 'SUCCESS' -- 'SUCCESS', 'ERROR'
                )
            ''')
            conn.commit()

    def log_interaction(
        self, 
        module: str, 
        action: str, 
        input_context: str, 
        output_result: str, 
        model_id: str = None, 
        metadata: Dict = None,
        status: str = 'SUCCESS'
    ):
        """Logs a generic AI interaction."""
        if metadata is None:
            metadata = {}
            
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO interactions 
                    (module, action, input_context, output_result, model_id, metadata, status) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (module, action, input_context, output_result, model_id, json.dumps(metadata), status)
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to log interaction history: {e}")

    def get_history(self, limit: int = 50, offset: int = 0, module: str = None) -> List[Dict]:
        """Retrieve interaction history."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT * FROM interactions"
            params = []
            
            if module:
                query += " WHERE module = ?"
                params.append(module)
                
            query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            cursor.execute(query, tuple(params))
            
            results = []
            for row in cursor.fetchall():
                item = dict(row)
                try:
                    item['metadata'] = json.loads(item['metadata']) if item['metadata'] else {}
                    # Try parsing output if it looks like JSON, for easier frontend handling
                    if item['output_result'] and (item['output_result'].startswith('{') or item['output_result'].startswith('[')):
                         try:
                             item['output_result_json'] = json.loads(item['output_result'])
                         except:
                             pass
                except:
                    item['metadata'] = {}
                results.append(item)
                
            return results
