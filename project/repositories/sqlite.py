"""SQLite 仓储实现（评审通过后补齐）。

V1 约定：
- datetime 以 ISO 字符串（UTC→本地 Asia/Shanghai）存 TEXT 列；
- 主键 UUID 以 32 位 hex 字符串存 TEXT 列；
- 单进程短事务：``with connection:`` 自动在块尾 commit、异常时 rollback；
- 所有 SQL 走参数化占位符，不拼接字符串，杜绝 SQL 注入。
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from project.db import connect
from project.domain.enums import EmailStatus, PolicyType, RegistrationStatus
from project.domain.models import Activity, EmailLog, Message, Registration, Student
from project.repositories.interfaces import (
    ActivityRepository,
    EmailLogRepository,
    MessageRepository,
    RegistrationRepository,
    StudentRepository,
)


# ---------------------------------------------------------------------------
# 行 → 领域模型 转换
# ---------------------------------------------------------------------------

def _row_to_activity(row: sqlite3.Row) -> Activity:
    return Activity(
        activity_id=row["activity_id"],
        title=row["title"],
        category=row["category"] or "",
        start_at=datetime.fromisoformat(row["start_at"]),
        location=row["location"],
        capacity=int(row["capacity"]),
        policy_type=PolicyType(row["policy_type"]),
    )


def _row_to_registration(row: sqlite3.Row) -> Registration:
    return Registration(
        registration_id=row["registration_id"],
        activity_id=row["activity_id"],
        student_id=row["student_id"],
        status=RegistrationStatus(row["status"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _row_to_student(row: sqlite3.Row) -> Student:
    return Student(
        student_id=row["student_id"],
        name=row["name"],
        grade=int(row["grade"]),
        email=row["email"] or "",
    )


def _row_to_email_log(row: sqlite3.Row) -> EmailLog:
    return EmailLog(
        email_id=row["email_id"],
        event_id=row["event_id"],
        registration_id=row["registration_id"],
        student_id=row["student_id"],
        recipient=row["recipient"],
        subject=row["subject"],
        content=row["content"],
        status=EmailStatus(row["status"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        error=row["error"],
    )


def _row_to_message(row: sqlite3.Row) -> Message:
    return Message(
        message_id=row["message_id"],
        student_id=row["student_id"],
        activity_id=row["activity_id"],
        content=row["content"],
        created_at=datetime.fromisoformat(row["created_at"]),
        is_read=bool(row["is_read"]),
    )


# ---------------------------------------------------------------------------
# Activity 仓储
# ---------------------------------------------------------------------------

class SqliteActivityRepository(ActivityRepository):
    def __init__(self, database_path: Path) -> None:
        self._database_path = Path(database_path)

    def find_by_id(self, activity_id: str) -> Activity | None:
        with connect(self._database_path) as conn:
            row = conn.execute(
                "SELECT * FROM activities WHERE activity_id = ?", (activity_id,)
            ).fetchone()
        return _row_to_activity(row) if row else None

    def list(self, keyword: str | None = None) -> list[Activity]:
        with connect(self._database_path) as conn:
            if keyword:
                rows = conn.execute(
                    "SELECT * FROM activities WHERE title LIKE ? ORDER BY start_at DESC",
                    (f"%{keyword}%",),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM activities ORDER BY start_at DESC"
                ).fetchall()
        return [_row_to_activity(r) for r in rows]

    def save(self, activity: Activity) -> Activity:
        now_iso = datetime.now().isoformat()
        activity.activity_id = activity.activity_id or uuid4().hex
        with connect(self._database_path) as conn:
            conn.execute(
                """
                INSERT INTO activities
                    (activity_id, title, category, start_at, location, capacity, policy_type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    activity.activity_id,
                    activity.title,
                    activity.category,
                    activity.start_at.isoformat(),
                    activity.location,
                    activity.capacity,
                    activity.policy_type.value,
                ),
            )
        return activity

    def update(self, activity: Activity) -> Activity:
        with connect(self._database_path) as conn:
            conn.execute(
                """
                UPDATE activities
                SET title = ?, category = ?, start_at = ?, location = ?,
                    capacity = ?, policy_type = ?
                WHERE activity_id = ?
                """,
                (
                    activity.title,
                    activity.category,
                    activity.start_at.isoformat(),
                    activity.location,
                    activity.capacity,
                    activity.policy_type.value,
                    activity.activity_id,
                ),
            )
        return activity

    def delete(self, activity_id: str) -> None:
        with connect(self._database_path) as conn:
            conn.execute(
                "DELETE FROM activities WHERE activity_id = ?", (activity_id,)
            )


# ---------------------------------------------------------------------------
# Registration 仓储
# ---------------------------------------------------------------------------

class SqliteRegistrationRepository(RegistrationRepository):
    def __init__(self, database_path: Path) -> None:
        self._database_path = Path(database_path)

    def find_by_id(self, registration_id: str) -> Registration | None:
        with connect(self._database_path) as conn:
            row = conn.execute(
                "SELECT * FROM registrations WHERE registration_id = ?",
                (registration_id,),
            ).fetchone()
        return _row_to_registration(row) if row else None

    def find_active(self, student_id: str, activity_id: str) -> Registration | None:
        """PENDING / APPROVED 视为有效报名（B.2.4）。"""
        with connect(self._database_path) as conn:
            row = conn.execute(
                """
                SELECT * FROM registrations
                WHERE student_id = ? AND activity_id = ?
                  AND status IN ('PENDING', 'APPROVED')
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (student_id, activity_id),
            ).fetchone()
        return _row_to_registration(row) if row else None

    def exists_any_by_activity(self, activity_id: str) -> bool:
        with connect(self._database_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM registrations WHERE activity_id = ? LIMIT 1",
                (activity_id,),
            ).fetchone()
        return row is not None

    def count_approved(self, activity_id: str) -> int:
        with connect(self._database_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM registrations "
                "WHERE activity_id = ? AND status = 'APPROVED'",
                (activity_id,),
            ).fetchone()
        return int(row["c"])

    def count_pending(self, activity_id: str) -> int:
        with connect(self._database_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM registrations "
                "WHERE activity_id = ? AND status = 'PENDING'",
                (activity_id,),
            ).fetchone()
        return int(row["c"])

    def save(self, registration: Registration) -> Registration:
        registration.registration_id = registration.registration_id or uuid4().hex
        with connect(self._database_path) as conn:
            conn.execute(
                """
                INSERT INTO registrations
                    (registration_id, activity_id, student_id, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    registration.registration_id,
                    registration.activity_id,
                    registration.student_id,
                    registration.status.value,
                    registration.created_at.isoformat(),
                    registration.updated_at.isoformat(),
                ),
            )
        return registration

    def update(self, registration: Registration) -> Registration:
        with connect(self._database_path) as conn:
            conn.execute(
                """
                UPDATE registrations
                SET status = ?, updated_at = ?
                WHERE registration_id = ?
                """,
                (
                    registration.status.value,
                    registration.updated_at.isoformat(),
                    registration.registration_id,
                ),
            )
        return registration

    def list_by_student(self, student_id: str) -> list[Registration]:
        with connect(self._database_path) as conn:
            rows = conn.execute(
                "SELECT * FROM registrations WHERE student_id = ? "
                "ORDER BY created_at DESC",
                (student_id,),
            ).fetchall()
        return [_row_to_registration(r) for r in rows]

    def list_by_activity_status(
        self, activity_id: str, status: RegistrationStatus
    ) -> list[Registration]:
        with connect(self._database_path) as conn:
            rows = conn.execute(
                "SELECT * FROM registrations "
                "WHERE activity_id = ? AND status = ? "
                "ORDER BY created_at ASC",
                (activity_id, status.value),
            ).fetchall()
        return [_row_to_registration(r) for r in rows]


# ---------------------------------------------------------------------------
# Message 仓储
# ---------------------------------------------------------------------------

class SqliteMessageRepository(MessageRepository):
    def __init__(self, database_path: Path) -> None:
        self._database_path = Path(database_path)

    def save(self, message: Message) -> Message:
        message.message_id = message.message_id or uuid4().hex
        with connect(self._database_path) as conn:
            conn.execute(
                """
                INSERT INTO messages
                    (message_id, student_id, activity_id, content, created_at, is_read)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    message.message_id,
                    message.student_id,
                    message.activity_id,
                    message.content,
                    message.created_at.isoformat(),
                    1 if message.is_read else 0,
                ),
            )
        return message

    def list_by_student(self, student_id: str) -> list[Message]:
        with connect(self._database_path) as conn:
            rows = conn.execute(
                "SELECT * FROM messages WHERE student_id = ? "
                "ORDER BY created_at DESC",
                (student_id,),
            ).fetchall()
        return [_row_to_message(r) for r in rows]


# ---------------------------------------------------------------------------
# Student 仓储
# ---------------------------------------------------------------------------

class SqliteStudentRepository(StudentRepository):
    def __init__(self, database_path: Path) -> None:
        self._database_path = Path(database_path)

    def find_by_id(self, student_id: str) -> Student | None:
        with connect(self._database_path) as conn:
            row = conn.execute(
                "SELECT * FROM students WHERE student_id = ?", (student_id,)
            ).fetchone()
        return _row_to_student(row) if row else None


# ---------------------------------------------------------------------------
# EmailLog 仓储
# ---------------------------------------------------------------------------

class SqliteEmailLogRepository(EmailLogRepository):
    def __init__(self, database_path: Path) -> None:
        self._database_path = Path(database_path)

    def exists_by_event(self, event_id: str) -> bool:
        with connect(self._database_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM email_logs WHERE event_id = ? LIMIT 1", (event_id,)
            ).fetchone()
        return row is not None

    def save(self, log: EmailLog) -> EmailLog:
        log.email_id = log.email_id or uuid4().hex
        with connect(self._database_path) as conn:
            conn.execute(
                """
                INSERT INTO email_logs
                    (email_id, event_id, registration_id, student_id, recipient,
                     subject, content, status, error, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    log.email_id,
                    log.event_id,
                    log.registration_id,
                    log.student_id,
                    log.recipient,
                    log.subject,
                    log.content,
                    log.status.value,
                    log.error,
                    log.created_at.isoformat(),
                ),
            )
        return log

    def list_recent(self, limit: int = 50) -> list[EmailLog]:
        with connect(self._database_path) as conn:
            rows = conn.execute(
                "SELECT * FROM email_logs ORDER BY created_at DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [_row_to_email_log(r) for r in rows]
