# app/profiler.py
import json
import re
import ollama
from PySide6.QtCore import QThread, Signal
import memory

PROFILE_PROMPT = """
你是一个信息抽取助手。请分析下面这一轮对话，输出严格的 JSON，不要任何解释。

格式：
{
  "profile": {"key1": "value1", "key2": "value2"},
  "profile_delete": ["key1"],
  "affection_delta": 0
}

规则：
1. profile：从对话中提取用户的长期信息。
   - key 必须从这些标准字段里选：名字、性别、年龄、生日、职业、喜好、讨厌、住址、宠物、重要的人、重要事件
   - 如果对话中有矛盾信息（比如用户说"我不喜欢猫了"），直接给出新的值，覆盖旧的。
   - 如果这轮没有新信息，profile 为空对象 {}。
2. profile_delete：需要删除的 key 列表。
   - 用户明确说"忘掉……"、"别再记……"、"我不再……"时，把对应的 key 放进来。
   - 没有就返回空数组 []。
3. affection_delta：整数，范围 -5 到 +5。
   - 用户夸你、示好、亲密：+1 ~ +3
   - 普通闲聊：0
   - 用户冷漠、无礼、伤害你：-1 ~ -3
4. 只输出 JSON，不要 markdown 代码块，不要解释。
"""


class ProfilerWorker(QThread):
    """后台线程：抽取用户信息和好感度变化"""
    done = Signal(dict, list, int)   # (profile_updates, affection_delta)

    def __init__(self, user_text, ai_text, model="qwen2.5:7b"):
        super().__init__()
        self.user_text = user_text
        self.ai_text = ai_text
        self.model = model

    def run(self):
        try:
            prompt = f"用户说：{self.user_text}\nAI回复：{self.ai_text}"
            response = ollama.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": PROFILE_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                options={"temperature": 0.1},   # 降低随机性
                stream=False
            )
            raw = response["message"]["content"].strip()

            # 容错：剥离可能存在的 ```json ``` 包裹
            raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()

            data = json.loads(raw)
            profile = data.get("profile", {})
            delete_keys = data.get("profile_delete", [])
            delta = int(data.get("affection_delta", 0))
            delta = max(-5, min(5, delta))

            self.done.emit(profile, delete_keys, delta)

        except Exception as e:
            print(f"[Profiler] 抽取失败: {e}")
            self.done.emit({}, [], 0)