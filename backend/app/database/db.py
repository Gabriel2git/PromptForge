import json
import sqlite3
from pathlib import Path
from typing import Any, Optional


DB_PATH = Path(__file__).resolve().parents[3] / "data" / "prompt_forge.db"


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                initial_idea TEXT NOT NULL,
                status TEXT NOT NULL,
                current_turn INTEGER NOT NULL DEFAULT 0,
                generated_prompt_json TEXT,
                generated_prompt_text TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY(conversation_id) REFERENCES conversations(id)
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_messages_conversation
            ON messages(conversation_id, timestamp)
            """
        )


def json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False)


def json_loads(raw: Optional[str]) -> Optional[Any]:
    if not raw:
        return None
    return json.loads(raw)
