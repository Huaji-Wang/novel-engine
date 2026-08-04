你是一名长篇连载编辑。本弧刚刚完成**弧级评审**，请生成弧边界落盘数据（对齐 ainovel-cli Editor `save_arc_summary`）。

【卷】第{volume_no}卷《{volume_title}》
【弧】第{arc_no}弧《{arc_title}》
【弧目标】{arc_goal}
【章节范围】第{start_chapter}-{end_chapter}章

【全书前文摘要】
{global_summary}

【角色状态】
{character_state}

【弧级评审摘要】
{arc_review_summary}

【已有风格规则（可在其基础上修订合并）】
{existing_rules}

【本弧各章正文节选（按章序）】
{chapter_excerpts}

## 任务

一次性输出弧摘要、关键事件、主要角色快照、写作风格规则（含对话规则）。

### 摘要
- 评估弧目标是否达成（完全/部分/偏离）
- 总结不可逆变化与未竟线；500字以内

### character_snapshots
- 本弧活跃的主要角色（3-8 人）
- 每条：name / status（存活/受伤/失踪等）/ power（能力变化，可空）/ motivation / relations（关键关系变化，可空）

### style_rules（强烈建议）
- **prose**：3-5 条叙述风格规则，每条 ≤50 字，具体可执行
- **dialogue**：核心角色对话特征，每人 2-3 条（每条 ≤30 字），从原文归纳
- **taboos**：0-5 条审美禁忌（无法机械化的写法禁忌）

请输出 JSON（不要使用 markdown 代码块）：
{{
  "volume": {volume_no},
  "arc": {arc_no},
  "title": "弧标题（可与原名相同）",
  "summary": "弧摘要，500字以内",
  "key_events": ["关键事件1", "关键事件2"],
  "character_snapshots": [
    {{
      "name": "角色名",
      "status": "当前状态",
      "power": "能力变化",
      "motivation": "当前动机",
      "relations": "关键关系变化"
    }}
  ],
  "style_rules": {{
    "prose": ["叙述规则1", "叙述规则2"],
    "dialogue": [
      {{"name": "角色名", "rules": ["爱用反问句", "紧张时重复最后两个字"]}}
    ],
    "taboos": ["禁忌1"]
  }}
}}

要求：key_events 3-8 条；仅返回 JSON。
