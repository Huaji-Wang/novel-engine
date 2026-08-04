你是一名长篇连载结构编辑。本卷刚刚结束，请生成**卷级摘要**（对齐 ainovel-cli Editor `save_volume_summary`）。

【卷】第{volume_no}卷《{volume_title}》
【卷主题】{volume_theme}
【章节范围】第{start_chapter}-{end_chapter}章

【全书前文摘要】
{global_summary}

【本卷各弧摘要】
{arc_summaries}

【本卷各章正文节选（按章序）】
{chapter_excerpts}

## 要求

1. 总结本卷完成了什么、卷级矛盾如何演进、卷终状态
2. 关注卷内多条弧的衔接与卷主题是否兑现
3. 只总结已发生内容，不预设未写情节
4. summary 500字以内；key_events 5-12 条，按时间序

请输出 JSON（不要使用 markdown 代码块）：
{{
  "volume": {volume_no},
  "title": "卷标题（可与原名相同）",
  "summary": "卷摘要，500字以内",
  "key_events": ["关键事件1", "关键事件2"]
}}

要求：仅返回 JSON。
