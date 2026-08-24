你是一名长篇连载总编。请根据共创与已生成的近处蓝图，生成或润色**全书弱指南针**（StoryCompass）。

这是「整体故事倾向指引」，不是逐章大纲，也不是固定结局剧本。

【共创/内容指导（最高优先级）】
【开书共创指令】
{cocreate_context}

【全局写作指导·文风语气】
{guide_style}

【全局写作指导·视角人称】
{guide_pov}

【全局写作指导·禁忌与硬要求】
{guide_taboos}

【核心种子】
{core_seed}

【第1弧架构（近处，勿据此写死全书）】
{plot_architecture}

【规模参考】{scale_label}（非硬性完结章号）

【若已有指南针草稿则在其基础上精炼，不要推翻共创】
{existing_compass}

请输出 JSON（不要使用 markdown 代码块）：
{{
  "ending_direction": "终局方向倾向（主题性、可演化；未定可写待定；150字内）",
  "open_threads": ["活跃长线1", "活跃长线2"],
  "estimated_scale": "模糊规模（如：中长篇 / 约 3-5 卷），勿写必须第几章完结",
  "tone_notes": "调性与禁区摘要（可空字符串）"
}}

要求：
1. 严格尊重共创；禁止发明共创未同意的重大新开局
2. open_threads 2-6 条
3. 不要输出章节目录或散文故事
4. 仅返回 JSON
