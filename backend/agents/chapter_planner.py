"""Chapter Planner Agent：滚动生成接下来 N 章细纲，并解析为结构化条目。"""

from __future__ import annotations

import re

from backend.context.assembler import append_reference_block, arc_planner_references
from backend.llm.client import LLMClient
from backend.prompts import definitions as P

_CHAPTER_HEAD_RE = re.compile(r"^第\s*(\d+)\s*章\s*[-－—–:：]?\s*(.*)$")


def parse_outline_blocks(text: str) -> list[dict]:
    """把"第n章 - 标题\\n..."格式的细纲文本切分为 [{chapter_no, title, content}]。"""
    blocks: list[dict] = []
    current: dict | None = None
    for line in text.splitlines():
        m = _CHAPTER_HEAD_RE.match(line.strip())
        if m:
            if current:
                current["content"] = current["content"].strip()
                blocks.append(current)
            title = re.sub(r"^[\[【《]|[\]】》]$", "", m.group(2).strip())
            current = {"chapter_no": int(m.group(1)), "title": title, "content": line.strip() + "\n"}
        elif current is not None:
            current["content"] += line + "\n"
    if current:
        current["content"] = current["content"].strip()
        blocks.append(current)
    return blocks


class ChapterPlannerAgent:
    def __init__(self):
        self.llm = LLMClient("chapter_planner")

    def plan_next(self, *, core_seed: str, world_building: str, plot_architecture: str,
                  character_state: str, global_summary: str, existing_outlines: str,
                  num_chapters: int, start_no: int, end_no: int,
                  user_guidance: str = "",
                  cocreate_context: str = "",
                  guide_style: str = "", guide_pov: str = "", guide_taboos: str = "",
                  foreshadowing_ledger: str = "",
                  volume_context: str = "", arc_context: str = "",
                  compass_context: str = "",
                  factions_brief: str = "",
                  payoff_ledger: str = "",
                  is_fanfic: bool = False) -> list[dict]:
        if is_fanfic:
            contract_extra = (
                "【同人章契约加厚】每章禁做至少写 1 条防 OOC/破原作边界/提前泄底；"
                "必做须服务同人锚点或已锁定的势力/声口约束。"
            )
        else:
            contract_extra = "【章契约】必做/禁做各写短句即可；禁做无内容时写「无」。"
        from backend.planning.guidance import prompt_guide_fields, scale_label
        gf = prompt_guide_fields(
            cocreate_context=cocreate_context or user_guidance,
            guide_style=guide_style, guide_pov=guide_pov, guide_taboos=guide_taboos,
        )
        text = self.llm.invoke(P.CHAPTER_OUTLINES_PROMPT.format(
            core_seed=core_seed,
            world_building=world_building,
            plot_architecture=plot_architecture,
            compass_context=compass_context or "（无）",
            character_state=character_state or "（尚未建立）",
            global_summary=global_summary or "（尚未开始写作）",
            existing_outlines=existing_outlines or "（无）",
            foreshadowing_ledger=foreshadowing_ledger or "（暂无伏笔记录）",
            volume_context=volume_context or "（未分卷）",
            arc_context=arc_context or "（未分弧）",
            factions_brief=factions_brief or "（未设置阵营）",
            payoff_ledger=payoff_ledger or "（暂无爽点记录）",
            num_chapters=num_chapters,
            scale_label=scale_label(num_chapters),
            start_no=start_no,
            end_no=end_no,
            contract_extra=contract_extra,
            **gf,
        ))
        blocks = parse_outline_blocks(text)
        # 仅保留请求范围内的章节，防止模型越界生成
        return [b for b in blocks if start_no <= b["chapter_no"] <= end_no]

    def plan_arc_expand(
        self,
        *,
        core_seed: str,
        world_building: str,
        plot_architecture: str,
        character_state: str,
        global_summary: str,
        existing_outlines: str,
        start_no: int,
        end_no: int,
        volume_no: int,
        arc_no: int,
        arc_title: str,
        arc_goal: str,
        estimated_chapters: int,
        user_guidance: str = "",
        cocreate_context: str = "",
        guide_style: str = "",
        guide_pov: str = "",
        guide_taboos: str = "",
        foreshadowing_ledger: str = "",
        volume_context: str = "",
        arc_context: str = "",
        prev_arcs_context: str = "",
        compass_context: str = "",
        factions_brief: str = "",
        payoff_ledger: str = "",
    ) -> list[dict]:
        """展开 skeleton 弧：对齐 ainovel expand_arc 细纲（core_event / hook / scenes）。"""
        from backend.planning.guidance import prompt_guide_fields
        gf = prompt_guide_fields(
            cocreate_context=cocreate_context or user_guidance,
            guide_style=guide_style, guide_pov=guide_pov, guide_taboos=guide_taboos,
        )
        prompt = append_reference_block(
            P.EXPAND_ARC_OUTLINES_PROMPT.format(
                core_seed=core_seed,
                world_building=world_building,
                plot_architecture=plot_architecture,
                compass_context=compass_context or "（无）",
                character_state=character_state or "（尚未建立）",
                global_summary=global_summary or "（尚未开始写作）",
                foreshadowing_ledger=foreshadowing_ledger or "（暂无伏笔记录）",
                volume_context=volume_context or "（未分卷）",
                volume_no=volume_no,
                arc_no=arc_no,
                arc_title=arc_title or "（无）",
                arc_goal=arc_goal or "（无）",
                estimated_chapters=estimated_chapters or (end_no - start_no + 1),
                start_no=start_no,
                end_no=end_no,
                prev_arcs_context=prev_arcs_context or "（无）",
                arc_context=arc_context or "（无）",
                factions_brief=factions_brief or "（未设置阵营）",
                payoff_ledger=payoff_ledger or "（暂无爽点记录）",
                existing_outlines=existing_outlines or "（无）",
                **gf,
            ),
            arc_planner_references(),
        )
        text = self.llm.invoke(prompt)
        blocks = parse_outline_blocks(text)
        return [b for b in blocks if start_no <= b["chapter_no"] <= end_no]
