"""项目整包导入/导出（zip）。

包含：项目绑定元数据、任务列表、可选 runs、业务 sdd-loop-workflow-config、
以及不在 config 内的规则目录。
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from .config_loader import APP_CONFIG_DIR_NAME

MANIFEST_NAME = "project.manifest.json"
TEXT_SUFFIXES = {".md", ".yaml", ".yml", ".json", ".txt", ".toml", ".prompt"}
MAX_FILE_BYTES = 2_000_000
MAX_RUNS_DEFAULT = 50
MAX_RUN_LOG_LINES = 2000
# 整包导入硬上限（防止一次灌爆磁盘/内存）
MAX_PROJECT_IMPORT_BYTES = 50 * 1024 * 1024


def _safe_rel(path: Path, root: Path) -> str | None:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None


def _should_pack_file(path: Path) -> bool:
    if not path.is_file():
        return False
    if path.name.startswith("."):
        return False
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return False
    try:
        return path.stat().st_size <= MAX_FILE_BYTES
    except OSError:
        return False


def _add_dir_to_zip(
    zf: zipfile.ZipFile,
    folder: Path,
    *,
    arc_prefix: str,
) -> list[str]:
    added: list[str] = []
    if not folder.is_dir():
        return added
    for path in sorted(folder.rglob("*")):
        if not _should_pack_file(path):
            continue
        rel = _safe_rel(path, folder)
        if not rel:
            continue
        arc = f"{arc_prefix.rstrip('/')}/{rel}"
        zf.write(path, arcname=arc)
        added.append(arc)
    return added


def build_project_export_zip(
    *,
    project: dict[str, Any],
    tasks: list[dict[str, Any]],
    runs: list[dict[str, Any]] | None = None,
    app_root: Path,
    rules_dir: Path | None = None,
    include_runs: bool = False,
    max_runs: int = MAX_RUNS_DEFAULT,
) -> bytes:
    app_root = app_root.expanduser().resolve()
    config_dir = app_root / APP_CONFIG_DIR_NAME
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        packed_files: list[str] = []
        packed_files.extend(_add_dir_to_zip(zf, config_dir, arc_prefix="config"))

        extra_rules_note = ""
        if rules_dir is not None:
            rules_dir = rules_dir.expanduser().resolve()
            if rules_dir.is_dir():
                under_config = _safe_rel(rules_dir, config_dir)
                under_app = _safe_rel(rules_dir, app_root)
                if under_config is not None:
                    # 已在 config/ 内
                    extra_rules_note = f"rules already in config/{under_config}"
                elif under_app is not None:
                    packed_files.extend(
                        _add_dir_to_zip(zf, rules_dir, arc_prefix=f"app_files/{under_app}")
                    )
                    extra_rules_note = f"app_files/{under_app}"
                else:
                    packed_files.extend(
                        _add_dir_to_zip(zf, rules_dir, arc_prefix="extra_rules")
                    )
                    extra_rules_note = "extra_rules"

        runs_payload: list[dict[str, Any]] = []
        if include_runs and runs:
            for raw in runs[: max(0, max_runs)]:
                item = dict(raw)
                # 控制体积：需求正文只留预览；日志截断
                req = str(item.get("requirement") or "")
                if len(req) > 4000:
                    item["requirement"] = req[:4000]
                    item["requirement_truncated"] = True
                logs = item.get("logs") or []
                if isinstance(logs, list) and len(logs) > MAX_RUN_LOG_LINES:
                    item["logs"] = logs[-MAX_RUN_LOG_LINES:]
                    item["logs_truncated"] = True
                # 去掉过大 result 里的无关键字段可选；保留完整 result 便于回放
                runs_payload.append(item)

        manifest = {
            "format": "loop-ai-project-v1",
            "name": str(project.get("name") or "project"),
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "include_runs": bool(include_runs),
            "run_count": len(runs_payload),
            "task_count": len(tasks),
            "packed_files": packed_files,
            "extra_rules": extra_rules_note,
            "source_app_root": str(app_root),
        }
        zf.writestr(
            MANIFEST_NAME,
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        )
        zf.writestr(
            "project.json",
            json.dumps(
                {
                    "name": project.get("name") or "",
                    "docs_dir": project.get("docs_dir") or "docs",
                    "ai_rules_dir": project.get("ai_rules_dir") or "ai-rules",
                    "node_rules": project.get("node_rules") or {},
                    "source_project_id": project.get("project_id") or "",
                    "source_app_root": str(app_root),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
        )
        zf.writestr(
            "tasks.json",
            json.dumps(tasks, ensure_ascii=False, indent=2) + "\n",
        )
        if include_runs:
            zf.writestr(
                "runs.json",
                json.dumps(runs_payload, ensure_ascii=False, indent=2) + "\n",
            )
    return buffer.getvalue()


def parse_project_import_zip(data: bytes) -> dict[str, Any]:
    with zipfile.ZipFile(io.BytesIO(data), "r") as zf:
        names = zf.namelist()
        if MANIFEST_NAME not in names:
            raise ValueError(f"缺少 {MANIFEST_NAME}")
        manifest = json.loads(zf.read(MANIFEST_NAME).decode("utf-8"))
        if not isinstance(manifest, dict):
            raise ValueError("manifest 格式错误")
        fmt = str(manifest.get("format") or "")
        if fmt not in {"loop-ai-project-v1"}:
            raise ValueError(f"不支持的项目包格式: {fmt or '(empty)'}")

        project = {}
        if "project.json" in names:
            project = json.loads(zf.read("project.json").decode("utf-8"))
            if not isinstance(project, dict):
                raise ValueError("project.json 格式错误")

        tasks: list[dict[str, Any]] = []
        if "tasks.json" in names:
            raw_tasks = json.loads(zf.read("tasks.json").decode("utf-8"))
            if isinstance(raw_tasks, list):
                tasks = [t for t in raw_tasks if isinstance(t, dict)]

        runs: list[dict[str, Any]] = []
        if "runs.json" in names:
            raw_runs = json.loads(zf.read("runs.json").decode("utf-8"))
            if isinstance(raw_runs, list):
                runs = [r for r in raw_runs if isinstance(r, dict)]

        files: dict[str, bytes] = {}
        for name in names:
            if name.endswith("/"):
                continue
            if name in {MANIFEST_NAME, "project.json", "tasks.json", "runs.json"}:
                continue
            if not (
                name.startswith("config/")
                or name.startswith("extra_rules/")
                or name.startswith("app_files/")
            ):
                continue
            if ".." in Path(name).parts:
                continue
            files[name] = zf.read(name)

    return {
        "manifest": manifest,
        "project": project,
        "tasks": tasks,
        "runs": runs,
        "files": files,
    }


def write_project_pack_files(app_root: Path, files: dict[str, bytes]) -> list[str]:
    """把包内 config/extra_rules/app_files 写回目标 app_root。"""
    app_root = app_root.expanduser().resolve()
    app_root.mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    for rel, content in files.items():
        if rel.startswith("config/"):
            target = app_root / APP_CONFIG_DIR_NAME / rel[len("config/") :]
        elif rel.startswith("extra_rules/"):
            # 外部规则 → 落到业务 config/ai-rules
            target = (
                app_root
                / APP_CONFIG_DIR_NAME
                / "ai-rules"
                / rel[len("extra_rules/") :]
            )
        elif rel.startswith("app_files/"):
            target = app_root / rel[len("app_files/") :]
        else:
            continue
        try:
            rel_parts = target.resolve().relative_to(app_root.resolve()).parts
        except ValueError:
            continue
        if ".." in rel_parts:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        written.append(str(target))
    return written
