"""新角色人设深化：定稿后或下章登场前补全角色卡 / 动力学 / 状态表。"""

from __future__ import annotations

import json
from typing import Any

from backend.context.assembler import append_reference_block, load_reference
from backend.llm.client import LLMClient
from backend.prompts import definitions as P

_CARD_FIELDS = (
    "identity", "appearance", "traits", "motivation", "secret", "arc",
    "relationships", "story_function", "debut_plan", "voice_rules", "aliases",
)

_PROPOSAL_FIELDS = (
    "importance", "future_relevance", "evidence", "reason",
)


def _character_references() -> str:
    refs: dict[str, str] = {}
    for key, name in (
        ("character_building", "character-building"),
        ("character_template", "character-template"),
    ):
        text = load_reference(name)
        if text:
            refs[key] = text
    if not refs:
        return "（无）"
    parts = [f"### {k}\n{v.strip()}" for k, v in refs.items()]
    return "\n\n".join(parts)


def normalize_card_payload(raw: dict[str, Any]) -> dict[str, Any]:
    """从 LLM JSON 提取角色卡字段（去掉 meta 字段）。"""
    if not isinstance(raw, dict):
        return {}
    out: dict[str, Any] = {}
    for key in _CARD_FIELDS:
        val = raw.get(key)
        if val is not None and val != "" and val != []:
            out[key] = val
    return out


def merge_card_data(existing: dict[str, Any], enriched: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing or {})
    for key in _CARD_FIELDS:
        new_val = enriched.get(key)
        if new_val is None or new_val == "" or new_val == []:
            continue
        merged[key] = new_val
    merged["_deepened"] = True
    return merged


class CharacterAgent:
    def __init__(self):
        self.llm = LLMClient("character")

    def design_dynamics(
        self, core_seed: str, *,
        cocreate_context: str = "", guide_style: str = "",
        guide_pov: str = "", guide_taboos: str = "",
        user_guidance: str = "",
    ) -> str:
        from backend.planning.guidance import prompt_guide_fields
        gf = prompt_guide_fields(
            cocreate_context=cocreate_context or user_guidance,
            guide_style=guide_style, guide_pov=guide_pov, guide_taboos=guide_taboos,
        )
        return self.llm.invoke(P.CHARACTER_DYNAMICS_PROMPT.format(
            core_seed=core_seed, **gf,
        ))

    def extract_from_chapter(self, *, chapter_no: int, chapter_text: str,
                             character_dynamics: str,
                             existing: list[dict]) -> dict:
        """定稿时增量抽取：new / appeared / inactive。"""
        slim = [{"name": c["name"], "status": c.get("status", "active")}
                for c in existing]
        result = self.llm.invoke_json(P.CHARACTER_EXTRACT_CHAPTER_PROMPT.format(
            chapter_no=chapter_no,
            chapter_text=chapter_text,
            character_dynamics=character_dynamics or "（无）",
            existing_json=json.dumps(slim, ensure_ascii=False),
        ))
        if not isinstance(result, dict):
            return {"new": [], "appeared": [], "inactive": []}
        new = []
        for raw in result.get("new") or []:
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("name", "")).strip()
            if not name:
                continue
            data = {
                k: v for k, v in raw.items()
                if k != "name" and k not in _PROPOSAL_FIELDS
            }
            new.append({
                "name": name,
                "data": data,
                **{k: raw.get(k) for k in _PROPOSAL_FIELDS},
            })
        return {
            "new": new,
            "appeared": [str(n).strip() for n in (result.get("appeared") or [])
                         if str(n).strip()],
            "inactive": [str(n).strip() for n in (result.get("inactive") or [])
                         if str(n).strip()],
        }

    def create_state(self, character_dynamics: str) -> str:
        return self.llm.invoke(P.CREATE_CHARACTER_STATE_PROMPT.format(
            character_dynamics=character_dynamics,
        ))

    def update_state(self, chapter_text: str, old_state: str) -> str:
        return self.llm.invoke(P.UPDATE_CHARACTER_STATE_PROMPT.format(
            chapter_text=chapter_text, old_state=old_state,
        ))

    def deepen_character(
        self,
        *,
        name: str,
        mode: str,
        core_seed: str,
        character_dynamics: str,
        world_building: str,
        global_summary: str,
        character_state: str,
        current_card: dict[str, Any] | None = None,
        context_block: str = "",
        user_hint: str = "",
    ) -> dict[str, Any]:
        """深化单个角色：返回完整 JSON（含 dynamics_appendix / state_block）。"""
        if mode == "planned":
            mode_label = "规划模式（尚未正式登场，为 upcoming 章节准备）"
            mode_instruction = (
                "该角色可能尚未在正文出现。请结合细纲/功能预期设计完整人设，"
                "debut_plan 要写清楚建议的首场戏要点。"
            )
        else:
            mode_label = "已有初稿模式（角色已在正文登场，在定稿抽卡基础上完善）"
            mode_instruction = (
                "该角色已在正文中出现。请保留已展现的行为事实，补全驱动力、弧线与关系网。"
            )
        prompt = append_reference_block(
            P.DEEPEN_NEW_CHARACTER_PROMPT.format(
                mode_label=mode_label,
                mode_instruction=mode_instruction,
                core_seed=(core_seed or "（无）")[:2000],
                character_dynamics=(character_dynamics or "（无）")[:4000],
                world_building=(world_building or "（无）")[:2000],
                global_summary=(global_summary or "（无）")[:3000],
                character_state=(character_state or "（无）")[:4000],
                name=name,
                current_card_json=json.dumps(
                    current_card or {}, ensure_ascii=False, indent=2),
                context_block=context_block or "（无）",
                user_hint=user_hint or "无",
            ),
            _character_references(),
        )
        result = self.llm.invoke_json(prompt)
        if not isinstance(result, dict):
            return {}
        result.setdefault("name", name)
        return result

    def update_voice_rules(
        self,
        *,
        name: str,
        chapter_excerpts: str,
        existing_rules: list[str] | None = None,
    ) -> list[str]:
        """从正文归纳对话特征规则（对齐 ainovel CharacterVoice）。"""
        result = self.llm.invoke_json(P.UPDATE_VOICE_RULES_PROMPT.format(
            name=name,
            existing_rules="\n".join(f"- {r}" for r in (existing_rules or [])) or "（无）",
            chapter_excerpts=(chapter_excerpts or "（无）")[:16000],
        ))
        if not isinstance(result, dict):
            return existing_rules or []
        rules = result.get("voice_rules")
        if not isinstance(rules, list):
            return existing_rules or []
        cleaned = [str(r).strip() for r in rules if str(r).strip()]
        return cleaned[:3] if cleaned else (existing_rules or [])

    def extract_cast_from_chapter(
        self,
        *,
        chapter_no: int,
        chapter_text: str,
        core_names: list[str],
    ) -> dict:
        import json
        result = self.llm.invoke_json(P.CAST_EXTRACT_CHAPTER_PROMPT.format(
            chapter_no=chapter_no,
            chapter_text=(chapter_text or "")[:14000],
            core_names_json=json.dumps(core_names, ensure_ascii=False),
        ))
        if not isinstance(result, dict):
            return {"appeared": [], "cast_intros": []}
        return {
            "appeared": [str(x) for x in (result.get("appeared") or []) if str(x).strip()],
            "cast_intros": [
                x for x in (result.get("cast_intros") or [])
                if isinstance(x, dict) and str(x.get("name", "")).strip()
            ],
        }
