你是一名长篇连载总编。请根据全书蓝图，生成**终局方向指南针**（StoryCompass），供后续**滚动分卷**（首卷 + 卷末 append）时校准方向（允许创作过程中演化，但需有明确终局命题）。

【说明】不要在此写死第 2 卷及以后的具体卷名/章号；只锚定终局与长线。
【核心种子】
{core_seed}

【整本书压缩故事】
{full_story}

【三幕式情节架构】
{plot_architecture}

【全书章数】{num_chapters}

【用户指导】
{user_guidance}

请输出 JSON（不要使用 markdown 代码块）：
{{
  "ending_direction": "终局方向（主题性描述，不是具体卷名/章节数，150字内）",
  "open_threads": ["活跃长线1（需收束才能结局）", "活跃长线2"],
  "estimated_scale": "模糊规模（如：预计 3-5 卷 / 80-120 章）"
}}

要求：
1. open_threads 3-6 条，每条一句
2. 与 full_story 结局方向一致，但留演化空间
3. 仅返回 JSON
