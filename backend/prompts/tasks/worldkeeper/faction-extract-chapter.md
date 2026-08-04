你维护这部小说的阵营库。一章刚刚定稿，请识别本章对阵营库的操作。

【世界观要点】
{world_building}

【已有阵营】
{existing_factions_json}

【已有阵营关系】
{existing_relations_json}

【第{chapter_no}章正文】
{chapter_text}

输出 JSON（不要使用 markdown 代码块）：
{{
  "new_factions": [
    {{
      "name": "阵营名称",
      "faction_type": "类型",
      "positioning": "定位",
      "public_stance": "公开立场",
      "core_goal": "核心目标",
      "hidden_goal": "",
      "resources_and_advantages": [],
      "organization_style": "",
      "core_values": [],
      "conflict_with_mainline": "",
      "is_public": true,
      "influence_scope": "区域级",
      "expandability": "",
      "tags": [],
      "importance": 0.0,
      "future_relevance": "high|medium|low",
      "evidence": "正文中证明该势力实际介入剧情的连续原文（80字内）",
      "reason": "为何该势力值得成为后续 canon（60字内）"
    }}
  ],
  "updated_factions": [
    {{"name": "已有阵营名（必须完全一致）", "public_stance": "更新后公开立场", "core_goal": "更新后目标"}}
  ],
  "new_relations": [
    {{
      "source_faction_name": "阵营A",
      "target_faction_name": "阵营B",
      "relation_type": "hostile|allied|cold_war|dependent|subordinate|trade_partner|secret_cooperation|historical_enemy",
      "current_state": "",
      "core_conflict": "",
      "hidden_tension": "",
      "possible_change": "",
      "intensity": 5,
      "is_active": true,
      "importance": 0.0,
      "future_relevance": "high|medium|low",
      "evidence": "正文中确立该关系的连续原文（80字内）",
      "reason": "为何该关系将持续影响后续冲突（60字内）"
    }}
  ],
  "appeared": ["本章剧情中活跃/被重点描写的已有阵营名"],
  "inactive": ["本章明确瓦解/覆灭且短期内不会再活跃的已有阵营名"]
}}

规则：
1. new_factions 仅收录本章**首次登场**、对主线有持续影响的势力；一章通常 0-1 个
2. 临时帮派、路人组织、仅被提及未实际出场的势力 → 不入库
3. importance 为 0~1；新阵营/关系只有持续影响主线才可 >=0.75
4. evidence 必须逐字摘自本章正文，不得概括或编造
5. 新阵营与新关系各最多建议 1 条；能并入已有阵营就不新建
6. appeared/inactive 的 name 必须与已有库完全一致
7. inactive 宁缺毋滥

仅返回 JSON。
