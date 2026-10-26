# app/window.py
import os
import memory
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout
)
from PySide6.QtCore import Qt, QUrl, QObject, Slot
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel
from chat import ChatWorker


class Bridge(QObject):
    """Python 与 JavaScript 通信的桥梁"""
    def __init__(self, window):
        super().__init__()
        self.window = window

    @Slot(str)
    def sendMessage(self, text):
        self.window.on_user_message(text)


class DragBar(QWidget):
    """顶部透明拖动条"""
    def __init__(self, target_window):
        super().__init__()
        self.target = target_window
        self.setFixedHeight(40)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.SizeAllCursor)
        self._drag_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.target.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self._drag_pos is not None:
            self.target.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        event.accept()


class AvatarWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        memory.init_db()

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(800, 800)

        # ---- WebView ----
        self.view = QWebEngineView()
        self.view.page().setBackgroundColor(Qt.transparent)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        html_path = os.path.join(base_dir, "web", "index.html")
        self.view.load(QUrl.fromLocalFile(html_path))

        # ---- 容器：拖动条 + WebView ----
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.drag_bar = DragBar(self)
        layout.addWidget(self.drag_bar)
        layout.addWidget(self.view, 1)
        self.setCentralWidget(container)

        # ---- WebChannel ----
        self.channel = QWebChannel()
        self.bridge = Bridge(self)
        self.channel.registerObject("bridge", self.bridge)
        self.view.page().setWebChannel(self.channel)

        # ---- 当前活跃的 worker ----
        self.worker = None

        # ---- 【新增】页面加载完成后推一次好感度 ----
        self.view.loadFinished.connect(self._on_page_loaded)

    def _on_page_loaded(self, ok):
        """页面加载完成时，把当前好感度推给 UI"""
        if ok:
            self.set_affection_ui(memory.get_affection())

    def on_user_message(self, text):
        """处理用户消息"""
        print(f"用户说: {text}")

        # 上一条还在跑，忽略
        if self.worker is not None and self.worker.isRunning():
            print("[提示] 上一条还在处理中，请稍等")
            return

        self.clear_text()
        self.worker = ChatWorker(text)
        # 所有信号统一在这里 connect
        self.worker.emotion_received.connect(self.set_emotion)
        self.worker.token_received.connect(self.append_text)
        self.worker.chat_finished.connect(self.on_chat_finished)   # 【修复】原来的 finished 是错的
        self.worker.affection_changed.connect(self.set_affection_ui)
        self.worker.start()

    def on_chat_finished(self):
        print("聊天结束")
        self.worker = None

    def set_emotion(self, emotion):
        print(f"Python 发送表情给 JS: {emotion}")
        self.view.page().runJavaScript(f"window.setEmotion('{emotion}')")

    def append_text(self, text):
        self.view.page().runJavaScript(f"window.appendText({text!r})")

    def clear_text(self):
        self.view.page().runJavaScript("window.clearText()")

    def set_affection_ui(self, value):
        """把好感度推给前端 UI"""
        self.view.page().runJavaScript(f"window.setAffection({value})")