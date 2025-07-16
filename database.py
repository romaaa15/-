import sqlite3
from datetime import datetime

DB_NAME = "contest.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS participants (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
            username TEXT,
            join_time TEXT
        );
    """)
    conn.commit()
    conn.close()

def add_participant(user_id: int, full_name: str, username: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO participants (user_id, full_name, username, join_time)
        VALUES (?, ?, ?, ?)
    """, (user_id, full_name, username, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    with open("users_log.txt", "a", encoding="utf-8") as f:
        f.write(f"{user_id} | {full_name} | @{username} | {datetime.now().isoformat()}\n")

def get_all_participants():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM participants")
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]

def remove_participant(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM participants WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
