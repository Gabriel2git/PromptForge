from fastapi import APIRouter

from app.database.db import fetch_app_settings, get_conn
from app.schemas import (
    IntentClassifyRequest,
    IntentClassifyResponse,
    PreviewSkeletonRequest,
    PromptOptionsResponse,
)
from app.services.intent_classifier import classify_intent
from app.services.prompt_assembler import apply_profile_to_prompt, resolve_conversation_config
from app.services.prompt_generator import build_prompt
from app.services.prompt_options_store import get_prompt_options

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/prompt-options", response_model=PromptOptionsResponse)
def get_config_prompt_options():
    options = get_prompt_options()
    return PromptOptionsResponse(**options)


@router.get("/scenarios")
def list_scenarios():
    return get_prompt_options().get("scenarios", [])


@router.get("/personalities")
def list_personalities():
    return get_prompt_options().get("personalities", [])


@router.get("/templates")
def list_templates():
    return get_prompt_options().get("templates", [])


@router.post("/classify-intent", response_model=IntentClassifyResponse)
def classify_user_intent(payload: IntentClassifyRequest):
    result = classify_intent(payload.initial_idea, threshold=payload.threshold)
    return IntentClassifyResponse(**result)


@router.post("/preview-skeleton")
def preview_skeleton(payload: PreviewSkeletonRequest):
    with get_conn() as conn:
        settings = fetch_app_settings(conn)

    config_payload = payload.config.model_dump(exclude_none=True) if payload.config else None
    resolved_config, max_turns = resolve_conversation_config(
        payload.initial_idea or "示例任务",
        config_payload,
        payload.framework,
        settings["default_framework"],
        settings["max_turns"],
    )

    skeleton = build_prompt(payload.initial_idea or "示例任务", [], framework=resolved_config["framework"])
    skeleton = apply_profile_to_prompt(skeleton, resolved_config["framework"], resolved_config)

    return {
        "resolved_config": resolved_config,
        "max_turns": max_turns,
        "skeleton": skeleton,
    }
