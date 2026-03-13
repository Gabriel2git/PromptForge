from fastapi import APIRouter, HTTPException

from app.database.db import fetch_app_settings, get_conn, json_loads
from app.schemas import (
    PromptDetailResponse,
    PromptListItem,
    PromptListResponse,
    ResolvedConversationConfig,
)

router = APIRouter(prefix="/api", tags=["prompts"])


def _resolved_config_from_row(convo_row, default_framework: str) -> dict:
    resolved = json_loads(convo_row["resolved_config_json"]) if convo_row["resolved_config_json"] else None
    if isinstance(resolved, dict):
        return resolved

    return {
        "mode": convo_row["mode"] or "auto",
        "scenario": convo_row["scenario"] or "general",
        "personality": convo_row["personality"] or "professional",
        "template": convo_row["template"] or "standard",
        "verbosity": int(convo_row["verbosity"] or 5),
        "framework": convo_row["framework"] or default_framework,
        "confidence": float(convo_row["classification_confidence"] or 0.0),
        "matched_keywords": [],
        "reason": "legacy",
        "source": "legacy",
    }


@router.get("/prompts", response_model=PromptListResponse)
def list_prompts(limit: int = 50):
    safe_limit = max(1, min(limit, 200))

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT p.id, p.conversation_id, p.updated_at, p.framework, p.raw_text, p.tags_json
            FROM prompts p
            ORDER BY p.updated_at DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()

    items = []
    for row in rows:
        tags = json_loads(row["tags_json"]) or []
        if not isinstance(tags, list):
            tags = []

        snippet = (row["raw_text"] or "").strip().replace("\n", " ")
        snippet = snippet[:140]

        items.append(
            PromptListItem(
                id=row["id"],
                conversation_id=row["conversation_id"],
                updated_at=row["updated_at"],
                framework=row["framework"],
                tags=[str(item) for item in tags if str(item).strip()],
                snippet=snippet,
            )
        )

    return PromptListResponse(items=items, total=len(items))


@router.get("/prompts/{prompt_id}", response_model=PromptDetailResponse)
def get_prompt_detail(prompt_id: str):
    with get_conn() as conn:
        prompt_row = conn.execute("SELECT * FROM prompts WHERE id = ?", (prompt_id,)).fetchone()
        if not prompt_row:
            raise HTTPException(status_code=404, detail="Prompt not found")

        convo = conn.execute("SELECT * FROM conversations WHERE id = ?", (prompt_row["conversation_id"],)).fetchone()
        if not convo:
            raise HTTPException(status_code=404, detail="Conversation not found")

        settings = fetch_app_settings(conn)

    prompt = json_loads(prompt_row["prompt_json"]) or {}
    resolved = _resolved_config_from_row(convo, settings["default_framework"])

    return PromptDetailResponse(
        id=prompt_row["id"],
        conversation_id=prompt_row["conversation_id"],
        updated_at=prompt_row["updated_at"],
        framework=prompt_row["framework"],
        resolved_config=ResolvedConversationConfig(**resolved),
        prompt=prompt,
    )


@router.delete("/prompts/{prompt_id}")
def delete_prompt(prompt_id: str):
    with get_conn() as conn:
        row = conn.execute("SELECT conversation_id FROM prompts WHERE id = ?", (prompt_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Prompt not found")

        conn.execute("DELETE FROM prompts WHERE id = ?", (prompt_id,))
        conn.execute(
            """
            UPDATE conversations
            SET generated_prompt_json = NULL,
                generated_prompt_text = NULL,
                status = 'in_progress'
            WHERE id = ?
            """,
            (row["conversation_id"],),
        )

    return {"ok": True}
