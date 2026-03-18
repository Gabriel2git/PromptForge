import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException

from app.config import clamp_max_turns
from app.database.db import (
    fetch_app_settings,
    get_conn,
    json_dumps,
    json_loads,
    normalize_framework,
    save_app_settings,
)
from app.schemas import (
    ConversationCreateRequest,
    ConversationDetail,
    MessageCreateRequest,
    MessageItem,
    PromptRefineRequest,
    PromptUpdateRequest,
    ResolvedConversationConfig,
    RethinkRequest,
    SettingsResponse,
    SettingsUpdateRequest,
)
from app.services.llm_service import LLMCallError, client_from_runtime
from app.services.prompt_assembler import apply_profile_to_prompt, build_profile, resolve_conversation_config
from app.services.prompt_generator import (
    build_prompt,
    merge_generated_prompt,
    merge_generated_prompt_with_fallback,
)
from app.services.socratic_engine import next_assistant_turn, should_generate

router = APIRouter(prefix="/api", tags=["conversations"])
logger = logging.getLogger(__name__)


FALLBACK_REASONS = {"parse_error", "network_error", "timeout", "disabled", "none"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fetch_messages(conversation_id: str) -> list[MessageItem]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT role, content, timestamp FROM messages WHERE conversation_id = ? ORDER BY timestamp",
            (conversation_id,),
        ).fetchall()
    return [MessageItem(role=r["role"], content=r["content"], timestamp=r["timestamp"]) for r in rows]


def _fetch_conversation(conversation_id: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
    return row


def _fetch_prompt_row(conversation_id: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM prompts WHERE conversation_id = ?", (conversation_id,)).fetchone()
    return row


def _to_qa_pairs(messages: list[MessageItem]) -> list[dict[str, str]]:
    qa_pairs: list[dict[str, str]] = []
    current_q: str | None = None
    for msg in messages:
        if msg.role == "assistant":
            current_q = msg.content
        elif msg.role == "user" and current_q:
            qa_pairs.append({"question": current_q, "answer": msg.content})
            current_q = None
    return qa_pairs


def _build_profile_hint(resolved_config: dict[str, Any]) -> str:
    profile = build_profile(resolved_config)
    return " | ".join(
        [
            f"scenario={resolved_config.get('scenario')}",
            f"personality={resolved_config.get('personality')}",
            f"template={resolved_config.get('template')}",
            profile.get("scenario_contract", ""),
            profile.get("template_instruction", ""),
            profile.get("verbosity_instruction", ""),
        ]
    )


def _normalize_fallback_reason(reason: str) -> str:
    candidate = str(reason or "none").strip().lower()
    return candidate if candidate in FALLBACK_REASONS else "parse_error"


def _sanitize_fallback_detail(detail: str) -> str:
    raw = str(detail or "").replace("\r", " ").replace("\n", " ").strip()
    if not raw:
        return ""

    lowered = raw.lower()
    if "authorization" in lowered:
        raw = "Authorization header error"

    # Redact common token patterns.
    for marker in ["sk-", "Bearer "]:
        idx = raw.find(marker)
        if idx >= 0:
            raw = f"{raw[:idx]}{marker}[REDACTED]"

    if len(raw) > 180:
        return f"{raw[:180].rstrip()}..."
    return raw


def _attach_turn_meta(assistant_turn: dict[str, Any], source: str, reason: str, detail: str = "") -> dict[str, Any]:
    normalized_reason = _normalize_fallback_reason(reason)
    normalized_source = "llm" if source == "llm" else "fallback"

    result = dict(assistant_turn)
    result["allow_custom"] = True
    result["custom_label"] = str(result.get("custom_label") or "自定义输入").strip() or "自定义输入"
    result["turn_source"] = normalized_source
    result["fallback_reason"] = "none" if normalized_source == "llm" else normalized_reason
    if normalized_source == "fallback":
        result["fallback_detail"] = _sanitize_fallback_detail(detail)
    else:
        result["fallback_detail"] = ""
    return result


def _coerce_assistant_turn(candidate: Any, fallback_turn: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(candidate, dict):
        return _attach_turn_meta(fallback_turn, "fallback", "parse_error", "LLM response is not a JSON object")

    question = str(candidate.get("question") or "").strip() or fallback_turn["question"]

    options_raw = candidate.get("options")
    parsed_options: list[dict[str, str]] = []
    if isinstance(options_raw, list):
        for idx, item in enumerate(options_raw[:3]):
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or "").strip()
            if not label:
                continue
            key = str(item.get("key") or f"opt_{idx + 1}").strip() or f"opt_{idx + 1}"
            parsed_options.append({"key": key, "label": label})

    if len(parsed_options) != 3:
        parsed_options = fallback_turn["options"]

    payload = {
        "question": question,
        "options": parsed_options,
        "allow_custom": True,
        "custom_label": str(candidate.get("custom_label") or fallback_turn.get("custom_label") or "自定义输入").strip()
        or "自定义输入",
    }
    return _attach_turn_meta(payload, "llm", "none", "")


def _build_fallback_turn(
    turn_index: int,
    initial_idea: str,
    resolved_config: dict[str, Any],
    reason: str,
    detail: str = "",
) -> dict[str, Any]:
    scenario = resolved_config.get("scenario", "general")
    base_turn = next_assistant_turn(turn_index, initial_idea=initial_idea, scenario=scenario)
    return _attach_turn_meta(base_turn, "fallback", reason, detail)


def _build_assistant_turn(
    llm_client,
    initial_idea: str,
    qa_pairs: list[dict[str, str]],
    turn_index: int,
    framework: str,
    profile_hint: str,
    resolved_config: dict[str, Any],
) -> dict[str, Any]:
    fallback_turn = _build_fallback_turn(turn_index, initial_idea, resolved_config, "none", "")

    if not llm_client.enabled:
        return _attach_turn_meta(fallback_turn, "fallback", "disabled", "API key missing")

    try:
        generated = llm_client.generate_next_turn(
            initial_idea,
            qa_pairs,
            turn_index,
            framework=framework,
            profile_hint=profile_hint,
            retries=2,
        )
        return _coerce_assistant_turn(generated, fallback_turn)
    except LLMCallError as exc:
        logger.warning("Assistant turn fallback triggered, reason=%s, err=%s", exc.reason, exc)
        return _attach_turn_meta(fallback_turn, "fallback", exc.reason, str(exc))
    except Exception as exc:  # defensive fallback
        logger.exception("Assistant turn fallback triggered by unexpected error: %s", exc)
        return _attach_turn_meta(fallback_turn, "fallback", "parse_error", str(exc))


def _upsert_prompt(conversation_id: str, framework: str, prompt_payload: dict[str, Any]) -> dict[str, str]:
    now = _now_iso()
    tags = [str(item).strip() for item in prompt_payload.get("tags", []) if str(item).strip()]

    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id, created_at FROM prompts WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()

        prompt_id = existing["id"] if existing else str(uuid.uuid4())
        created_at = existing["created_at"] if existing else now

        conn.execute(
            """
            INSERT INTO prompts (id, conversation_id, created_at, updated_at, framework, prompt_json, raw_text, tags_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(conversation_id) DO UPDATE SET
                updated_at = excluded.updated_at,
                framework = excluded.framework,
                prompt_json = excluded.prompt_json,
                raw_text = excluded.raw_text,
                tags_json = excluded.tags_json
            """,
            (
                prompt_id,
                conversation_id,
                created_at,
                now,
                normalize_framework(framework),
                json_dumps(prompt_payload),
                prompt_payload.get("raw_text", ""),
                json_dumps(tags),
            ),
        )

    return {"id": prompt_id, "updated_at": now}


def _resolved_config_from_row(convo_row, fallback_framework: str, fallback_max_turns: int) -> dict[str, Any]:
    raw = json_loads(convo_row["resolved_config_json"]) if convo_row["resolved_config_json"] else None
    if isinstance(raw, dict):
        resolved = dict(raw)
    else:
        resolved = {
            "mode": convo_row["mode"] or "auto",
            "scenario": convo_row["scenario"] or "general",
            "personality": convo_row["personality"] or "professional",
            "template": convo_row["template"] or "standard",
            "verbosity": int(convo_row["verbosity"] or 5),
            "framework": convo_row["framework"] or fallback_framework,
            "confidence": float(convo_row["classification_confidence"] or 0.0),
            "matched_keywords": [],
            "reason": "legacy",
            "source": "legacy",
        }

    resolved["framework"] = normalize_framework(resolved.get("framework") or convo_row["framework"] or fallback_framework)
    resolved["verbosity"] = max(1, min(int(resolved.get("verbosity", 5)), 10))
    resolved.setdefault("mode", "auto")
    resolved.setdefault("scenario", "general")
    resolved.setdefault("personality", "professional")
    resolved.setdefault("template", "standard")
    resolved.setdefault("confidence", float(convo_row["classification_confidence"] or 0.0))
    resolved.setdefault("matched_keywords", [])
    resolved.setdefault("reason", "legacy")
    resolved.setdefault("source", "legacy")
    return resolved


def _resolve_runtime_for_conversation(convo_row) -> tuple[dict[str, Any], dict[str, Any], int]:
    with get_conn() as conn:
        settings = fetch_app_settings(conn)

    runtime = json_loads(convo_row["runtime_config_json"]) if convo_row["runtime_config_json"] else None
    if not isinstance(runtime, dict):
        runtime = {
            "api_key": settings["api_key"],
            "base_url": settings["base_url"],
            "model": settings["model"],
        }

    max_turns = clamp_max_turns(convo_row["max_turns"] if convo_row["max_turns"] is not None else settings["max_turns"])
    resolved = _resolved_config_from_row(convo_row, settings["default_framework"], max_turns)
    return runtime, resolved, max_turns


def _save_generated_prompt(conversation_id: str, structured: dict[str, Any], framework: str, current_turn: int) -> dict[str, str]:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE conversations
            SET status = 'completed', current_turn = ?, generated_prompt_json = ?, generated_prompt_text = ?
            WHERE id = ?
            """,
            (
                current_turn,
                json_dumps(structured),
                structured.get("raw_text", ""),
                conversation_id,
            ),
        )

    return _upsert_prompt(conversation_id, framework, structured)


def _fallback_refine(current_prompt: dict[str, Any], instruction: str, framework: str) -> dict[str, Any]:
    refined = dict(current_prompt)
    refined["task"] = f"{refined.get('task', '').strip()} 优化目标：{instruction}".strip()

    constraints = list(refined.get("constraints", []))
    constraints.append(f"Refine requirement: {instruction}")
    deduped: list[str] = []
    for item in constraints:
        row = str(item).strip()
        if row and row not in deduped:
            deduped.append(row)
    refined["constraints"] = deduped[:12]
    refined.setdefault("tags", [])
    return merge_generated_prompt_with_fallback(refined, current_prompt, framework)


@router.get("/settings", response_model=SettingsResponse)
def get_settings():
    with get_conn() as conn:
        settings = fetch_app_settings(conn)
    return SettingsResponse(**settings)


@router.put("/settings", response_model=SettingsResponse)
def update_settings(payload: SettingsUpdateRequest):
    with get_conn() as conn:
        settings = save_app_settings(conn, payload.model_dump())
    return SettingsResponse(**settings)


@router.post("/conversations")
def create_conversation(payload: ConversationCreateRequest):
    cid = str(uuid.uuid4())
    now = _now_iso()

    with get_conn() as conn:
        settings = fetch_app_settings(conn)

    config_payload = payload.config.model_dump(exclude_none=True) if payload.config else None
    resolved_config, max_turns = resolve_conversation_config(
        payload.initial_idea,
        config_payload,
        payload.framework,
        settings["default_framework"],
        settings["max_turns"],
    )

    runtime_config = {
        "api_key": settings["api_key"],
        "base_url": settings["base_url"],
        "model": settings["model"],
    }

    llm_client = client_from_runtime(runtime_config)
    assistant_turn = _build_assistant_turn(
        llm_client,
        payload.initial_idea,
        [],
        0,
        resolved_config["framework"],
        _build_profile_hint(resolved_config),
        resolved_config,
    )
    initial_question = assistant_turn["question"]

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO conversations (
                id,
                created_at,
                initial_idea,
                status,
                current_turn,
                runtime_config_json,
                framework,
                max_turns,
                mode,
                scenario,
                personality,
                template,
                verbosity,
                classification_confidence,
                resolved_config_json
            ) VALUES (?, ?, ?, 'in_progress', 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cid,
                now,
                payload.initial_idea,
                json_dumps(runtime_config),
                resolved_config["framework"],
                max_turns,
                resolved_config.get("mode", "auto"),
                resolved_config.get("scenario", "general"),
                resolved_config.get("personality", "professional"),
                resolved_config.get("template", "standard"),
                resolved_config.get("verbosity", 5),
                resolved_config.get("confidence", 0.0),
                json_dumps(resolved_config),
            ),
        )

        conn.execute(
            "INSERT INTO messages (id, conversation_id, role, content, timestamp) VALUES (?, ?, 'assistant', ?, ?)",
            (str(uuid.uuid4()), cid, initial_question, _now_iso()),
        )

    return {
        "conversation_id": cid,
        "status": "in_progress",
        "current_turn": 1,
        "framework": resolved_config["framework"],
        "max_turns": max_turns,
        "resolved_config": resolved_config,
        "assistant_message": initial_question,
        "assistant_turn": assistant_turn,
    }


@router.post("/conversations/{conversation_id}/messages")
def append_message(conversation_id: str, payload: MessageCreateRequest):
    convo = _fetch_conversation(conversation_id)
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if convo["status"] == "completed":
        raise HTTPException(status_code=400, detail="Conversation already completed")

    runtime_config, resolved_config, max_turns = _resolve_runtime_for_conversation(convo)
    framework = resolved_config["framework"]
    profile_hint = _build_profile_hint(resolved_config)
    llm_client = client_from_runtime(runtime_config)

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO messages (id, conversation_id, role, content, timestamp) VALUES (?, ?, 'user', ?, ?)",
            (str(uuid.uuid4()), conversation_id, payload.content, _now_iso()),
        )

    messages = _fetch_messages(conversation_id)
    user_answers = [m.content for m in messages if m.role == "user"]

    if should_generate(len(user_answers), max_turns=max_turns, force_generate=payload.force_generate):
        structured = build_prompt(convo["initial_idea"], user_answers, framework=framework)

        if llm_client.enabled:
            try:
                generated = llm_client.generate_structured_prompt(
                    convo["initial_idea"],
                    user_answers,
                    framework=framework,
                    profile_hint=profile_hint,
                )
                if isinstance(generated, dict):
                    structured = merge_generated_prompt(
                        generated,
                        convo["initial_idea"],
                        user_answers,
                        framework=framework,
                    )
            except Exception as exc:
                logger.warning("generate_structured_prompt failed, using local build_prompt fallback: %s", exc)
                structured = build_prompt(convo["initial_idea"], user_answers, framework=framework)

        structured = apply_profile_to_prompt(structured, framework, resolved_config)
        prompt_meta = _save_generated_prompt(conversation_id, structured, framework, len(user_answers))

        return {
            "conversation_id": conversation_id,
            "completed": True,
            "framework": framework,
            "max_turns": max_turns,
            "resolved_config": resolved_config,
            "prompt_id": prompt_meta["id"],
            "generated_prompt": structured,
        }

    assistant_turn = _build_assistant_turn(
        llm_client,
        convo["initial_idea"],
        _to_qa_pairs(messages),
        len(user_answers),
        framework,
        profile_hint,
        resolved_config,
    )
    question = assistant_turn["question"]

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO messages (id, conversation_id, role, content, timestamp) VALUES (?, ?, 'assistant', ?, ?)",
            (str(uuid.uuid4()), conversation_id, question, _now_iso()),
        )
        conn.execute(
            "UPDATE conversations SET current_turn = ? WHERE id = ?",
            (len(user_answers) + 1, conversation_id),
        )

    return {
        "conversation_id": conversation_id,
        "completed": False,
        "current_turn": len(user_answers) + 1,
        "framework": framework,
        "max_turns": max_turns,
        "resolved_config": resolved_config,
        "assistant_message": question,
        "assistant_turn": assistant_turn,
    }


@router.post("/conversations/{conversation_id}/refine")
def refine_prompt(conversation_id: str, payload: PromptRefineRequest):
    convo = _fetch_conversation(conversation_id)
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    runtime_config, resolved_config, max_turns = _resolve_runtime_for_conversation(convo)
    framework = resolved_config["framework"]
    profile_hint = _build_profile_hint(resolved_config)
    llm_client = client_from_runtime(runtime_config)

    prompt_row = _fetch_prompt_row(conversation_id)
    current_prompt = json_loads(prompt_row["prompt_json"]) if prompt_row else json_loads(convo["generated_prompt_json"])
    if not isinstance(current_prompt, dict):
        raise HTTPException(status_code=400, detail="Conversation has no generated prompt to refine")

    refined = _fallback_refine(current_prompt, payload.instruction, framework)
    if llm_client.enabled:
        try:
            generated = llm_client.refine_structured_prompt(
                current_prompt,
                payload.instruction,
                framework=framework,
                profile_hint=profile_hint,
            )
            if isinstance(generated, dict):
                refined = merge_generated_prompt_with_fallback(generated, current_prompt, framework)
        except Exception as exc:
            logger.warning("refine_structured_prompt failed, using local refine fallback: %s", exc)
            refined = _fallback_refine(current_prompt, payload.instruction, framework)

    refined = apply_profile_to_prompt(refined, framework, resolved_config)
    prompt_meta = _save_generated_prompt(conversation_id, refined, framework, int(convo["current_turn"] or 1))

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO messages (id, conversation_id, role, content, timestamp) VALUES (?, ?, 'assistant', ?, ?)",
            (
                str(uuid.uuid4()),
                conversation_id,
                f"已根据你的优化要求更新 Prompt：{payload.instruction}",
                _now_iso(),
            ),
        )

    return {
        "conversation_id": conversation_id,
        "completed": True,
        "framework": framework,
        "max_turns": max_turns,
        "resolved_config": resolved_config,
        "prompt_id": prompt_meta["id"],
        "generated_prompt": refined,
    }


@router.post("/conversations/{conversation_id}/rethink")
def rethink_question(conversation_id: str, payload: RethinkRequest):
    convo = _fetch_conversation(conversation_id)
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if convo["status"] == "completed":
        raise HTTPException(status_code=400, detail="Conversation already completed")

    runtime_config, resolved_config, max_turns = _resolve_runtime_for_conversation(convo)
    framework = resolved_config["framework"]
    profile_hint = _build_profile_hint(resolved_config)
    llm_client = client_from_runtime(runtime_config)

    messages = _fetch_messages(conversation_id)
    user_answers = [m.content for m in messages if m.role == "user"]
    turn_index = len(user_answers)

    rethink_hint = payload.hint.strip()
    if rethink_hint:
        profile_hint = f"{profile_hint} | rethink_hint={rethink_hint}"

    assistant_turn = _build_assistant_turn(
        llm_client,
        convo["initial_idea"],
        _to_qa_pairs(messages),
        turn_index,
        framework,
        profile_hint,
        resolved_config,
    )

    question = assistant_turn["question"]
    if not question.startswith("换个角度"):
        question = f"换个角度：{question}"
        assistant_turn["question"] = question

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO messages (id, conversation_id, role, content, timestamp) VALUES (?, ?, 'assistant', ?, ?)",
            (str(uuid.uuid4()), conversation_id, question, _now_iso()),
        )
        conn.execute(
            "UPDATE conversations SET current_turn = ? WHERE id = ?",
            (turn_index + 1, conversation_id),
        )

    return {
        "conversation_id": conversation_id,
        "completed": False,
        "current_turn": turn_index + 1,
        "framework": framework,
        "max_turns": max_turns,
        "resolved_config": resolved_config,
        "assistant_message": question,
        "assistant_turn": assistant_turn,
    }


@router.get("/conversations")
def list_conversations(limit: int = 30):
    safe_limit = max(1, min(limit, 100))

    with get_conn() as conn:
        settings = fetch_app_settings(conn)
        rows = conn.execute(
            """
            SELECT
                c.id,
                c.created_at,
                c.initial_idea,
                c.status,
                c.current_turn,
                c.generated_prompt_text,
                c.framework,
                c.max_turns,
                c.mode,
                c.scenario,
                c.personality,
                c.template,
                c.verbosity,
                c.classification_confidence,
                c.resolved_config_json,
                p.id AS prompt_id,
                p.updated_at AS prompt_updated_at
            FROM conversations c
            LEFT JOIN prompts p ON p.conversation_id = c.id
            ORDER BY c.created_at DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()

    result = []
    for row in rows:
        resolved = _resolved_config_from_row(row, settings["default_framework"], settings["max_turns"])
        has_prompt = bool(row["generated_prompt_text"] or row["prompt_id"])
        result.append(
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "initial_idea": row["initial_idea"],
                "status": row["status"],
                "current_turn": int(row["current_turn"] or 0),
                "framework": resolved["framework"],
                "max_turns": clamp_max_turns(row["max_turns"] if row["max_turns"] is not None else settings["max_turns"]),
                "scenario": resolved.get("scenario", "general"),
                "template": resolved.get("template", "standard"),
                "personality": resolved.get("personality", "professional"),
                "resolved_config": resolved,
                "has_prompt": has_prompt,
                "prompt_id": row["prompt_id"],
                "prompt_updated_at": row["prompt_updated_at"],
            }
        )

    return result


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: str):
    convo = _fetch_conversation(conversation_id)
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    with get_conn() as conn:
        settings = fetch_app_settings(conn)

    resolved = _resolved_config_from_row(convo, settings["default_framework"], settings["max_turns"])

    prompt_row = _fetch_prompt_row(conversation_id)
    prompt = json_loads(prompt_row["prompt_json"]) if prompt_row else json_loads(convo["generated_prompt_json"])

    return ConversationDetail(
        id=convo["id"],
        created_at=convo["created_at"],
        initial_idea=convo["initial_idea"],
        status=convo["status"],
        current_turn=int(convo["current_turn"] or 0),
        framework=resolved["framework"],
        max_turns=clamp_max_turns(convo["max_turns"] if convo["max_turns"] is not None else settings["max_turns"]),
        resolved_config=ResolvedConversationConfig(**resolved),
        messages=_fetch_messages(conversation_id),
        generated_prompt=prompt,
    )


@router.put("/conversations/{conversation_id}/prompt")
def update_prompt(conversation_id: str, payload: PromptUpdateRequest):
    convo = _fetch_conversation(conversation_id)
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    with get_conn() as conn:
        settings = fetch_app_settings(conn)

    resolved = _resolved_config_from_row(convo, settings["default_framework"], settings["max_turns"])
    framework = resolved["framework"]

    prompt_row = _fetch_prompt_row(conversation_id)
    prompt = json_loads(prompt_row["prompt_json"]) if prompt_row else json_loads(convo["generated_prompt_json"]) or {}
    prompt["raw_text"] = payload.raw_text
    prompt.setdefault("tags", [])

    prompt_meta = _save_generated_prompt(conversation_id, prompt, framework, int(convo["current_turn"] or 1))
    return {"ok": True, "prompt_id": prompt_meta["id"]}


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str):
    convo = _fetch_conversation(conversation_id)
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    with get_conn() as conn:
        conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
        conn.execute("DELETE FROM prompts WHERE conversation_id = ?", (conversation_id,))
        conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))

    return {"ok": True}
