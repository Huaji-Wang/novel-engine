你维护这部小说的角色库。一章刚刚定稿，请识别本章对角色库的操作。

【角色动力学框架（设计参考，勿把未出场者提前建档）】
{character_dynamics}

【已有角色库】
{existing_json}

【第{chapter_no}章正文】
{chapter_text}

输出 JSON（不要使用 markdown 代码块）：
{{
  "new": [
    {{
      "name": "角色名",
      "identity": "身份/职业等一句话",
      "appearance": "外貌一句话，可为空",
      "traits": ["性格特质"],
      "motivation": {{"surface": "", "desire": "", "soul": ""}},
      "secret": "秘密或弱点，可为空",
      "arc": "弧线一句话，可为空",
      "relationships": [{{"target": "另一角色名", "type": "关系", "detail": "描述"}}],
      "importance": 0.0,
      "future_relevance": "high|medium|low",
      "evidence": "正文中证明其真实登场的连续原文（80字内）",
      "reason": "为何值得成为后续必须维护的核心角色（60字内）"
    }}
  ],
  "appeared": ["本章出场的已有角色名"],
  "inactive": ["本章明确退场/死亡/长期离场且短期内不会再出场的已有角色名"]
}}

规则：
1. new 仅收录本章**首次登场**、有名字、对后续剧情有持续影响的核心角色
2. 龙套、一次性路人、无名者、仅被提及但未出场者 → 不入 new
3. 角色若只需记住姓名和一句定位，应交给配角名册，不得放入 new
4. importance 为 0~1；只有预计跨章持续影响主线者才可 >=0.75
5. evidence 必须逐字摘自本章正文，不得概括或编造
6. 一章通常 new 0-1 人；没有则留空数组
7. appeared/inactive 的 name 必须与已有库完全一致
8. inactive 宁缺毋滥：普通暂时未出场不算 inactive

仅返回 JSON。
