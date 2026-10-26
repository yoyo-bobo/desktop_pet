# app/emotion.py
import re

class EmotionStreamParser:
    def __init__(self):
        self.emotion = "neutral"
        self.has_emotion = False   # 是否已检测到情绪标签
        self.pending = ""          # 待处理文本（含半个标签残留）

    def feed(self, token: str) -> str:
        self.pending += token

        # 1. 循环剥离所有完整标签（不区分位置）
        while True:
            match = re.search(r'\[emotion:(\w+)\]', self.pending)
            if not match:
                break
            if not self.has_emotion:
                self.emotion = match.group(1)
                self.has_emotion = True
            self.pending = self.pending[:match.start()] + self.pending[match.end():]

        # 2. 处理可能是"半个标签"的尾部（比如 "[emotion:h"）
        last_open = self.pending.rfind('[')
        if last_open != -1 and ']' not in self.pending[last_open:]:
            # 把 "[emotion:h" 这一段 hold 住，等下一个 token 拼齐
            output = self.pending[:last_open]
            self.pending = self.pending[last_open:]
        else:
            output = self.pending
            self.pending = ""

        return output

    def flush(self) -> str:
        """流结束时调用，把残留内容吐出去"""
        content = self.pending
        self.pending = ""
        return re.sub(r'\[emotion:\w+\]', '', content)