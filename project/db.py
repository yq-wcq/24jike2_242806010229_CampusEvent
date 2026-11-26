"""SQLite 连接、建表与数据初始化（V2 含幂等增量迁移）。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from project.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    student_id TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    grade      INTEGER NOT NULL DEFAULT 2 CHECK (grade BETWEEN 1 AND 4),
    email      TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS activities (
    activity_id TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    category    TEXT NOT NULL DEFAULT '',
    start_at    TEXT NOT NULL,
    location    TEXT NOT NULL,
    capacity    INTEGER NOT NULL CHECK (capacity > 0),
    policy_type TEXT NOT NULL
        CHECK (policy_type IN ('DIRECT', 'APPROVAL', 'GRADE_DIRECT'))
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

CREATE TABLE IF NOT EXISTS email_logs (
    email_id        TEXT PRIMARY KEY,
    event_id        TEXT NOT NULL UNIQUE,
    registration_id TEXT NOT NULL,
    student_id      TEXT NOT NULL,
    recipient       TEXT NOT NULL,
    subject         TEXT NOT NULL,
    content         TEXT NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('SENT', 'FAILED')),
    error           TEXT,
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_registrations_activity_status
    ON registrations (activity_id, status);
CREATE INDEX IF NOT EXISTS idx_registrations_student_activity
    ON registrations (student_id, activity_id, status);
CREATE INDEX IF NOT EXISTS idx_messages_student
    ON messages (student_id, created_at);
CREATE INDEX IF NOT EXISTS idx_email_logs_created_at
    ON email_logs (created_at);

-- 按设计说明：V1 不采用数据库唯一索引兜底，重复报名由服务层校验。
-- V2 的 email_logs.event_id 唯一约束用于通知去重（CR-02）。
"""

SEED_STUDENTS = (
    ("S001", "张三", 2, "s001@campus.example"),
    ("S002", "李四", 3, "s002@campus.example"),
    ("S003", "王五", 1, "s003@campus.example"),
    ("S004", "赵六", 4, "s004@campus.example"),
)


def connect(database_path: Path | None = None) -> sqlite3.Connection:
    """打开连接并启用外键约束。"""
    path = Path(database_path or settings.database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _column_names(connection: sqlite3.Connection, table: str) -> set[str]:
    return {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
    }


def _ensure_students_columns(connection: sqlite3.Connection) -> None:
    columns = _column_names(connection, "students")
    if "grade" not in columns:
        connection.execute(
            "ALTER TABLE students ADD COLUMN grade INTEGER NOT NULL DEFAULT 2 "
            "CHECK (grade BETWEEN 1 AND 4)"
        )
    if "email" not in columns:
        connection.execute(
            "ALTER TABLE students ADD COLUMN email TEXT NOT NULL DEFAULT ''"
        )


def _ensure_activities_policy_check(connection: sqlite3.Connection) -> None:
    """旧库的 policy_type CHECK 只有两个值；SQLite 需重建表才能扩展。"""
    row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'activities'"
    ).fetchone()
    if row is None or "GRADE_DIRECT" in (row["sql"] or ""):
        return

    connection.commit()
    connection.execute("PRAGMA foreign_keys = OFF")
    try:
        connection.executescript(
            """
            DROP TABLE IF EXISTS activities_new;
            CREATE TABLE activities_new (
                activity_id TEXT PRIMARY KEY,
                title       TEXT NOT NULL,
                category    TEXT NOT NULL DEFAULT '',
                start_at    TEXT NOT NULL,
                location    TEXT NOT NULL,
                capacity    INTEGER NOT NULL CHECK (capacity > 0),
                policy_type TEXT NOT NULL
                    CHECK (policy_type IN ('DIRECT', 'APPROVAL', 'GRADE_DIRECT'))
            );
            INSERT INTO activities_new
                (activity_id, title, category, start_at, location, capacity, policy_type)
            SELECT activity_id, title, category, start_at, location, capacity, policy_type
            FROM activities;
            DROP TABLE activities;
            ALTER TABLE activities_new RENAME TO activities;
            """
        )
    finally:
        connection.execute("PRAGMA foreign_keys = ON")

    violations = connection.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise RuntimeError(f"activities 表迁移后发现外键异常：{violations}")


def _ensure_schema(connection: sqlite3.Connection) -> None:
    _ensure_students_columns(connection)
    _ensure_activities_policy_check(connection)


def _seed_students(connection: sqlite3.Connection) -> None:
    connection.executemany(
        "INSERT OR IGNORE INTO students (student_id, name, grade, email) "
        "VALUES (?, ?, ?, ?)",
        SEED_STUDENTS,
    )
    # 旧库迁移后为演示学生补齐年级与邮箱；只处理仍为默认邮箱的记录。
    connection.executemany(
        "UPDATE students SET grade = ?, email = ? "
        "WHERE student_id = ? AND (email = '' OR email IS NULL)",
        [(grade, email, student_id) for student_id, _name, grade, email in SEED_STUDENTS],
    )


def reset_db(database_path: Path | None = None) -> None:
    """清空所有业务表（用于测试隔离）。先确保表结构为 V2，再清空。"""
    path = Path(database_path or settings.database_path)
    with connect(path) as connection:
        connection.executescript(SCHEMA)
        _ensure_schema(connection)
        connection.executescript(
            "DELETE FROM email_logs; DELETE FROM messages; "
            "DELETE FROM registrations; DELETE FROM activities;"
        )
        _seed_students(connection)


def init_db(database_path: Path | None = None) -> None:
    """建表、执行增量迁移并写入固定演示学生账号（可重复执行）。"""
    path = Path(database_path or settings.database_path)
    with connect(path) as connection:
        connection.executescript(SCHEMA)
        _ensure_schema(connection)
        _seed_students(connection)


if __name__ == "__main__":
    init_db()
    print(f"数据库已初始化：{settings.database_path}")
