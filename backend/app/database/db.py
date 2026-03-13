import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    DEFAULT_FRAMEWORK,
    DEFAULT_MAX_TURNS,
    clamp_max_turns,
)


DB_PATH = Path(__file__).resolve().parents[3] / "data" / "prompt_forge.db"
FRAMEWORK_VALUES = {"standard", "langgpt", "co-star", "xml"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_framework(value: Optional[str]) -> str:
    candidate = (value or "standard").strip().lower()
    mapping = {
        "co_star": "co-star",
        "costar": "co-star",
        "structured": "xml",
    }
    candidate = mapping.get(candidate, candidate)
    return candidate if candidate in FRAMEWORK_VALUES else "standard"


def default_app_settings() -> dict[str, Any]:
    return {
        "api_key": DEEPSEEK_API_KEY,
        "base_url": DEEPSEEK_BASE_URL,
        "model": DEEPSEEK_MODEL,
        "max_turns": clamp_max_turns(DEFAULT_MAX_TURNS),
        "default_framework": normalize_framework(DEFAULT_FRAMEWORK),
    }


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row["name"] for row in rows}


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    if column not in _table_columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def fetch_app_settings(conn: sqlite3.Connection) -> dict[str, Any]:
    defaults = default_app_settings()
    row = conn.execute(
        "SELECT api_key, base_url, model, max_turns, default_framework FROM app_settings WHERE id = 1"
    ).fetchone()

    if not row:
        return save_app_settings(conn, defaults)

    settings = {
        "api_key": row["api_key"] if row["api_key"] is not None else defaults["api_key"],
        "base_url": (row["base_url"] or defaults["base_url"]).strip() or defaults["base_url"],
        "model": (row["model"] or defaults["model"]).strip() or defaults["model"],
        "max_turns": clamp_max_turns(row["max_turns"] if row["max_turns"] is not None else defaults["max_turns"]),
        "default_framework": normalize_framework(row["default_framework"] or defaults["default_framework"]),
    }

    if (
        settings["api_key"] != (row["api_key"] or "")
        or settings["base_url"] != (row["base_url"] or "")
        or settings["model"] != (row["model"] or "")
        or settings["max_turns"] != row["max_turns"]
        or settings["default_framework"] != (row["default_framework"] or "")
    ):
        save_app_settings(conn, settings)

    return settings


def save_app_settings(conn: sqlite3.Connection, payload: dict[str, Any]) -> dict[str, Any]:
    defaults = default_app_settings()
    settings = {
        "api_key": str(payload.get("api_key", defaults["api_key"]) or ""),
        "base_url": str(payload.get("base_url", defaults["base_url"]) or defaults["base_url"]).strip()
        or defaults["base_url"],
        "model": str(payload.get("model", defaults["model"]) or defaults["model"]).strip() or defaults["model"],
        "max_turns": clamp_max_turns(payload.get("max_turns", defaults["max_turns"])),
        "default_framework": normalize_framework(payload.get("default_framework", defaults["default_framework"])),
    }

    conn.execute(
        """
        INSERT INTO app_settings (id, api_key, base_url, model, max_turns, default_framework, updated_at)
        VALUES (1, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            api_key = excluded.api_key,
            base_url = excluded.base_url,
            model = excluded.model,
            max_turns = excluded.max_turns,
            default_framework = excluded.default_framework,
            updated_at = excluded.updated_at
        """,
        (
            settings["api_key"],
            settings["base_url"],
            settings["model"],
            settings["max_turns"],
            settings["default_framework"],
            _now_iso(),
        ),
    )
    return settings


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
                generated_prompt_text TEXT,
                runtime_config_json TEXT,
                framework TEXT NOT NULL DEFAULT 'standard',
                max_turns INTEGER NOT NULL DEFAULT 5,
                mode TEXT NOT NULL DEFAULT 'auto',
                scenario TEXT NOT NULL DEFAULT 'general',
                personality TEXT NOT NULL DEFAULT 'professional',
                template TEXT NOT NULL DEFAULT 'standard',
                verbosity INTEGER NOT NULL DEFAULT 5,
                classification_confidence REAL NOT NULL DEFAULT 0,
                resolved_config_json TEXT
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
            CREATE TABLE IF NOT EXISTS prompts (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                framework TEXT NOT NULL DEFAULT 'standard',
                prompt_json TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                tags_json TEXT,
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
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_prompts_updated
            ON prompts(updated_at DESC)
            """
        )

        _ensure_column(conn, "conversations", "runtime_config_json", "TEXT")
        _ensure_column(conn, "conversations", "framework", "TEXT NOT NULL DEFAULT 'standard'")
        _ensure_column(conn, "conversations", "max_turns", "INTEGER NOT NULL DEFAULT 5")
        _ensure_column(conn, "conversations", "mode", "TEXT NOT NULL DEFAULT 'auto'")
        _ensure_column(conn, "conversations", "scenario", "TEXT NOT NULL DEFAULT 'general'")
        _ensure_column(conn, "conversations", "personality", "TEXT NOT NULL DEFAULT 'professional'")
        _ensure_column(conn, "conversations", "template", "TEXT NOT NULL DEFAULT 'standard'")
        _ensure_column(conn, "conversations", "verbosity", "INTEGER NOT NULL DEFAULT 5")
        _ensure_column(conn, "conversations", "classification_confidence", "REAL NOT NULL DEFAULT 0")
        _ensure_column(conn, "conversations", "resolved_config_json", "TEXT")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                id INTEGER PRIMARY KEY CHECK(id = 1),
                api_key TEXT NOT NULL DEFAULT '',
                base_url TEXT NOT NULL DEFAULT 'https://api.deepseek.com/v1',
                model TEXT NOT NULL DEFAULT 'deepseek-chat',
                max_turns INTEGER NOT NULL DEFAULT 5,
                default_framework TEXT NOT NULL DEFAULT 'standard',
                updated_at TEXT NOT NULL
            )
            """
        )

        save_app_settings(conn, fetch_app_settings(conn))


def json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False)


def json_loads(raw: Optional[str]) -> Optional[Any]:
    if not raw:
        return None
    return json.loads(raw)
