你是一名长篇结构策划师。请**仅重规划**指定卷内 **skeleton 弧**（expanded/finished 弧勿动）。

【终局指南针】
{story_compass}

【全书前文摘要】
{global_summary}

【目标卷】第{volume_no}卷《{volume_title}》
主题：{volume_theme}
章范围：第{start_chapter}–{end_chapter}章

【已锁定弧（勿改）】
{locked_arcs}

【当前 skeleton 弧（待替换）】
{current_skeleton_arcs}

【用户调整意图】
{user_hint}

## 新弧须满足（对齐 ainovel 弧级检查清单）

- 每条 goal：明确目标、阻力、转折、弧末不可逆变化
- 与已锁定弧**不重复冲突类型**；承接上一弧未竟线
- 主弧 estimated_chapters **8–15**；过渡弧 5–8；弧型宜与同卷其他弧形成节奏对比
- 总和 + 已锁定弧章数 ≤ 本卷 {volume_chapters} 章

请输出 JSON 数组，替换卷内全部 skeleton 弧（1–5 条）：
[
  {{
    "arc_no": 2,
    "title": "弧标题",
    "goal": "目标+阻力+转折/代价（50–80字）",
    "estimated_chapters": 8
  }}
]

要求：
1. arc_no 从「已锁定弧最大 arc_no + 1」起连续
2. 仅返回 JSON 数组
