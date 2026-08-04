"""角色对话区分度：voice_rules + 历史对白样本，注入 Writer。"""

from __future__ import annotations

import re

from backend.characters.dialogue import extract_dialogue, load_finalized_chapter_texts
from backend.db.session import db_session

_CORE_CHAR_RE = re.compile(r"核心人物[：:]\s*(.+)", re.MULTILINE)


def guess_chapter_characters(outline_text: str, characters: list[dict]) -> list[str]:
    """从细纲「核心人物」行 + 名字命中推断本章相关角色。"""
    names: list[str] = []
    m = _CORE_CHAR_RE.search(outline_text or "")
    if m:
        chunk = m.group(1)
        for c in characters:
            if c["name"] in chunk:
                names.append(c["name"])
    if names:
        return names
    text = outline_text or ""
    active = [c for c in characters if c.get("status") == "active"]
    active.sort(key=lambda c: c.get("last_chapter") or 0, reverse=True)
    for c in active:
        if c["name"] in text and c["name"] not in names:
            names.append(c["name"])
    if names:
        return names[:8]
    return [c["name"] for c in active[:5]]


def build_voice_context(
    novel_id: int,
    *,
    outline_text: str,
    characters: list[dict],
    style_dialogue: list[dict] | None = None,
    max_characters: int = 5,
    max_samples: int = 3,
) -> str:
    """组装 Writer 用的对话区分度块（规则 + 样本）。"""
    picked = guess_chapter_characters(outline_text, characters)[:max_characters]
    if not picked:
        return "（无）"

    with db_session() as session:
        all_texts = load_finalized_chapter_texts(session, novel_id)

    blocks: list[str] = []
    by_name = {c["name"]: c for c in characters}
    dialogue_by_name = {
        v.get("name"): v.get("rules") or []
        for v in (style_dialogue or [])
        if isinstance(v, dict) and v.get("name")
    }
    for name in picked:
        row = by_name.get(name)
        if not row:
            continue
        data = row.get("data") or {}
        rules = data.get("voice_rules") or dialogue_by_name.get(name) or []
        aliases = data.get("aliases") or []
        parts = [f"### {name}"]
        if rules:
            parts.append("对话规则：" + "；".join(str(r) for r in rules[:5]))
        samples = extract_dialogue(
            all_texts, name, aliases=aliases, max_samples=max_samples,
        )
        if samples:
            parts.append("历史对白样本（请保持口吻一致，勿照抄原句）：")
            parts.extend(f"- {s}" for s in samples)
        elif rules:
            parts.append("（尚无历史对白样本，请严格按对话规则写）")
        else:
            parts.append("（暂无对话规则与样本，请依据性格特质区分语气）")
        blocks.append("\n".join(parts))
    if not blocks:
        return "（无）"
    return "\n\n".join(blocks)
