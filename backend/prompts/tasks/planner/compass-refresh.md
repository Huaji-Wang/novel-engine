你是一名长篇连载总编。作者手动调整了终局指南针或创作方向，请**刷新 StoryCompass**，使其与当前已写进展一致，并为后续滚动分卷提供校准。

【当前指南针】
{current_compass}

【全书前文摘要】
{global_summary}

【已规划卷摘要】
{volume_summaries}

【用户调整说明】
{user_hint}

请输出 JSON（不要用 markdown 代码块）：
{{
  "ending_direction": "更新后的终局方向（150字内，主题性描述）",
  "open_threads": ["仍活跃的长线1", "长线2"],
  "estimated_scale": "模糊规模（如：预计 3–5 卷 / 80–120 章）"
}}

要求：
1. open_threads 3–6 条；已明确收束的删除，新出现的加入
2. 留演化空间，不要写死尚未 append 的具体卷名
3. 仅返回 JSON
