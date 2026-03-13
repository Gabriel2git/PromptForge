from typing import Any

from app.services.prompt_options_store import get_prompt_options


BUILTIN_KEYWORDS: dict[str, list[str]] = {
    "code_assistant": [
        "\u4ee3\u7801", "\u8c03\u8bd5", "\u6d4b\u8bd5", "\u540e\u7aef", "\u524d\u7aef", "\u63a5\u53e3", "\u91cd\u6784",
    ],
    "customer_service": [
        "\u5ba2\u670d", "\u5de5\u5355", "\u6295\u8bc9", "\u552e\u540e", "\u56de\u590d",
    ],
    "content_writer": [
        "\u5199\u4f5c", "\u6587\u6848", "\u6587\u7ae0", "\u6545\u4e8b", "\u811a\u672c", "\u8425\u9500",
    ],
    "analyst": [
        "\u5206\u6790", "\u62a5\u544a", "\u6307\u6807", "\u6570\u636e", "\u6d1e\u5bdf", "\u7814\u7a76",
    ],
    "educator": [
        "\u6559\u5b66", "\u6559\u7a0b", "\u8bfe\u7a0b", "\u8bb2\u89e3", "\u8bad\u7ec3",
    ],
}


def _normalize_text(text: str) -> str:
    return " ".join(text.lower().strip().split())


def classify_intent(initial_idea: str, threshold: float = 0.34) -> dict[str, Any]:
    options = get_prompt_options()
    scenarios = options.get("scenarios", [])
    text = _normalize_text(initial_idea)

    score_rows: list[dict[str, Any]] = []
    total_score = 0.0

    for item in scenarios:
        scenario_id = item.get("id")
        if not scenario_id or scenario_id in {"general", "auto"}:
            continue

        keywords = [str(word).lower() for word in item.get("keywords", []) if str(word).strip()]
        keywords.extend([word.lower() for word in BUILTIN_KEYWORDS.get(scenario_id, [])])

        hits = []
        score = 0.0
        for keyword in sorted(set(keywords)):
            if keyword and keyword in text:
                hits.append(keyword)
                score += 1.0

        if score > 0:
            total_score += score
            score_rows.append(
                {
                    "scenario": scenario_id,
                    "score": score,
                    "hits": sorted(set(hits)),
                    "recommended_personality": item.get("recommended_personality", "professional"),
                    "recommended_template": item.get("recommended_template", "standard"),
                }
            )

    if not score_rows:
        return {
            "scenario": "general",
            "recommended_personality": "professional",
            "recommended_template": "standard",
            "confidence": 0.0,
            "matched_keywords": [],
            "reason": "no_keyword_hit",
        }

    score_rows.sort(key=lambda row: row["score"], reverse=True)
    best = score_rows[0]
    confidence = round(best["score"] / max(1.0, total_score), 4)

    if confidence < threshold:
        return {
            "scenario": "general",
            "recommended_personality": "professional",
            "recommended_template": "standard",
            "confidence": confidence,
            "matched_keywords": best["hits"],
            "reason": "low_confidence_fallback",
        }

    return {
        "scenario": best["scenario"],
        "recommended_personality": best["recommended_personality"],
        "recommended_template": best["recommended_template"],
        "confidence": confidence,
        "matched_keywords": best["hits"],
        "reason": "matched",
    }
