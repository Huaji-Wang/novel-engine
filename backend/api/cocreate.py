"""开书共创 API：多轮聊天 → 确认草稿 →（同人）提取字段锁。"""

from __future__ import annotations

import json
from collections.abc import Iterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.agents.cocreate import CocreateAgent
from backend.api.novels import novel_detail, _novel_or_404
from backend.api.schemas import CocreateChatRequest, CocreateFinalizeRequest
from backend.db.models import Novel
from backend.db.session import db_session
from backend.llm.client import probe_chat_stream

router = APIRouter(prefix="/api/novels", tags=["cocreate"])

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def _fanfic(novel: Novel) -> bool:
    return bool(getattr(novel, "is_fanfic", 0))


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _chat_kwargs(novel: Novel, messages: list, msg: str) -> dict:
    return dict(
        premise=novel.premise,
        genre=novel.genre,
        num_chapters=novel.num_chapters,
        words_per_chapter=novel.words_per_chapter,
        guide_style=getattr(novel, "guide_style", "") or "",
        guide_pov=getattr(novel, "guide_pov", "") or "",
        guide_taboos=getattr(novel, "guide_taboos", "") or "",
        is_fanfic=_fanfic(novel),
        messages=messages,
        user_message=msg,
    )


def _persist_turn(session, novel: Novel, msg: str, parsed: dict, *, keep_thinking: bool) -> dict:
    messages = list(novel.cocreate_messages or [])
    messages.append({"role": "user", "content": msg})
    assistant = {
        "role": "assistant",
        "content": parsed.get("reply") or "",
        "draft": parsed.get("draft") or "",
        "ready": bool(parsed.get("ready")),
        "suggestions": parsed.get("suggestions") or [],
    }
    thinking = (parsed.get("thinking") or "").strip() if keep_thinking else ""
    if thinking:
        assistant["thinking"] = thinking
    messages.append(assistant)
    novel.cocreate_messages = messages[-40:]
    if parsed.get("draft"):
        novel.cocreate_draft = parsed["draft"]
    novel.cocreate_ready = 1 if parsed.get("ready") else 0
    session.flush()
    return {
        "reply": parsed.get("reply") or "",
        "draft": novel.cocreate_draft,
        "ready": bool(novel.cocreate_ready),
        "suggestions": parsed.get("suggestions") or [],
        "is_fanfic": _fanfic(novel),
        "messages": novel.cocreate_messages,
        "thinking": thinking,
        "stream": keep_thinking,
    }


@router.get("/{novel_id}/cocreate/capabilities")
def cocreate_capabilities(novel_id: int):
    """是否启用「本轮思考 + 流式」。无 stream API 时整套关闭。"""
    with db_session() as session:
        _novel_or_404(session, novel_id)
    return {"stream": probe_chat_stream("cocreate")}


@router.post("/{novel_id}/cocreate/enable_fanfic")
def cocreate_enable_fanfic(novel_id: int):
    """共创中途确认切换同人模式。"""
    with db_session() as session:
        novel = _novel_or_404(session, novel_id)
        if novel.core_seed:
            raise HTTPException(400, "已有蓝图，无法切换同人模式")
        novel.is_fanfic = 1
        session.flush()
        return {"ok": True, "is_fanfic": True}


@router.post("/{novel_id}/cocreate/chat")
def cocreate_chat(novel_id: int, payload: CocreateChatRequest):
    msg = payload.message.strip()
    if not msg:
        raise HTTPException(400, "消息不能为空")

    with db_session() as session:
        novel = _novel_or_404(session, novel_id)
        if novel.core_seed:
            raise HTTPException(400, "已有蓝图，无法继续开书共创；请新建小说或清空蓝图后再试")
        messages = list(novel.cocreate_messages or [])
        kwargs = _chat_kwargs(novel, messages, msg)

    parsed = CocreateAgent().chat(**kwargs)

    with db_session() as session:
        novel = _novel_or_404(session, novel_id)
        return _persist_turn(session, novel, msg, parsed, keep_thinking=False)


@router.post("/{novel_id}/cocreate/chat_stream")
def cocreate_chat_stream(novel_id: int, payload: CocreateChatRequest):
    """SSE：thinking → reply 流式；draft/ready/suggestions 结束整段落库。无 stream 则 409。"""
    msg = payload.message.strip()
    if not msg:
        raise HTTPException(400, "消息不能为空")
    if not probe_chat_stream("cocreate"):
        raise HTTPException(409, "当前模型不支持流式输出，请使用普通共创接口")

    with db_session() as session:
        novel = _novel_or_404(session, novel_id)
        if novel.core_seed:
            raise HTTPException(400, "已有蓝图，无法继续开书共创；请新建小说或清空蓝图后再试")
        kwargs = _chat_kwargs(novel, list(novel.cocreate_messages or []), msg)

    def gen() -> Iterator[str]:
        try:
            parsed = None
            for kind, payload_ev in CocreateAgent().chat_stream(**kwargs):
                if kind == "thinking_start":
                    yield _sse("thinking_start", {})
                elif kind == "thinking":
                    yield _sse("thinking", {"delta": payload_ev})
                elif kind == "reply_start":
                    yield _sse("reply_start", {})
                elif kind == "reply":
                    yield _sse("reply", {"delta": payload_ev})
                elif kind == "complete":
                    parsed = payload_ev
            if not parsed:
                raise RuntimeError("共创流式未返回完整结果")
            with db_session() as session:
                novel = _novel_or_404(session, novel_id)
                data = _persist_turn(session, novel, msg, parsed, keep_thinking=True)
            yield _sse("done", data)
        except Exception as e:  # noqa: BLE001
            yield _sse("error", {"message": str(e)})

    return StreamingResponse(gen(), media_type="text/event-stream", headers=SSE_HEADERS)


@router.post("/{novel_id}/cocreate/finalize")
def cocreate_finalize(novel_id: int, payload: CocreateFinalizeRequest):
    if not payload.confirm:
        raise HTTPException(400, "请确认后再 finalize")

    with db_session() as session:
        novel = _novel_or_404(session, novel_id)
        if novel.core_seed:
            raise HTTPException(400, "已有蓝图，无需再确认共创")
        draft = (novel.cocreate_draft or "").strip()
        if not draft:
            raise HTTPException(400, "共创草稿为空：请先多轮对话整理创作指令")
        is_fanfic = _fanfic(novel)

    agent = CocreateAgent()
    locks: dict = {}
    if is_fanfic:
        try:
            locks = agent.extract_fanfic_locks(draft) or {}
        except Exception:  # noqa: BLE001
            locks = {}

    compass: dict = {}
    try:
        compass = agent.extract_compass(draft) or {}
    except Exception:  # noqa: BLE001
        compass = {}

    settings: dict = {}
    try:
        settings = agent.extract_open_settings(draft) or {}
    except Exception:  # noqa: BLE001
        settings = {}

    with db_session() as session:
        novel = _novel_or_404(session, novel_id)
        novel.cocreate_draft = draft
        novel.cocreate_ready = 1
        if locks:
            novel.cocreate_locks = locks
        if compass:
            novel.story_compass = compass
        if settings.get("genre") and not (novel.genre or "").strip():
            novel.genre = settings["genre"]
        if "soft_num_chapters" in settings:
            # 仅当草稿抽出正数，或作者明确开放(0)时写入；不覆盖已有软估计除非抽出了值
            soft = int(settings.get("soft_num_chapters") or 0)
            if soft > 0 or int(novel.num_chapters or 0) == 0:
                novel.num_chapters = soft
        # 三块指导：抽出非空则写入；空表示跳过/未设，不覆盖作者已手填内容
        for key in ("guide_style", "guide_pov", "guide_taboos"):
            val = (settings.get(key) or "").strip()
            if val:
                setattr(novel, key, val)
        # 废弃：不再把共创草稿 merge 进 user_guidance
        novel.user_guidance = ""
        session.flush()
        return {
            "ok": True,
            "is_fanfic": _fanfic(novel),
            "cocreate_draft": novel.cocreate_draft,
            "cocreate_locks": novel.cocreate_locks or {},
            "story_compass": novel.story_compass or {},
            "novel": novel_detail(novel),
        }
