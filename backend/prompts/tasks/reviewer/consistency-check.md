请基于以下信息，审校最新章节中是否存在明显冲突或不一致：

【小说设定】
核心种子：{core_seed}
世界观要点：
{world_building}

【角色状态（本章写作前）】
{character_state}

【前文摘要】
{global_summary}

【伏笔台账】
{foreshadowing_ledger}

【本章细纲（应当被遵循）】
{chapter_outline}

【待审校章节正文】
{chapter_text}

请逐项检查：
1. 角色行为是否违背其动机、性格或当前状态
2. 是否与前文摘要中的既定事实矛盾（时间线、地点、人物关系）
3. 是否违背世界观规则（能力体系、社会规则）
4. 是否严重偏离本章细纲的核心目标与伏笔操作
5. 伏笔是否被无意中提前揭晓或遗忘

输出 JSON（不要使用 markdown 代码块）：
{{
  "ok": true 或 false,
  "issues": [
    {{"severity": "high|medium|low", "type": "角色|时间线|世界观|细纲偏离|伏笔", "description": "问题描述", "suggestion": "修改建议"}}
  ]
}}

若无明显冲突，返回 {{"ok": true, "issues": []}}。轻微的风格问题不算冲突。
