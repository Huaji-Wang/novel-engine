"""API 请求/响应模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class NovelCreate(BaseModel):
    title: str = "未命名小说"
    premise: str = Field(..., min_length=2, description="故事主要方向/创意")
    genre: str = ""
    num_chapters: int = Field(0, ge=0, le=2000, description="0=规模未锁定；>0=软估计章数")
    words_per_chapter: int = Field(3000, ge=300, le=20000)
    is_fanfic: bool = False


class CocreateChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)


class CocreateFinalizeRequest(BaseModel):
    confirm: bool = True


class StyleLearnRequest(BaseModel):
    reference_text: str = Field(..., min_length=200, description="参考书节选，至少200字")


class FieldEdit(BaseModel):
    field: str = Field(..., description="可编辑字段名")
    content: str


class OutlineEdit(BaseModel):
    title: str | None = None
    content: str


class ChapterEdit(BaseModel):
    content: str


class ReviseRequest(BaseModel):
    target_type: str = Field(..., description="core_seed/world_building/plot_architecture/character_dynamics/chapter_outline/chapter")
    chapter_no: int | None = None
    instruction: str = Field(..., min_length=2)
    analyze_impact: bool = True


class WriteChapterRequest(BaseModel):
    user_guidance: str = ""


class PolishRequest(BaseModel):
    instruction: str = ""


class SegmentReviseRequest(BaseModel):
    selected_text: str = Field(..., min_length=8, description="用户在正文中选中的片段")
    instruction: str = Field(..., min_length=2, description="对该片段的评论/修改要求")


class SegmentEditRequest(BaseModel):
    """片段润色 / 去 AI 味：instruction 可选。"""
    selected_text: str = Field(..., min_length=8, description="用户在正文中选中的片段")
    instruction: str = ""


class VolumeEdit(BaseModel):
    title: str | None = None
    theme: str | None = None
    summary: str | None = None


class LoreEntryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    category: str = "其他"
    keywords: list[str] = []
    content: str = ""


class PlannedCharacter(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    role_hint: str = Field("", description="叙事功能，如：下章对手、导师、变量")


class ExpandArcRequest(BaseModel):
    volume_no: int = Field(..., ge=1)
    arc_no: int = Field(..., ge=1)


class CompassEdit(BaseModel):
    ending_direction: str | None = None
    open_threads: list[str] | None = None
    estimated_scale: str | None = None


class UserHintRequest(BaseModel):
    user_hint: str = ""


class ProposeNextVolumeRequest(BaseModel):
    user_hint: str = ""
    volume_no: int | None = Field(None, ge=1, description="指定刚结束的卷号，默认最后一卷")


class AppendVolumeRequest(BaseModel):
    option_id: str = Field(..., min_length=1, description="propose 返回的 options[].id")
    user_hint: str = ""


class ReplanSkeletonArcsRequest(BaseModel):
    volume_no: int = Field(..., ge=1)
    user_hint: str = ""


class DeepenCharactersRequest(BaseModel):
    """深化新角色：已有初稿（names）或下章规划登场（planned）。"""
    names: list[str] = Field(default_factory=list, description="已建档角色的名字，深化初稿卡")
    planned: list[PlannedCharacter] = Field(
        default_factory=list, description="尚未登场、为 upcoming 章节预建并深化")
    target_chapter_no: int | None = Field(
        None, ge=1, description="planned 模式：预计登场章节号，用于读取该章细纲")
    debut_chapter_no: int | None = Field(
        None, ge=1, description="existing 模式：首次登场章节，用于读取该章正文")
    user_hint: str = ""


class LoreEntryEdit(BaseModel):
    name: str | None = None
    category: str | None = None
    keywords: list[str] | None = None
    content: str | None = None
    enabled: bool | None = None
