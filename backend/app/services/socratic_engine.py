from typing import List


QUESTION_BANK: List[str] = [
    "你希望 AI 最终完成什么核心任务？请尽量具体。",
    "这个结果将给谁用？在什么场景下使用？",
    "输出需要满足哪些约束？例如语气、长度、禁用内容、必须包含内容。",
    "你偏好的输出格式是什么？例如 Markdown、表格、JSON、分点列表。",
    "还有哪些边界情况或异常输入时，希望 AI 如何处理？",
]


def next_question(turn: int) -> str:
    safe_turn = max(0, min(turn, len(QUESTION_BANK) - 1))
    return QUESTION_BANK[safe_turn]


def should_generate(user_turn_count: int, max_turns: int = 5, force_generate: bool = False) -> bool:
    if force_generate:
        return True
    safe_max_turns = max(1, min(int(max_turns), 10))
    return user_turn_count >= safe_max_turns
