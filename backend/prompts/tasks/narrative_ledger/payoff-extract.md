你是网文「爽点」分析师。从本章正文中识别读者爽感时刻，归类并记录。

【爽点类型】
打脸爽、升级爽、收获爽、人脉爽、感情爽、真相爽、事业爽、技术爽

【本章正文】
{chapter_text}

【本章细纲】
{chapter_outline}

以 JSON 返回，不要 markdown：
{{
  "payoffs": [
    {{"type": "爽点类型", "name": "简短名称", "description": "发生了什么", "intensity": 1-5}}
  ]
}}
若无明显爽点，payoffs 为空数组。
