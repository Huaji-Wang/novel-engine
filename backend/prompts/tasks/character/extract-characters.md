请从以下角色动力学设定中，抽取所有核心角色的结构化信息：

{character_dynamics}

输出 JSON 数组，每个角色一个对象，字段如下：
[
  {{
    "name": "角色名",
    "identity": "身份/职业/年龄/性别等一句话概括",
    "appearance": "外貌特征一句话",
    "traits": ["性格特质1", "性格特质2"],
    "motivation": {{
      "surface": "表面追求",
      "desire": "深层渴望",
      "soul": "灵魂需求"
    }},
    "secret": "暗藏的秘密或弱点",
    "arc": "角色弧线一句话（初始→蜕变→终点）",
    "relationships": [
      {{"target": "另一角色名", "type": "关系类型", "detail": "关系描述/冲突点"}}
    ]
  }}
]

仅返回 JSON 数组，不要解释任何内容，不要使用 markdown 代码块。
