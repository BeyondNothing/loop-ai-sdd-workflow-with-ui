"""系统设置：节点 tool/model/阈值、MCP、Skill 的读写与同步。"""

from __future__ import annotations

import json
import shutil
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import yaml

from .agents.registry import list_ai_tools
from .cli import AGENT_SKILL_DIRS, SKILL_NAME, install_app_config, install_skills, skill_template_path
from .config_loader import (
    APP_CONFIG_DIR_NAME,
    APP_WORKFLOW_CONFIG_FILENAME,
    SUGGESTION_CONFIDENCE_RULES_FILENAME,
    NodeScoringRules,
    _load_scoring_rules_file,
    load_suggestion_confidence_rules,
)
from .mcp.cli_sync import ensure_mcp_for_agents
from .mcp.config import DEFAULT_SERVERS_PATH, load_cli_mcp_servers

NODE_ORDER = (
    "analyze_requirements",
    "create_plan",
    "design_test_cases",
    "review_plan",
    "split_tasks",
    "design_tech_solution",
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


def _probe_url(url: str, *, timeout: float = 3.0) -> dict[str, Any]:
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return {"ok": True, "status": int(getattr(resp, "status", 200) or 200)}
    except urllib.error.HTTPError as exc:
        # 不少 MCP HTTP 端点不支持 HEAD，4xx 也说明可达
        return {"ok": True, "status": int(exc.code), "note": "HTTPError"}
    except Exception as exc:  # noqa: BLE001
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
                return {"ok": True, "status": int(getattr(resp, "status", 200) or 200)}
        except Exception as exc2:  # noqa: BLE001
            return {"ok": False, "error": str(exc2 or exc)}


def probe_connectivity(engine_root: Path, app_root: Path) -> dict[str, Any]:
    """轻量探测：不拉起长驻 MCP 进程，只检查可执行文件/脚本/URL/Skill 文件。"""
    engine_root = engine_root.expanduser().resolve()
    app_root = app_root.expanduser().resolve()
    listed = list_mcp_servers(engine_root)
    mcp_items: list[dict[str, Any]] = []
    for server in listed.get("servers") or []:
        name = str(server.get("name") or "")
        enabled = bool(server.get("enabled", True))
        command = str(server.get("command") or "").strip()
        wrapper = str(server.get("wrapper") or "").strip()
        url = str(server.get("url") or "").strip()
        detail: dict[str, Any] = {
            "name": name,
            "enabled": enabled,
            "ok": False,
            "checks": [],
        }
        if not enabled:
            detail["ok"] = True
            detail["skipped"] = True
            detail["message"] = "已禁用，跳过"
            mcp_items.append(detail)
            continue

        all_ok = True
        if url:
            url_probe = _probe_url(url)
            detail["checks"].append({"type": "url", "target": url, **url_probe})
            all_ok = all_ok and bool(url_probe.get("ok"))
        if wrapper:
            wrapper_path = Path(wrapper)
            if not wrapper_path.is_absolute():
                wrapper_path = (engine_root / wrapper).resolve()
            exists = wrapper_path.is_file()
            detail["checks"].append(
                {
                    "type": "wrapper",
                    "target": str(wrapper_path),
                    "ok": exists,
                    "error": None if exists else "脚本不存在",
                }
            )
            all_ok = all_ok and exists
        if command:
            which = shutil.which(command)
            cmd_path = Path(command)
            ok_cmd = bool(which) or cmd_path.is_file()
            detail["checks"].append(
                {
                    "type": "command",
                    "target": which or str(cmd_path),
                    "ok": ok_cmd,
                    "error": None if ok_cmd else f"PATH 中找不到: {command}",
                }
            )
            all_ok = all_ok and ok_cmd
        if not (url or wrapper or command):
            detail["checks"].append(
                {"type": "config", "ok": False, "error": "缺少 command/wrapper/url"}
            )
            all_ok = False
        detail["ok"] = all_ok
        detail["message"] = "就绪" if all_ok else "异常"
        mcp_items.append(detail)

    # 业务根 Agent MCP 落盘情况（同步后应存在）
    agent_files = [
        app_root / ".omp" / "mcp.json",
        app_root / ".cursor" / "mcp.json",
        app_root / ".mcp.json",
    ]
    agent_sync = [
        {
            "path": str(p),
            "ok": p.is_file(),
            "message": "已同步" if p.is_file() else "未找到（可点「同步到项目」）",
        }
        for p in agent_files
    ]

    skills = list_skills(engine_root, app_root)
    skill_items: list[dict[str, Any]] = []
    template = Path(str(skills.get("template_path") or ""))
    template_ok = template.is_file()
    template_size = template.stat().st_size if template_ok else 0
    for agent in skills.get("agents") or []:
        path = Path(str(agent.get("path") or ""))
        installed = path.is_file()
        size = path.stat().st_size if installed else 0
        empty = installed and size == 0
        skill_items.append(
            {
                "agent": agent.get("agent"),
                "tool": agent.get("tool"),
                "path": str(path),
                "installed": installed,
                "ok": installed and not empty,
                "size": size,
                "stale_hint": bool(
                    installed and template_ok and size != template_size and template_size > 0
                ),
                "message": (
                    "已安装"
                    if installed and not empty
                    else ("文件为空" if empty else "未安装")
                ),
            }
        )

    mcp_ok = all(item.get("ok") for item in mcp_items) if mcp_items else True
    skill_ok = all(item.get("ok") for item in skill_items) if skill_items else False
    return {
        "app_root": str(app_root),
        "engine_root": str(engine_root),
        "mcp": {
            "ok": mcp_ok,
            "path": listed.get("path"),
            "servers": mcp_items,
            "agent_sync": agent_sync,
            "summary": (
                f"{sum(1 for i in mcp_items if i.get('ok'))}/{len(mcp_items)} 就绪"
            ),
        },
        "skills": {
            "ok": skill_ok and template_ok,
            "skill_name": skills.get("skill_name"),
            "template_exists": template_ok,
            "template_path": str(template),
            "agents": skill_items,
            "summary": (
                f"{sum(1 for i in skill_items if i.get('ok'))}/{len(skill_items)} 已安装"
            ),
        },
        "ok": mcp_ok and skill_ok and template_ok,
    }


def _serialize_scoring_rules(rules: dict[str, NodeScoringRules]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for node_id in NODE_ORDER:
        item = rules.get(node_id)
        if item is None:
            continue
        rows.append(
            {
                "node_id": node_id,
                "description": item.description or "",
                "high_confidence_rules": [
                    {"condition": r.condition, "reason": r.reason}
                    for r in item.high_confidence_rules
                ],
                "low_confidence_rules": [
                    {"condition": r.condition, "reason": r.reason}
                    for r in item.low_confidence_rules
                ],
            }
        )
    # 附带 NODE_ORDER 之外的节点
    for node_id, item in rules.items():
        if node_id in NODE_ORDER:
            continue
        rows.append(
            {
                "node_id": node_id,
                "description": item.description or "",
                "high_confidence_rules": [
                    {"condition": r.condition, "reason": r.reason}
                    for r in item.high_confidence_rules
                ],
                "low_confidence_rules": [
                    {"condition": r.condition, "reason": r.reason}
                    for r in item.low_confidence_rules
                ],
            }
        )
    return rows


def get_confidence_rules(engine_root: Path, app_root: Path) -> dict[str, Any]:
    engine_path = engine_root / "config" / SUGGESTION_CONFIDENCE_RULES_FILENAME
    business_path = _app_config_dir(app_root) / SUGGESTION_CONFIDENCE_RULES_FILENAME
    engine_rules = _load_scoring_rules_file(engine_path)
    business_rules = _load_scoring_rules_file(business_path)
    merged = load_suggestion_confidence_rules(app_root, engine_root)
    return {
        "app_root": str(app_root.resolve()),
        "engine_path": str(engine_path),
        "path": str(business_path),
        "exists": business_path.is_file(),
        "engine_nodes": _serialize_scoring_rules(engine_rules),
        "nodes": _serialize_scoring_rules(business_rules),
        "merged_nodes": _serialize_scoring_rules(merged),
        "node_order": list(NODE_ORDER),
    }


def update_confidence_rules(
    engine_root: Path,
    app_root: Path,
    nodes_payload: list[dict[str, Any]] | dict[str, Any],
) -> dict[str, Any]:
    """只写业务根 suggestion-confidence-rules.yaml（项目扩展，不改引擎基线）。"""
    ensure_project_config(engine_root, app_root)
    business_path = _app_config_dir(app_root) / SUGGESTION_CONFIDENCE_RULES_FILENAME

    items: list[Any]
    if isinstance(nodes_payload, list):
        items = nodes_payload
    elif isinstance(nodes_payload, dict):
        raw_nodes = nodes_payload.get("nodes", nodes_payload)
        if isinstance(raw_nodes, list):
            items = raw_nodes
        elif isinstance(raw_nodes, dict):
            items = [
                {"node_id": k, **(v if isinstance(v, dict) else {})}
                for k, v in raw_nodes.items()
            ]
        else:
            items = []
    else:
        items = []

    nodes_out: dict[str, Any] = {}
    for raw in items:
        if not isinstance(raw, dict):
            continue
        node_id = str(raw.get("node_id") or "").strip()
        if not node_id:
            continue
        high: list[dict[str, str]] = []
        for rule in raw.get("high_confidence_rules") or []:
            if not isinstance(rule, dict):
                continue
            condition = str(rule.get("condition") or "").strip()
            if not condition:
                continue
            high.append(
                {
                    "condition": condition,
                    "reason": str(rule.get("reason") or "").strip(),
                }
            )
        low: list[dict[str, str]] = []
        for rule in raw.get("low_confidence_rules") or []:
            if not isinstance(rule, dict):
                continue
            condition = str(rule.get("condition") or "").strip()
            if not condition:
                continue
            low.append(
                {
                    "condition": condition,
                    "reason": str(rule.get("reason") or "").strip(),
                }
            )
        entry: dict[str, Any] = {
            "description": str(raw.get("description") or "").strip(),
            "high_confidence_rules": high,
            "low_confidence_rules": low,
        }
        if entry["description"] or high or low:
            nodes_out[node_id] = entry

    _write_yaml(business_path, {"nodes": nodes_out})
    return get_confidence_rules(engine_root, app_root)
