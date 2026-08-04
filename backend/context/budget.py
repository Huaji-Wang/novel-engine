"""上下文预算器：CJK 感知的 token 估算 + 按层级优先裁剪写章上下文。

自适应策略（按全书规划章数）：
- full    （≤50 章） ：预算宽松，前章节选保留更多；
- sliding （51–150 章）：中等预算，主要依赖摘要 + 前章结尾；
- layered （>150 章） ：紧预算，几乎完全依赖分层摘要/台账。

裁剪次序遵循分层优先级：L3 外部参考最先被裁，其次 L2 写法约束、
L1 规划，L0 本书事实（摘要/角色状态）最后裁且保留高地板值——
保证「事实一致性 > 规划 > 风格 > 参考」。
"""

from __future__ import annotations

import re
from typing import Any

from backend.config import app_config

# 中日韩统一表意 + 常用中文标点/全角区
_CJK = re.compile(
    r"[\u3000-\u303f\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef]")

_TRUNCATE_HEAD_MARK = "\n……（超出上下文预算，后文已截断）"
_TRUNCATE_TAIL_MARK = "……（超出上下文预算，前文已截断）\n"

# 每策略的输入预算（估算 token）与前章节选长度（字符）
STRATEGY_PROFILES: dict[str, dict[str, int]] = {
    "full": {"budget_tokens": 30000, "prev_excerpt_chars": 1200},
    "sliding": {"budget_tokens": 26000, "prev_excerpt_chars": 800},
    "layered": {"budget_tokens": 22000, "prev_excerpt_chars": 600},
}

# 检索结果（写章图 retrieve_memory 节点在裁剪之后才注入）+ 提示词骨架的预留量
RESERVE_TOKENS = 2500

# 裁剪次序：(字段, 地板 token, 保留方式)
# keep="head" 保留开头 / "tail" 保留结尾 / "lines" 按整行从头保留
TRIM_ORDER: list[tuple[str, int, str]] = [
    # L3 外部参考
    ("retrieved_context", 0, "lines"),
    ("recent_cast_context", 100, "lines"),
    # L2 写法约束
    ("style_rules_context", 120, "head"),
    ("voice_context", 150, "lines"),
    ("compiled_style", 300, "head"),
    # L1 规划（本章细纲不裁）
    ("next_chapter_outline", 150, "head"),
    ("plot_architecture", 400, "head"),
    ("compass_context", 200, "head"),
    ("foreshadowing_ledger", 250, "lines"),
    # L0 事实（最后裁、地板高；摘要保留最近部分）
    ("lore_context", 250, "lines"),
    ("world_building", 400, "head"),
    ("previous_chapter_excerpt", 300, "tail"),
    ("global_summary", 800, "tail"),
    ("character_state", 600, "head"),
]

# 不参与裁剪但计入总量的字段
_COUNTED_FIELDS = [
    "chapter_outline", "user_guidance", "core_seed", "arc_hook_note",
    "chapter_title", "style_guide",
]


def estimate_tokens(text: str | None) -> int:
    """粗估 token：CJK 约 1 字 ≈ 1.5 token；其余按 4 字符 ≈ 1 token。"""
    if not text:
        return 0
    cjk = len(_CJK.findall(text))
    other = len(text) - cjk
    return int(cjk * 1.5 + other / 4) + 1


def clip_to_tokens(text: str, max_tokens: int, keep: str = "head") -> str:
    """把文本裁到约 max_tokens 以内；keep 决定保留哪一端。"""
    if not text or max_tokens <= 0:
        return "" if max_tokens <= 0 else (text or "")
    if estimate_tokens(text) <= max_tokens:
        return text

    if keep == "lines":
        out: list[str] = []
        used = 0
        for line in text.splitlines():
            cost = estimate_tokens(line)
            if used + cost > max_tokens:
                break
            out.append(line)
            used += cost
        clipped = "\n".join(out)
        return (clipped + _TRUNCATE_HEAD_MARK) if clipped else ""

    # head/tail：按估算比例定位切点，再收敛校正
    n = len(text)
    for _ in range(4):
        est = estimate_tokens(text[:n] if keep == "head" else text[-n:])
        if est <= max_tokens:
            break
        n = max(1, int(n * max_tokens / est * 0.95))
    if keep == "head":
        return text[:n] + _TRUNCATE_HEAD_MARK
    return _TRUNCATE_TAIL_MARK + text[-n:]


def context_strategy(num_chapters: int) -> str:
    if num_chapters <= 50:
        return "full"
    if num_chapters <= 150:
        return "sliding"
    return "layered"


def strategy_profile(num_chapters: int) -> dict[str, Any]:
    name = context_strategy(num_chapters)
    profile = dict(STRATEGY_PROFILES[name])
    override = app_config().get("context_budget_tokens")
    if override:
        profile["budget_tokens"] = int(override)
    profile["strategy"] = name
    return profile


def apply_writer_budget(state: dict, *, num_chapters: int) -> dict:
    """就地裁剪写章 state 的上下文字段，返回报告。

    报告：{strategy, budget, before, after, trimmed: {字段: [裁前, 裁后]}}
    """
    profile = strategy_profile(num_chapters)
    budget = int(profile["budget_tokens"]) - RESERVE_TOKENS

    def _tok(field: str) -> int:
        return estimate_tokens(state.get(field) or "")

    total = sum(_tok(f) for f, _, _ in TRIM_ORDER) + \
        sum(_tok(f) for f in _COUNTED_FIELDS)
    before = total
    trimmed: dict[str, list[int]] = {}

    for field, floor, keep in TRIM_ORDER:
        if total <= budget:
            break
        current = _tok(field)
        if current <= floor:
            continue
        target = max(floor, current - (total - budget))
        new_text = clip_to_tokens(state.get(field) or "", target, keep=keep)
        new_tokens = estimate_tokens(new_text)
        if new_tokens < current:
            state[field] = new_text
            trimmed[field] = [current, new_tokens]
            total -= current - new_tokens

    # style_guide 与 compiled_style 是同一份内容的两个键，保持同步
    if "compiled_style" in trimmed:
        old_guide = estimate_tokens(state.get("style_guide"))
        state["style_guide"] = state["compiled_style"]
        total += estimate_tokens(state["style_guide"]) - old_guide

    return {
        "strategy": profile["strategy"],
        "budget": int(profile["budget_tokens"]),
        "before": before,
        "after": total,
        "trimmed": trimmed,
    }


def budget_log_message(report: dict) -> str:
    trimmed = report.get("trimmed") or {}
    base = (f"上下文策略 {report.get('strategy')}：约 {report.get('before')} tokens"
            f"（预算 {report.get('budget')}）")
    if not trimmed:
        return base + "，未裁剪"
    parts = [f"{k} {v[0]}→{v[1]}" for k, v in trimmed.items()]
    return (f"{base}，裁剪后约 {report.get('after')} tokens：" + "；".join(parts))
