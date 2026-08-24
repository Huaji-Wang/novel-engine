你是一名长篇小说结构策划师。本书采用**滚动分卷**：开局只规划**第 1 卷**，后续卷在卷末 append；终局由 StoryCompass 锚定。

输入信息：
- 核心种子：{core_seed}
- 整本书压缩故事（终局与主线参考，允许演化）：
{full_story}
- 三幕式情节架构：
{plot_architecture}
- 目标规模参考：{scale_label}（软上限，0/未锁定则勿写死全书末章）
- 内容指导：
【开书共创指令】
{cocreate_context}

【全局写作指导·文风语气】
{guide_style}

【全局写作指导·视角人称】
{guide_pov}

【全局写作指导·禁忌与硬要求】
{guide_taboos}

## 卷级要求

1. **仅输出第 1 卷**
2. `start_chapter` 固定为 1；`end_chapter` 为本卷预估末章（建议 10–30 章）
3. 卷 theme / summary：卷级核心冲突 + **卷终强钩子**
4. 本卷须回答：新增了什么 / 失去了什么 / 关系如何变化 / 为何必须进入下一卷（在 summary 中体现）

## 弧级要求（对齐 ainovel layered_outline）

5. 卷内划分 **2–5 条叙事弧**，每条弧须像「可独立成立的小故事」：
   - **goal**：明确目标、阻力、转折与代价（50–80 字，不要空泛「成长」）
   - 各弧 goal **不得重复同一冲突类型**（避免换皮打怪）
   - **主弧** estimated_chapters 建议 **8–15**；**过渡弧**可 5–8
   - 弧型宜交替（如：成长突破 / 恩怨冲突 / 探索 / 过渡），遵循「铺垫→积累→爆发→收获」
6. 系统落库后**仅展开第 1 弧**章范围；其余 skeleton，写作前再 expand
7. 弧 title：名词或动名词短语，忌完整句；同卷各弧标题风格宜统一气质
8. 第一弧 goal 须能承接开篇冲突；最后一弧 goal 须指向卷终钩子

请严格输出 JSON 对象（不要用 markdown 代码块）：
{{
  "volume_no": 1,
  "title": "卷名",
  "start_chapter": 1,
  "end_chapter": 12,
  "theme": "本卷主题与卷级核心冲突（50字内）",
  "summary": "本卷走向与卷终高潮钩子（150字内）",
  "arcs": [
    {{
      "arc_no": 1,
      "title": "弧标题",
      "goal": "本弧叙事目标：目标+阻力+转折/代价（50–80字）",
      "start_chapter": 0,
      "end_chapter": 0,
      "estimated_chapters": 8
    }}
  ]
}}
