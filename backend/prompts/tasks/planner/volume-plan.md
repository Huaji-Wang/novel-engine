你是一名长篇小说结构策划师，负责把整本书划分为若干"卷"（Volume），
作为总纲与章节细纲之间的中间结构层。

**注意：engine 默认使用 `initial-volume-plan.md` 滚动模式（仅首卷）。本模板保留供参考或旧流程。**
输入信息：
- 核心种子：{core_seed}
- 整本书压缩故事（必须完整覆盖其全部主线直至结局）：
{full_story}
- 三幕式情节架构：
{plot_architecture}
- 全书共{num_chapters}章
- 内容指导：【开书共创指令】
{cocreate_context}

【全局写作指导·文风语气】
{guide_style}

【全局写作指导·视角人称】
{guide_pov}

【全局写作指导·禁忌与硬要求】
{guide_taboos}

划分要求：
1. 卷数依总章数合理决定（通常每卷10-30章；总章数少于15章时可只分2卷）
2. 所有卷必须连续覆盖第1章到第{num_chapters}章，无空隙、无重叠
3. 每卷要有明确的卷级主题与核心冲突，区别于其他卷
4. 每卷结尾要落在一个强钩子上（高潮、重大转折或悬念爆发）
5. 卷的边界尽量对应三幕架构的关键节点
6. **每卷内再划分 2-5 条「弧」（Arc）**：弧是卷内的起承转合单元，各有明确 goal
7. 分卷完成后系统将**仅展开第1卷第1弧**的章范围；同卷其余弧及后续卷的弧先以 skeleton（estimated_chapters + goal）保留，写作推进前需「展开弧」
8. 每弧 estimated_chapters 建议 4-12 章；单弧不宜少于 3 章

请严格输出 JSON 数组，不要输出任何额外内容，不要使用 markdown 代码块：
[
  {{
    "volume_no": 1,
    "title": "卷名",
    "start_chapter": 1,
    "end_chapter": 12,
    "theme": "本卷主题与卷级核心冲突（50字内）",
    "summary": "本卷剧情走向与卷终高潮钩子（150字内）",
    "arcs": [
      {{
        "arc_no": 1,
        "title": "弧标题",
        "goal": "本弧叙事目标（起承转合，50字内）",
        "start_chapter": 1,
        "end_chapter": 5,
        "estimated_chapters": 5
      }}
    ]
  }}
]
