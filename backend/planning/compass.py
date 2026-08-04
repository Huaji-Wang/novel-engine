"""StoryCompass 格式化与读写。"""

from __future__ import annotations

from backend.db.models import CharacterSnapshot
from backend.db.session import db_session


def format_compass_context(compass: dict | None) -> str:
    if not compass:
        return "（尚未建立终局指南针）"
    lines = []
    if compass.get("ending_direction"):
        lines.append(f"终局方向：{compass['ending_direction']}")
    threads = compass.get("open_threads") or []
    if threads:
        lines.append("活跃长线：" + "；".join(str(t) for t in threads[:8]))
    if compass.get("estimated_scale"):
        lines.append(f"规模预期：{compass['estimated_scale']}")
    return "\n".join(lines) if lines else "（尚未建立终局指南针）"


def format_style_rules_context(rules: dict | None) -> str:
    if not rules:
        return "（无）"
    parts: list[str] = []
    prose = rules.get("prose") or []
    if prose:
        parts.append("叙述风格规则：\n" + "\n".join(f"- {r}" for r in prose[:5]))
    dialogue = rules.get("dialogue") or []
    if dialogue:
        lines = []
        for v in dialogue[:8]:
            if not isinstance(v, dict):
                continue
            name = v.get("name") or "（未命名）"
            drules = v.get("rules") or []
            if drules:
                lines.append(f"- {name}：" + "；".join(str(r) for r in drules[:3]))
        if lines:
            parts.append("对话风格规则：\n" + "\n".join(lines))
    taboos = rules.get("taboos") or []
    if taboos:
        parts.append("审美禁忌：\n" + "\n".join(f"- {t}" for t in taboos[:8]))
    return "\n\n".join(parts) if parts else "（无）"


def load_latest_character_snapshots(novel_id: int) -> list[dict]:
    """取每个角色最新一条快照（按 volume_no、arc_no 最大）。"""
    with db_session() as session:
        rows = session.query(CharacterSnapshot).filter_by(
            novel_id=novel_id,
        ).order_by(
            CharacterSnapshot.volume_no,
            CharacterSnapshot.arc_no,
        ).all()
    latest: dict[str, dict] = {}
    for row in rows:
        latest[row.name] = {
            "volume_no": row.volume_no,
            "arc_no": row.arc_no,
            "name": row.name,
            "status": row.status,
            "power": row.power,
            "motivation": row.motivation,
            "relations": row.relations,
        }
    return list(latest.values())


def format_character_snapshots_context(snapshots: list[dict] | None) -> str:
    if not snapshots:
        return "（无）"
    lines = []
    for s in snapshots[:12]:
        parts = [f"### {s.get('name', '（未命名）')}"]
        if s.get("status"):
            parts.append(f"状态：{s['status']}")
        if s.get("power"):
            parts.append(f"能力：{s['power']}")
        if s.get("motivation"):
            parts.append(f"动机：{s['motivation']}")
        if s.get("relations"):
            parts.append(f"关系：{s['relations']}")
        lines.append("\n".join(parts))
    return "\n\n".join(lines) if lines else "（无）"
