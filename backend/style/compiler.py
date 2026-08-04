"""写法特征池编译：profile + style_guide + 弧末 style_rules → Writer prompt。"""

from __future__ import annotations

import json
import re
from typing import Any


def parse_style_learn_result(raw: str) -> dict[str, Any]:
    """解析 StyleLearner 输出（JSON 或 fallback bullet 文本）。"""
    text = (raw or "").strip()
    if not text:
        return {"features": [], "compiled_summary": ""}
    if text.startswith("{"):
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return {
                    "features": data.get("features") or [],
                    "compiled_summary": str(data.get("compiled_summary") or "").strip(),
                }
        except json.JSONDecodeError:
            pass
    lines = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("-")]
    features = []
    for i, ln in enumerate(lines):
        body = ln.lstrip("- ").strip()
        if not body:
            continue
        features.append({
            "id": f"feat_{i + 1}",
            "label": body[:40],
            "category": "general",
            "enabled": True,
            "prompt_snippet": body,
        })
    return {"features": features, "compiled_summary": text[:800]}


def compile_style_context(
    *,
    profile: dict[str, Any] | None,
    style_guide: str,
    style_rules: dict[str, Any] | None,
    writing_style: str = "",
) -> str:
    """合并写法约束；弧末 style_rules 优先级最高。"""
    parts: list[str] = []
    if writing_style and writing_style.strip() not in ("", "（不限）"):
        parts.append(f"【风格标签】{writing_style.strip()}")

    if profile:
        enabled = [
            f for f in (profile.get("features") or [])
            if f.get("enabled", True) and str(f.get("prompt_snippet", "")).strip()
        ]
        if enabled:
            parts.append("【写法特征池（已启用）】")
            for feat in enabled[:20]:
                parts.append(f"- {feat['prompt_snippet'].strip()}")
        summary = str(profile.get("compiled_summary") or "").strip()
        if summary and not enabled:
            parts.append(f"【写法摘要】\n{summary}")

    guide = (style_guide or "").strip()
    if guide and guide not in ("（无）", ""):
        if not profile or not (profile.get("features") or []):
            parts.append(f"【参考书风格指南】\n{guide}")
        elif len(guide) < 400:
            parts.append(f"【补充指南】\n{guide}")

    rules = style_rules or {}
    prose = [str(x).strip() for x in (rules.get("prose") or []) if str(x).strip()]
    taboos = [str(x).strip() for x in (rules.get("taboos") or []) if str(x).strip()]
    dialogue = rules.get("dialogue") or []
    if prose or taboos or dialogue:
        parts.append("【本书已沉淀写作规则（优先遵守）】")
        for p in prose[:5]:
            parts.append(f"- 叙述：{p}")
        for d in dialogue[:5]:
            if isinstance(d, dict):
                name = d.get("name") or d.get("character") or ""
                rule = d.get("rule") or d.get("voice") or ""
                if name and rule:
                    parts.append(f"- 对话·{name}：{rule}")
            elif isinstance(d, str) and d.strip():
                parts.append(f"- 对话：{d.strip()}")
        for t in taboos[:8]:
            parts.append(f"- 禁忌：{t}")

    return "\n".join(parts).strip() or "（无）"


def profile_from_learn_result(result: dict[str, Any], *, name: str = "StyleLearner") -> dict[str, Any]:
    features = result.get("features") or []
    normalized = []
    for i, feat in enumerate(features):
        if not isinstance(feat, dict):
            continue
        snippet = str(feat.get("prompt_snippet") or feat.get("label") or "").strip()
        if not snippet:
            continue
        fid = str(feat.get("id") or f"feat_{i + 1}")
        normalized.append({
            "id": re.sub(r"[^\w\-]", "_", fid)[:40],
            "label": str(feat.get("label") or snippet[:40])[:80],
            "category": str(feat.get("category") or "general")[:30],
            "enabled": bool(feat.get("enabled", True)),
            "prompt_snippet": snippet[:300],
        })
    summary = str(result.get("compiled_summary") or "").strip()
    if not summary and normalized:
        summary = "\n".join(f"- {f['prompt_snippet']}" for f in normalized[:12])[:800]
    return {
        "name": name,
        "features": normalized,
        "compiled_summary": summary,
    }
