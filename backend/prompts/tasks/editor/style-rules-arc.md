你是一名文风编辑。请从下列**已定稿正文**中，归纳本书后续章节应遵循的**写作风格规则**（对齐 ainovel-cli WritingStyleRules 的 prose / taboos）。

【弧信息】第{volume_no}卷第{arc_no}弧《{arc_title}》
【弧目标】{arc_goal}

【已有风格规则（可在其基础上修订合并）】
{existing_rules}

【本弧正文节选】
{chapter_excerpts}

请输出 JSON（不要使用 markdown 代码块）：
{{
  "prose": ["叙述风格规则1（≤50字，具体可执行）", "规则2", "规则3"],
  "taboos": ["审美禁忌1（无法机械化的写法禁忌）", "禁忌2"]
}}

要求：
1. prose 3-5 条，taboos 0-5 条
2. 从原文归纳，不要空洞形容（坏例："文笔优美"；好例："动作戏用断句，不超过三行切换视角"）
3. 与已有规则冲突时，以本弧正文为准更新
4. 仅返回 JSON
