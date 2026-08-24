"""Writer Agent：章节正文写作与扩写。"""

from __future__ import annotations

from backend.context.assembler import append_reference_block, writer_references
from backend.llm.client import LLMClient
from backend.planning.guidance import prompt_guide_fields
from backend.prompts import definitions as P
from backend.prompts.anti_ai import load_writing_quality, prompt_kwargs


class WriterAgent:
    def __init__(self):
        self.llm = LLMClient("writer")

    def write_first_chapter(self, *, chapter_no: int, chapter_title: str,
                            chapter_outline: str, core_seed: str, world_building: str,
                            plot_architecture: str, character_state: str,
                            words_per_chapter: int, user_guidance: str = "",
                            guide_style: str = "", guide_pov: str = "",
                            guide_taboos: str = "", cocreate_context: str = "",
                            chapter_extra: str = "",
                            writing_style: str = "", narrative_pov: str = "",
                            style_guide: str = "", voice_context: str = "",
                            compass_context: str = "", style_rules_context: str = "",
                            recent_cast_context: str = "",
                            arc_hook_note: str = "",
                            chapter_contract: str = "") -> str:
        gf = prompt_guide_fields(
            guide_style=guide_style,
            guide_pov=guide_pov,
            guide_taboos=guide_taboos,
            cocreate_context=cocreate_context or user_guidance,
            chapter_extra=chapter_extra,
        )
        prompt = append_reference_block(
            P.FIRST_CHAPTER_DRAFT_PROMPT.format(
                chapter_no=chapter_no, chapter_title=chapter_title,
                chapter_outline=chapter_outline, core_seed=core_seed,
                world_building=world_building, plot_architecture=plot_architecture,
                character_state=character_state, words_per_chapter=words_per_chapter,
                writing_style=writing_style or "（不限）",
                narrative_pov=narrative_pov or "（不限）",
                style_guide=style_guide or "（无）",
                voice_context=voice_context or "（无）",
                compass_context=compass_context or "（无）",
                style_rules_context=style_rules_context or "（无）",
                recent_cast_context=recent_cast_context or "（无）",
                writing_quality=load_writing_quality() or "（无）",
                arc_hook_note=arc_hook_note or "",
                chapter_contract=chapter_contract or "",
                **gf,
                **prompt_kwargs(),
            ),
            writer_references(chapter_no=chapter_no),
        )
        return self.llm.invoke(prompt)

    def write_next_chapter(self, *, chapter_no: int, chapter_title: str,
                           chapter_outline: str, next_chapter_outline: str,
                           global_summary: str, previous_chapter_excerpt: str,
                           character_state: str, world_building: str,
                           words_per_chapter: int, user_guidance: str = "",
                           guide_style: str = "", guide_pov: str = "",
                           guide_taboos: str = "", cocreate_context: str = "",
                           chapter_extra: str = "",
                           retrieved_context: str = "",
                           writing_style: str = "", narrative_pov: str = "",
                           lore_context: str = "", style_guide: str = "",
                           voice_context: str = "", compass_context: str = "",
                           style_rules_context: str = "",
                           recent_cast_context: str = "",
                           arc_hook_note: str = "",
                           chapter_contract: str = "") -> str:
        gf = prompt_guide_fields(
            guide_style=guide_style,
            guide_pov=guide_pov,
            guide_taboos=guide_taboos,
            cocreate_context=cocreate_context or user_guidance,
            chapter_extra=chapter_extra,
        )
        prompt = append_reference_block(
            P.NEXT_CHAPTER_DRAFT_PROMPT.format(
                chapter_no=chapter_no, chapter_title=chapter_title,
                chapter_outline=chapter_outline,
                next_chapter_outline=next_chapter_outline or "（暂无）",
                global_summary=global_summary or "（无）",
                previous_chapter_excerpt=previous_chapter_excerpt or "（无）",
                character_state=character_state or "（无）",
                world_building=world_building,
                words_per_chapter=words_per_chapter,
                retrieved_context=retrieved_context or "（无）",
                writing_style=writing_style or "（不限）",
                narrative_pov=narrative_pov or "（不限）",
                lore_context=lore_context or "（无）",
                style_guide=style_guide or "（无）",
                voice_context=voice_context or "（无）",
                compass_context=compass_context or "（无）",
                style_rules_context=style_rules_context or "（无）",
                recent_cast_context=recent_cast_context or "（无）",
                writing_quality=load_writing_quality() or "（无）",
                arc_hook_note=arc_hook_note or "",
                chapter_contract=chapter_contract or "",
                **gf,
                **prompt_kwargs(),
            ),
            writer_references(chapter_no=chapter_no),
        )
        return self.llm.invoke(prompt)

    def enrich(self, chapter_text: str, words_per_chapter: int) -> str:
        return self.llm.invoke(P.ENRICH_PROMPT.format(
            chapter_text=chapter_text, words_per_chapter=words_per_chapter,
        ))

    def update_summary(self, chapter_text: str, global_summary: str) -> str:
        return self.llm.invoke(P.SUMMARY_UPDATE_PROMPT.format(
            chapter_text=chapter_text, global_summary=global_summary or "（空）",
        ))
