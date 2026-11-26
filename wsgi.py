"""PythonAnywhere WSGI 入口。

FastAPI 是 ASGI 应用，PythonAnywhere Web tab 只接受 WSGI callable。
本文件用我们手写的 ASGI→WSGI 适配器把 FastAPI app 包成 WSGI。

部署步骤（PythonAnywhere）：
1. 代码目录：/home/ZYQ/24-2-_242806010229_StudyTask
2. Bash console: pip install -r requirements.prod.txt
3. Web tab → Manual configuration（Python 3.11/3.12/3.13）
4. Working directory: /home/ZYQ/24-2-_242806010229_StudyTask
5. WSGI file 里的 application = 指向本文件
6. 点 "Reload"
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# 项目根目录进 sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# 服务器上 DB 路径用绝对路径覆盖
os.environ.setdefault(
    "CAMPUS_EVENT_DB",
    str(BASE_DIR / "campus_event.db"),
)

from asgi_wsgi_adapter import ASGItoWSGIAdapter  # noqa: E402
from project.api.deps import (  # noqa: E402
    get_email_service,
    get_event_bus,
    get_notification_service,
)
from project.db import init_db  # noqa: E402
from project.main import app as asgi_app  # noqa: E402

# WSGI 模式不会触发 FastAPI 的 lifespan，这里显式完成应用启动动作。
init_db()
get_event_bus().subscribe(get_notification_service())
get_event_bus().subscribe(get_email_service())

application = ASGItoWSGIAdapter(asgi_app)
