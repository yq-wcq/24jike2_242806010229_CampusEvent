"""应用配置。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    """V1 配置：SQLite 文件库 + 单进程部署。

    database_path 由 ``CAMPUS_EVENT_DB`` 环境变量覆盖（PythonAnywhere 上用绝对路径），
    默认值基于 BASE_DIR 自动推导。
    """

    database_path: Path = Path(
        os.getenv("CAMPUS_EVENT_DB", str(BASE_DIR / "campus_event.db"))
    )
    timezone: str = os.getenv("CAMPUS_EVENT_TZ", "Asia/Shanghai")


settings = Settings()
