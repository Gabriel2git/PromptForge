import json
import logging
import re
import socket
import time
from typing import Any, Dict, List
from urllib import error, request

from app.config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    DEEPSEEK_TIMEOUT_SECONDS,
)
from app.services.prompt_generator import normalize_framework

logger = logging.getLogger(__name__)

MODEL_ALIASES = {
    "deepseek-v3.2": "deepseek-chat",
    "deepseek-v3": "deepseek-chat",
}


class LLMCallError(RuntimeError):
    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


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
        raw_model = (model or DEEPSEEK_MODEL).strip()
        self.model = MODEL_ALIASES.get(raw_model.lower(), raw_model)
        self.timeout = float(timeout)

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _chat(self, messages: List[Dict[str, str]], temperature: float = 0.3) -> str:
        if not self.enabled:
            raise LLMCallError("disabled", "DeepSeek API key is missing")

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
        except error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="ignore")
            except Exception:
                detail = ""
            message = f"DeepSeek HTTP error {exc.code}: {detail[:240]}".strip()
            raise LLMCallError("network_error", message) from exc
        except socket.timeout as exc:
            raise LLMCallError("timeout", f"DeepSeek request timed out: {exc}") from exc
        except TimeoutError as exc:
            raise LLMCallError("timeout", f"DeepSeek request timed out: {exc}") from exc
        except error.URLError as exc:
            if isinstance(exc.reason, socket.timeout):
                raise LLMCallError("timeout", f"DeepSeek request timed out: {exc}") from exc
            raise LLMCallError("network_error", f"DeepSeek request failed: {exc}") from exc

        try:
            parsed = json.loads(raw)
            return str(parsed["choices"][0]["message"]["content"]).strip()
        except Exception as exc:
            raise LLMCallError("network_error", "DeepSeek response payload is invalid") from exc

    def _parse_json_response(self, raw: str) -> Dict[str, Any]:
        cleaned = raw.strip()

        fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, flags=re.IGNORECASE | re.DOTALL)
        if fenced:
            cleaned = fenced.group(1).strip()

        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                return parsed
            raise ValueError("JSON root must be an object")
        except Exception:
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start == -1 or end <= start:
                raise
            parsed = json.loads(cleaned[start : end + 1])
            if not isinstance(parsed, dict):
                raise ValueError("JSON root must be an object")
            return parsed

    def _normalize_turn_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        question = str(payload.get("question") or "").strip()
        if not question:
            raise ValueError("Missing question")

        options_raw = payload.get("options")
        if not isinstance(options_raw, list):
            raise ValueError("Missing options list")

        options: List[Dict[str, str]] = []
        for idx, item in enumerate(options_raw[:3]):
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or "").strip()
            if not label:
                continue
            key = str(item.get("key") or f"opt_{idx + 1}").strip() or f"opt_{idx + 1}"
            options.append({"key": key, "label": label})

        if len(options) != 3:
            raise ValueError("Options must contain exactly 3 valid items")

        custom_label = str(payload.get("custom_label") or "自定义输入").strip() or "自定义输入"
        return {
            "question": question,
            "options": options,
            "allow_custom": True,
            "custom_label": custom_label,
        }

    def _retry_delays(self, retries: int) -> List[float]:
        if retries <= 0:
            return []
        base = [0.3, 0.6]
        if retries <= len(base):
            return base[:retries]
        extra = [base[-1] * (idx + 1) for idx in range(retries - len(base))]
        return base + extra

    def _compact_error_text(self, exc: Exception, max_len: int = 140) -> str:
        text = str(exc).replace("\r", " ").replace("\n", " ").strip()
        if len(text) > max_len:
            return f"{text[:max_len].rstrip()}..."
        return text

    def generate_next_question(
        self,
        initial_idea: str,
        qa_pairs: List[Dict[str, str]],
        turn_index: int,
        framework: str = "standard",
        profile_hint: str = "",
    ) -> str:
        context = "\n".join([f"Q: {item['question']}\nA: {item['answer']}" for item in qa_pairs]) or "No history"
        style = normalize_framework(framework)
        hint_text = f"\nProfile hint: {profile_hint}" if profile_hint else ""

        messages = [
            {
                "role": "system",
                "content": "You are a Socratic assistant. Output one concise Chinese question only.",
            },
            {
                "role": "user",
                "content": (
                    f"Initial idea: {initial_idea}\n"
                    f"Turn: {turn_index + 1}\n"
                    f"Framework: {style}\n"
                    f"History:\n{context}{hint_text}\n"
                    "Return the next best clarification question in Chinese."
                ),
            },
        ]

        question = self._chat(messages, temperature=0.4)
        compact = question.replace("\n", " ").strip(" ?？")
        return f"{compact}？" if compact else "你希望最终达成什么目标？"

    def generate_next_turn(
        self,
        initial_idea: str,
        qa_pairs: List[Dict[str, str]],
        turn_index: int,
        framework: str = "standard",
        profile_hint: str = "",
        retries: int = 2,
    ) -> Dict[str, Any]:
        context = "\n".join([f"Q: {item['question']}\nA: {item['answer']}" for item in qa_pairs]) or "No history"
        style = normalize_framework(framework)

        schema_hint = {
            "question": "string",
            "options": [
                {"key": "opt_1", "label": "string"},
                {"key": "opt_2", "label": "string"},
                {"key": "opt_3", "label": "string"},
            ],
            "allow_custom": True,
            "custom_label": "自定义输入",
        }

        hint_text = f"\nProfile hint: {profile_hint}" if profile_hint else ""
        messages = [
            {
                "role": "system",
                "content": (
                    "You must return strict JSON only. "
                    "No markdown, no explanation. "
                    "Question and option labels must be Chinese."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Initial idea: {initial_idea}\n"
                    f"Turn: {turn_index + 1}\n"
                    f"Framework: {style}\n"
                    f"History:\n{context}{hint_text}\n"
                    f"Generate one Chinese question and exactly 3 selectable options with JSON schema: {json.dumps(schema_hint, ensure_ascii=False)}"
                ),
            },
        ]

        safe_retries = max(0, int(retries))
        delays = self._retry_delays(safe_retries)
        total_attempts = safe_retries + 1
        last_reason = "parse_error"
        last_detail = "LLM returned non-JSON content"

        for attempt in range(total_attempts):
            raw_preview = ""
            try:
                raw = self._chat(messages, temperature=0.35)
                raw_preview = raw.replace("\r", " ").replace("\n", " ").strip()
                parsed = self._parse_json_response(raw)
                return self._normalize_turn_payload(parsed)
            except LLMCallError as exc:
                last_reason = exc.reason
                last_detail = self._compact_error_text(exc)
                logger.warning(
                    "generate_next_turn call failed (attempt %s/%s, reason=%s): %s",
                    attempt + 1,
                    total_attempts,
                    last_reason,
                    exc,
                )
                if exc.reason == "disabled":
                    raise
            except Exception as exc:
                last_reason = "parse_error"
                preview_suffix = ""
                if raw_preview:
                    clipped = self._compact_error_text(Exception(raw_preview), max_len=90)
                    preview_suffix = f" | raw={clipped}"
                last_detail = f"Invalid JSON from LLM: {self._compact_error_text(exc)}{preview_suffix}"
                logger.warning(
                    "generate_next_turn parse failed (attempt %s/%s): %s",
                    attempt + 1,
                    total_attempts,
                    exc,
                )

            if attempt < safe_retries:
                time.sleep(delays[attempt])

        raise LLMCallError(last_reason, last_detail)

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
                "placeholder": "{{user_input}}",
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

        hint_text = f"\nStyle hint: {profile_hint}" if profile_hint else ""
        messages = [
            {"role": "system", "content": "You are a prompt engineer. Return JSON only."},
            {
                "role": "user",
                "content": (
                    f"Initial idea: {initial_idea}\n"
                    f"Answers:\n{answer_text}\n"
                    f"Framework: {style}{hint_text}\n"
                    f"Return JSON following: {json.dumps(schema_hint, ensure_ascii=False)}"
                ),
            },
        ]

        raw = self._chat(messages, temperature=0.2)
        return self._parse_json_response(raw)

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
                "placeholder": "{{user_input}}",
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

        hint_text = f"\nConfig hint: {profile_hint}" if profile_hint else ""
        messages = [
            {"role": "system", "content": "You refine prompts. Return JSON only."},
            {
                "role": "user",
                "content": (
                    f"Current prompt: {json.dumps(current_prompt, ensure_ascii=False)}\n"
                    f"Instruction: {instruction}\n"
                    f"Framework: {normalize_framework(framework)}{hint_text}\n"
                    f"Return JSON following: {json.dumps(schema_hint, ensure_ascii=False)}"
                ),
            },
        ]

        raw = self._chat(messages, temperature=0.25)
        return self._parse_json_response(raw)


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
