"""SQLite 连接与建表脚本（数据初始化）。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from project.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    student_id TEXT PRIMARY KEY,
    name       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activities (
    activity_id TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    category    TEXT NOT NULL DEFAULT '',
    start_at    TEXT NOT NULL,
    location    TEXT NOT NULL,
    capacity    INTEGER NOT NULL CHECK (capacity > 0),
    policy_type TEXT NOT NULL CHECK (policy_type IN ('DIRECT', 'APPROVAL'))
);

CREATE TABLE IF NOT EXISTS registrations (
    registration_id TEXT PRIMARY KEY,
    activity_id     TEXT NOT NULL REFERENCES activities(activity_id),
    student_id      TEXT NOT NULL REFERENCES students(student_id),
    status          TEXT NOT NULL CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED')),
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    message_id  TEXT PRIMARY KEY,
    student_id  TEXT NOT NULL REFERENCES students(student_id),
    activity_id TEXT NOT NULL REFERENCES activities(activity_id),
    content     TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    is_read     INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_registrations_activity_status
    ON registrations (activity_id, status);
CREATE INDEX IF NOT EXISTS idx_registrations_student_activity
    ON registrations (student_id, activity_id, status);
CREATE INDEX IF NOT EXISTS idx_messages_student
    ON messages (student_id, created_at);

-- 按设计说明：V1 不采用数据库唯一索引兜底，重复报名由服务层校验。
"""

SEED_STUDENTS = (
    ("S001", "张三"),
    ("S002", "李四"),
    ("S003", "王五"),
)


def connect(database_path: Path | None = None) -> sqlite3.Connection:
    """打开连接并启用外键约束。"""
    path = Path(database_path or settings.database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def reset_db(database_path: Path | None = None) -> None:
    """清空所有业务表（用于测试隔离）。先 ensure 表存在，再清空。"""
    path = Path(database_path or settings.database_path)
    with connect(path) as connection:
        connection.executescript(SCHEMA)
        connection.executescript(
            "DELETE FROM messages; DELETE FROM registrations; DELETE FROM activities;"
        )
        connection.executemany(
            "INSERT OR IGNORE INTO students (student_id, name) VALUES (?, ?)",
            SEED_STUDENTS,
        )


def init_db(database_path: Path | None = None) -> None:
    """建表并写入固定演示学生账号（可重复执行）。"""
    path = Path(database_path or settings.database_path)
    with connect(path) as connection:
        connection.executescript(SCHEMA)
        connection.executemany(
            "INSERT OR IGNORE INTO students (student_id, name) VALUES (?, ?)",
            SEED_STUDENTS,
        )


if __name__ == "__main__":
    init_db()
    print(f"数据库已初始化：{settings.database_path}")
