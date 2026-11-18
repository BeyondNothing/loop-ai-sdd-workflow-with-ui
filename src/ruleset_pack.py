"""RuleSet 导入/导出（zip）。"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any


MANIFEST_NAME = "ruleset.manifest.json"


def build_export_zip(
    *,
    name: str,
    node_rules: dict[str, list[str]],
    folder: Path,
) -> bytes:
    folder = folder.expanduser().resolve()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        manifest = {
            "format": "loop-ai-ruleset-v1",
            "name": name,
            "node_rules": node_rules or {},
        }
        zf.writestr(MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        if folder.is_dir():
            for path in sorted(folder.rglob("*")):
                if not path.is_file():
                    continue
                if path.name.startswith("."):
                    continue
                # 只打文本规则相关文件
                if path.suffix.lower() not in {".md", ".yaml", ".yml", ".json", ".txt"}:
                    continue
                rel = path.relative_to(folder).as_posix()
                zf.write(path, arcname=f"files/{rel}")
    return buffer.getvalue()


def parse_import_zip(data: bytes) -> dict[str, Any]:
    with zipfile.ZipFile(io.BytesIO(data), "r") as zf:
        names = zf.namelist()
        if MANIFEST_NAME not in names:
            raise ValueError(f"缺少 {MANIFEST_NAME}")
        manifest = json.loads(zf.read(MANIFEST_NAME).decode("utf-8"))
        if not isinstance(manifest, dict):
            raise ValueError("manifest 格式错误")
        files: dict[str, bytes] = {}
        for name in names:
            if not name.startswith("files/") or name.endswith("/"):
                continue
            rel = name[len("files/") :]
            if not rel or ".." in Path(rel).parts:
                continue
            files[rel] = zf.read(name)
    return {
        "name": str(manifest.get("name") or "").strip() or "导入规则目录",
        "node_rules": {
            str(k): [str(item) for item in (v if isinstance(v, list) else [])]
            for k, v in (manifest.get("node_rules") or {}).items()
        },
        "files": files,
    }


def write_imported_files(folder: Path, files: dict[str, bytes]) -> list[str]:
    folder = folder.expanduser().resolve()
    folder.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for rel, content in files.items():
        target = folder / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        written.append(str(target))
    return written
