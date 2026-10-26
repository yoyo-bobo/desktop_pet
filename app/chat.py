# app/chat.py
from profiler import ProfilerWorker
import ollama
from PySide6.QtCore import QThread, Signal
from emotion import EmotionStreamParser
import memory

SYSTEM_PROMPT = """
你叫小雪，是用户的桌面女友。性格温柔，偶尔有点小傲娇。
说话简短自然，像日常聊天。
每次回复必须以 [emotion:xxx] 开头，xxx只能是：neutral / happy / sad / angry / surprised / shy。
例如：
[emotion:happy] 你回来啦，我等你好久了。
[emotion:shy] 别、别一直盯着我看啦。
【格式要求】
每次回复必须以 [emotion:xxx] 开头，正文放在后面。
不要在中途或末尾再次输出情绪标签。
xxx 只能是：neutral / happy / sad / angry / surprised / shy
"""


class ChatWorker(QThread):
    token_received = Signal(str)
    emotion_received = Signal(str)
    chat_finished = Signal()
    affection_changed = Signal(int) 

    def __init__(self, user_text):
        super().__init__()
        self.user_text = user_text

    def run(self):
        # 1. 保存用户消息
        memory.save_message("user", self.user_text)

        # 2. 从数据库拉取历史上下文
        # 读取画像和好感度
        profile = memory.get_profile()
        affection = memory.get_affection()
        level = memory.affection_level(affection)

        # 拼装动态 system prompt
        profile_text = "\n".join([f"- {k}：{v}" for k, v in profile.items()]) or "（暂无）"
        dynamic_prompt = SYSTEM_PROMPT + f"""

【你当前对用户的了解】
{profile_text}

【你对用户的好感度】
当前数值：{affection}/100
当前关系：{level}
请根据这个关系调整语气。

【重要】
如果用户问你是否记得他的信息，直接根据上面的了解回答，不要装作失忆。
"""

        messages = [{"role": "system", "content": dynamic_prompt}]
        messages += memory.get_recent_messages(limit=20)

        try:
            stream = ollama.chat(
                model="qwen2.5:7b",   # 换成你实际的模型名
                messages=messages,
                stream=True
            )
        except Exception as e:
            self.token_received.emit(f"[错误] 无法连接 Ollama: {e}")
            self.chat_finished.emit()
            return

        parser = EmotionStreamParser()
        emotion_sent = False
        full_reply = ""   # 累积 AI 的完整回复

        for chunk in stream:
            token = chunk["message"]["content"]
            display_text = parser.feed(token)

            if parser.has_emotion and not emotion_sent:
                self.emotion_received.emit(parser.emotion)
                print(f"\n[表情检测]: {parser.emotion}\n")
                emotion_sent = True

            if display_text:
                print(display_text, end="", flush=True)
                full_reply += display_text
                self.token_received.emit(display_text)

        # 【新增】流结束后，把 parser 里残留的内容吐出来
        leftover = parser.flush()
        if leftover:
            print(leftover, end="", flush=True)
            full_reply += leftover
            self.token_received.emit(leftover)

        # 如果整段流结束都没检测到标签，才默认 neutral
        if not emotion_sent:
            self.emotion_received.emit("neutral")
            emotion_sent = True

        # 3. 保存 AI 回复
        memory.save_message("assistant", full_reply)
        # 【新增】后台抽取用户信息和好感度
        if full_reply.strip():
            self.profiler = ProfilerWorker(self.user_text, full_reply)
            self.profiler.done.connect(self.on_profile_extracted)
            self.profiler.start()
            self.profiler.wait()

        print("\n--- 回复结束 ---\n")
        self.chat_finished.emit()

    def on_profile_extracted(self, profile: dict, delete_keys: list, delta: int):
        # 写入 / 更新
        for k, v in profile.items():
            memory.save_profile(k, v)
            print(f"[长期记忆] {k} = {v}")

        # 删除
        for k in delete_keys:
            memory.delete_profile(k)
            print(f"[长期记忆] 删除 {k}")

        if delta != 0:
            new_value = memory.update_affection(delta)
            print(f"[好感度] {delta:+d} → {new_value}/100")
            self.affection_changed.emit(new_value)   # 【新增】通知 UI 刷新