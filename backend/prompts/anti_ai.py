"""ainovel-cli 去 AI 味基线。

语义判据：assets/anti-ai-tone.md（与 ainovel-cli references/anti-ai-tone.md 同步，勿删条目）
机械规则：assets/default-rules.md + 下方常量（供 health_check 程序扫描）
Writer 补充：assets/writer-anti-ai-extra.md（ainovel-cli writer.md 去 AI 味 / 句式多样性段）
"""

from __future__ import annotations

from pathlib import Path

_ASSETS = Path(__file__).resolve().parent / "assets"

# 来自 ainovel-cli assets/rules/default.md（health_check 程序扫描用，与 default-rules.md 一致）
FORBIDDEN_PHRASES: tuple[str, ...] = (
    "某种程度上",
    "值得注意的是",
    "不知为何",
    "五味杂陈",
)

FATIGUE_WORDS: dict[str, int] = {
    "不禁": 1,
    "竟然": 1,
    "仿佛": 2,
    "此外": 1,
    "然而": 2,
    "一丝": 2,
    "一抹": 2,
    "一缕": 2,
    "宛如": 1,
    "不由得": 1,
    "像一": 3,
    "沉默了": 2,
    "没有说话": 2,
    "几息": 3,
    "一息": 3,
    "数息": 2,
}


def _read_asset(name: str) -> str:
    return (_ASSETS / name).read_text(encoding="utf-8").strip()


def load_anti_ai_tone() -> str:
    """完整 anti-ai-tone 判据（禁止在代码里摘要或删减）。"""
    return _read_asset("anti-ai-tone.md")


def load_mechanical_rules() -> str:
    """完整机械规则说明（禁止短语 + 疲劳词阈值 + default.md 注释）。"""
    return _read_asset("default-rules.md")


def load_writer_anti_ai_extra() -> str:
    """ainovel-cli writer.md 中与去 AI 味相关的补充约束（非 anti-ai-tone 正文）。"""
    return _read_asset("writer-anti-ai-extra.md")


def load_writing_quality() -> str:
    """Writer 写作质量总纲（references/writing-quality.md）。"""
    from backend.prompts.load import load_reference
    return load_reference("writing-quality")


def prompt_kwargs(*, include_writer_extra: bool = True) -> dict[str, str]:
    """供 Writer/Editor/Reviewer 等 prompt.format 使用。"""
    return {
        "anti_ai_tone": load_anti_ai_tone(),
        "mechanical_anti_ai_rules": load_mechanical_rules(),
        "writer_anti_ai_extra": load_writer_anti_ai_extra() if include_writer_extra else "",
    }
