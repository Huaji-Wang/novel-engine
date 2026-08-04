"""从已定稿正文提取角色对白样本（对齐 ainovel-cli DraftStore.ExtractDialogue）。"""

from __future__ import annotations

import re

_DIALOGUE_RE = re.compile(r'[「"\u201c][^」"\u201d]*[」"\u201d]')


def extract_dialogue(
    chapter_texts: list[str],
    character_name: str,
    *,
    aliases: list[str] | None = None,
    max_samples: int = 3,
) -> list[str]:
    """倒序扫描章节正文，抽取含角色名的段落中的引号对白。"""
    if max_samples <= 0 or not character_name:
        return []
    names = [character_name] + [a for a in (aliases or []) if a]
    samples: list[str] = []
    for text in reversed(chapter_texts):
        if len(samples) >= max_samples:
            break
        for para in text.splitlines():
            if len(samples) >= max_samples:
                break
            if not any(n in para for n in names):
                continue
            for match in _DIALOGUE_RE.findall(para):
                line = match.strip()
                if len(line) > 3:
                    samples.append(f"{character_name}: {line}")
                    if len(samples) >= max_samples:
                        break
    return list(reversed(samples))


def load_finalized_chapter_texts(
    session,
    novel_id: int,
    *,
    from_chapter: int = 1,
    to_chapter: int | None = None,
) -> list[str]:
    from backend.db.models import Chapter

    q = session.query(Chapter).filter_by(novel_id=novel_id, status="finalized")
    if from_chapter:
        q = q.filter(Chapter.chapter_no >= from_chapter)
    if to_chapter:
        q = q.filter(Chapter.chapter_no <= to_chapter)
    rows = q.order_by(Chapter.chapter_no).all()
    return [r.content for r in rows if r.content]
