from copy import deepcopy
from typing import Any

from app.config import clamp_max_turns
from app.services.intent_classifier import classify_intent
from app.services.prompt_generator import normalize_framework, render_raw_text
from app.services.prompt_options_store import get_prompt_options


DEFAULT_PERSONALITY = "professional"
DEFAULT_SCENARIO = "general"
DEFAULT_TEMPLATE = "standard"


def _clamp_verbosity(value: Any) -> int:
    try:
        parsed = int(value)
    except Exception:
        return 5
    return max(1, min(parsed, 10))


def normalize_template(value: Any) -> str:
    candidate = str(value or DEFAULT_TEMPLATE).strip().lower()
    mapping = {
        "structured": "xml",
        "costar": "co-star",
        "co_star": "co-star",
    }
    candidate = mapping.get(candidate, candidate)
    return candidate if candidate in {"standard", "langgpt", "co-star", "xml"} else DEFAULT_TEMPLATE


def resolve_conversation_config(
    initial_idea: str,
    incoming_config: dict[str, Any] | None,
    explicit_framework: str | None,
    default_framework: str,
    default_max_turns: int,
) -> tuple[dict[str, Any], int]:
    options = get_prompt_options()
    scenario_map = {item.get("id"): item for item in options.get("scenarios", []) if item.get("id")}

    payload = dict(incoming_config or {})
    mode = str(payload.get("mode") or "auto").strip().lower()
    mode = mode if mode in {"auto", "manual"} else "auto"

    scenario = str(payload.get("scenario") or "").strip().lower() or "auto"
    personality = str(payload.get("personality") or "").strip().lower() or ""
    template = normalize_template(payload.get("template")) if payload.get("template") else ""
    verbosity = _clamp_verbosity(payload.get("verbosity", 5))

    classification = {
        "scenario": DEFAULT_SCENARIO,
        "recommended_personality": DEFAULT_PERSONALITY,
        "recommended_template": DEFAULT_TEMPLATE,
        "confidence": 0.0,
        "matched_keywords": [],
        "reason": "manual",
    }

    auto_needed = mode == "auto" and (scenario in {"", "auto"} or not personality or not template)
    if auto_needed:
        classification = classify_intent(initial_idea)

    resolved_scenario = scenario
    if resolved_scenario in {"", "auto"}:
        resolved_scenario = classification["scenario"]
    if resolved_scenario not in scenario_map:
        resolved_scenario = DEFAULT_SCENARIO

    resolved_personality = personality or classification["recommended_personality"] or DEFAULT_PERSONALITY
    if resolved_personality not in {item.get("id") for item in options.get("personalities", [])}:
        resolved_personality = DEFAULT_PERSONALITY

    resolved_template = template or normalize_template(classification["recommended_template"])

    compatibility = options.get("compatibility_matrix", {}).get(resolved_scenario, [])
    if compatibility and resolved_template not in compatibility:
        resolved_template = compatibility[0]

    chosen_framework = normalize_framework(explicit_framework or payload.get("framework") or resolved_template or default_framework)

    max_turns = clamp_max_turns(payload.get("max_turns", default_max_turns))

    resolved = {
        "mode": mode,
        "scenario": resolved_scenario,
        "personality": resolved_personality,
        "template": resolved_template,
        "verbosity": verbosity,
        "framework": chosen_framework,
        "confidence": float(classification.get("confidence", 0.0)),
        "matched_keywords": classification.get("matched_keywords", []),
        "reason": classification.get("reason", "manual"),
        "source": "auto" if auto_needed else "manual",
    }
    return resolved, max_turns


def build_profile(resolved_config: dict[str, Any]) -> dict[str, Any]:
    options = get_prompt_options()
    scenario_map = {item.get("id"): item for item in options.get("scenarios", []) if item.get("id")}
    personality_map = {item.get("id"): item for item in options.get("personalities", []) if item.get("id")}
    template_map = {item.get("id"): item for item in options.get("templates", []) if item.get("id")}

    scenario = scenario_map.get(resolved_config.get("scenario"), scenario_map.get(DEFAULT_SCENARIO, {}))
    personality = personality_map.get(resolved_config.get("personality"), personality_map.get(DEFAULT_PERSONALITY, {}))
    template = template_map.get(normalize_template(resolved_config.get("template")), template_map.get(DEFAULT_TEMPLATE, {}))

    verbosity = _clamp_verbosity(resolved_config.get("verbosity", 5))
    if verbosity <= 3:
        verbosity_instruction = "Prefer concise responses and avoid unnecessary elaboration."
    elif verbosity <= 7:
        verbosity_instruction = "Balance clarity and detail with practical structure."
    else:
        verbosity_instruction = "Provide thorough detail, rationale, and fallback options."

    return {
        "scenario_contract": scenario.get("prompt_contract", ""),
        "scenario_constraints": scenario.get("constraints", []),
        "personality_instruction": personality.get("instruction", ""),
        "personality_constraints": personality.get("constraints", []),
        "template_instruction": template.get("instruction", ""),
        "template_output_hint": template.get("output_format_hint", ""),
        "verbosity_instruction": verbosity_instruction,
        "tags": [
            f"scenario:{resolved_config.get('scenario', DEFAULT_SCENARIO)}",
            f"personality:{resolved_config.get('personality', DEFAULT_PERSONALITY)}",
            f"template:{normalize_template(resolved_config.get('template', DEFAULT_TEMPLATE))}",
            f"framework:{normalize_framework(resolved_config.get('framework', 'standard'))}",
            f"verbosity:{verbosity}",
        ],
    }


def apply_profile_to_prompt(
    structured_prompt: dict[str, Any],
    framework: str,
    resolved_config: dict[str, Any],
) -> dict[str, Any]:
    structured = deepcopy(structured_prompt)
    profile = build_profile(resolved_config)

    role_prefix = profile.get("personality_instruction", "")
    if role_prefix:
        structured["role"] = f"{structured.get('role', '')} {role_prefix}".strip()

    task_suffixes = [
        profile.get("scenario_contract", ""),
        profile.get("template_instruction", ""),
    ]
    task_suffix = " ".join([item for item in task_suffixes if item]).strip()
    if task_suffix:
        structured["task"] = f"{structured.get('task', '')} {task_suffix}".strip()

    constraints = list(structured.get("constraints", []))
    constraints.extend(profile.get("scenario_constraints", []))
    constraints.extend(profile.get("personality_constraints", []))
    constraints.append(profile.get("verbosity_instruction", ""))
    cleaned_constraints: list[str] = []
    for item in constraints:
        row = str(item).strip()
        if row and row not in cleaned_constraints:
            cleaned_constraints.append(row)
    structured["constraints"] = cleaned_constraints[:12]

    output_hint = profile.get("template_output_hint", "")
    if output_hint:
        structured["output_format"] = output_hint

    init_parts = [structured.get("initialization", ""), profile.get("scenario_contract", "")]
    structured["initialization"] = " ".join([item for item in init_parts if item]).strip()

    tags = [str(item).strip() for item in structured.get("tags", []) if str(item).strip()]
    for item in profile.get("tags", []):
        if item not in tags:
            tags.append(item)
    structured["tags"] = tags

    structured["raw_text"] = render_raw_text(structured, framework)
    return structured
