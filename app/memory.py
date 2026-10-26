# app/memory.py
import sqlite3
import os
from datetime import datetime

# 数据库放在项目根目录的 data 文件夹里
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "memory.db")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # 原来的消息表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)
    # 【新增】用户画像表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_profile (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    # 【新增】好感度表（只有一行）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS affection (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            value INTEGER NOT NULL DEFAULT 20,
            updated_at TEXT NOT NULL
        )
    """)
    # 初始化好感度行（如果不存在）
    cursor.execute("SELECT COUNT(*) FROM affection")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO affection (id, value, updated_at) VALUES (1, 20, ?)",
            (datetime.now().isoformat(),)
        )
    conn.commit()
    conn.close()


def save_message(role: str, content: str):
    """保存一条消息，role 是 'user' 或 'assistant'"""
    if not content or not content.strip():
        return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO messages (role, content, timestamp) VALUES (?, ?, ?)",
        (role, content, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def get_recent_messages(limit: int = 20):
    """取出最近 limit 条消息，按时间正序返回，供 Ollama 使用"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, content FROM messages ORDER BY id DESC LIMIT ?",
        (limit,)
    )
    rows = cursor.fetchall()
    conn.close()
    # 反转成正序（旧 -> 新）
    rows.reverse()
    return [{"role": r, "content": c} for r, c in rows]


def clear_history():
    """清空所有历史（调试用）"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages")
    conn.commit()
    conn.close()

# ---------- 用户画像 ----------

def save_profile(key: str, value: str):
    """保存或更新一条用户画像"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO user_profile (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = excluded.updated_at
    """, (key, value, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def get_profile() -> dict:
    """读取全部用户画像"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM user_profile")
    rows = cursor.fetchall()
    conn.close()
    return {k: v for k, v in rows}


# ---------- 好感度 ----------

def get_affection() -> int:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM affection WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 20


def update_affection(delta: int):
    """调整好感度，限制在 0~100"""
    current = get_affection()
    new_value = max(0, min(100, current + delta))
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE affection SET value = ?, updated_at = ? WHERE id = 1",
        (new_value, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    return new_value


def affection_level(value: int = None) -> str:
    """好感度等级描述，用于 system prompt"""
    if value is None:
        value = get_affection()
    if value < 20:
        return "陌生（保持礼貌，有点距离感）"
    elif value < 40:
        return "认识（普通朋友，语气自然）"
    elif value < 60:
        return "熟悉（比较亲近，会主动关心）"
    elif value < 80:
        return "喜欢（明显依赖，偶尔撒娇）"
    else:
        return "恋人（亲密，会吃醋，会表白）"

def delete_profile(key: str):
    """删除某条用户画像"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_profile WHERE key = ?", (key,))
    conn.commit()
    conn.close()