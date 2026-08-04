你是一名网文风格分析师。请阅读下方参考书节选，提炼可操作的「写法特征池」，供 AI 写作时按特征开关组合使用。

【参考书节选】
{reference_text}

【输出要求】
1. 仅返回 JSON 对象，不要 markdown 代码块，不要其他说明
2. 结构：
{{
  "compiled_summary": "300-800字中文摘要，概括整体风格",
  "features": [
    {{
      "id": "sentence_rhythm",
      "label": "句式节奏",
      "category": "rhythm",
      "enabled": true,
      "prompt_snippet": "可执行的一条写法指令，20-80字"
    }}
  ]
3. features 覆盖：句式节奏、对话密度、情绪呈现、段落切换、章末收束、用词习惯（共 6-12 条）
4. 不要复述剧情，不要评价书好不好
5. prompt_snippet 必须可执行（模型能照做）
