import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException

from app.database.db import get_conn, json_dumps, json_loads
from app.schemas import (
    ConversationCreateRequest,
    ConversationDetail,
    MessageCreateRequest,
    MessageItem,
    PromptUpdateRequest,
)
from app.services.llm_service import client as llm_client
from app.services.prompt_generator import build_prompt
from app.services.socratic_engine import next_question, should_generate

router = APIRouter(prefix="/api", tags=["conversations"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fetch_messages(conversation_id: str):
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


def _to_qa_pairs(messages: list[MessageItem]) -> list[dict[str, str]]:
    qa_pairs = []
    current_q = None
    for msg in messages:
        if msg.role == "assistant":
            current_q = msg.content
        elif msg.role == "user" and current_q:
            qa_pairs.append({"question": current_q, "answer": msg.content})
            current_q = None
    return qa_pairs


@router.post("/conversations")
def create_conversation(payload: ConversationCreateRequest):
    cid = str(uuid.uuid4())
    now = _now_iso()

    initial_question = next_question(0)
    if llm_client.enabled:
        try:
            initial_question = llm_client.generate_next_question(payload.initial_idea, [], 0)
        except Exception:
            initial_question = next_question(0)

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO conversations (id, created_at, initial_idea, status, current_turn) VALUES (?, ?, ?, 'in_progress', 0)",
            (cid, now, payload.initial_idea),
        )

        conn.execute(
            "INSERT INTO messages (id, conversation_id, role, content, timestamp) VALUES (?, ?, 'assistant', ?, ?)",
            (str(uuid.uuid4()), cid, initial_question, _now_iso()),
        )

    return {
        "conversation_id": cid,
        "status": "in_progress",
        "current_turn": 1,
        "assistant_message": initial_question,
    }


@router.post("/conversations/{conversation_id}/messages")
def append_message(conversation_id: str, payload: MessageCreateRequest):
    convo = _fetch_conversation(conversation_id)
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if convo["status"] == "completed":
        raise HTTPException(status_code=400, detail="Conversation already completed")

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO messages (id, conversation_id, role, content, timestamp) VALUES (?, ?, 'user', ?, ?)",
            (str(uuid.uuid4()), conversation_id, payload.content, _now_iso()),
        )

    messages = _fetch_messages(conversation_id)
    user_answers = [m.content for m in messages if m.role == "user"]

    if should_generate(len(user_answers), payload.force_generate):
        structured = build_prompt(convo["initial_idea"], user_answers)

        if llm_client.enabled:
            try:
                generated = llm_client.generate_structured_prompt(convo["initial_idea"], user_answers)
                if isinstance(generated, dict) and generated.get("raw_text"):
                    structured = generated
            except Exception:
                structured = build_prompt(convo["initial_idea"], user_answers)

        with get_conn() as conn:
            conn.execute(
                "UPDATE conversations SET status = 'completed', current_turn = ?, generated_prompt_json = ?, generated_prompt_text = ? WHERE id = ?",
                (
                    len(user_answers),
                    json_dumps(structured),
                    structured["raw_text"],
                    conversation_id,
                ),
            )

        return {
            "conversation_id": conversation_id,
            "completed": True,
            "generated_prompt": structured,
        }

    question = next_question(len(user_answers))
    if llm_client.enabled:
        try:
            qa_pairs = _to_qa_pairs(messages)
            question = llm_client.generate_next_question(
                convo["initial_idea"],
                qa_pairs,
                len(user_answers),
            )
        except Exception:
            question = next_question(len(user_answers))

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO messages (id, conversation_id, role, content, timestamp) VALUES (?, ?, 'assistant', ?, ?)",
            (str(uuid.uuid4()), conversation_id, question, _now_iso()),
        )
        conn.execute(
            "UPDATE conversations SET current_turn = ? WHERE id = ?",
            (len(user_answers), conversation_id),
        )

    return {
        "conversation_id": conversation_id,
        "completed": False,
        "current_turn": len(user_answers) + 1,
        "assistant_message": question,
    }


@router.get("/conversations")
def list_conversations(limit: int = 30):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, created_at, initial_idea, status, current_turn, generated_prompt_text FROM conversations ORDER BY created_at DESC LIMIT ?",
            (max(1, min(limit, 100)),),
        ).fetchall()

    return [
        {
            "id": r["id"],
            "created_at": r["created_at"],
            "initial_idea": r["initial_idea"],
            "status": r["status"],
            "current_turn": r["current_turn"],
            "has_prompt": bool(r["generated_prompt_text"]),
        }
        for r in rows
    ]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: str):
    convo = _fetch_conversation(conversation_id)
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    prompt = json_loads(convo["generated_prompt_json"])
    return ConversationDetail(
        id=convo["id"],
        created_at=convo["created_at"],
        initial_idea=convo["initial_idea"],
        status=convo["status"],
        current_turn=convo["current_turn"],
        messages=_fetch_messages(conversation_id),
        generated_prompt=prompt,
    )


@router.put("/conversations/{conversation_id}/prompt")
def update_prompt(conversation_id: str, payload: PromptUpdateRequest):
    convo = _fetch_conversation(conversation_id)
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    prompt = json_loads(convo["generated_prompt_json"]) or {}
    prompt["raw_text"] = payload.raw_text

    with get_conn() as conn:
        conn.execute(
            "UPDATE conversations SET generated_prompt_json = ?, generated_prompt_text = ? WHERE id = ?",
            (json_dumps(prompt), payload.raw_text, conversation_id),
        )

    return {"ok": True}
