"""ASGI → WSGI 桥接适配器。

FastAPI/Starlette 是 ASGI 应用，而 PythonAnywhere 的 Web tab
只暴露 WSGI callable。本适配器在每个 WSGI 请求里用
``asyncio.run`` 同步跑一次 ASGI app。

PythonAnywhere 单进程模型下够用；如果以后需要更好的异步支持，
可以换用 ``hypercorn`` 或 ``uvicorn`` 直接起 ASGI 服务器
（需要服务器 shell 权限，免费版通常不够）。
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any, Callable, Iterable


class ASGItoWSGIAdapter:
    """把 ASGI 3.0 app 包成 PEP 3333 WSGI callable。"""

    def __init__(self, asgi_app: Any) -> None:
        self.asgi_app = asgi_app

    # ------------------------------------------------------------------
    def __call__(self, environ: dict[str, Any], start_response: Callable) -> Iterable[bytes]:
        scope = self._build_scope(environ)
        body = self._read_body(environ)

        chunks: list[bytes] = []
        started = [False]

        async def receive() -> dict[str, Any]:
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                reason = "OK"
                status_line = f"{message['status']} {reason}"
                headers = [
                    (k.decode("latin-1"), v.decode("latin-1"))
                    for k, v in message.get("headers", [])
                ]
                start_response(status_line, headers)
                started[0] = True
            elif message["type"] == "http.response.body":
                if message.get("body"):
                    chunks.append(message["body"])

        try:
            asyncio.run(self.asgi_app(scope, receive, send))
        except Exception as exc:
            # ASGI 层未正常响应时，兜底返回 500，避免 PythonAnywhere 报 "application did not start response"
            if not started[0]:
                start_response(
                    "500 Internal Server Error",
                    [("Content-Type", "text/plain; charset=utf-8")],
                )
            chunks = [f"ASGI handler error: {exc}".encode("utf-8", errors="replace")]

        if not started[0]:
            start_response(
                "502 Bad Gateway",
                [("Content-Type", "text/plain; charset=utf-8")],
            )
            chunks = [b"ASGI app did not produce a response"]

        return chunks

    # ------------------------------------------------------------------
    @staticmethod
    def _build_scope(environ: dict[str, Any]) -> dict[str, Any]:
        protocol = environ.get("SERVER_PROTOCOL", "HTTP/1.1")
        http_version = protocol.split("/")[-1] if "/" in protocol else "1.1"

        return {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": http_version,
            "method": environ.get("REQUEST_METHOD", "GET"),
            "scheme": environ.get("wsgi.url_scheme", "http"),
            "path": environ.get("PATH_INFO", "/"),
            "raw_path": environ.get("PATH_INFO", "/").encode("latin-1"),
            "query_string": environ.get("QUERY_STRING", "").encode("latin-1"),
            "headers": ASGItoWSGIAdapter._wsgi_headers(environ),
            "server": (
                environ.get("SERVER_NAME", "localhost"),
                int(environ.get("SERVER_PORT", "80")),
            ),
            "client": None,
        }

    @staticmethod
    def _wsgi_headers(environ: dict[str, Any]) -> list[tuple[bytes, bytes]]:
        headers: list[tuple[bytes, bytes]] = []
        # Host
        host = environ.get("HTTP_HOST")
        if host:
            headers.append((b"host", host.encode("latin-1")))
        for key, value in environ.items():
            if key.startswith("HTTP_") and key != "HTTP_HOST":
                name = key[5:].replace("_", "-").lower().encode("latin-1")
                headers.append((name, value.encode("latin-1")))
            elif key == "CONTENT_TYPE" and value:
                headers.append((b"content-type", value.encode("latin-1")))
            elif key == "CONTENT_LENGTH" and value:
                headers.append((b"content-length", value.encode("latin-1")))
        return headers

    @staticmethod
    def _read_body(environ: dict[str, Any]) -> bytes:
        try:
            clen = int(environ.get("CONTENT_LENGTH", "0") or "0")
        except (TypeError, ValueError):
            clen = 0
        if clen <= 0:
            return b""
        try:
            return environ["wsgi.input"].read(clen)
        except Exception:
            return b""
