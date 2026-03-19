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

SLOT_ORDER = ["goal", "audience", "constraints", "output", "fallback"]
ESSENTIAL_SLOTS = {"goal", "audience", "constraints", "output"}

QUESTION_BANK: Dict[str, Dict[str, Dict[str, Any]]] = {
    "general": {
        "goal": {
            "title": "任务目标",
            "question": "你希望 AI 最终完成的核心任务是什么？",
            "options": ["拆成可执行步骤", "先给结论再给依据", "输出一个最小可行版本"],
        },
        "audience": {
            "title": "受众场景",
            "question": "这个结果主要给谁使用，在哪个场景下落地？",
            "options": ["面向业务同学可直接用", "面向技术同学可实现", "面向管理层便于决策"],
        },
        "constraints": {
            "title": "限制条件",
            "question": "你对输出的质量标准或约束有哪些硬要求？",
            "options": ["严格控制长度", "强调准确与可验证", "语气专业但不生硬"],
        },
        "output": {
            "title": "输出形式",
            "question": "你更偏好的输出格式是什么？",
            "options": ["Markdown 分点", "表格化输出", "JSON 结构化输出"],
        },
        "fallback": {
            "title": "缺失处理",
            "question": "如果信息不足，AI 应该优先如何处理？",
            "options": ["先列缺失信息并补问", "基于假设先产出草案", "给出多方案并标注风险"],
        },
    },
    "sales": {
        "goal": {
            "title": "销售目标",
            "question": "你这次最想解决的销售问题是什么？",
            "options": ["做一个销售复盘助手", "做一个跟进话术助手", "做一个商机推进助手"],
        },
        "audience": {
            "title": "客户场景",
            "question": "目标客户与当前商机阶段分别是什么？",
            "options": ["按行业/客群细分策略", "按漏斗阶段给动作", "按客户异议给回应"],
        },
        "constraints": {
            "title": "优化重点",
            "question": "你希望输出重点偏向策略、话术，还是执行动作？",
            "options": ["重点优化转化率", "重点提升客单价", "重点缩短成交周期"],
        },
        "output": {
            "title": "交付形式",
            "question": "结果需要按什么结构呈现给团队？",
            "options": ["按周计划 + 执行清单", "按客户分层输出", "按机会优先级排序"],
        },
        "fallback": {
            "title": "缺失处理",
            "question": "遇到客户信息不全时，AI 应先补问还是先给草案？",
            "options": ["先补问关键客户信息", "先给通用版再细化", "给 A/B 两套策略"],
        },
    },
    "writing": {
        "goal": {
            "title": "写作目标",
            "question": "你希望这次写作最终达成什么效果？",
            "options": ["写短篇小说片段", "写品牌宣传文案", "写公众号长文"],
        },
        "audience": {
            "title": "读者场景",
            "question": "目标读者是谁，阅读场景是什么？",
            "options": ["突出人物性格", "突出节奏推进", "突出情绪感染力"],
        },
        "constraints": {
            "title": "风格约束",
            "question": "你对文风、语气、长度有哪些要求？",
            "options": ["语气克制专业", "语气轻松有梗", "语气诗性细腻"],
        },
        "output": {
            "title": "输出形式",
            "question": "你希望输出按什么结构组织？",
            "options": ["三段式结构", "章节式结构", "先大纲后正文"],
        },
        "fallback": {
            "title": "缺失处理",
            "question": "如果素材不足，AI 应该先提问还是先给版本 0.1？",
            "options": ["先补素材问题", "先给初稿再迭代", "给多种文风版本"],
        },
    },
    "report": {
        "goal": {
            "title": "汇报目标",
            "question": "这份报告最核心要回答哪个问题？",
            "options": ["做周报自动生成器", "做项目复盘助手", "做管理汇报助手"],
        },
        "audience": {
            "title": "汇报对象",
            "question": "汇报对象是谁，他们最关心哪些指标？",
            "options": ["先讲成果再讲风险", "先讲问题再讲对策", "按目标-结果-计划展开"],
        },
        "constraints": {
            "title": "重点约束",
            "question": "你希望重点突出成果、风险，还是行动计划？",
            "options": ["强调业务影响", "强调数据指标", "强调可执行动作"],
        },
        "output": {
            "title": "交付形式",
            "question": "报告最终要用什么格式交付？",
            "options": ["一页摘要 + 附录", "标准周报模板", "表格 + 要点混排"],
        },
        "fallback": {
            "title": "缺失处理",
            "question": "遇到数据缺失时，希望 AI 如何标注和处理？",
            "options": ["缺失数据显式标注", "先产出草案后补数", "给保守/激进两版"],
        },
    },
    "ppt": {
        "goal": {
            "title": "演示目标",
            "question": "这份 PPT 的核心目标和主结论是什么？",
            "options": ["做路演型演示稿", "做内部汇报演示稿", "做产品方案演示稿"],
        },
        "audience": {
            "title": "听众场景",
            "question": "听众是谁，他们的决策关注点是什么？",
            "options": ["先目录后逐页展开", "先关键页再补细节", "先讲故事再给证据"],
        },
        "constraints": {
            "title": "表达约束",
            "question": "你更看重叙事说服、数据证明，还是视觉表达？",
            "options": ["每页只保留一个主信息", "每页配讲稿备注", "每页附可视化建议"],
        },
        "output": {
            "title": "输出粒度",
            "question": "你希望每页输出到什么粒度？",
            "options": ["输出 10 页精简版", "输出 20 页完整版", "输出可裁剪模块化版本"],
        },
        "fallback": {
            "title": "缺失处理",
            "question": "资料不完整时，AI 先补问还是先给目录草案？",
            "options": ["先补问受众与时长", "先给目录草案", "给两种叙事路线"],
        },
    },
}

REFINEMENT_BANK: Dict[str, List[Dict[str, Any]]] = {
    "general": [
        {
            "slot_id": "constraints_refine",
            "title": "补充边界",
            "question": "还有哪些边界条件、禁区或必须避免的内容需要提前说明？",
            "options": ["补充禁用表达", "补充风险边界", "补充验收标准"],
        },
        {
            "slot_id": "input_refine",
            "title": "补充输入",
            "question": "为了让结果更贴近你的实际任务，还需要补充哪些背景材料？",
            "options": ["补充示例素材", "补充上下文数据", "补充参考风格"],
        },
        {
            "slot_id": "output_refine",
            "title": "补充细节",
            "question": "你希望最终结果在哪些细节上更像“可以直接拿去用”？",
            "options": ["增加步骤清单", "增加示例输出", "增加执行提醒"],
        },
    ],
    "sales": [
        {
            "slot_id": "crm_refine",
            "title": "补充商机",
            "question": "还需要补充哪些客户背景，才能让销售建议更贴近真实商机？",
            "options": ["补充客户画像", "补充成交阻碍", "补充阶段目标"],
        },
        {
            "slot_id": "action_refine",
            "title": "补充动作",
            "question": "你更希望结果里体现哪些可执行动作？",
            "options": ["补充跟进节奏", "补充话术细节", "补充优先级排序"],
        },
    ],
    "writing": [
        {
            "slot_id": "style_refine",
            "title": "补充风格",
            "question": "还需要补充哪些风格线索，才能让写作结果更贴近你的预期？",
            "options": ["补充参考作者", "补充情绪基调", "补充篇幅节奏"],
        },
        {
            "slot_id": "material_refine",
            "title": "补充素材",
            "question": "你希望 AI 更依赖现有素材，还是允许在合理范围内补充创造？",
            "options": ["严格基于素材", "有限度延展", "先给多个版本"],
        },
    ],
    "report": [
        {
            "slot_id": "metric_refine",
            "title": "补充指标",
            "question": "还有哪些指标、风险或结论需要在报告中单独强调？",
            "options": ["补充关键指标", "补充风险说明", "补充行动建议"],
        },
        {
            "slot_id": "decision_refine",
            "title": "补充决策",
            "question": "你希望这份报告最终支持怎样的决策或后续动作？",
            "options": ["支持项目决策", "支持资源协调", "支持复盘复用"],
        },
    ],
    "ppt": [
        {
            "slot_id": "story_refine",
            "title": "补充叙事",
            "question": "你希望演示稿在哪一部分更突出说服力？",
            "options": ["加强开场结论", "加强中段论证", "加强结尾行动建议"],
        },
        {
            "slot_id": "visual_refine",
            "title": "补充表达",
            "question": "还有哪些展示层要求，需要在每页内容里显式体现？",
            "options": ["补充图表建议", "补充讲稿备注", "补充页间过渡"],
        },
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


def _slot_question_map(topic: str) -> Dict[str, str]:
    bank = QUESTION_BANK.get(topic, QUESTION_BANK["general"])
    return {item["question"]: slot_id for slot_id, item in bank.items()}


def _question_to_slot(question: str, topic: str, index: int) -> str:
    normalized = str(question or "").strip()
    mapped = _slot_question_map(topic).get(normalized)
    if mapped:
        return mapped
    if index < len(SLOT_ORDER):
        return SLOT_ORDER[index]
    refinements = REFINEMENT_BANK.get(topic, REFINEMENT_BANK["general"])
    if refinements:
        return refinements[(index - len(SLOT_ORDER)) % len(refinements)]["slot_id"]
    return SLOT_ORDER[index % len(SLOT_ORDER)]


def _asked_slots(qa_pairs: List[Dict[str, str]], topic: str) -> List[str]:
    asked: List[str] = []
    for index, pair in enumerate(qa_pairs):
        slot_id = _question_to_slot(pair.get("question", ""), topic, index)
        if slot_id not in asked:
            asked.append(slot_id)
    return asked


def estimate_information_coverage(
    qa_pairs: List[Dict[str, str]],
    initial_idea: str = "",
    scenario: str = "general",
) -> Dict[str, Any]:
    topic = _detect_topic(initial_idea, scenario)
    asked_slots = _asked_slots(qa_pairs, topic)
    missing_slots = [slot_id for slot_id in SLOT_ORDER if slot_id not in asked_slots]
    covered_essential = [slot_id for slot_id in asked_slots if slot_id in ESSENTIAL_SLOTS]
    ready = len(qa_pairs) >= 3 and len(covered_essential) >= 4

    return {
        "topic": topic,
        "asked_slots": asked_slots,
        "missing_slots": missing_slots,
        "covered_essential_slots": covered_essential,
        "ready_to_generate": ready,
    }


def _build_options(labels: List[str]) -> List[Dict[str, str]]:
    return [{"key": f"opt_{idx + 1}", "label": labels[idx]} for idx in range(min(3, len(labels)))]


def next_assistant_turn(
    turn: int,
    initial_idea: str = "",
    scenario: str = "general",
    qa_pairs: List[Dict[str, str]] | None = None,
) -> Dict[str, Any]:
    safe_turn = max(0, int(turn))
    pairs = qa_pairs or []
    coverage = estimate_information_coverage(pairs, initial_idea=initial_idea, scenario=scenario)
    topic = coverage["topic"]
    bank = QUESTION_BANK.get(topic, QUESTION_BANK["general"])

    missing_slots = coverage["missing_slots"]
    if missing_slots:
        slot_id = missing_slots[0]
        entry = bank[slot_id]
        stage = "coverage"
    else:
        refinements = REFINEMENT_BANK.get(topic, REFINEMENT_BANK["general"])
        refine_index = max(0, safe_turn - len(SLOT_ORDER)) % len(refinements)
        entry = refinements[refine_index]
        slot_id = entry["slot_id"]
        stage = "refine"

    return {
        "slot_id": slot_id,
        "slot_title": entry["title"],
        "question": entry["question"],
        "options": _build_options(entry["options"]),
        "allow_custom": True,
        "custom_label": "自定义输入",
        "stage": stage,
    }


def should_generate(
    user_turn_count: int,
    max_turns: int = 5,
    force_generate: bool = False,
    qa_pairs: List[Dict[str, str]] | None = None,
    initial_idea: str = "",
    scenario: str = "general",
) -> bool:
    if force_generate:
        return True
    safe_max_turns = max(1, min(int(max_turns), 10))
    if qa_pairs:
        coverage = estimate_information_coverage(qa_pairs, initial_idea=initial_idea, scenario=scenario)
        if coverage["ready_to_generate"]:
            return True
    return user_turn_count >= safe_max_turns
