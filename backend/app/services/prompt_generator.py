from typing import List, Dict


def _extract_constraints(answers: List[str]) -> List[str]:
    constraints: List[str] = []
    if len(answers) >= 3:
        parts = [part.strip(" ;；。\n") for part in answers[2].replace("，", ";").split(";")]
        constraints.extend([p for p in parts if p])
    if not constraints:
        constraints = ["事实优先", "表达清晰", "结构完整"]
    return constraints[:8]


def build_prompt(initial_idea: str, answers: List[str]) -> Dict:
    task = answers[0] if len(answers) > 0 else initial_idea
    audience_scene = answers[1] if len(answers) > 1 else "面向通用用户场景"
    output_format = answers[3] if len(answers) > 3 else "使用 Markdown 分点输出"
    error_handling = answers[4] if len(answers) > 4 else "当信息不足时，先列出缺失信息并给出最小可行答案。"

    structured = {
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
    }

    raw_text = (
        f"# Role\n{structured['role']}\n\n"
        f"# Task\n{structured['task']}\n\n"
        "# Input Specification\n"
        f"- required: {structured['input_spec']['required']}\n"
        f"- type: {structured['input_spec']['type']}\n"
        f"- description: {structured['input_spec']['description']}\n"
        f"- placeholder: {structured['input_spec']['placeholder']}\n\n"
        "# Constraints\n"
        + "\n".join([f"- {item}" for item in structured["constraints"]])
        + "\n\n"
        f"# Output Format\n{structured['output_format']}\n\n"
        f"# Thinking Strategy\n{structured['thinking_strategy']}\n\n"
        f"# Error Handling\n{structured['error_handling']}\n\n"
        f"# Initialization\n{structured['initialization']}"
    )

    structured["raw_text"] = raw_text
    return structured
