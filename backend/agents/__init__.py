"""合并后的 Agent 导出与 LLM 配置键说明。"""

from backend.agents.chapter_planner import ChapterPlannerAgent
from backend.agents.character import CharacterAgent
from backend.agents.editor import EditorAgent
from backend.agents.impact import ImpactAgent
from backend.agents.memory import MemoryAgent, MemoryService
from backend.agents.narrative_ledger import NarrativeLedgerAgent
from backend.agents.planner import PlannerAgent
from backend.agents.reviewer import ReviewerAgent
from backend.agents.revision import RevisionAgent
from backend.agents.style_learner import StyleLearnerAgent
from backend.agents.worldkeeper import WorldKeeperAgent
from backend.agents.writer import WriterAgent

# config.yaml → llm.agents 键名（LLMClient 注册名）
LLM_AGENT_KEYS = (
    "planner",
    "meta",
    "volume_planner",
    "chapter_planner",
    "character",
    "writer",
    "revision",
    "consistency",
    "critic",
    "editor",
    "faction",
    "lore",
    "foreshadow",
    "impact",
)

__all__ = [
    "ChapterPlannerAgent",
    "CharacterAgent",
    "EditorAgent",
    "ImpactAgent",
    "MemoryAgent",
    "MemoryService",
    "NarrativeLedgerAgent",
    "PlannerAgent",
    "ReviewerAgent",
    "RevisionAgent",
    "StyleLearnerAgent",
    "WorldKeeperAgent",
    "WriterAgent",
    "LLM_AGENT_KEYS",
]
