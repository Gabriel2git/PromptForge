import json
from typing import Dict, List
from urllib import error, request

from app.config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    DEEPSEEK_TIMEOUT_SECONDS,
)


class DeepSeekClient:
    def __init__(self) -> None:
        self.api_key = DEEPSEEK_API_KEY
        self.base_url = DEEPSEEK_BASE_URL.rstrip("/")
        self.model = DEEPSEEK_MODEL
        self.timeout = DEEPSEEK_TIMEOUT_SECONDS

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
    ) -> str:
        context = "\n".join(
            [f"Q: {item['question']}\nA: {item['answer']}" for item in qa_pairs]
        ) or "暂无历史问答"

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
                    f"已有问答:\n{context}\n"
                    "请给出下一条最关键的问题。"
                ),
            },
        ]

        question = self._chat(messages, temperature=0.4)
        return question.replace("\n", " ").strip(" ？?") + "？"

    def generate_structured_prompt(self, initial_idea: str, answers: List[str]) -> Dict:
        answer_text = "\n".join([f"{idx + 1}. {ans}" for idx, ans in enumerate(answers)])
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
            "raw_text": "string",
        }

        messages = [
            {
                "role": "system",
                "content": "你是提示词工程专家。仅返回 JSON，不要使用 markdown 代码块，不要额外解释。",
            },
            {
                "role": "user",
                "content": (
                    f"用户初始想法: {initial_idea}\n"
                    f"澄清回答:\n{answer_text}\n\n"
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


client = DeepSeekClient()
