"""Planner Agent：蓝图规划 + 书籍包装(Meta) + 分卷(VolumePlanner)。"""

from __future__ import annotations

from backend.context.assembler import append_reference_block, arc_planner_references, planner_references
from backend.llm.client import LLMClient
from backend.prompts import definitions as P

NARRATIVE_POV_VALUES = {"第一人称", "第三人称有限视角", "全知视角"}


class PlannerAgent:
    def __init__(self):
        self.llm = LLMClient("planner")
        self._meta_llm = LLMClient("meta")
        self._volume_llm = LLMClient("volume_planner")

    def expand_story(self, premise: str, genre: str, num_chapters: int,
                     words_per_chapter: int, user_guidance: str) -> str:
        prompt = append_reference_block(
            P.EXPAND_STORY_PROMPT.format(
                premise=premise, genre=genre, num_chapters=num_chapters,
                words_per_chapter=words_per_chapter, user_guidance=user_guidance or "无",
            ),
            planner_references(),
        )
        return self.llm.invoke(prompt)

    def core_seed(self, premise: str, genre: str, num_chapters: int,
                  words_per_chapter: int, user_guidance: str,
                  full_story: str = "") -> str:
        return self.llm.invoke(P.CORE_SEED_PROMPT.format(
            premise=premise, genre=genre, num_chapters=num_chapters,
            words_per_chapter=words_per_chapter, user_guidance=user_guidance or "无",
            full_story=full_story or "（无）",
        ))

    def world_building(self, core_seed: str, user_guidance: str) -> str:
        return self.llm.invoke(P.WORLD_BUILDING_PROMPT.format(
            core_seed=core_seed, user_guidance=user_guidance or "无",
        ))

    def plot_architecture(self, core_seed: str, character_dynamics: str,
                          world_building: str, user_guidance: str,
                          full_story: str = "") -> str:
        prompt = append_reference_block(
            P.PLOT_ARCHITECTURE_PROMPT.format(
                core_seed=core_seed, character_dynamics=character_dynamics,
                world_building=world_building, user_guidance=user_guidance or "无",
                full_story=full_story or "（无）",
            ),
            planner_references(),
        )
        return self.llm.invoke(prompt)

    def generate_meta(self, *, premise: str, genre: str, num_chapters: int,
                      words_per_chapter: int, core_seed: str, full_story: str) -> dict:
        """原 MetaAgent.generate"""
        result = self._meta_llm.invoke_json(P.NOVEL_META_PROMPT.format(
            premise=premise, genre=genre, num_chapters=num_chapters,
            words_per_chapter=words_per_chapter,
            core_seed=core_seed or "（无）",
            full_story=full_story or "（无）",
        ))
        if not isinstance(result, dict):
            return {}
        if result.get("narrative_pov") not in NARRATIVE_POV_VALUES:
            result["narrative_pov"] = "第三人称有限视角"
        if not isinstance(result.get("tags"), list):
            result["tags"] = []
        return result

    def _parse_volume_dict(self, v: dict, *, default_no: int = 1) -> dict | None:
        if not isinstance(v, dict):
            return None
        arcs_raw = v.get("arcs") or []
        arcs = []
        for j, a in enumerate(arcs_raw, start=1):
            if not isinstance(a, dict):
                continue
            arcs.append({
                "arc_no": int(a.get("arc_no") or j),
                "title": str(a.get("title", "")),
                "goal": str(a.get("goal", "")),
                "start_chapter": int(a.get("start_chapter") or 0),
                "end_chapter": int(a.get("end_chapter") or 0),
                "estimated_chapters": int(
                    a.get("estimated_chapters")
                    or max(0, int(a.get("end_chapter") or 0) - int(a.get("start_chapter") or 0) + 1)
                    or 5
                ),
            })
        return {
            "volume_no": int(v.get("volume_no") or default_no),
            "title": str(v.get("title", "")),
            "start_chapter": int(v.get("start_chapter") or 0),
            "end_chapter": int(v.get("end_chapter") or 0),
            "theme": str(v.get("theme", "")),
            "summary": str(v.get("summary", "")),
            "arcs": arcs,
        }

    def plan_initial_volume(self, *, core_seed: str, full_story: str, plot_architecture: str,
                            num_chapters: int, user_guidance: str) -> dict | None:
        """滚动分卷：仅规划第 1 卷。"""
        result = self._volume_llm.invoke_json(append_reference_block(
            P.INITIAL_VOLUME_PLAN_PROMPT.format(
                core_seed=core_seed,
                full_story=full_story or "（无）",
                plot_architecture=plot_architecture,
                num_chapters=num_chapters,
                user_guidance=user_guidance or "无",
            ),
            arc_planner_references(),
        ))
        if isinstance(result, list) and result:
            result = result[0]
        if not isinstance(result, dict):
            return None
        vol = self._parse_volume_dict(result, default_no=1)
        if not vol:
            return None
        vol["volume_no"] = 1
        vol["start_chapter"] = max(1, vol["start_chapter"] or 1)
        if vol["end_chapter"] < vol["start_chapter"]:
            vol["end_chapter"] = min(num_chapters, vol["start_chapter"] + 11)
        return vol

    def plan_volumes(self, *, core_seed: str, full_story: str, plot_architecture: str,
                     num_chapters: int, user_guidance: str) -> list[dict]:
        """兼容旧接口：等价于 plan_initial_volume 返回单卷列表。"""
        vol = self.plan_initial_volume(
            core_seed=core_seed, full_story=full_story,
            plot_architecture=plot_architecture,
            num_chapters=num_chapters, user_guidance=user_guidance,
        )
        return [vol] if vol else []

    def propose_next_volume(
        self, *,
        story_compass: dict,
        global_summary: str,
        volume_no: int,
        volume_title: str,
        volume_theme: str,
        volume_summary: str,
        arc_summaries: str,
        num_chapters: int,
        user_hint: str = "",
    ) -> dict:
        import json
        result = self._volume_llm.invoke_json(append_reference_block(
            P.VOLUME_PROPOSE_NEXT_PROMPT.format(
                story_compass=json.dumps(story_compass or {}, ensure_ascii=False, indent=2),
                global_summary=global_summary or "（无）",
                volume_no=volume_no,
                volume_title=volume_title or "（无）",
                volume_theme=volume_theme or "（无）",
                volume_summary=volume_summary or "（无）",
                arc_summaries=arc_summaries or "（无）",
                num_chapters=num_chapters,
                user_hint=user_hint or "无",
            ),
            arc_planner_references(),
        ))
        return result if isinstance(result, dict) else {}

    def replan_skeleton_arcs(
        self, *,
        story_compass: dict,
        global_summary: str,
        volume: dict,
        locked_arcs: str,
        current_skeleton_arcs: str,
        user_hint: str = "",
    ) -> list[dict]:
        import json
        vol_chapters = int(volume["end_chapter"]) - int(volume["start_chapter"]) + 1
        result = self._volume_llm.invoke_json(append_reference_block(
            P.REPLAN_SKELETON_ARCS_PROMPT.format(
                story_compass=json.dumps(story_compass or {}, ensure_ascii=False, indent=2),
                global_summary=global_summary or "（无）",
                volume_no=volume["volume_no"],
                volume_title=volume.get("title", ""),
                volume_theme=volume.get("theme", ""),
                start_chapter=volume["start_chapter"],
                end_chapter=volume["end_chapter"],
                locked_arcs=locked_arcs or "（无）",
                current_skeleton_arcs=current_skeleton_arcs or "（无）",
                user_hint=user_hint or "无",
                volume_chapters=vol_chapters,
            ),
            arc_planner_references(),
        ))
        if not isinstance(result, list):
            return []
        arcs = []
        for j, a in enumerate(result, start=1):
            if not isinstance(a, dict):
                continue
            arcs.append({
                "arc_no": int(a.get("arc_no") or j),
                "title": str(a.get("title", "")),
                "goal": str(a.get("goal", "")),
                "start_chapter": 0,
                "end_chapter": 0,
                "estimated_chapters": int(a.get("estimated_chapters") or 5),
                "status": "skeleton",
            })
        return arcs

    def refresh_compass(
        self, *,
        current_compass: dict,
        global_summary: str,
        volume_summaries: str,
        user_hint: str = "",
    ) -> dict:
        import json
        result = self._volume_llm.invoke_json(P.COMPASS_REFRESH_PROMPT.format(
            current_compass=json.dumps(current_compass or {}, ensure_ascii=False, indent=2),
            global_summary=global_summary or "（无）",
            volume_summaries=volume_summaries or "（无）",
            user_hint=user_hint or "无",
        ))
        return result if isinstance(result, dict) else {}

    def init_compass(self, *, core_seed: str, full_story: str, plot_architecture: str,
                     num_chapters: int, user_guidance: str) -> dict:
        result = self._volume_llm.invoke_json(P.COMPASS_INIT_PROMPT.format(
            core_seed=core_seed,
            full_story=full_story or "（无）",
            plot_architecture=plot_architecture,
            num_chapters=num_chapters,
            user_guidance=user_guidance or "无",
        ))
        return result if isinstance(result, dict) else {}

    def update_compass(self, *, current_compass: dict, global_summary: str,
                       volume_no: int, volume_title: str, volume_theme: str,
                       user_hint: str = "") -> dict:
        import json
        result = self._volume_llm.invoke_json(P.COMPASS_UPDATE_PROMPT.format(
            current_compass=json.dumps(current_compass or {}, ensure_ascii=False, indent=2),
            global_summary=global_summary or "（无）",
            volume_no=volume_no,
            volume_title=volume_title or "（无）",
            volume_theme=volume_theme or "（无）",
            user_hint=user_hint or "无",
        ))
        return result if isinstance(result, dict) else {}


def format_volume_context(volumes: list[dict], start_no: int, end_no: int) -> str:
    """格式化与本批细纲相关的卷上下文（当前卷 + 已 append 的下一卷）。"""
    if not volumes:
        return ""
    lines = []
    last = max(volumes, key=lambda v: v["volume_no"])
    for v in volumes:
        overlaps = v["start_chapter"] <= end_no and v["end_chapter"] >= start_no
        if overlaps:
            lines.append(
                f"第{v['volume_no']}卷《{v['title']}》（第{v['start_chapter']}-{v['end_chapter']}章）\n"
                f"  主题：{v['theme']}\n  走向：{v['summary']}"
            )
        elif v["start_chapter"] == end_no + 1:
            lines.append(
                f"（下一卷预告）第{v['volume_no']}卷《{v['title']}》：{v['theme']}")
    if end_no >= last["end_chapter"] and not any(
        v["start_chapter"] == end_no + 1 for v in volumes
    ):
        lines.append(
            "（滚动规划）当前已规划至最后一卷末尾；"
            "后续卷尚未 append，请以终局指南针与卷末方向选项为准，勿臆造未落盘的卷名。"
        )
    return "\n".join(lines)
