from copy import deepcopy
from html import escape
from typing import Any, Dict, List


FRAMEWORK_VALUES = {"standard", "langgpt", "co-star", "xml"}


def normalize_framework(value: str | None) -> str:
    candidate = (value or "standard").strip().lower()
    mapping = {
        "co_star": "co-star",
        "costar": "co-star",
        "structured": "xml",
    }
    candidate = mapping.get(candidate, candidate)
    return candidate if candidate in FRAMEWORK_VALUES else "standard"


def _extract_constraints(answers: List[str]) -> List[str]:
    constraints: List[str] = []
    if len(answers) >= 3:
        parts = [part.strip(" ;；。\n") for part in answers[2].replace("，", ";").split(";")]
        constraints.extend([p for p in parts if p])
    if not constraints:
        constraints = ["事实优先", "表达清晰", "结构完整"]
    return constraints[:8]


def _build_base_structured(initial_idea: str, answers: List[str]) -> Dict[str, Any]:
    task = answers[0] if len(answers) > 0 else initial_idea
    audience_scene = answers[1] if len(answers) > 1 else "面向通用用户场景"
    output_format = answers[3] if len(answers) > 3 else "使用 Markdown 分点输出"
    error_handling = answers[4] if len(answers) > 4 else "当信息不足时，先列出缺失信息并给出最小可行答案。"

    return {
        "role": "你是一名资深提示词工程师与领域顾问。",
        "task": f"围绕以下目标完成任务：{task}",
        "input_spec": {
            "required": True,
            "type": "text",
            "description": f"用户初始想法：{initial_idea}；使用场景：{audience_scene}",
            "placeholder": "{{用户输入}}",
        },
        "constraints": _extract_constraints(answers),
        "output_format": output_format,
        "thinking_strategy": "先澄清目标与边界，再给出分步骤执行结果。",
        "error_handling": error_handling,
        "initialization": "先用 1-2 句复述用户目标，确认理解后再执行。",
        "examples": [],
        "tags": [],
    }


def _normalize_structured(structured: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, Any]:
    normalized = deepcopy(fallback)

    for key in ["role", "task", "output_format", "thinking_strategy", "error_handling", "initialization"]:
        value = structured.get(key)
        if isinstance(value, str) and value.strip():
            normalized[key] = value.strip()

    input_spec_raw = structured.get("input_spec")
    if isinstance(input_spec_raw, dict):
        input_spec = dict(normalized.get("input_spec", {}))
        input_spec["required"] = bool(input_spec_raw.get("required", input_spec.get("required", True)))
        input_spec["type"] = str(input_spec_raw.get("type", input_spec.get("type", "text")))
        input_spec["description"] = str(input_spec_raw.get("description", input_spec.get("description", "")))
        input_spec["placeholder"] = str(input_spec_raw.get("placeholder", input_spec.get("placeholder", "{{用户输入}}")))
        normalized["input_spec"] = input_spec

    constraints = structured.get("constraints")
    if isinstance(constraints, list):
        cleaned = [str(item).strip() for item in constraints if str(item).strip()]
        normalized["constraints"] = cleaned[:12] or fallback.get("constraints", [])

    examples = structured.get("examples")
    if isinstance(examples, list):
        normalized["examples"] = [str(item).strip() for item in examples if str(item).strip()][:12]

    tags = structured.get("tags")
    if isinstance(tags, list):
        normalized["tags"] = [str(item).strip() for item in tags if str(item).strip()][:20]

    return normalized


def render_raw_text(structured: Dict[str, Any], framework: str) -> str:
    style = normalize_framework(framework)
    input_spec = structured.get("input_spec", {})
    constraints = "\n".join([f"- {item}" for item in structured.get("constraints", [])])

    if style == "langgpt":
        return (
            f"# Role\n{structured.get('role', '')}\n\n"
            "# Skills\n"
            "- 需求澄清\n"
            "- 信息结构化\n"
            "- 高质量提示词撰写\n\n"
            f"# Rules\n{constraints}\n\n"
            "# Workflow\n"
            "1. 先复述并确认目标与边界\n"
            "2. 根据输入分解任务并输出步骤\n"
            f"3. 严格遵循输出格式：{structured.get('output_format', '')}\n"
            "4. 信息不足时先提问补齐\n\n"
            f"# Input\n- required: {input_spec.get('required', True)}\n- type: {input_spec.get('type', 'text')}\n"
            f"- description: {input_spec.get('description', '')}\n- placeholder: {input_spec.get('placeholder', '{{用户输入}}')}\n\n"
            f"# Task\n{structured.get('task', '')}\n\n"
            f"# Error Handling\n{structured.get('error_handling', '')}\n\n"
            f"# Initialization\n{structured.get('initialization', '')}"
        )

    if style == "co-star":
        return (
            f"# CONTEXT\n{input_spec.get('description', '')}\n\n"
            f"# OBJECTIVE\n{structured.get('task', '')}\n\n"
            f"# STYLE\n{structured.get('output_format', '')}\n\n"
            "# TONE\n专业、清晰、可执行\n\n"
            "# AUDIENCE\n需要直接执行结果的业务或技术使用者\n\n"
            "# RESPONSE\n"
            "请按目标拆解步骤并给出可落地产出，必要时给出示例。\n\n"
            f"# GUARDRAILS\n{constraints}\n\n"
            f"# ERROR_HANDLING\n{structured.get('error_handling', '')}\n\n"
            f"# INIT\n{structured.get('initialization', '')}"
        )

    if style == "xml":
        constraints_xml = "\n".join([f"    <item>{escape(item)}</item>" for item in structured.get("constraints", [])])
        examples_xml = "\n".join([f"    <example>{escape(item)}</example>" for item in structured.get("examples", [])])
        return (
            "<prompt>\n"
            f"  <role>{escape(str(structured.get('role', '')))}</role>\n"
            f"  <task>{escape(str(structured.get('task', '')))}</task>\n"
            "  <input_spec>\n"
            f"    <required>{str(input_spec.get('required', True)).lower()}</required>\n"
            f"    <type>{escape(str(input_spec.get('type', 'text')))}</type>\n"
            f"    <description>{escape(str(input_spec.get('description', '')))}</description>\n"
            f"    <placeholder>{escape(str(input_spec.get('placeholder', '{{用户输入}}')))}</placeholder>\n"
            "  </input_spec>\n"
            "  <constraints>\n"
            f"{constraints_xml}\n"
            "  </constraints>\n"
            f"  <output_format>{escape(str(structured.get('output_format', '')))}</output_format>\n"
            f"  <thinking_strategy>{escape(str(structured.get('thinking_strategy', '')))}</thinking_strategy>\n"
            f"  <error_handling>{escape(str(structured.get('error_handling', '')))}</error_handling>\n"
            f"  <initialization>{escape(str(structured.get('initialization', '')))}</initialization>\n"
            "  <examples>\n"
            f"{examples_xml}\n"
            "  </examples>\n"
            "</prompt>"
        )

    return (
        f"# Role\n{structured.get('role', '')}\n\n"
        f"# Task\n{structured.get('task', '')}\n\n"
        "# Input Specification\n"
        f"- required: {input_spec.get('required', True)}\n"
        f"- type: {input_spec.get('type', 'text')}\n"
        f"- description: {input_spec.get('description', '')}\n"
        f"- placeholder: {input_spec.get('placeholder', '{{用户输入}}')}\n\n"
        "# Constraints\n"
        f"{constraints}\n\n"
        f"# Output Format\n{structured.get('output_format', '')}\n\n"
        f"# Thinking Strategy\n{structured.get('thinking_strategy', '')}\n\n"
        f"# Error Handling\n{structured.get('error_handling', '')}\n\n"
        f"# Initialization\n{structured.get('initialization', '')}"
    )


def build_prompt(initial_idea: str, answers: List[str], framework: str = "standard") -> Dict[str, Any]:
    structured = _build_base_structured(initial_idea, answers)
    structured["raw_text"] = render_raw_text(structured, framework)
    return structured


def merge_generated_prompt(
    generated: Dict[str, Any],
    initial_idea: str,
    answers: List[str],
    framework: str,
) -> Dict[str, Any]:
    fallback = _build_base_structured(initial_idea, answers)
    normalized = _normalize_structured(generated, fallback)
    normalized["raw_text"] = render_raw_text(normalized, framework)
    return normalized


def merge_generated_prompt_with_fallback(
    generated: Dict[str, Any],
    fallback_prompt: Dict[str, Any],
    framework: str,
) -> Dict[str, Any]:
    fallback = deepcopy(fallback_prompt)
    fallback.setdefault("tags", [])
    normalized = _normalize_structured(generated, fallback)
    normalized["raw_text"] = render_raw_text(normalized, framework)
    return normalized
