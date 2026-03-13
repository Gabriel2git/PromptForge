import json
from pathlib import Path
from typing import Any


OPTIONS_PATH = Path(__file__).resolve().parents[1] / "resources" / "prompt_options.json"


class PromptOptionsStore:
    def __init__(self) -> None:
        self._cache: dict[str, Any] | None = None

    def load(self, force_reload: bool = False) -> dict[str, Any]:
        if self._cache is not None and not force_reload:
            return self._cache

        if not OPTIONS_PATH.exists():
            self._cache = {
                "scenarios": [],
                "personalities": [],
                "templates": [],
                "compatibility_matrix": {},
            }
            return self._cache

        raw = OPTIONS_PATH.read_text(encoding="utf-8-sig")
        parsed = json.loads(raw)
        parsed.setdefault("scenarios", [])
        parsed.setdefault("personalities", [])
        parsed.setdefault("templates", [])
        parsed.setdefault("compatibility_matrix", {})
        self._cache = parsed
        return parsed

    def scenario_map(self) -> dict[str, dict[str, Any]]:
        return {item.get("id", ""): item for item in self.load().get("scenarios", []) if item.get("id")}

    def personality_map(self) -> dict[str, dict[str, Any]]:
        return {item.get("id", ""): item for item in self.load().get("personalities", []) if item.get("id")}

    def template_map(self) -> dict[str, dict[str, Any]]:
        return {item.get("id", ""): item for item in self.load().get("templates", []) if item.get("id")}


store = PromptOptionsStore()


def get_prompt_options(force_reload: bool = False) -> dict[str, Any]:
    return store.load(force_reload=force_reload)
