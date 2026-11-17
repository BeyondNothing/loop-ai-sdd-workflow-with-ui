"""系统设置：节点 tool/model/阈值、MCP、Skill 的读写与同步。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import yaml

from .agents.registry import list_ai_tools
from .cli import AGENT_SKILL_DIRS, SKILL_NAME, install_app_config, install_skills, skill_template_path
from .config_loader import APP_CONFIG_DIR_NAME, APP_WORKFLOW_CONFIG_FILENAME
from .mcp.cli_sync import ensure_mcp_for_agents
from .mcp.config import DEFAULT_SERVERS_PATH, load_cli_mcp_servers

NODE_ORDER = (
    "analyze_requirements",
    "create_plan",
    "design_test_cases",
    "review_plan",
    "split_tasks",
    "implement_code",
    "verify_tests",
    "ai_review",
    "commit_code",
)


def _app_config_dir(app_root: Path) -> Path:
    return app_root / APP_CONFIG_DIR_NAME


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def ensure_project_config(engine_root: Path, app_root: Path) -> list[str]:
    """确保业务根有 sdd-loop-workflow-config（缺则从引擎模板初始化）。"""
    dest = _app_config_dir(app_root)
    if dest.is_dir() and (dest / APP_WORKFLOW_CONFIG_FILENAME).is_file():
        return [f"已存在: {dest}"]
    return install_app_config(engine_root, app_root)


def get_node_runtime_config(engine_root: Path, app_root: Path) -> dict[str, Any]:
    ensure_project_config(engine_root, app_root)
    # 用临时引擎 workflow + 业务覆盖加载合并结果
    engine_cfg_path = engine_root / "config" / "workflow.yaml"
    # load_workflow_config 会按 app_root 环境？它用 config 内 app_root。
    # 这里直接读引擎文件，并把业务 app_root 写入临时不方便；改为手动合并展示。
    engine = _read_yaml(engine_cfg_path)
    engine_nodes = engine.get("nodes") or {}
    engine_defaults = engine.get("defaults") or {}
    app = _read_yaml(_app_config_dir(app_root) / APP_WORKFLOW_CONFIG_FILENAME)
    if "workflow" in app and isinstance(app["workflow"], dict):
        # 兼容误包一层
        nested = dict(app["workflow"])
        for key in ("docs_dir", "defaults", "nodes"):
            if key not in nested and key in app:
                nested[key] = app[key]
        app = nested
    app_defaults = app.get("defaults") if isinstance(app.get("defaults"), dict) else {}
    app_nodes = app.get("nodes") if isinstance(app.get("nodes"), dict) else {}

    default_tool = str(
        app_defaults.get("tool")
        or engine_defaults.get("tool")
        or "omp"
    ).strip() or "omp"
    default_model = str(app_defaults.get("model") or engine_defaults.get("model") or "").strip()

    rows: list[dict[str, Any]] = []
    for node_id in NODE_ORDER:
        eng = engine_nodes.get(node_id) if isinstance(engine_nodes.get(node_id), dict) else {}
        own = app_nodes.get(node_id) if isinstance(app_nodes.get(node_id), dict) else {}
        tool = str(
            own.get("tool") or app_defaults.get("tool") or eng.get("tool") or default_tool
        ).strip()
        model = str(
            own.get("model") if "model" in own else (
                app_defaults.get("model") if "model" in app_defaults else eng.get("model") or ""
            )
            or ""
        ).strip()
        threshold_raw = own.get("recommendation_threshold", eng.get("recommendation_threshold", 0.8))
        try:
            threshold = float(threshold_raw)
        except (TypeError, ValueError):
            threshold = 0.8
        rows.append(
            {
                "id": node_id,
                "name": str(eng.get("name") or node_id),
                "tool": tool,
                "model": model,
                "recommendation_threshold": threshold,
                "mode": str(eng.get("mode") or "headless"),
            }
        )

    return {
        "app_root": str(app_root),
        "docs_dir": str(app.get("docs_dir") or engine.get("workflow", {}).get("docs_dir") or "spec"),
        "defaults": {"tool": default_tool, "model": default_model},
        "nodes": rows,
        "available_tools": list_ai_tools(),
    }


def update_node_runtime_config(
    engine_root: Path,
    app_root: Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    ensure_project_config(engine_root, app_root)
    path = _app_config_dir(app_root) / APP_WORKFLOW_CONFIG_FILENAME
    data = _read_yaml(path)
    if "workflow" in data and isinstance(data["workflow"], dict) and "defaults" not in data:
        data = dict(data["workflow"])

    defaults = data.get("defaults") if isinstance(data.get("defaults"), dict) else {}
    incoming_defaults = payload.get("defaults") or {}
    if isinstance(incoming_defaults, dict):
        if "tool" in incoming_defaults:
            defaults["tool"] = str(incoming_defaults.get("tool") or "omp").strip() or "omp"
        if "model" in incoming_defaults:
            defaults["model"] = str(incoming_defaults.get("model") or "").strip()
    data["defaults"] = defaults

    if "docs_dir" in payload:
        data["docs_dir"] = str(payload.get("docs_dir") or data.get("docs_dir") or "spec").strip()

    nodes = data.get("nodes") if isinstance(data.get("nodes"), dict) else {}
    for item in payload.get("nodes") or []:
        if not isinstance(item, dict):
            continue
        node_id = str(item.get("id") or "").strip()
        if node_id not in NODE_ORDER:
            continue
        entry = nodes.get(node_id) if isinstance(nodes.get(node_id), dict) else {}
        if "tool" in item:
            entry["tool"] = str(item.get("tool") or "").strip()
        if "model" in item:
            entry["model"] = str(item.get("model") or "").strip()
        if "recommendation_threshold" in item:
            try:
                entry["recommendation_threshold"] = float(item.get("recommendation_threshold"))
            except (TypeError, ValueError):
                entry["recommendation_threshold"] = 0.8
        nodes[node_id] = entry
    data["nodes"] = nodes
    _write_yaml(path, data)
    return get_node_runtime_config(engine_root, app_root)


def list_mcp_servers(engine_root: Path) -> dict[str, Any]:
    path = engine_root / "config" / "mcp" / "servers.json"
    if not path.is_file():
        path = DEFAULT_SERVERS_PATH
    raw = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    servers_raw = raw.get("servers") or {}
    meta = raw.get("_meta") if isinstance(raw.get("_meta"), dict) else {}
    items: list[dict[str, Any]] = []
    for name, cfg in servers_raw.items():
        if not isinstance(cfg, dict):
            continue
        description = ""
        if isinstance(meta.get(name), str):
            description = str(meta.get(name) or "")
        elif name == "playwright":
            description = str(meta.get("note") or "")
        items.append(
            {
                "name": name,
                "enabled": cfg.get("enabled") is not False,
                "command": cfg.get("command") or "",
                "wrapper": cfg.get("wrapper") or "",
                "args": cfg.get("args") or [],
                "url": cfg.get("url") or "",
                "description": description,
            }
        )
    return {"path": str(path), "meta": meta, "servers": items}


def _mcp_config_path(engine_root: Path) -> Path:
    path = engine_root / "config" / "mcp" / "servers.json"
    return path if path.parent.is_dir() or path.is_file() else DEFAULT_SERVERS_PATH


def _load_mcp_raw(engine_root: Path) -> tuple[Path, dict[str, Any]]:
    path = _mcp_config_path(engine_root)
    raw: dict[str, Any]
    if path.is_file():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        raw = loaded if isinstance(loaded, dict) else {"servers": {}}
    else:
        raw = {"servers": {}}
    if not isinstance(raw.get("servers"), dict):
        raw["servers"] = {}
    return path, raw


def update_mcp_servers(engine_root: Path, servers: list[dict[str, Any]]) -> dict[str, Any]:
    path, raw = _load_mcp_raw(engine_root)
    existing = raw["servers"]
    for item in servers:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name or name not in existing:
            continue
        entry = dict(existing[name]) if isinstance(existing[name], dict) else {}
        if "enabled" in item:
            entry["enabled"] = bool(item.get("enabled"))
        if "args" in item and isinstance(item.get("args"), list):
            entry["args"] = item["args"]
        existing[name] = entry
    raw["servers"] = existing
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return list_mcp_servers(engine_root)


def upsert_mcp_server(engine_root: Path, server: dict[str, Any]) -> dict[str, Any]:
    """新增或覆盖一条 MCP 服务器定义。"""
    name = str(server.get("name") or "").strip()
    if not name:
        raise ValueError("name is required")
    if "/" in name or "\\" in name or name in {".", ".."}:
        raise ValueError("invalid MCP server name")

    path, raw = _load_mcp_raw(engine_root)
    existing = raw["servers"]
    prev = dict(existing[name]) if isinstance(existing.get(name), dict) else {}

    entry: dict[str, Any] = {"enabled": bool(server.get("enabled", prev.get("enabled", True)))}
    command = str(server.get("command") or "").strip()
    wrapper = str(server.get("wrapper") or "").strip()
    url = str(server.get("url") or "").strip()
    args = server.get("args") if isinstance(server.get("args"), list) else prev.get("args") or []
    args = [str(a) for a in args]

    if url:
        entry["url"] = url
    elif wrapper:
        entry["wrapper"] = wrapper
        if args:
            entry["args"] = args
    elif command:
        entry["command"] = command
        if args:
            entry["args"] = args
    else:
        # 保留原有启动方式，仅更新开关/参数
        for key in ("url", "wrapper", "command", "args"):
            if key in prev:
                entry[key] = prev[key]
        if args and "url" not in entry:
            entry["args"] = args
        if not any(k in entry for k in ("url", "wrapper", "command")):
            raise ValueError("需要提供 command / wrapper / url 之一")

    description = str(server.get("description") or "").strip()
    if description:
        meta = raw.get("_meta") if isinstance(raw.get("_meta"), dict) else {}
        meta = dict(meta)
        meta[name] = description
        raw["_meta"] = meta

    existing[name] = entry
    raw["servers"] = existing
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return list_mcp_servers(engine_root)


def delete_mcp_server(engine_root: Path, name: str) -> dict[str, Any]:
    name = str(name or "").strip()
    if not name:
        raise ValueError("name is required")
    path, raw = _load_mcp_raw(engine_root)
    existing = raw["servers"]
    if name not in existing:
        raise KeyError(f"Unknown MCP server: {name}")
    del existing[name]
    raw["servers"] = existing
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return list_mcp_servers(engine_root)


def sync_mcp_to_project(engine_root: Path, app_root: Path, *, headless: bool = False) -> dict[str, Any]:
    config_path = engine_root / "config" / "mcp" / "servers.json"
    # Playwright wrapper 在引擎仓库，以引擎根解析绝对路径
    result = ensure_mcp_for_agents(
        engine_root,
        config_path=config_path if config_path.is_file() else None,
        e2e_headless=headless,
    )
    app_result: dict[str, Any] | None = None
    if app_root.resolve() != engine_root.resolve():
        # 业务根不同：把同一套 servers（含引擎内 wrapper 绝对路径）写入业务项目 Agent 配置
        from .mcp.cli_sync import (
            _apply_playwright_headless,
            _prepare_cli_servers,
            sync_claude_mcp,
            sync_codex_mcp,
            sync_cursor_mcp,
            sync_omp_mcp,
            sync_omp_project_config,
        )

        servers = _prepare_cli_servers(
            engine_root,
            load_cli_mcp_servers(config_path if config_path.is_file() else None),
        )
        servers = _apply_playwright_headless(servers, headless=headless)
        app_result = {
            "cursor_mcp_files": [str(p) for p in sync_cursor_mcp(app_root, servers)],
            "claude_mcp_files": [str(p) for p in sync_claude_mcp(app_root, servers)],
            "codex_mcp_files": [str(p) for p in sync_codex_mcp(app_root, servers)],
            "omp_mcp_files": [str(p) for p in sync_omp_mcp(app_root, servers)],
            "omp_config_files": [str(p) for p in sync_omp_project_config(app_root)],
            "servers": list(servers.keys()),
        }
    return {
        "engine": result,
        "app": app_result,
        "active_servers": list(
            load_cli_mcp_servers(config_path if config_path.is_file() else None).keys()
        ),
    }


def list_skills(engine_root: Path, app_root: Path) -> dict[str, Any]:
    template = engine_root / "skills" / SKILL_NAME / "SKILL.md"
    installed: list[dict[str, Any]] = []
    for agent, (relative_dir, tool) in AGENT_SKILL_DIRS.items():
        skill_file = app_root / relative_dir / SKILL_NAME / "SKILL.md"
        installed.append(
            {
                "agent": agent,
                "tool": tool,
                "path": str(skill_file),
                "relative_dir": relative_dir,
                "installed": skill_file.is_file(),
            }
        )
    return {
        "skill_name": SKILL_NAME,
        "template_exists": template.is_file(),
        "template_path": str(template),
        "agents": installed,
    }


def install_project_skills(
    engine_root: Path,
    app_root: Path,
    *,
    agents: list[str] | None = None,
) -> dict[str, Any]:
    template = skill_template_path(engine_root).read_text(encoding="utf-8")
    selected = set(agents or list(AGENT_SKILL_DIRS.keys()))
    written: list[str] = []
    for agent, (relative_dir, tool) in AGENT_SKILL_DIRS.items():
        if agent not in selected and tool not in selected:
            continue
        dest = app_root / relative_dir / SKILL_NAME
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)
        skill_file = dest / "SKILL.md"
        skill_file.write_text(template.format(tool=tool), encoding="utf-8")
        written.append(str(skill_file))
    return {
        "written": written,
        "skills": list_skills(engine_root, app_root),
    }


def init_project(engine_root: Path, app_root: Path) -> dict[str, Any]:
    config_actions = install_app_config(engine_root, app_root)
    skills = install_skills(engine_root, app_root)
    mcp = sync_mcp_to_project(engine_root, app_root)
    return {
        "config_actions": config_actions,
        "skills_written": [str(p) for p in skills],
        "mcp": mcp,
        "node_config": get_node_runtime_config(engine_root, app_root),
        "skills": list_skills(engine_root, app_root),
    }
