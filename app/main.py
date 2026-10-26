import sys
import os
os.environ["QTWEBENGINE_REMOTE_DEBUGGING"] = "9222"
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer  # 引入定时器
from window import AvatarWindow

def main():
    app = QApplication(sys.argv)
    window = AvatarWindow()
    window.show()
   # 【临时测试代码】程序启动3秒后，自动触发一次聊天
   #QTimer.singleShot(3000, lambda: window.on_user_message("你好，你能看到我吗？"))
    sys.exit(app.exec())

if __name__ == "__main__":
    main()