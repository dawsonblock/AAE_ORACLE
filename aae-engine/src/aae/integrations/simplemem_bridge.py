from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List


class SimpleMemBridge:
    """SQLite-backed L1 episodic memory inspired by SimpleMem-Cross."""

    def __init__(self, db_path: str | Path = 'artifacts/simplemem_bridge.db') -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    objective TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    finalized_at REAL
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
                """
            )

    def start_session(self, session_id: str, objective: str) -> None:
        with self._connect() as conn:
            conn.execute(
                'INSERT OR REPLACE INTO sessions(session_id, objective, created_at, finalized_at) VALUES (?, ?, ?, NULL)',
                (session_id, objective, time.time()),
            )

    def record_message(self, session_id: str, role: str, content: str, metadata: Dict[str, Any] | None = None) -> None:
        self._record(session_id, role, 'message', content, metadata or {})

    def record_tool_use(self, session_id: str, tool_name: str, input_text: str, output_text: str) -> None:
        content = f'tool={tool_name}\ninput={input_text}\noutput={output_text}'
        self._record(session_id, 'tool', 'tool_use', content, {'tool_name': tool_name})

    def _record(self, session_id: str, role: str, event_type: str, content: str, metadata: Dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                'INSERT INTO events(session_id, role, event_type, content, metadata_json, created_at) VALUES (?, ?, ?, ?, ?, ?)',
                (session_id, role, event_type, content, json.dumps(metadata, sort_keys=True), time.time()),
            )

    def finalize_session(self, session_id: str) -> Dict[str, Any]:
        with self._connect() as conn:
            rows = conn.execute(
                'SELECT role, event_type, content, metadata_json FROM events WHERE session_id = ? ORDER BY id',
                (session_id,),
            ).fetchall()
            conn.execute('UPDATE sessions SET finalized_at = ? WHERE session_id = ?', (time.time(), session_id))

        messages = []
        tools = []
        for row in rows:
            if row['event_type'] == 'message':
                messages.append({'role': row['role'], 'content': row['content']})
            else:
                tools.append({'role': row['role'], 'content': row['content'], 'metadata': json.loads(row['metadata_json'])})

        summary = {
            'session_id': session_id,
            'message_count': len(messages),
            'tool_event_count': len(tools),
            'summary_text': self._summarize(messages, tools),
            'messages': messages[-6:],
            'tools': tools[-6:],
        }
        return summary

    def _summarize(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> str:
        user_bits = [m['content'] for m in messages if m['role'] == 'user'][-3:]
        tool_bits = [t['metadata'].get('tool_name', 'tool') for t in tools][-3:]
        joined = ' | '.join(user_bits)
        tool_text = ', '.join(tool_bits) if tool_bits else 'no tools'
        return f"User focus: {joined or 'no user content'}. Tool activity: {tool_text}."

    def search(self, query: str, limit: int = 8) -> List[Dict[str, Any]]:
        q = query.lower().strip()
        with self._connect() as conn:
            rows = conn.execute(
                'SELECT session_id, role, content, metadata_json FROM events ORDER BY id DESC'
            ).fetchall()
        hits: List[Dict[str, Any]] = []
        for row in rows:
            hay = f"{row['role']} {row['content']} {row['metadata_json']}".lower()
            if q and q not in hay:
                continue
            score = hay.count(q) if q else 1
            hits.append({
                'source': 'simplemem_l1',
                'session_id': row['session_id'],
                'title': f"{row['role']} event",
                'content': row['content'],
                'metadata': json.loads(row['metadata_json']),
                'score': float(score),
            })
        hits.sort(key=lambda x: x['score'], reverse=True)
        return hits[:limit]
