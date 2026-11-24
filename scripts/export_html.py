"""把设计说明导出为图片内嵌的自包含 HTML。

用法：.venv\\Scripts\\python.exe scripts\\export_html.py
"""

from __future__ import annotations

import base64
import re
import sys
from pathlib import Path

import markdown

BASE_DIR = Path(__file__).resolve().parent.parent
DOC_NAME = sys.argv[1] if len(sys.argv) > 1 else "设计说明V1"
DOC_PATH = BASE_DIR / "docs" / f"{DOC_NAME}.md"
HTML_PATH = BASE_DIR / "docs" / f"{DOC_NAME}.html"

IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\((\./images/[^)]+)\)")
MERMAID_BLOCK = re.compile(r"```mermaid\s*\n.*?```", flags=re.DOTALL)

STYLE = """
body { margin: 0; background: #f3f4f6; color: #1f2937;
  font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", sans-serif;
  line-height: 1.75; }
main { max-width: 1180px; margin: 24px auto; background: #fff; padding: 48px 56px;
  box-shadow: 0 2px 16px rgba(0,0,0,.08); }
h1 { font-size: 28px; border-bottom: 2px solid #2563eb; padding-bottom: 12px; }
h2 { font-size: 22px; margin-top: 36px; border-left: 4px solid #2563eb; padding-left: 10px; }
h3 { font-size: 18px; margin-top: 26px; }
table { border-collapse: collapse; width: 100%; margin: 14px 0; font-size: 14px; }
th, td { border: 1px solid #d1d5db; padding: 8px 10px; text-align: left; vertical-align: top; }
th { background: #eff6ff; }
tr:nth-child(even) td { background: #f9fafb; }
img { max-width: 100%; height: auto; display: block; margin: 18px auto;
  border: 1px solid #e5e7eb; background: #fff; }
p > em { display: block; text-align: center; color: #6b7280; font-size: 13px; }
code { background: #f3f4f6; padding: 1px 5px; border-radius: 4px;
  font-family: Consolas, "Courier New", monospace; font-size: 13px; }
pre { background: #0f172a; color: #e2e8f0; padding: 14px 16px; border-radius: 6px;
  overflow-x: auto; }
pre code { background: none; color: inherit; padding: 0; }
blockquote { margin: 12px 0; padding: 8px 14px; background: #eff6ff;
  border-left: 4px solid #60a5fa; color: #1e3a8a; }
@media print {
  body { background: #fff; }
  main { max-width: none; margin: 0; padding: 24px 32px; box-shadow: none; }
  h1, h2, h3 { page-break-after: avoid; }
  img, table, pre, blockquote { page-break-inside: avoid; }
}
"""


def embed_images(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        alt, relative = match.group(1), match.group(2)
        image_path = (DOC_PATH.parent / relative).resolve()
        if not image_path.is_file():
            return match.group(0)
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        return f"![{alt}](data:image/png;base64,{encoded})"

    return IMAGE_PATTERN.sub(replace, text)


def main() -> int:
    source = DOC_PATH.read_text(encoding="utf-8")
    # HTML 版本以图片为准，隐藏 Mermaid 源码，避免重复占版面。
    source = MERMAID_BLOCK.sub("", source)
    source = embed_images(source)
    body = markdown.markdown(
        source,
        extensions=["tables", "fenced_code", "sane_lists", "toc"],
    )
    html = (
        "<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<title>实验二 {DOC_NAME}</title>\n"
        f"<style>{STYLE}</style>\n</head>\n<body>\n<main>\n"
        f"{body}\n</main>\n</body>\n</html>\n"
    )
    HTML_PATH.write_text(html, encoding="utf-8")
    print(f"已生成：{HTML_PATH}（{HTML_PATH.stat().st_size} bytes）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
