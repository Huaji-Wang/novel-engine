"""SQLite 数据模型：小说 / 角色 / 章节细纲 / 章节 / 修订记录。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Novel(Base):
    __tablename__ = "novels"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), default="未命名小说")
    premise: Mapped[str] = mapped_column(Text, default="")          # 用户原始方向
    genre: Mapped[str] = mapped_column(String(100), default="")
    num_chapters: Mapped[int] = mapped_column(Integer, default=0)  # 0=规模未锁定；>0=软估计
    words_per_chapter: Mapped[int] = mapped_column(Integer, default=3000)
    user_guidance: Mapped[str] = mapped_column(Text, default="")  # 已废弃；保留列兼容旧库
    # 作者全局写作指导（与 meta 的 writing_style / narrative_pov 分离）
    guide_style: Mapped[str] = mapped_column(Text, default="")
    guide_pov: Mapped[str] = mapped_column(Text, default="")
    guide_taboos: Mapped[str] = mapped_column(Text, default="")
    # 同人 / 开书共创（Integer 以便 SQLite 自动 DDL 识别为 INT）
    is_fanfic: Mapped[int] = mapped_column(Integer, default=0)
    cocreate_draft: Mapped[str] = mapped_column(Text, default="")
    cocreate_messages: Mapped[list] = mapped_column(JSON, default=list)
    cocreate_ready: Mapped[int] = mapped_column(Integer, default=0)
    cocreate_locks: Mapped[dict] = mapped_column(JSON, default=dict)  # 同人字段锁等

    # 书籍包装（PlannerAgent.generate_meta；writing_style/narrative_pov 约束 Writer）
    subtitle: Mapped[str] = mapped_column(String(200), default="")
    introduction: Mapped[str] = mapped_column(Text, default="")
    book_summary: Mapped[str] = mapped_column(Text, default="")
    writing_style: Mapped[str] = mapped_column(String(200), default="")
    narrative_pov: Mapped[str] = mapped_column(String(50), default="")
    era_background: Mapped[str] = mapped_column(String(200), default="")
    tags: Mapped[list] = mapped_column(JSON, default=list)
    style_guide: Mapped[str] = mapped_column(Text, default="")  # StyleLearner 参考书风格指南
    style_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("writing_style_profiles.id"), nullable=True, default=None)
    quality_gate: Mapped[dict] = mapped_column(JSON, default=dict)

    # 蓝图层（Planner / Character Agent 产出）
    full_story: Mapped[str] = mapped_column(Text, default="")     # 整本书压缩版完整故事
    core_seed: Mapped[str] = mapped_column(Text, default="")
    character_dynamics: Mapped[str] = mapped_column(Text, default="")
    world_building: Mapped[str] = mapped_column(Text, default="")
    plot_architecture: Mapped[str] = mapped_column(Text, default="")

    # 状态层（State Keeper 维护）
    global_summary: Mapped[str] = mapped_column(Text, default="")
    character_state: Mapped[str] = mapped_column(Text, default="")

    # 长篇滚动规划（对齐 ainovel-cli StoryCompass / WritingStyleRules）
    story_compass: Mapped[dict] = mapped_column(JSON, default=dict)
    writing_style_rules: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)

    characters: Mapped[list["Character"]] = relationship(
        back_populates="novel", cascade="all, delete-orphan"
    )
    chapter_outlines: Mapped[list["ChapterOutline"]] = relationship(
        back_populates="novel", cascade="all, delete-orphan"
    )
    chapters: Mapped[list["Chapter"]] = relationship(
        back_populates="novel", cascade="all, delete-orphan"
    )


class Character(Base):
    """结构化角色卡（定稿时按章增量建档，非蓝图一次性生成）。"""

    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(primary_key=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"))
    name: Mapped[str] = mapped_column(String(100))
    first_chapter: Mapped[int] = mapped_column(Integer, default=0)
    last_chapter: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active/inactive
    # identity / traits / motivation / arc / secrets / relationships[]
    data: Mapped[dict] = mapped_column(JSON, default=dict)

    novel: Mapped[Novel] = relationship(back_populates="characters")


class ChapterOutline(Base):
    """章节细纲（滚动窗口生成，可被用户或修订 Agent 修改）。"""

    __tablename__ = "chapter_outlines"
    __table_args__ = (UniqueConstraint("novel_id", "chapter_no"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"))
    chapter_no: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft/edited/approved

    novel: Mapped[Novel] = relationship(back_populates="chapter_outlines")


class Chapter(Base):
    __tablename__ = "chapters"
    __table_args__ = (UniqueConstraint("novel_id", "chapter_no"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"))
    chapter_no: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    review: Mapped[str] = mapped_column(Text, default="")             # 最近一次一致性审校结果
    critique: Mapped[str] = mapped_column(Text, default="")           # 最近一次质量评审报告(JSON)
    health_report: Mapped[str] = mapped_column(Text, default="")     # 规则化健康检查(JSON)
    readiness_report: Mapped[str] = mapped_column(Text, default="")  # 发布结构审稿(JSON)
    quality_decision: Mapped[str] = mapped_column(Text, default="")  # rewrite_decider 结果(JSON)
    toxin_report: Mapped[str] = mapped_column(Text, default="")      # 毒点扫描(JSON)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft/edited/finalized

    novel: Mapped[Novel] = relationship(back_populates="chapters")


class Volume(Base):
    """卷（L2 结构层）：总纲与章节细纲之间的中间规划单位。"""

    __tablename__ = "volumes"
    __table_args__ = (UniqueConstraint("novel_id", "volume_no"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"))
    volume_no: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200), default="")
    start_chapter: Mapped[int] = mapped_column(Integer, default=0)
    end_chapter: Mapped[int] = mapped_column(Integer, default=0)
    theme: Mapped[str] = mapped_column(Text, default="")    # 卷主题与卷级核心冲突
    summary: Mapped[str] = mapped_column(Text, default="")  # 卷结束时 LLM 回填的卷摘要
    key_events: Mapped[list] = mapped_column(JSON, default=list)  # 卷内关键事件
    status: Mapped[str] = mapped_column(String(20), default="draft")

    arcs: Mapped[list["Arc"]] = relationship(
        back_populates="volume", cascade="all, delete-orphan",
        order_by="Arc.arc_no",
    )


class Arc(Base):
    """弧（L3 结构层）：卷内的起承转合单元，对齐 ainovel-cli ArcOutline。"""

    __tablename__ = "arcs"
    __table_args__ = (UniqueConstraint("novel_id", "volume_id", "arc_no"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"))
    volume_id: Mapped[int] = mapped_column(ForeignKey("volumes.id"))
    arc_no: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200), default="")
    goal: Mapped[str] = mapped_column(Text, default="")
    start_chapter: Mapped[int] = mapped_column(Integer, default=0)
    end_chapter: Mapped[int] = mapped_column(Integer, default=0)
    estimated_chapters: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[str] = mapped_column(Text, default="")  # 弧结束时回填
    key_events: Mapped[list] = mapped_column(JSON, default=list)
    arc_review: Mapped[str] = mapped_column(Text, default="")  # 弧级评审 JSON
    status: Mapped[str] = mapped_column(
        String(20), default="skeleton")  # skeleton / expanded / active / finished

    volume: Mapped[Volume] = relationship(back_populates="arcs")


class CharacterSnapshot(Base):
    """角色状态快照（弧边界时记录，对齐 ainovel-cli CharacterSnapshot）。"""

    __tablename__ = "character_snapshots"
    __table_args__ = (UniqueConstraint("novel_id", "volume_no", "arc_no", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"))
    volume_no: Mapped[int] = mapped_column(Integer)
    arc_no: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(200), default="")
    power: Mapped[str] = mapped_column(String(300), default="")
    motivation: Mapped[str] = mapped_column(Text, default="")
    relations: Mapped[str] = mapped_column(Text, default="")


class CastEntry(Base):
    """配角名册：有名字的次要角色（对齐 ainovel-cli cast_ledger）。"""

    __tablename__ = "cast_entries"
    __table_args__ = (UniqueConstraint("novel_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"))
    name: Mapped[str] = mapped_column(String(100))
    brief_role: Mapped[str] = mapped_column(String(300), default="")
    first_seen_chapter: Mapped[int] = mapped_column(Integer, default=0)
    last_seen_chapter: Mapped[int] = mapped_column(Integer, default=0)
    appearance_count: Mapped[int] = mapped_column(Integer, default=0)
    appearance_chapters: Mapped[list] = mapped_column(JSON, default=list)
    promoted: Mapped[int] = mapped_column(Integer, default=0)  # 1=已升格到 Character


class Faction(Base):
    """全书级核心阵营（WorldKeeperAgent 产出）。"""

    __tablename__ = "factions"

    id: Mapped[int] = mapped_column(primary_key=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"))
    name: Mapped[str] = mapped_column(String(200))
    first_chapter: Mapped[int] = mapped_column(Integer, default=0)
    last_chapter: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active/inactive
    # faction_type/positioning/public_stance/core_goal/hidden_goal/
    # resources_and_advantages/organization_style/core_values/
    # conflict_with_mainline/is_public/influence_scope/expandability/tags
    data: Mapped[dict] = mapped_column(JSON, default=dict)


class FactionRelation(Base):
    __tablename__ = "faction_relations"

    id: Mapped[int] = mapped_column(primary_key=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"))
    source: Mapped[str] = mapped_column(String(200))
    target: Mapped[str] = mapped_column(String(200))
    relation_type: Mapped[str] = mapped_column(String(50), default="")
    # current_state/core_conflict/hidden_tension/possible_change/intensity/is_active
    data: Mapped[dict] = mapped_column(JSON, default=dict)


class LoreEntry(Base):
    """世界书/设定库条目（Lore Keeper 维护）。

    写章节时按 name/keywords 与本章细纲做关键词匹配，仅注入相关条目（零 LLM 成本）；
    定稿时自动抽取本章新确立的设定沉淀入库。
    """

    __tablename__ = "lore_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"))
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(50), default="其他")  # 地点/物品/组织/规则/历史/种族/能力/其他
    keywords: Mapped[list] = mapped_column(JSON, default=list)  # 额外触发词
    content: Mapped[str] = mapped_column(Text, default="")
    source_chapter: Mapped[int] = mapped_column(Integer, default=0)  # 0=初始抽取或手动
    enabled: Mapped[int] = mapped_column(Integer, default=1)


class Payoff(Base):
    """爽点台账：定稿时抽取，细纲生成时检查节奏缺口。"""

    __tablename__ = "payoffs"

    id: Mapped[int] = mapped_column(primary_key=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"))
    chapter_no: Mapped[int] = mapped_column(Integer)
    payoff_type: Mapped[str] = mapped_column(String(50), default="")  # 打脸/升级/收获/...
    name: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    intensity: Mapped[int] = mapped_column(Integer, default=3)  # 1-5 星


class Foreshadowing(Base):
    """伏笔台账：定稿时由伏笔 Agent 抽取维护，细纲与审校时注入提示词。"""

    __tablename__ = "foreshadowings"

    id: Mapped[int] = mapped_column(primary_key=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="planted")  # planted/reinforced/resolved
    planted_chapter: Mapped[int] = mapped_column(Integer, default=0)
    last_touched_chapter: Mapped[int] = mapped_column(Integer, default=0)
    resolve_by_chapter: Mapped[int] = mapped_column(Integer, default=0)  # 0 = 未约定
    notes: Mapped[str] = mapped_column(Text, default="")


class MemoryChunk(Base):
    """章节切片向量库（SQLite 内嵌实现，供记忆检索 Agent 使用）。"""

    __tablename__ = "memory_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"))
    chapter_no: Mapped[int] = mapped_column(Integer)
    seq: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list] = mapped_column(JSON)


class WritingStyleProfile(Base):
    """写法特征池：可开关的风格特征，编译后进 Writer/Editor prompt。"""

    __tablename__ = "writing_style_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    novel_id: Mapped[int | None] = mapped_column(ForeignKey("novels.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(200), default="默认写法")
    description: Mapped[str] = mapped_column(Text, default="")
    # [{id, label, category, enabled, prompt_snippet}]
    features: Mapped[list] = mapped_column(JSON, default=list)
    compiled_summary: Mapped[str] = mapped_column(Text, default="")
    source_excerpt: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)


class PendingProposal(Base):
    """定稿提取的待确认提案（角色/配角/设定/阵营），Writer 不可引用为既成事实。"""

    __tablename__ = "pending_proposals"

    id: Mapped[int] = mapped_column(primary_key=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"))
    chapter_no: Mapped[int] = mapped_column(Integer, default=0)
    kind: Mapped[str] = mapped_column(String(30))  # character|cast|lore|faction|faction_relation
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|confirmed|rejected
    created_at: Mapped[datetime] = mapped_column(default=_now)


class Job(Base):
    """后台任务：长流程（写章/定稿）入队执行，带步骤级 checkpoint 可断点恢复。"""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"))
    kind: Mapped[str] = mapped_column(String(40))  # write_chapter|finalize_chapter
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    # queued|running|succeeded|failed|cancelling|cancelled
    status: Mapped[str] = mapped_column(String(20), default="queued")
    progress: Mapped[list] = mapped_column(JSON, default=list)   # [{event,data,ts}]
    checkpoint: Mapped[dict] = mapped_column(JSON, default=dict)  # 断点恢复用中间状态
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True, default=None)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True, default=None)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)


class RevisionLog(Base):
    """修订历史：保留被覆盖前的内容，便于回滚与追溯。"""

    __tablename__ = "revision_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"))
    target_type: Mapped[str] = mapped_column(String(50))   # outline/chapter_outline/chapter/...
    target_key: Mapped[str] = mapped_column(String(100))   # 字段名或章节号
    instruction: Mapped[str] = mapped_column(Text, default="")  # 空表示手动编辑
    old_content: Mapped[str] = mapped_column(Text, default="")
    impact_report: Mapped[str] = mapped_column(Text, default="")  # 修订影响分析(JSON)
    created_at: Mapped[datetime] = mapped_column(default=_now)
