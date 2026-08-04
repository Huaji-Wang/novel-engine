你维护本书的**配角名册**（cast_ledger）。一章刚刚定稿，请识别本章对次要角色的记录需求。

【核心角色库（已在 Character 表，勿重复入 cast）】
{core_names_json}

【第{chapter_no}章正文】
{chapter_text}

请输出 JSON（不要使用 markdown 代码块）：
{{
  "appeared": ["本章出场且有名字、但不在核心角色库的次要角色名"],
  "cast_intros": [
    {{
      "name": "角色名",
      "brief_role": "一句话定位（仅首次出场或 brief 仍空时填写）",
      "importance": 0.0,
      "future_relevance": "high|medium|low",
      "evidence": "正文中真实出场的连续原文（80字内）",
      "reason": "为何后文仍需记住此人（60字内）"
    }}
  ]
}}

规则：
1. 核心角色、龙套无名者、仅被提及未出场者 → 不入 appeared
2. cast_intros 仅收录 appeared 中**本章首次出现**或需要补全定位者
3. 不确定是否再出场 → 宁可不收录
4. importance 为 0~1；有明确跨章复用价值才可 >=0.60
5. evidence 必须逐字摘自本章正文，不得概括或编造
6. 每章通常 0-2 个新配角；一次性功能人物不建档
7. 仅返回 JSON
