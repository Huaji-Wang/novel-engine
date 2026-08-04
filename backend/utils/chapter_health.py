"""规则化章节健康检查（零 LLM）：模板词、引号、Humanizer 模式、字数偏差等。"""

from __future__ import annotations

import re
from typing import Any

from backend.prompts.anti_ai import FATIGUE_WORDS, FORBIDDEN_PHRASES

THRESHOLD_CRITICAL = {
    "chinese_quotes_min": 6,
    "template_word_max": 8,
    "template_single_max": 3,
    "ai_psychology_max": 8,
    "cringe_monologue_max": 2,
}

THRESHOLD_WARNING = {
    "word_count_deviation": 20.0,
    "humanizer_a_max": 3,
    "humanizer_b_max": 5,
    "cringe_monologue_max": 1,
}

TEMPLATE_WORDS = [
    "笑了笑", "点了点头", "脸红了红",
    "眼睛一亮", "眼睛都直了", "嘴角微微上扬",
    "心里头一暖", "心里头那个高兴", "心里头有些异样",
    "心里头七上八下", "心里头咯噔", "心里咯噔",
    "心里头一紧", "心里头一沉", "心里头一软",
    "激动得心跳加速", "心跳加快", "脑子嗡的一声",
    "攥紧了拳头", "攥紧了车把", "深吸了口气", "深吸一口气",
    "眉头皱了皱", "眉头一挑", "冷哼了一声", "冷哼一声",
    "没搭理", "心里盘算", "心里头有了数",
    "消息传得比风还快",
]

CRINGE_MONOLOGUE = [
    "等着吧", "十倍奉还", "付出代价", "不会认输",
    "迟早让你", "迟早要", "走着瞧", "给我等着",
    "总有一天", "总会让",
]

AI_PSYCHOLOGY_CLICHE = [
    "心里头咯噔", "心里咯噔", "心里头一紧", "心里一紧",
    "心里头一沉", "心里一沉", "心里头一软", "心里一软",
    "心里头七上八下", "心里七上八下",
    "脑子嗡的一声", "脑袋嗡的一声", "脑子一片空白",
    "眼前发黑", "眼前一黑",
    "攥紧了拳头", "攥紧拳头", "握紧了拳头",
    "深吸了口气", "深吸一口气",
    "眉头皱了皱", "眉头微皱", "眉头一挑",
    "冷哼了一声", "冷哼一声",
    "心跳加快", "心跳加速",
]

HUMANIZER_A = {
    "否定式排比": ["不是", "也不是", "更不是", "既不", "也不"],
    "三段式堆砌": ["首先", "其次", "最后", "第一", "第二", "第三"],
    "谄媚语气": ["当然", "毫无疑问", "无可否认"],
    "强行展望结尾": ["挑战与机遇并存", "光明的前途", "未来一定", "必将"],
}
HUMANIZER_B = {
    "填充短语": ["总而言之", "值得注意的是", "实际上", "事实上", "从某种意义上说"],
    "AI高频词": ["此外", "深入探讨", "至关重要", "不可或缺"],
    "过度限定": ["可能", "也许", "大概", "应该", "似乎", "看上去"],
}


def _clean_text(raw: str) -> str:
    text = re.sub(r"^【第\d+章[^】]*】\n", "", raw)
    return re.sub(r"（本章完）\s*$", "", text)


def _count_chinese_quotes(text: str) -> int:
    curly = text.count("\u201c")
    straight_pairs = text.count('"') // 2
    return curly + straight_pairs


def _count_words(text: str) -> dict[str, int]:
    return {w: text.count(w) for w in TEMPLATE_WORDS if text.count(w) > 0}


def _pattern_counts(text: str, patterns: dict[str, list[str]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for name, keys in patterns.items():
        c = sum(text.count(k) for k in keys)
        if c:
            out[name] = c
    return out


def check_chapter_health(
    text: str,
    *,
    chapter_no: int = 0,
    target_words: int = 3000,
) -> dict[str, Any]:
    """返回 {status: ok|warning|critical, score, items: [...], summary}."""
    body = _clean_text(text.strip())
    char_count = len(body)
    items: list[dict[str, Any]] = []
    critical = False
    warning = False

    quotes = _count_chinese_quotes(body)
    dialogue_lines = len([ln for ln in body.splitlines() if "\u201c" in ln or '"' in ln])
    if dialogue_lines >= 6 and quotes < THRESHOLD_CRITICAL["chinese_quotes_min"]:
        critical = True
        items.append({
            "level": "critical",
            "code": "quotes_low",
            "message": f"对话引号对仅 {quotes} 对（对话行≥6 时建议≥{THRESHOLD_CRITICAL['chinese_quotes_min']}）",
        })

    template_map = _count_words(body)
    template_total = sum(template_map.values())
    if template_total > THRESHOLD_CRITICAL["template_word_max"]:
        critical = True
        items.append({
            "level": "critical",
            "code": "template_words",
            "message": f"AI 模板词共 {template_total} 次（上限 {THRESHOLD_CRITICAL['template_word_max']}）",
            "detail": template_map,
        })
    for word, cnt in template_map.items():
        if cnt > THRESHOLD_CRITICAL["template_single_max"]:
            critical = True
            items.append({
                "level": "critical",
                "code": "template_word_single",
                "message": f"「{word}」出现 {cnt} 次",
            })

    for phrase in FORBIDDEN_PHRASES:
        cnt = body.count(phrase)
        if cnt >= 1:
            critical = True
            items.append({
                "level": "critical",
                "code": "forbidden_phrase",
                "message": f"禁止短语「{phrase}」出现 {cnt} 次",
            })

    for word, limit in FATIGUE_WORDS.items():
        cnt = body.count(word)
        if cnt > limit:
            warning = True
            items.append({
                "level": "warning",
                "code": "fatigue_word",
                "message": f"疲劳词「{word}」{cnt} 次（上限 {limit}）",
            })

    psych_total = sum(body.count(w) for w in AI_PSYCHOLOGY_CLICHE)
    if psych_total > THRESHOLD_CRITICAL["ai_psychology_max"]:
        critical = True
        items.append({
            "level": "critical",
            "code": "ai_psychology",
            "message": f"套路心理描写 {psych_total} 次（上限 {THRESHOLD_CRITICAL['ai_psychology_max']}）",
        })

    cringe = sum(body.count(w) for w in CRINGE_MONOLOGUE)
    if cringe > THRESHOLD_CRITICAL["cringe_monologue_max"]:
        critical = True
        items.append({
            "level": "critical",
            "code": "cringe_monologue",
            "message": f"中二独白词 {cringe} 次",
        })
    elif cringe > THRESHOLD_WARNING["cringe_monologue_max"]:
        warning = True
        items.append({
            "level": "warning",
            "code": "cringe_monologue",
            "message": f"中二独白词 {cringe} 次，建议删减",
        })

    if target_words > 0:
        dev = abs(char_count - target_words) / target_words * 100
        if dev > THRESHOLD_WARNING["word_count_deviation"]:
            warning = True
            items.append({
                "level": "warning",
                "code": "word_count",
                "message": f"字数 {char_count}，目标 {target_words}，偏差 {dev:.0f}%",
            })

    ha = _pattern_counts(body, HUMANIZER_A)
    hb = _pattern_counts(body, HUMANIZER_B)
    a_total = sum(ha.values())
    b_total = sum(hb.values())
    if a_total > THRESHOLD_WARNING["humanizer_a_max"]:
        warning = True
        items.append({
            "level": "warning",
            "code": "humanizer_a",
            "message": f"Humanizer A 类模式 {a_total} 次",
            "detail": ha,
        })
    if b_total > THRESHOLD_WARNING["humanizer_b_max"]:
        warning = True
        items.append({
            "level": "warning",
            "code": "humanizer_b",
            "message": f"Humanizer B 类模式 {b_total} 次",
            "detail": hb,
        })

    # markdown / 表情符号
    if "**" in body or re.search(r"[🎯🔥⭐✅⚠️💡✨]", body):
        warning = True
        items.append({
            "level": "warning",
            "code": "markdown_emoji",
            "message": "正文含 markdown 加粗或表情符号",
        })

    status = "critical" if critical else ("warning" if warning else "ok")
    summary = {
        "ok": "健康检查通过",
        "warning": f"{len([i for i in items if i['level'] == 'warning'])} 项警告",
        "critical": f"{len([i for i in items if i['level'] == 'critical'])} 项致命问题，建议修订后再定稿",
    }[status]

    return {
        "status": status,
        "summary": summary,
        "chapter_no": chapter_no,
        "char_count": char_count,
        "quotes": quotes,
        "template_total": template_total,
        "items": items,
        "critical": [i for i in items if i["level"] == "critical"],
        "warning": [i for i in items if i["level"] == "warning"],
        "metrics": {
            "chinese_quotes": quotes,
            "quote_pairs": quotes,
            "template_words_total": template_total,
            "char_count": char_count,
        },
    }
