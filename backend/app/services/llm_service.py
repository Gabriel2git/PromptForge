import json
from typing import Any, Dict, List
from urllib import error, request

from app.config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    DEEPSEEK_TIMEOUT_SECONDS,
)
from app.services.prompt_generator import normalize_framework


class DeepSeekClient:
    def __init__(
        self,
        api_key: str = "",
        base_url: str = DEEPSEEK_BASE_URL,
        model: str = DEEPSEEK_MODEL,
        timeout: float = DEEPSEEK_TIMEOUT_SECONDS,
    ) -> None:
        self.api_key = api_key.strip()
        self.base_url = (base_url or DEEPSEEK_BASE_URL).rstrip("/")
        self.model = (model or DEEPSEEK_MODEL).strip()
        self.timeout = float(timeout)

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _chat(self, messages: List[Dict[str, str]], temperature: float = 0.3) -> str:
        if not self.enabled:
            raise RuntimeError("DeepSeek API key is missing")

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
        except error.URLError as exc:
            raise RuntimeError(f"DeepSeek request failed: {exc}") from exc

        parsed = json.loads(raw)
        return parsed["choices"][0]["message"]["content"].strip()

    def generate_next_question(
        self,
        initial_idea: str,
        qa_pairs: List[Dict[str, str]],
        turn_index: int,
        framework: str = "standard",
        profile_hint: str = "",
    ) -> str:
        context = "\n".join(
            [f"Q: {item['question']}\nA: {item['answer']}" for item in qa_pairs]
        ) or "暂无历史问答"

        style = normalize_framework(framework)
        style_hint = {
            "standard": "使用通用结构化提问风格",
            "langgpt": "提问时突出角色、规则、流程等信息缺口",
            "co-star": "提问时突出上下文、目标、受众与输出风格",
            "xml": "提问时注意未来输出的标签化结构需求",
        }[style]

        hint_text = f"\n上下文提示: {profile_hint}" if profile_hint else ""

        messages = [
            {
                "role": "system",
                "content": "你是苏格拉底式提问助手。每次仅输出一个中文问题，20-60字，聚焦澄清需求，不要输出解释。",
            },
            {
                "role": "user",
                "content": (
                    f"用户初始想法: {initial_idea}\n"
                    f"当前轮次: 第{turn_index + 1}轮\n"
                    f"框架偏好: {style}\n"
                    f"提问提示: {style_hint}\n"
                    f"已有问答:\n{context}{hint_text}\n"
                    "请给出下一条最关键的问题。"
                ),
            },
        ]

        question = self._chat(messages, temperature=0.4)
        return question.replace("\n", " ").strip(" ？?") + "？"

    def generate_structured_prompt(
        self,
        initial_idea: str,
        answers: List[str],
        framework: str = "standard",
        profile_hint: str = "",
    ) -> Dict[str, Any]:
        answer_text = "\n".join([f"{idx + 1}. {ans}" for idx, ans in enumerate(answers)])
        style = normalize_framework(framework)
        schema_hint = {
            "role": "string",
            "task": "string",
            "input_spec": {
                "required": True,
                "type": "text|code|data|query|document",
                "description": "string",
                "placeholder": "{{用户输入}}",
            },
            "constraints": ["string"],
            "output_format": "string",
            "thinking_strategy": "string",
            "error_handling": "string",
            "initialization": "string",
            "examples": ["string"],
            "tags": ["string"],
            "raw_text": "string",
        }

        framework_hint = {
            "standard": "raw_text 使用标准分节结构",
            "langgpt": "raw_text 使用 Role/Skills/Rules/Workflow 风格",
            "co-star": "raw_text 使用 CONTEXT/OBJECTIVE/STYLE/TONE/AUDIENCE/RESPONSE",
            "xml": "raw_text 使用 XML 标签结构",
        }[style]

        hint_text = f"\n风格配置提示: {profile_hint}" if profile_hint else ""

        messages = [
            {
                "role": "system",
                "content": "你是提示词工程专家。仅返回 JSON，不要使用 markdown 代码块，不要额外解释。",
            },
            {
                "role": "user",
                "content": (
                    f"用户初始想法: {initial_idea}\n"
                    f"澄清回答:\n{answer_text}\n"
                    f"框架: {style}\n"
                    f"格式提示: {framework_hint}{hint_text}\n\n"
                    f"请基于以下结构输出 JSON: {json.dumps(schema_hint, ensure_ascii=False)}"
                ),
            },
        ]

        raw = self._chat(messages, temperature=0.2)
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = cleaned.replace("json", "", 1).strip()
        result = json.loads(cleaned)
        return result

    def refine_structured_prompt(
        self,
        current_prompt: Dict[str, Any],
        instruction: str,
        framework: str = "standard",
        profile_hint: str = "",
    ) -> Dict[str, Any]:
        schema_hint = {
            "role": "string",
            "task": "string",
            "input_spec": {
                "required": True,
                "type": "text|code|data|query|document",
                "description": "string",
                "placeholder": "{{用户输入}}",
            },
            "constraints": ["string"],
            "output_format": "string",
            "thinking_strategy": "string",
            "error_handling": "string",
            "initialization": "string",
            "examples": ["string"],
            "tags": ["string"],
            "raw_text": "string",
        }

        hint_text = f"\n配置提示: {profile_hint}" if profile_hint else ""

        messages = [
            {
                "role": "system",
                "content": "你是 Prompt 优化专家。根据用户优化意图改写结构化 Prompt。只返回 JSON。",
            },
            {
                "role": "user",
                "content": (
                    f"当前 Prompt(JSON): {json.dumps(current_prompt, ensure_ascii=False)}\n"
                    f"优化意图: {instruction}\n"
                    f"框架: {normalize_framework(framework)}{hint_text}\n"
                    f"输出 JSON 结构: {json.dumps(schema_hint, ensure_ascii=False)}"
                ),
            },
        ]

        raw = self._chat(messages, temperature=0.25)
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = cleaned.replace("json", "", 1).strip()
        result = json.loads(cleaned)
        return result


def client_from_runtime(runtime_config: Dict[str, Any] | None) -> DeepSeekClient:
    runtime = runtime_config or {}
    return DeepSeekClient(
        api_key=str(runtime.get("api_key", "") or ""),
        base_url=str(runtime.get("base_url", DEEPSEEK_BASE_URL) or DEEPSEEK_BASE_URL),
        model=str(runtime.get("model", DEEPSEEK_MODEL) or DEEPSEEK_MODEL),
        timeout=DEEPSEEK_TIMEOUT_SECONDS,
    )


client = DeepSeekClient(
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
    model=DEEPSEEK_MODEL,
    timeout=DEEPSEEK_TIMEOUT_SECONDS,
)
