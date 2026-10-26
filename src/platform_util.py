"""运行环境平台识别（workflow 在 Python 服务端执行，以此为准）。"""

from __future__ import annotations

import sys
from pathlib import Path


def platform_key() -> str:
    if sys.platform == "darwin":
        return "darwin"
    if sys.platform.startswith("win"):
        return "windows"
    return "linux"


def platform_label() -> str:
    return {
        "darwin": "macOS",
        "windows": "Windows",
        "linux": "Linux",
    }.get(platform_key(), sys.platform)


def platform_info() -> dict[str, str | bool]:
    key = platform_key()
    return {
        "platform": key,
        "os_name": platform_label(),
        "is_mac": key == "darwin",
        "is_windows": key == "windows",
        "path_sep": "\\" if key == "windows" else "/",
    }


def resolve_prd_path(app_root: str, requirement_path: str) -> Path:
    raw = requirement_path.strip()
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = Path(app_root).expanduser().resolve() / path
    return path.resolve()
