"""V1 → V2 数据库迁移脚本：备份后执行幂等迁移。

用法（项目根目录）：
    python scripts/migrate_v2.py
"""

from __future__ import annotations

import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from project.config import settings  # noqa: E402
from project.db import connect, init_db  # noqa: E402

TABLES = (
    "students",
    "activities",
    "registrations",
    "messages",
    "email_logs",
)


def _backup(database_path: Path) -> Path | None:
    if not database_path.exists():
        return None
    backup = database_path.with_name(
        f"{database_path.name}.bak-{datetime.now():%Y%m%d%H%M%S}"
    )
    shutil.copy2(database_path, backup)
    return backup


def _counts(database_path: Path) -> dict[str, int]:
    with connect(database_path) as connection:
        result = {}
        for table in TABLES:
            row = connection.execute(
                f"SELECT COUNT(*) AS c FROM {table}"
            ).fetchone()
            result[table] = int(row["c"])
        return result


def main() -> None:
    database_path = Path(settings.database_path)
    backup = _backup(database_path)
    print(f"备份：{backup}" if backup else "数据库不存在，将直接创建新库。")

    init_db()

    for table, count in _counts(database_path).items():
        print(f"{table}: {count} 行")

    with connect(database_path) as connection:
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(students)").fetchall()
        }
        activity_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'activities'"
        ).fetchone()["sql"]
    print(f"students 列：{sorted(columns)}")
    print(f"activities 支持 GRADE_DIRECT：{'GRADE_DIRECT' in activity_sql}")
    print("迁移完成。")


if __name__ == "__main__":
    try:
        main()
    except sqlite3.Error as exc:
        print(f"迁移失败：{exc}")
        raise
