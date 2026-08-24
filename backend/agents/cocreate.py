"""开书共创：多轮澄清需求，累积创作指令草稿。"""

from __future__ import annotations

import re
from typing import Any

from backend.llm.client import LLMClient
from backend.planning.guidance import scale_label, slot_text
from backend.prompts.load import load_task

_TAG_RE = re.compile(
    r"<(thinking|reply|draft|ready|suggestions)>(.*?)</\1>",
    re.DOTALL | re.IGNORECASE,
)


def normalize_thinking(text: str) -> str:
    """思考摘要：最多 5 条、每条不超过 30 字。"""
    items: list[str] = []
    for raw in (text or "").splitlines():
        s = raw.strip().lstrip("-•*").strip()
        if not s:
            continue
        items.append(s[:30])
        if len(items) >= 5:
            break
    if not items:
        blob = re.sub(r"\s+", " ", (text or "").strip())
        if blob:
            items.append(blob[:30])
    return "\n".join(f"- {x}" for x in items)


def parse_cocreate_xml(text: str) -> dict[str, Any]:
    """解析共创 XML；缺段时尽量降级。thinking 可空。"""
    found = {m.group(1).lower(): m.group(2).strip() for m in _TAG_RE.finditer(text or "")}
    reply = found.get("reply") or ""
    if not reply and not found.get("draft"):
        reply = (text or "").strip()
    draft = found.get("draft") or ""
    ready_raw = (found.get("ready") or "false").strip().lower()
    ready = ready_raw in ("true", "1", "yes")
    suggestions: list[str] = []
    for line in (found.get("suggestions") or "").splitlines():
        s = line.strip().lstrip("-•*").strip()
        if s:
            suggestions.append(s[:80])
    return {
        "thinking": normalize_thinking(found.get("thinking") or ""),
        "reply": reply,
        "draft": draft,
        "ready": ready,
        "suggestions": suggestions[:5],
    }


def _find_ci(hay: str, needle: str) -> int:
    return hay.lower().find(needle.lower())


class CocreateStreamParser:
    """从增量文本中拆出 thinking → reply，其余缓冲到结束再解析。"""

    def __init__(self):
        self.buf = ""
        self.phase = "seek_thinking"
        self.thinking = ""
        self.reply = ""
        self.rest = ""

    def feed(self, delta: str) -> list[tuple[str, str]]:
        events: list[tuple[str, str]] = []
        if not delta:
            return events
        self.buf += delta
        while True:
            if self.phase == "seek_thinking":
                i = _find_ci(self.buf, "<thinking>")
                if i < 0:
                    if len(self.buf) > 24:
                        self.buf = self.buf[-24:]
                    break
                self.buf = self.buf[i + len("<thinking>"):]
                self.phase = "in_thinking"
                events.append(("thinking_start", ""))
            elif self.phase == "in_thinking":
                i = _find_ci(self.buf, "</thinking>")
                if i < 0:
                    keep = 16
                    if len(self.buf) > keep:
                        piece = self.buf[:-keep]
                        self.buf = self.buf[-keep:]
                        self.thinking += piece
                        events.append(("thinking", piece))
                    break
                piece = self.buf[:i]
                self.thinking += piece
                if piece:
                    events.append(("thinking", piece))
                self.buf = self.buf[i + len("</thinking>"):]
                self.phase = "seek_reply"
            elif self.phase == "seek_reply":
                i = _find_ci(self.buf, "<reply>")
                if i < 0:
                    if len(self.buf) > 16:
                        self.buf = self.buf[-16:]
                    break
                self.buf = self.buf[i + len("<reply>"):]
                self.phase = "in_reply"
                events.append(("reply_start", ""))
            elif self.phase == "in_reply":
                i = _find_ci(self.buf, "</reply>")
                if i < 0:
                    keep = 16
                    if len(self.buf) > keep:
                        piece = self.buf[:-keep]
                        self.buf = self.buf[-keep:]
                        self.reply += piece
                        events.append(("reply", piece))
                    break
                piece = self.buf[:i]
                self.reply += piece
                if piece:
                    events.append(("reply", piece))
                self.buf = self.buf[i + len("</reply>"):]
                self.phase = "rest"
            else:
                self.rest += self.buf
                self.buf = ""
                break
        return events

    def finish(self) -> dict[str, Any]:
        if self.phase == "in_thinking":
            self.thinking += self.buf
        elif self.phase == "in_reply":
            self.reply += self.buf
        else:
            self.rest += self.buf
        self.buf = ""
        blob = (
            f"<thinking>{self.thinking}</thinking>\n"
            f"<reply>{self.reply}</reply>\n{self.rest}"
        )
        parsed = parse_cocreate_xml(blob)
        if self.reply.strip():
            parsed["reply"] = self.reply.strip()
        parsed["thinking"] = normalize_thinking(self.thinking)
        return parsed


def format_cocreate_context(
    *,
    draft: str = "",
    locks: dict | None = None,
    is_fanfic: bool = False,
) -> str:
    """注入蓝图/细纲/写作的共创约束块。"""
    parts: list[str] = []
    if draft.strip():
        parts.append("【开书共创指令（不得违背用户已确认方向）】\n" + draft.strip())
    locks = locks or {}
    if is_fanfic and locks:
        lines = ["【同人字段锁】"]
        if locks.get("ip_name"):
            lines.append(f"- IP：{locks['ip_name']}")
        for key, label in (
            ("must_not_change", "不可改/禁区"),
            ("canon_ok", "可借用"),
            ("free_to_invent", "可原创"),
            ("voice_notes", "声口/站位"),
            ("anchors", "同人锚点"),
        ):
            vals = locks.get(key) or []
            if isinstance(vals, list) and vals:
                lines.append(f"- {label}：" + "；".join(str(v) for v in vals[:12]))
        parts.append("\n".join(lines))
    return "\n\n".join(parts) if parts else ""


_MUST_RE = re.compile(r"必做[：:]\s*(.+)", re.MULTILINE)
_MUST_NOT_RE = re.compile(r"禁做[：:]\s*(.+)", re.MULTILINE)


def extract_chapter_contract(outline_content: str) -> dict[str, list[str]]:
    """从细纲正文提取轻量 must / must_not。"""
    text = outline_content or ""
    must = [m.group(1).strip() for m in _MUST_RE.finditer(text) if m.group(1).strip()]
    must_not = [m.group(1).strip() for m in _MUST_NOT_RE.finditer(text) if m.group(1).strip()]
    return {"must": must, "must_not": must_not}


def format_chapter_contract(outline_content: str) -> str:
    c = extract_chapter_contract(outline_content)
    if not c["must"] and not c["must_not"]:
        return ""
    lines = ["【本章契约】"]
    for item in c["must"]:
        lines.append(f"- 必做：{item}")
    for item in c["must_not"]:
        lines.append(f"- 禁做：{item}")
    return "\n".join(lines)


class CocreateAgent:
    def __init__(self):
        self.llm = LLMClient("cocreate")

    def _system_prompt(self, *, task: str, **kwargs) -> str:
        is_fanfic = bool(kwargs.get("is_fanfic"))
        mode_label = "同人模式" if is_fanfic else "原创/一般模式"
        mode_extra = (
            load_task("cocreate/fanfic-extra")
            if is_fanfic
            else "（非同人：按一般共创澄清主题、人物、冲突与禁区即可。）"
        )
        return load_task(task).format(
            mode_label=mode_label,
            premise=kwargs.get("premise") or "（未填）",
            genre=kwargs.get("genre") or "未指定",
            words_per_chapter=kwargs.get("words_per_chapter"),
            scale_label=scale_label(kwargs.get("num_chapters") or 0),
            guide_style=slot_text(kwargs.get("guide_style") or ""),
            guide_pov=slot_text(kwargs.get("guide_pov") or ""),
            guide_taboos=slot_text(kwargs.get("guide_taboos") or ""),
            mode_extra=mode_extra,
        )

    def _history_prompt(self, messages: list[dict], user_message: str, *, xml_hint: str) -> str:
        # 只喂正文 content，不把 thinking 送回模型
        history_lines = []
        for m in messages[-16:]:
            role = "用户" if m.get("role") == "user" else "助手"
            history_lines.append(f"{role}：{m.get('content', '')}")
        history_lines.append(f"用户：{user_message.strip()}")
        return f"以下是共创对话，请按系统要求输出{xml_hint}。\n\n" + "\n".join(history_lines)

    def _fill_draft(self, parsed: dict[str, Any], messages: list[dict]) -> dict[str, Any]:
        if not parsed.get("draft") and messages:
            for m in reversed(messages):
                if m.get("role") == "assistant" and m.get("draft"):
                    parsed["draft"] = m["draft"]
                    break
        return parsed

    def chat(
        self,
        *,
        premise: str,
        genre: str,
        num_chapters: int,
        words_per_chapter: int,
        guide_style: str,
        guide_pov: str,
        guide_taboos: str,
        is_fanfic: bool,
        messages: list[dict],
        user_message: str,
    ) -> dict[str, Any]:
        system = self._system_prompt(
            task="cocreate/chat",
            premise=premise, genre=genre, num_chapters=num_chapters,
            words_per_chapter=words_per_chapter, guide_style=guide_style,
            guide_pov=guide_pov, guide_taboos=guide_taboos, is_fanfic=is_fanfic,
        )
        prompt = self._history_prompt(messages, user_message, xml_hint="四段 XML")
        raw = self.llm.invoke(prompt, system=system)
        parsed = parse_cocreate_xml(raw)
        parsed["thinking"] = ""  # 非整包流式路径不启用思考
        return self._fill_draft(parsed, messages)

    def chat_stream(self, **kwargs):
        """产出 ('thinking_start'|'thinking'|'reply_start'|'reply', text)，结束时 StopIteration 不带值。
        完整解析结果放在 self._last_streamed。
        """
        messages = kwargs.get("messages") or []
        user_message = kwargs["user_message"]
        system = self._system_prompt(task="cocreate/chat-stream", **kwargs)
        prompt = self._history_prompt(messages, user_message, xml_hint="五段 XML（thinking 必须最先）")
        parser = CocreateStreamParser()
        for piece in self.llm.invoke_stream(prompt, system=system):
            for ev in parser.feed(piece):
                yield ev
        parsed = self._fill_draft(parser.finish(), messages)
        self._last_streamed = parsed
        yield ("complete", parsed)

    def extract_fanfic_locks(self, draft: str) -> dict:
        if not (draft or "").strip():
            return {}
        prompt = load_task("cocreate/extract-locks").format(draft=draft)
        data = self.llm.invoke_json(prompt)
        return data if isinstance(data, dict) else {}

    def extract_compass(self, draft: str) -> dict:
        """从共创草稿抽取弱指南针（整体故事倾向）。"""
        if not (draft or "").strip():
            return {}
        prompt = load_task("cocreate/extract-compass").format(draft=draft)
        data = self.llm.invoke_json(prompt)
        if not isinstance(data, dict):
            return {}
        threads = data.get("open_threads") or []
        if not isinstance(threads, list):
            threads = []
        return {
            "ending_direction": str(data.get("ending_direction") or "")[:500],
            "open_threads": [str(t) for t in threads if str(t).strip()][:8],
            "estimated_scale": str(data.get("estimated_scale") or "")[:200],
            "tone_notes": str(data.get("tone_notes") or "")[:300],
            "source": "cocreate",
        }

    def extract_open_settings(self, draft: str) -> dict[str, Any]:
        """抽取类型、软章数、三块全局指导。"""
        if not (draft or "").strip():
            return {}
        prompt = load_task("cocreate/extract-guides").format(draft=draft)
        data = self.llm.invoke_json(prompt)
        if not isinstance(data, dict):
            return {}
        soft = data.get("soft_num_chapters") or 0
        try:
            soft_n = int(soft)
        except (TypeError, ValueError):
            soft_n = 0
        soft_n = max(0, min(2000, soft_n))
        return {
            "genre": str(data.get("genre") or "").strip()[:100],
            "soft_num_chapters": soft_n,
            "guide_style": str(data.get("guide_style") or "").strip()[:2000],
            "guide_pov": str(data.get("guide_pov") or "").strip()[:500],
            "guide_taboos": str(data.get("guide_taboos") or "").strip()[:4000],
        }
