"""WorldKeeper Agent：阵营(Faction) + 世界书(LoreKeeper)。"""

from __future__ import annotations

import json

from backend.llm.client import LLMClient
from backend.prompts import definitions as P

RELATION_LABELS = {
    "hostile": "敌对", "allied": "同盟", "cold_war": "冷战",
    "dependent": "依附", "subordinate": "从属", "trade_partner": "贸易伙伴",
    "secret_cooperation": "秘密合作", "historical_enemy": "历史宿敌",
}

VALID_CATEGORIES = {"地点", "物品", "组织", "规则", "历史", "种族", "能力", "其他"}
_PROPOSAL_FIELDS = ("importance", "future_relevance", "evidence", "reason")


def _clean_lore_entry(raw: dict) -> dict | None:
    name = str(raw.get("name", "")).strip()
    if not name:
        return None
    category = str(raw.get("category", "其他")).strip()
    keywords = raw.get("keywords")
    cleaned = {
        "name": name[:200],
        "category": category if category in VALID_CATEGORIES else "其他",
        "keywords": [str(k).strip() for k in keywords if str(k).strip()]
        if isinstance(keywords, list) else [],
        "content": str(raw.get("content", "")).strip(),
    }
    cleaned.update({
        key: raw.get(key) for key in _PROPOSAL_FIELDS if key in raw
    })
    return cleaned


class WorldKeeperAgent:
    def __init__(self):
        self._faction_llm = LLMClient("faction")
        self._lore_llm = LLMClient("lore")

    def seed_factions(self, *, world_building: str, core_seed: str,
                      existing_names: list[str]) -> dict:
        result = self._faction_llm.invoke_json(P.FACTION_SEED_OPENING_PROMPT.format(
            world_building=world_building or "（无）",
            core_seed=core_seed or "（无）",
            existing_names="、".join(existing_names) or "（无）",
        ))
        if not isinstance(result, dict):
            return {"core_factions": [], "faction_relations": []}
        result.setdefault("core_factions", [])
        result.setdefault("faction_relations", [])
        return result

    def extract_factions_from_chapter(self, *, chapter_no: int, chapter_text: str,
                                      world_building: str,
                                      factions: list[dict],
                                      relations: list[dict]) -> dict:
        f_json = [{"name": f["name"], "status": f.get("status", "active")}
                  for f in factions]
        r_json = [{"source": r["source"], "target": r["target"],
                   "relation_type": r.get("relation_type", "")}
                  for r in relations]
        result = self._faction_llm.invoke_json(P.FACTION_EXTRACT_CHAPTER_PROMPT.format(
            chapter_no=chapter_no,
            chapter_text=chapter_text,
            world_building=(world_building or "（无）")[:1500],
            existing_factions_json=json.dumps(f_json, ensure_ascii=False),
            existing_relations_json=json.dumps(r_json, ensure_ascii=False),
        ))
        if not isinstance(result, dict):
            return {"new_factions": [], "updated_factions": [],
                    "new_relations": [], "appeared": [], "inactive": []}
        for key in ("new_factions", "updated_factions", "new_relations",
                    "appeared", "inactive"):
            val = result.get(key)
            result[key] = val if isinstance(val, list) else []
        return result

    def extract_initial_lore(self, *, world_building: str, full_story: str,
                             plot_architecture: str) -> list[dict]:
        result = self._lore_llm.invoke_json(P.LORE_EXTRACT_INITIAL_PROMPT.format(
            world_building=world_building or "（无）",
            full_story=full_story or "（无）",
            plot_architecture=plot_architecture or "（无）",
        ))
        if not isinstance(result, list):
            return []
        return [e for e in (
            _clean_lore_entry(r) for r in result if isinstance(r, dict)) if e]

    def extract_lore_from_chapter(self, *, chapter_no: int, chapter_text: str,
                                  existing_names: list[str]) -> dict:
        result = self._lore_llm.invoke_json(P.LORE_UPDATE_PROMPT.format(
            chapter_no=chapter_no,
            chapter_text=chapter_text,
            existing_names="、".join(existing_names) or "（空）",
        ))
        if not isinstance(result, dict):
            return {"new": [], "updated": []}
        new = [e for e in (
            _clean_lore_entry(r) for r in result.get("new", [])
            if isinstance(r, dict)) if e]
        updated = [
            {"name": str(r.get("name", "")).strip(),
             "content": str(r.get("content", "")).strip()}
            for r in result.get("updated", [])
            if isinstance(r, dict) and str(r.get("name", "")).strip()
        ]
        return {"new": new, "updated": updated}


def format_factions_brief(factions: list[dict], relations: list[dict]) -> str:
    active = [f for f in factions if f.get("status", "active") == "active"]
    if not active:
        return ""
    active_names = {f["name"] for f in active}
    lines = ["各阵营（当前活跃）："]
    for f in active:
        d = f.get("data", {})
        lines.append(
            f"- {f['name']}（{d.get('faction_type', '')}）：{d.get('public_stance', '')}；"
            f"真实目标：{d.get('core_goal', '')}"
        )
    if relations:
        lines.append("阵营关系：")
        for r in relations:
            if r["source"] not in active_names and r["target"] not in active_names:
                continue
            d = r.get("data", {})
            label = RELATION_LABELS.get(r.get("relation_type", ""), r.get("relation_type", ""))
            lines.append(
                f"- {r['source']} ↔ {r['target']}（{label}，强度{d.get('intensity', '?')}）："
                f"{d.get('core_conflict', '')}"
            )
    return "\n".join(lines)


def match_lore(entries: list[dict], text: str, limit: int = 8) -> list[dict]:
    if not text:
        return []
    hits = []
    for e in entries:
        if not e.get("enabled", 1):
            continue
        terms = [e["name"]] + list(e.get("keywords") or [])
        if any(t and t in text for t in terms):
            hits.append(e)
        if len(hits) >= limit:
            break
    return hits


def format_lore(entries: list[dict]) -> str:
    return "\n".join(
        f"- [{e['category']}] {e['name']}：{e['content']}" for e in entries)
