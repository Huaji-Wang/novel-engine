你是一名小说世界观策划。请从以下信息中识别**开篇即已存在、且会长期影响主线**的核心阵营，
不要预先列出全书所有势力——后续章节会随剧情增量引入新阵营。

【世界观】
{world_building}

【核心种子】
{core_seed}

【已有阵营】（不要重复）
{existing_names}

要求：
1. 只输出 0-2 个开篇核心阵营；若开篇无明显多势力结构，返回空数组
2. 不要生成地方组织、临时小队、任务型团体
3. 严禁绑定具体角色名单

请严格输出 JSON，不要使用 markdown 代码块：
{{
  "core_factions": [ /* 结构同 CREATE_FACTIONS 的 core_factions 条目 */ ],
  "faction_relations": [ /* 结构同 CREATE_FACTIONS 的 faction_relations 条目 */ ]
}}
