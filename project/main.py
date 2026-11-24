"""FastAPI 应用入口。"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from project.api.deps import get_event_bus, get_notification_service
from project.api.routes import activities, admin, health, messages, registrations
from project.db import init_db
from project.domain.errors import BusinessError

_STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    # 观察者注册：通知服务订阅报名状态变更事件（只订阅一次）。
    get_event_bus().subscribe(get_notification_service())
    yield


async def business_error_handler(_: Request, exc: BusinessError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"code": exc.code, "message": str(exc)})


async def not_implemented_handler(_: Request, exc: NotImplementedError) -> JSONResponse:
    return JSONResponse(
        status_code=501,
        content={"code": "NOT_IMPLEMENTED", "message": str(exc) or "功能尚未实现"},
    )


def create_app() -> FastAPI:
    app = FastAPI(title="CampusEvent", version="0.1.0", lifespan=lifespan)

    @app.get("/", include_in_schema=False, response_class=HTMLResponse)
    def index() -> str:
        """可视化界面首页。"""
        return (_STATIC_DIR / "index.html").read_text(encoding="utf-8")

    app.add_exception_handler(BusinessError, business_error_handler)
    app.add_exception_handler(NotImplementedError, not_implemented_handler)
    app.include_router(health.router)
    app.include_router(activities.router)
    app.include_router(registrations.router)
    app.include_router(admin.router)
    app.include_router(messages.router)
    return app


app = create_app()
