你是一名长篇连载总编。本卷刚刚结束，请**更新终局方向指南针**（StoryCompass），反映当前已写进展并调整 open_threads。

【当前指南针】
{current_compass}

【全书前文摘要】
{global_summary}

【刚结束的卷】第{volume_no}卷《{volume_title}》
主题：{volume_theme}

【用户补充】
{user_hint}

请输出 JSON（不要使用 markdown 代码块）：
{{
  "ending_direction": "更新后的终局方向（150字内）",
  "open_threads": ["仍活跃的长线（已收束的删除，新出现的加入）"],
  "estimated_scale": "规模预期（可微调）"
}}

要求：
1. 已在本卷明确收束的线从 open_threads 移除
2. 仅返回 JSON
