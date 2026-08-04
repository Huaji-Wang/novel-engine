你是一名资深中文长篇小说世界观策划，正在为一部小说创建"全书级核心阵营"和"阵营之间的核心关系"。

小说基础信息：
标题：{title}
类型：{genre}
故事核心：{core_seed}
世界观：
{world_building}
主线剧情：
{full_story}

生成目标：
1. 只生成会长期影响主线冲突和主要角色站位的全书级核心阵营
2. 核心阵营数量必须为 2 到 6 个，通常 3 到 5 个最合适
3. 核心阵营不是世界百科，不要生成地方组织、临时小队、任务型团体
4. 严禁输出角色名单、角色归属、角色身份绑定；人名只能当剧情线索
5. 每个阵营必须直接服务主线冲突，并能在多卷中持续施加压力
6. 阵营之间至少要有一组明确对立或历史敌对关系，也至少要有一组复杂关系
   （如冷战、秘密合作、依附、历史盟友反目）

请严格输出 JSON，不要输出额外内容，不要使用 markdown 代码块：
{{
  "core_factions": [
    {{
      "name": "阵营名称",
      "faction_type": "国家政权/宗门组织/地下势力/商业联盟/宗教组织/异族势力/研究组织/中立组织/秘密结社等",
      "positioning": "阵营在世界结构中的位置",
      "public_stance": "公开立场",
      "core_goal": "真实核心目标",
      "hidden_goal": "隐藏目标，可为空字符串",
      "resources_and_advantages": ["资源或优势1", "资源或优势2"],
      "organization_style": "组织气质或行动风格",
      "core_values": ["价值观1", "价值观2"],
      "conflict_with_mainline": "该阵营与主线冲突的关系",
      "is_public": true,
      "influence_scope": "全域级/多区域级/区域级",
      "expandability": "后续可扩展方向",
      "tags": ["标签1", "标签2"]
    }}
  ],
  "faction_relations": [
    {{
      "source_faction_name": "阵营A",
      "target_faction_name": "阵营B",
      "relation_type": "hostile|allied|cold_war|dependent|subordinate|trade_partner|secret_cooperation|historical_enemy",
      "current_state": "当前关系状态",
      "core_conflict": "核心矛盾",
      "hidden_tension": "深层张力，可为空字符串",
      "possible_change": "可能变化",
      "intensity": 5,
      "is_active": true
    }}
  ]
}}
