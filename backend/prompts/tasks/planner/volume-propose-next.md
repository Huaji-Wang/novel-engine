你是一名长篇连载总编。本卷刚刚结束，请提出 **2–4 个**「下一卷方向」；并评估是否可收束全书（对齐 ainovel append_volume 决策）。

【终局指南针】
{story_compass}

【全书前文摘要】
{global_summary}

【刚结束的卷】第{volume_no}卷《{volume_title}》
主题：{volume_theme}
卷摘要：{volume_summary}

【各卷弧摘要（已完成部分）】
{arc_summaries}

【目标规模参考】全书约 {num_chapters} 章（软上限）
【用户补充】{user_hint}

## 下一卷 / 下一组弧的要求（对齐 ainovel）

- 每个选项的卷须承担与**前卷不同的叙事功能**（立足/扩张/试错/反噬/转向/收束等，不要换皮）
- 第一弧须**自然衔接**前卷结尾；在 arcs[].goal 中体现未回收伏笔的承接
- 每条弧：goal 含目标+阻力+代价；主弧 estimated_chapters **8–15**，过渡弧 5–8
- 弧型宜交替；同卷内弧 goal 不得重复同一冲突类型

请输出 JSON（不要用 markdown 代码块）：
{{
  "can_complete_book": true,
  "complete_book_hint": "若可完结：open_threads 是否已可收束（80字内）",
  "options": [
    {{
      "id": "a",
      "title": "下一卷标题",
      "theme": "卷级核心冲突/主题",
      "summary": "走向与卷终钩子（150字内）",
      "narrative_function": "扩张/试错/反噬/转向/收束 等",
      "estimated_chapters": 18,
      "pros": "承接优势（40字内）",
      "risks": "节奏或结构风险（40字内）",
      "arcs": [
        {{
          "title": "弧标题（名词/动名词短语）",
          "goal": "目标+阻力+转折/代价（50–80字）",
          "estimated_chapters": 8
        }}
      ]
    }}
  ]
}}

要求：
1. options 2–4 条；id 用 a/b/c/d
2. 每选项 **2–4 个 arcs**（skeleton，无章细纲）
3. open_threads 仍多、终局未答 → can_complete_book 应为 false
4. 各选项叙事功能须明显不同
5. 仅返回 JSON
