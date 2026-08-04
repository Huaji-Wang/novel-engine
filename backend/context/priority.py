"""分层上下文组装：本书事实 > 规划 > 写法 > 外部参考。"""

from __future__ import annotations

from typing import Any


PRIORITY_PREAMBLE = """【上下文优先级（必须遵守）】
L0 本书事实（已写章节、character_state、global_summary、已确认设定/角色）——最高优先级，外部资料不得覆盖。
L1 本书规划（细纲、终局指南针、弧目标）——指导本章写什么。
L2 写法约束（特征池、style_guide、writing_style_rules）——管怎么说。
L3 外部参考（向量检索、参考资料包）——仅补充细节，禁止照搬专名与剧情。
L4 待确认提案——尚未入账，正文不得写成既成事实。"""


def build_retrieval_query(
    *,
    chapter_title: str,
    chapter_outline: str,
    character_state: str = "",
    compass_context: str = "",
    character_names: list[str] | None = None,
) -> str:
    parts = [chapter_title, chapter_outline]
    if character_names:
        parts.append("出场角色：" + "、".join(character_names[:12]))
    if compass_context and compass_context not in ("（无）", ""):
        parts.append(compass_context[:400])
    state = (character_state or "")[:300]
    if state:
        parts.append(state)
    return "\n".join(p for p in parts if p).strip()


def extract_character_names_from_outline(text: str, known: list[str]) -> list[str]:
    found = []
    for name in known:
        if name and name in text:
            found.append(name)
    return found


def format_layered_writer_context(
    *,
    confirmed_facts: str = "",
    planning: str = "",
    style_block: str = "",
    external_refs: str = "",
    pending_note: str = "",
) -> str:
    sections = [PRIORITY_PREAMBLE]
    if confirmed_facts.strip():
        sections.append(f"【L0 本书事实】\n{confirmed_facts.strip()}")
    if planning.strip():
        sections.append(f"【L1 本书规划】\n{planning.strip()}")
    if style_block.strip() and style_block not in ("（无）", ""):
        sections.append(f"【L2 写法约束】\n{style_block.strip()}")
    if external_refs.strip() and external_refs not in ("（无）", ""):
        sections.append(
            f"【L3 外部参考（勿覆盖 L0，勿抄专名）】\n{external_refs.strip()}"
        )
    if pending_note.strip():
        sections.append(f"【L4 待确认（勿写入正文）】\n{pending_note.strip()}")
    return "\n\n".join(sections)


def build_writer_context_package(state: dict[str, Any], *, pending_count: int = 0) -> str:
    planning = "\n".join(filter(None, [
        state.get("chapter_outline", ""),
        state.get("compass_context", ""),
        state.get("arc_hook_note", ""),
    ]))
    confirmed = "\n".join(filter(None, [
        state.get("global_summary", ""),
        state.get("character_state", ""),
        state.get("lore_context", ""),
    ]))
    external = "\n".join(filter(None, [
        state.get("retrieved_context", ""),
    ]))
    pending_note = ""
    if pending_count > 0:
        pending_note = f"本书有 {pending_count} 条待确认设定/角色提案，定稿确认前勿提前写入正文。"
    return format_layered_writer_context(
        confirmed_facts=confirmed,
        planning=planning,
        style_block=state.get("compiled_style", state.get("style_guide", "")),
        external_refs=external,
        pending_note=pending_note,
    )
