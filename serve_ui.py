#!/usr/bin/env python3
"""Launch web workbench for AI4SE workflow."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.webapp import serve_web_ui


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AI4SE workflow web workbench")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    parser.add_argument("--port", type=int, default=8787, help="Port to bind")
    args = parser.parse_args()

    project_root = Path(__file__).parent.resolve()
    dist = project_root / "webui" / "dist" / "index.html"
    if not dist.is_file():
        print(
            "提示: 未找到 webui/dist，请先执行: cd webui && npm install && npm run build",
            file=sys.stderr,
        )
    serve_web_ui(project_root, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
