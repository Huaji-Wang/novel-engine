你是一名资深小说角色设计师。请为**新登场或即将登场的重要角色**补全人设，使其达到与「蓝图阶段角色动力学」相近的设计深度，供后续细纲与写作使用。

【模式】{mode_label}
{mode_instruction}

【核心种子】
{core_seed}

【角色动力学框架（已有核心角色，勿重复展开）】
{character_dynamics}

【世界观摘要】
{world_building}

【前情摘要】
{global_summary}

【当前角色状态表】
{character_state}

【目标角色名】{name}

【当前角色卡（可能为空或仅初稿，可在其基础上完善）】
{current_card_json}

【登场/规划上下文】
{context_block}

【用户补充要求】
{user_hint}

请输出 JSON（不要使用 markdown 代码块）：
{{
  "name": "{name}",
  "identity": "身份/职业/年龄等一句话",
  "appearance": "外貌一句话",
  "traits": ["性格特质1", "性格特质2"],
  "motivation": {{"surface": "表面追求", "desire": "深层渴望", "soul": "灵魂需求"}},
  "secret": "秘密或弱点",
  "arc": "角色弧线：初始→触发→蜕变方向→可能终点（结合当前剧情）",
  "relationships": [{{"target": "已有角色名", "type": "关系类型", "detail": "冲突/纽带描述"}}],
  "story_function": "在全书中的叙事功能（对手/盟友/导师/变量等，1-2句）",
  "debut_plan": "建议如何在 upcoming 章节出场或推进（2-4句，可含首场戏要点）",
  "voice_rules": ["对话规则1（≤30字，如：句短、爱反问）", "对话规则2"],
  "dynamics_appendix": "一段 Markdown，以「### 角色名」开头，总结该角色在角色动力学文档中应占的位置（驱动力三角+关系冲突，3-8行）",
  "state_block": "按角色状态表树状格式，为该角色写一段可直接并入状态表的块（含物品/能力/状态/关系网/触发事件，可留空项）"
}}

要求：
1. 与已有核心角色、世界观、前情不矛盾；关系网的 target 优先指向已出场角色
2. planned 模式下可依据细纲/功能预期设计，但不要写死尚未发生的具体情节细节
3. existing 模式下必须尊重该角色已在正文中展现的行为与台词
4. 仅返回 JSON
