"""写法特征池 API。"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.agents.style_learner import StyleLearnerAgent
from backend.db.models import Novel, WritingStyleProfile
from backend.db.session import db_session
from backend.style.compiler import compile_style_context, parse_style_learn_result, profile_from_learn_result

router = APIRouter(prefix="/api/novels", tags=["style-profiles"])


class StyleFeatureEdit(BaseModel):
    id: str
    label: str = ""
    category: str = "general"
    enabled: bool = True
    prompt_snippet: str


class StyleProfileUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    features: list[StyleFeatureEdit] | None = None
    compiled_summary: str | None = None


class StyleLearnToProfileRequest(BaseModel):
    reference_text: str = Field(..., min_length=200)
    name: str = "StyleLearner"
    bind_to_novel: bool = True


def _profile_dict(row: WritingStyleProfile) -> dict:
    return {
        "id": row.id,
        "novel_id": row.novel_id,
        "name": row.name,
        "description": row.description or "",
        "features": row.features or [],
        "compiled_summary": row.compiled_summary or "",
        "compiled_prompt": compile_style_context(
            profile={"features": row.features, "compiled_summary": row.compiled_summary},
            style_guide="",
            style_rules={},
        ),
    }


@router.get("/{novel_id}/style-profile")
def get_style_profile(novel_id: int):
    with db_session() as session:
        novel = session.get(Novel, novel_id)
        if not novel:
            raise HTTPException(404, "小说不存在")
        if not novel.style_profile_id:
            return {"bound": False, "profile": None}
        profile = session.get(WritingStyleProfile, novel.style_profile_id)
        if not profile:
            return {"bound": False, "profile": None}
        return {"bound": True, "profile": _profile_dict(profile)}


@router.post("/{novel_id}/style-profile/learn")
def learn_style_profile(novel_id: int, payload: StyleLearnToProfileRequest):
    with db_session() as session:
        if not session.get(Novel, novel_id):
            raise HTTPException(404, "小说不存在")

    raw = StyleLearnerAgent().learn(payload.reference_text)
    parsed = parse_style_learn_result(raw)
    built = profile_from_learn_result(parsed, name=payload.name)

    with db_session() as session:
        novel = session.get(Novel, novel_id)
        profile = WritingStyleProfile(
            novel_id=novel_id,
            name=built["name"],
            features=built["features"],
            compiled_summary=built["compiled_summary"],
            source_excerpt=payload.reference_text[:12000],
        )
        session.add(profile)
        session.flush()
        if payload.bind_to_novel:
            novel.style_profile_id = profile.id
            novel.style_guide = built["compiled_summary"]
        return {
            "profile": _profile_dict(profile),
            "style_guide": novel.style_guide,
        }


@router.patch("/{novel_id}/style-profile")
def update_style_profile(novel_id: int, payload: StyleProfileUpdate):
    with db_session() as session:
        novel = session.get(Novel, novel_id)
        if not novel or not novel.style_profile_id:
            raise HTTPException(404, "未绑定写法特征池")
        profile = session.get(WritingStyleProfile, novel.style_profile_id)
        if not profile:
            raise HTTPException(404, "写法特征池不存在")
        if payload.name is not None:
            profile.name = payload.name
        if payload.description is not None:
            profile.description = payload.description
        if payload.compiled_summary is not None:
            profile.compiled_summary = payload.compiled_summary
        if payload.features is not None:
            profile.features = [f.model_dump() for f in payload.features]
        return {"profile": _profile_dict(profile)}


@router.post("/{novel_id}/style-profile/bind/{profile_id}")
def bind_style_profile(novel_id: int, profile_id: int):
    with db_session() as session:
        novel = session.get(Novel, novel_id)
        profile = session.get(WritingStyleProfile, profile_id)
        if not novel or not profile:
            raise HTTPException(404, "小说或写法池不存在")
        novel.style_profile_id = profile_id
        return {"bound": True, "profile_id": profile_id}
