from __future__ import annotations

from typing import Any, Dict, List


TOPIC_BY_SCENARIO: Dict[str, str] = {
    "content_writer": "writing",
    "sales": "sales",
    "weekly_report": "report",
    "presentation": "ppt",
    "general": "general",
}

TOPIC_KEYWORDS: Dict[str, List[str]] = {
    "sales": ["销售", "客户", "商机", "复盘", "crm", "funnel", "deal", "pipeline"],
    "writing": ["写作", "小说", "文案", "剧情", "角色", "story", "copy", "article"],
    "report": ["周报", "日报", "复盘", "总结", "汇报", "report", "summary"],
    "ppt": ["ppt", "幻灯", "演示", "路演", "slides", "deck"],
}

QUESTION_TEMPLATES: Dict[str, List[str]] = {
    "general": [
        "你希望 AI 最终完成的核心任务是什么？",
        "这个结果主要给谁使用，在哪个场景下落地？",
        "你对输出的质量标准或约束有哪些硬要求？",
        "你更偏好的输出格式是什么？",
        "如果信息不足，AI 应该优先如何处理？",
    ],
    "sales": [
        "你这次最想解决的销售问题是什么？",
        "目标客户与当前商机阶段分别是什么？",
        "你希望输出重点偏向策略、话术，还是执行动作？",
        "结果需要按什么结构呈现给团队？",
        "遇到客户信息不全时，AI 应先补问还是先给草案？",
    ],
    "writing": [
        "你希望这次写作最终达成什么效果？",
        "目标读者是谁，阅读场景是什么？",
        "你对文风、语气、长度有哪些要求？",
        "你希望输出按什么结构组织？",
        "如果素材不足，AI 应该先提问还是先给版本 0.1？",
    ],
    "report": [
        "这份报告最核心要回答哪个问题？",
        "汇报对象是谁，他们最关心哪些指标？",
        "你希望重点突出成果、风险，还是行动计划？",
        "报告最终要用什么格式交付？",
        "遇到数据缺失时，希望 AI 如何标注和处理？",
    ],
    "ppt": [
        "这份 PPT 的核心目标和主结论是什么？",
        "听众是谁，他们的决策关注点是什么？",
        "你更看重叙事说服、数据证明，还是视觉表达？",
        "你希望每页输出到什么粒度？",
        "资料不完整时，AI 先补问还是先给目录草案？",
    ],
}

OPTION_TEMPLATES: Dict[str, List[List[str]]] = {
    "general": [
        ["拆成可执行步骤", "先给结论再给依据", "输出一个最小可行版本"],
        ["面向业务同学可直接用", "面向技术同学可实现", "面向管理层便于决策"],
        ["严格控制长度", "强调准确与可验证", "语气专业但不生硬"],
        ["Markdown 分点", "表格化输出", "JSON 结构化输出"],
        ["先列缺失信息并补问", "基于假设先产出草案", "给出多方案并标注风险"],
    ],
    "sales": [
        ["做一个销售复盘助手", "做一个跟进话术助手", "做一个商机推进助手"],
        ["按行业/客群细分策略", "按漏斗阶段给动作", "按客户异议给回应"],
        ["重点优化转化率", "重点提升客单价", "重点缩短成交周期"],
        ["按周计划 + 执行清单", "按客户分层输出", "按机会优先级排序"],
        ["先补问关键客户信息", "先给通用版再细化", "给 A/B 两套策略"],
    ],
    "writing": [
        ["写短篇小说片段", "写品牌宣传文案", "写公众号长文"],
        ["突出人物性格", "突出节奏推进", "突出情绪感染力"],
        ["语气克制专业", "语气轻松有梗", "语气诗性细腻"],
        ["三段式结构", "章节式结构", "先大纲后正文"],
        ["先补素材问题", "先给初稿再迭代", "给多种文风版本"],
    ],
    "report": [
        ["做周报自动生成器", "做项目复盘助手", "做管理汇报助手"],
        ["先讲成果再讲风险", "先讲问题再讲对策", "按目标-结果-计划展开"],
        ["强调业务影响", "强调数据指标", "强调可执行动作"],
        ["一页摘要 + 附录", "标准周报模板", "表格 + 要点混排"],
        ["缺失数据显式标注", "先产出草案后补数", "给保守/激进两版"],
    ],
    "ppt": [
        ["做路演型演示稿", "做内部汇报演示稿", "做产品方案演示稿"],
        ["先目录后逐页展开", "先关键页再补细节", "先讲故事再给证据"],
        ["每页只保留一个主信息", "每页配讲稿备注", "每页附可视化建议"],
        ["输出 10 页精简版", "输出 20 页完整版", "输出可裁剪模块化版本"],
        ["先补问受众与时长", "先给目录草案", "给两种叙事路线"],
    ],
}


def _normalize_text(value: str) -> str:
    return (value or "").strip().lower()


def _detect_topic(initial_idea: str, scenario: str) -> str:
    normalized_scenario = _normalize_text(scenario)
    mapped = TOPIC_BY_SCENARIO.get(normalized_scenario)

    text = _normalize_text(initial_idea)
    scored: Dict[str, int] = {"general": 0, "sales": 0, "writing": 0, "report": 0, "ppt": 0}

    for topic, keywords in TOPIC_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                scored[topic] += 1

    best_topic = max(scored, key=scored.get)
    if scored[best_topic] > 0:
        return best_topic

    if mapped:
        return mapped

    return "general"


def _turn_slot(turn: int) -> int:
    safe_turn = max(0, int(turn))
    return safe_turn % 5


def next_question(turn: int, initial_idea: str = "", scenario: str = "general") -> str:
    topic = _detect_topic(initial_idea, scenario)
    slot = _turn_slot(turn)
    return QUESTION_TEMPLATES.get(topic, QUESTION_TEMPLATES["general"])[slot]


def next_options(turn: int, initial_idea: str = "", scenario: str = "general") -> List[Dict[str, str]]:
    topic = _detect_topic(initial_idea, scenario)
    slot = _turn_slot(turn)

    topic_options = OPTION_TEMPLATES.get(topic, OPTION_TEMPLATES["general"])
    labels = topic_options[slot]

    # Keep the contract stable: exactly 3 options.
    return [{"key": f"opt_{idx + 1}", "label": labels[idx]} for idx in range(3)]


def next_assistant_turn(turn: int, initial_idea: str = "", scenario: str = "general") -> Dict[str, Any]:
    return {
        "question": next_question(turn, initial_idea=initial_idea, scenario=scenario),
        "options": next_options(turn, initial_idea=initial_idea, scenario=scenario),
        "allow_custom": True,
        "custom_label": "自定义输入",
    }


def should_generate(user_turn_count: int, max_turns: int = 5, force_generate: bool = False) -> bool:
    if force_generate:
        return True
    safe_max_turns = max(1, min(int(max_turns), 10))
    return user_turn_count >= safe_max_turns
