"""把 docs/设计说明V1.md 中的 Mermaid 代码块渲染为 PNG（使用 mermaid.ink）。

用法：.venv\\Scripts\\python.exe scripts\\render_diagrams.py
"""

from __future__ import annotations

import base64
import os
import re
import sys
import time
from pathlib import Path

import httpx
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent.parent
DOC_PATH = BASE_DIR / "docs" / "设计说明V1.md"
IMAGE_DIR = BASE_DIR / "docs" / "images"
NAMES = ("uml-class-diagram", "sequence-register", "sequence-approve")


def extract_mermaid_blocks(text: str) -> list[str]:
    return re.findall(r"```mermaid\s*\n(.*?)```", text, flags=re.DOTALL)


def flatten_to_white(path: Path) -> None:
    """把透明 PNG 合成到白色背景，避免深色主题下看不清。"""
    with Image.open(path) as source:
        image = source.convert("RGBA")
    canvas = Image.new("RGBA", image.size, (255, 255, 255, 255))
    canvas.alpha_composite(image)
    # 先写临时文件再替换，避免 Windows 下覆盖被占用文件时报 Errno 22。
    temp_path = path.with_name(f"{path.stem}.tmp.png")
    canvas.convert("RGB").save(temp_path, format="PNG")
    os.replace(temp_path, path)


def render(source: str, output: Path) -> None:
    token = base64.urlsafe_b64encode(source.encode("utf-8")).decode("ascii")
    url = f"https://mermaid.ink/img/{token}?type=png&bgColor=white"
    last_error: Exception | None = None
    for attempt in range(1, 5):
        try:
            response = httpx.get(url, timeout=90.0)
            if response.status_code == 200:
                output.write_bytes(response.content)
                flatten_to_white(output)
                print(f"{output.name}: {output.stat().st_size} bytes")
                return
            last_error = RuntimeError(
                f"HTTP {response.status_code}: {response.text[:200]}"
            )
        except Exception as exc:  # 网络抖动时重试
            last_error = exc
        print(f"  第 {attempt} 次失败，重试：{last_error}")
        time.sleep(2 * attempt)
    raise RuntimeError(f"渲染失败：{output.name}，{last_error}")


def main() -> int:
    if "--flatten-only" in sys.argv:
        for path in sorted(IMAGE_DIR.glob("*.png")):
            flatten_to_white(path)
            print(f"{path.name}: 已填充白色背景")
        return 0

    blocks = extract_mermaid_blocks(DOC_PATH.read_text(encoding="utf-8"))
    if len(blocks) != len(NAMES):
        raise RuntimeError(f"预期 {len(NAMES)} 张图，实际找到 {len(blocks)} 张")
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    for source, name in zip(blocks, NAMES):
        render(source, IMAGE_DIR / f"{name}.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
