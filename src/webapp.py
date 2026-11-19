"""Lightweight web UI backend for project binding and workflow orchestration."""

from __future__ import annotations

import io
import json
import logging
import mimetypes
import subprocess
import sys
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import yaml

from .agents import interactive_runner
from .agents.registry import DEFAULT_AI_TOOL, list_ai_tools
from .config_loader import load_workflow_config
from .mcp import ensure_mcp_for_agents
from .platform_util import platform_info, platform_label, resolve_prd_path
from . import settings_service
from .artifact_insights import build_task_insights, set_test_cases_approval
from .run_control import (
    RunCancelled,
    kill_active_processes,
    set_active_run,
    set_progress_callback,
)
from .run_events import EVENT_BUS
from .project_pack import (
    MAX_PROJECT_IMPORT_BYTES,
    build_project_export_zip,
    parse_project_import_zip,
    write_project_pack_files,
)
from .ruleset_pack import build_export_zip, parse_import_zip, write_imported_files
from .workflow import DevWorkflow

logger = logging.getLogger(__name__)

NODE_IDS = (
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


def _relative_or_absolute_rules_dir(app_root: str, resolved: Path) -> str:
    app = Path(app_root).expanduser().resolve()
    target = resolved.expanduser().resolve()
    try:
        return str(target.relative_to(app))
    except ValueError:
        return str(target)


@dataclass
class ProjectBinding:
    project_id: str
    name: str
    app_root: str
    docs_dir: str = "docs"
    ai_rules_dir: str = "ai-rules"
    node_rules: dict[str, list[str]] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "name": self.name,
            "app_root": self.app_root,
            "docs_dir": self.docs_dir,
            "ai_rules_dir": self.ai_rules_dir,
            "node_rules": self.node_rules,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ProjectBinding":
        return cls(
            project_id=str(raw["project_id"]),
            name=str(raw["name"]),
            app_root=str(raw["app_root"]),
            docs_dir=str(raw.get("docs_dir") or "docs"),
            ai_rules_dir=str(raw.get("ai_rules_dir") or "ai-rules"),
            node_rules={
                str(k): [str(item) for item in (v or [])]
                for k, v in (raw.get("node_rules") or {}).items()
            },
            created_at=str(raw.get("created_at") or datetime.now().isoformat(timespec="seconds")),
            updated_at=str(raw.get("updated_at") or datetime.now().isoformat(timespec="seconds")),
        )


@dataclass
class RuleSet:
    rule_set_id: str
    name: str
    folder_path: str
    node_rules: dict[str, list[str]] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_set_id": self.rule_set_id,
            "name": self.name,
            "folder_path": self.folder_path,
            "node_rules": self.node_rules,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "RuleSet":
        return cls(
            rule_set_id=str(raw["rule_set_id"]),
            name=str(raw.get("name") or "").strip() or "规则目录",
            folder_path=str(raw.get("folder_path") or "").strip(),
            node_rules={
                str(k): [str(item) for item in (v or [])]
                for k, v in (raw.get("node_rules") or {}).items()
            },
            created_at=str(raw.get("created_at") or datetime.now().isoformat(timespec="seconds")),
            updated_at=str(raw.get("updated_at") or datetime.now().isoformat(timespec="seconds")),
        )


@dataclass
class WorkflowRun:
    run_id: str
    project_id: str
    task_id: str = ""
    status: str = "queued"
    requirement: str = ""
    requirement_path: str = ""
    requirement_name: str = ""
    tool: str = "echo"
    skip_clarification: bool = True
    auto: bool = False
    fresh: bool = False
    headless_all_nodes: bool = True
    skip_mcp_setup: bool = False
    resume_from_node: str = ""
    single_node: bool = False
    docs_dir: str = ""
    started_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    ended_at: str = ""
    result: dict[str, Any] | None = None
    error: str = ""
    logs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "project_id": self.project_id,
            "task_id": self.task_id,
            "status": self.status,
            "requirement": self.requirement,
            "requirement_path": self.requirement_path,
            "requirement_name": self.requirement_name,
            "tool": self.tool,
            "skip_clarification": self.skip_clarification,
            "auto": self.auto,
            "fresh": self.fresh,
            "headless_all_nodes": self.headless_all_nodes,
            "skip_mcp_setup": self.skip_mcp_setup,
            "resume_from_node": self.resume_from_node,
            "single_node": self.single_node,
            "docs_dir": self.docs_dir,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "ended_at": self.ended_at,
            "result": self.result,
            "error": self.error,
            "logs": self.logs,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "WorkflowRun":
        return cls(
            run_id=str(raw["run_id"]),
            project_id=str(raw["project_id"]),
            task_id=str(raw.get("task_id") or ""),
            status=str(raw.get("status") or "queued"),
            requirement=str(raw.get("requirement") or ""),
            requirement_path=str(raw.get("requirement_path") or ""),
            requirement_name=str(raw.get("requirement_name") or ""),
            tool=str(raw.get("tool") or "echo"),
            skip_clarification=bool(raw.get("skip_clarification", True)),
            auto=bool(raw.get("auto", False)),
            fresh=bool(raw.get("fresh", False)),
            headless_all_nodes=bool(raw.get("headless_all_nodes", True)),
            skip_mcp_setup=bool(raw.get("skip_mcp_setup", False)),
            resume_from_node=str(raw.get("resume_from_node") or ""),
            single_node=bool(raw.get("single_node", False)),
            docs_dir=str(raw.get("docs_dir") or ""),
            started_at=str(raw.get("started_at") or datetime.now().isoformat(timespec="seconds")),
            updated_at=str(raw.get("updated_at") or datetime.now().isoformat(timespec="seconds")),
            ended_at=str(raw.get("ended_at") or ""),
            result=raw.get("result") if isinstance(raw.get("result"), dict) else None,
            error=str(raw.get("error") or ""),
            logs=[str(item) for item in (raw.get("logs") or [])],
        )


class WebState:
    def __init__(self, workflow_root: Path):
        self.workflow_root = workflow_root.resolve()
        self.state_dir = self.workflow_root / ".dev-workflow" / "web-ui"
        self.runtime_dir = self.state_dir / "runtime"
        self.bindings_file = self.state_dir / "bindings.json"
        self.tasks_file = self.state_dir / "tasks.json"
        self.runs_file = self.state_dir / "runs.json"
        self.rule_sets_file = self.state_dir / "rule-sets.json"
        self.system_config_file = self.state_dir / "system-config.json"
        self.bindings: dict[str, ProjectBinding] = {}
        self.tasks_by_project: dict[str, list[dict[str, Any]]] = {}
        self.runs: dict[str, WorkflowRun] = {}
        self.rule_sets: dict[str, RuleSet] = {}
        self.system_config: dict[str, Any] = {"default_tool": DEFAULT_AI_TOOL}
        self.project_run_locks: dict[str, threading.Lock] = {}
        # project_id -> 当前持有项目锁的 run_id（强制取消时可跨线程释放）
        self.project_lock_holders: dict[str, str] = {}
        self.lock = threading.Lock()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self._load_bindings()
        self._load_rule_sets()
        self._load_system_config()
        self._migrate_rule_sets_from_bindings()
        self._load_tasks()
        self._load_runs()

    def _load_bindings(self) -> None:
        if not self.bindings_file.exists():
            self.bindings = {}
            return
        raw = json.loads(self.bindings_file.read_text(encoding="utf-8"))
        self.bindings = {
            item["project_id"]: ProjectBinding.from_dict(item)
            for item in (raw if isinstance(raw, list) else [])
        }

    def _save_bindings(self) -> None:
        payload = [binding.to_dict() for binding in self.bindings.values()]
        self.bindings_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _normalize_node_rules(raw: dict[str, Any] | None) -> dict[str, list[str]]:
        if not isinstance(raw, dict):
            return {}
        normalized: dict[str, list[str]] = {}
        for node_id, rules in raw.items():
            if node_id not in NODE_IDS:
                continue
            if not isinstance(rules, list):
                continue
            cleaned = [str(item).strip() for item in rules if str(item).strip()]
            if cleaned:
                normalized[str(node_id)] = cleaned
        return normalized

    def _resolve_binding_rules_dir(self, binding: ProjectBinding) -> Path:
        rules_dir = (binding.ai_rules_dir or "ai-rules").strip()
        path = Path(rules_dir).expanduser()
        if not path.is_absolute():
            path = Path(binding.app_root) / path
        return path.resolve()

    def _load_rule_sets(self) -> None:
        if not self.rule_sets_file.exists():
            self.rule_sets = {}
            return
        raw = json.loads(self.rule_sets_file.read_text(encoding="utf-8"))
        self.rule_sets = {
            item["rule_set_id"]: RuleSet.from_dict(item)
            for item in (raw if isinstance(raw, list) else [])
            if isinstance(item, dict) and str(item.get("rule_set_id") or "").strip()
        }

    def _save_rule_sets(self) -> None:
        payload = [
            rule_set.to_dict()
            for rule_set in sorted(
                self.rule_sets.values(),
                key=lambda item: item.name.lower(),
            )
        ]
        self.rule_sets_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _migrate_rule_sets_from_bindings(self) -> None:
        changed = False
        known_paths = {item.folder_path for item in self.rule_sets.values()}
        discovered: dict[str, dict[str, Any]] = {}

        for binding in self.bindings.values():
            try:
                resolved = str(self._resolve_binding_rules_dir(binding))
            except (OSError, ValueError):
                continue
            if resolved in known_paths or resolved in discovered:
                continue
            discovered[resolved] = {
                "name": Path(resolved).name or "ai-rules",
                "node_rules": dict(binding.node_rules),
            }

        for folder_path, meta in discovered.items():
            now = datetime.now().isoformat(timespec="seconds")
            rule_set_id = uuid.uuid4().hex[:12]
            self.rule_sets[rule_set_id] = RuleSet(
                rule_set_id=rule_set_id,
                name=str(meta["name"]),
                folder_path=folder_path,
                node_rules=self._normalize_node_rules(meta["node_rules"]),
                created_at=now,
                updated_at=now,
            )
            changed = True

        if changed:
            self._save_rule_sets()

    def list_rule_sets(self) -> list[dict[str, Any]]:
        with self.lock:
            return [item.to_dict() for item in self.rule_sets.values()]

    def get_rule_set(self, rule_set_id: str) -> RuleSet:
        with self.lock:
            rule_set = self.rule_sets.get(rule_set_id)
        if rule_set is None:
            raise KeyError(f"Unknown rule_set_id: {rule_set_id}")
        return rule_set

    def create_rule_set(
        self,
        *,
        name: str,
        folder_path: str,
        node_rules: dict[str, list[str]] | None = None,
        create_folder: bool = False,
    ) -> dict[str, Any]:
        display_name = name.strip()
        if not display_name:
            raise ValueError("name is required")

        target = Path(folder_path).expanduser()
        if not target.is_absolute():
            target = (self.workflow_root / target).resolve()
        else:
            target = target.resolve()

        if create_folder:
            target.mkdir(parents=True, exist_ok=True)
        elif not target.is_dir():
            raise ValueError(f"Rule directory does not exist: {target}")

        resolved = str(target)
        with self.lock:
            for existing in self.rule_sets.values():
                if existing.folder_path == resolved:
                    raise ValueError(f"Rule directory already registered: {display_name}")

            now = datetime.now().isoformat(timespec="seconds")
            rule_set_id = uuid.uuid4().hex[:12]
            rule_set = RuleSet(
                rule_set_id=rule_set_id,
                name=display_name,
                folder_path=resolved,
                node_rules=self._normalize_node_rules(node_rules or {}),
                created_at=now,
                updated_at=now,
            )
            self.rule_sets[rule_set_id] = rule_set
            self._save_rule_sets()
            return rule_set.to_dict()

    def update_rule_set(
        self,
        rule_set_id: str,
        *,
        name: str | None = None,
        folder_path: str | None = None,
        node_rules: dict[str, list[str]] | None = None,
        create_folder: bool = False,
    ) -> dict[str, Any]:
        with self.lock:
            rule_set = self.rule_sets.get(rule_set_id)
            if rule_set is None:
                raise KeyError(f"Unknown rule_set_id: {rule_set_id}")

            old_path = rule_set.folder_path
            if name is not None:
                cleaned = name.strip()
                if not cleaned:
                    raise ValueError("name is required")
                rule_set.name = cleaned

            if folder_path is not None:
                target = Path(folder_path).expanduser()
                if not target.is_absolute():
                    target = (self.workflow_root / target).resolve()
                else:
                    target = target.resolve()
                if create_folder:
                    target.mkdir(parents=True, exist_ok=True)
                elif not target.is_dir():
                    raise ValueError(f"Rule directory does not exist: {target}")
                resolved = str(target)
                for existing in self.rule_sets.values():
                    if existing.rule_set_id != rule_set_id and existing.folder_path == resolved:
                        raise ValueError("Rule directory already registered")
                rule_set.folder_path = resolved

            if node_rules is not None:
                rule_set.node_rules = self._normalize_node_rules(node_rules)

            rule_set.updated_at = datetime.now().isoformat(timespec="seconds")
            self.rule_sets[rule_set_id] = rule_set
            self._save_rule_sets()

            if node_rules is not None or folder_path is not None:
                self._sync_projects_for_rule_set(rule_set, old_path=old_path)

            return rule_set.to_dict()

    def delete_rule_set(self, rule_set_id: str) -> None:
        with self.lock:
            if rule_set_id not in self.rule_sets:
                raise KeyError(f"Unknown rule_set_id: {rule_set_id}")
            del self.rule_sets[rule_set_id]
            self._save_rule_sets()

    def _sync_projects_for_rule_set(self, rule_set: RuleSet, *, old_path: str | None = None) -> None:
        target_path = rule_set.folder_path
        old_resolved = str(Path(old_path).expanduser().resolve()) if old_path else target_path
        bindings_changed = False

        for binding in self.bindings.values():
            try:
                current = str(self._resolve_binding_rules_dir(binding))
            except (OSError, ValueError):
                continue
            if current not in {target_path, old_resolved}:
                continue
            binding.ai_rules_dir = _relative_or_absolute_rules_dir(
                binding.app_root,
                Path(target_path),
            )
            binding.node_rules = {
                node_id: list(rules)
                for node_id, rules in rule_set.node_rules.items()
            }
            binding.updated_at = datetime.now().isoformat(timespec="seconds")
            bindings_changed = True

        if bindings_changed:
            self._save_bindings()

    def _load_system_config(self) -> None:
        if not self.system_config_file.exists():
            self.system_config = {"default_tool": DEFAULT_AI_TOOL}
            return
        raw = json.loads(self.system_config_file.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            self.system_config = {"default_tool": DEFAULT_AI_TOOL}
            return
        tool = str(raw.get("default_tool") or DEFAULT_AI_TOOL).strip() or DEFAULT_AI_TOOL
        self.system_config = {"default_tool": tool}

    def _save_system_config(self) -> None:
        self.system_config_file.write_text(
            json.dumps(self.system_config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _system_config_payload(self) -> dict[str, Any]:
        return {
            "default_tool": self.system_config.get("default_tool") or DEFAULT_AI_TOOL,
            "available_tools": list_ai_tools(),
        }

    def get_system_config(self) -> dict[str, Any]:
        with self.lock:
            return self._system_config_payload()

    def update_system_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        tool = str(payload.get("default_tool") or DEFAULT_AI_TOOL).strip() or DEFAULT_AI_TOOL
        valid_ids = {item["id"] for item in list_ai_tools()}
        if tool not in valid_ids:
            raise ValueError(f"Unknown default_tool: {tool}")

        with self.lock:
            self.system_config = {"default_tool": tool}
            self._save_system_config()
            return self._system_config_payload()

    def get_default_tool(self) -> str:
        with self.lock:
            return str(self.system_config.get("default_tool") or DEFAULT_AI_TOOL)

    def bind_rule_set(self, rule_set_id: str, project_ids: list[str]) -> list[dict[str, Any]]:
        with self.lock:
            rule_set = self.rule_sets.get(rule_set_id)
            if rule_set is None:
                raise KeyError(f"Unknown rule_set_id: {rule_set_id}")

            target = Path(rule_set.folder_path).expanduser().resolve()
            if not target.is_dir():
                raise ValueError(f"Rule directory does not exist: {target}")

            bind_set = {str(item).strip() for item in project_ids if str(item).strip()}
            updated: list[dict[str, Any]] = []

            for binding in self.bindings.values():
                try:
                    current = self._resolve_binding_rules_dir(binding)
                except (OSError, ValueError):
                    continue

                if binding.project_id in bind_set:
                    binding.ai_rules_dir = _relative_or_absolute_rules_dir(
                        binding.app_root,
                        target,
                    )
                    binding.node_rules = {
                        node_id: list(rules)
                        for node_id, rules in rule_set.node_rules.items()
                    }
                    binding.updated_at = datetime.now().isoformat(timespec="seconds")
                    updated.append(binding.to_dict())
                elif str(current) == str(target) and binding.project_id not in bind_set:
                    binding.ai_rules_dir = "ai-rules"
                    binding.node_rules = {}
                    binding.updated_at = datetime.now().isoformat(timespec="seconds")
                    updated.append(binding.to_dict())

            self._save_bindings()
            return updated

    def _load_tasks(self) -> None:
        if not self.tasks_file.exists():
            self.tasks_by_project = {}
            return
        raw = json.loads(self.tasks_file.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            self.tasks_by_project = {}
            return
        normalized: dict[str, list[dict[str, Any]]] = {}
        for project_id, tasks in raw.items():
            if not isinstance(tasks, list):
                continue
            normalized[str(project_id)] = [
                task
                for task in tasks
                if isinstance(task, dict) and str(task.get("task_id") or "").strip()
            ]
        self.tasks_by_project = normalized

    def _save_tasks(self) -> None:
        self.tasks_file.write_text(
            json.dumps(self.tasks_by_project, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _load_runs(self) -> None:
        if not self.runs_file.exists():
            self.runs = {}
            return
        raw = json.loads(self.runs_file.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            self.runs = {}
            return
        self.runs = {
            item["run_id"]: WorkflowRun.from_dict(item)
            for item in raw
            if isinstance(item, dict) and str(item.get("run_id") or "").strip()
        }

    def _save_runs(self) -> None:
        payload = [
            run.to_dict()
            for run in sorted(self.runs.values(), key=lambda item: item.started_at)
        ]
        self.runs_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def list_bindings(self) -> list[dict[str, Any]]:
        with self.lock:
            return [binding.to_dict() for binding in self.bindings.values()]

    def create_binding(
        self,
        *,
        name: str,
        app_root: str,
        docs_dir: str = "docs",
        ai_rules_dir: str = "ai-rules",
    ) -> dict[str, Any]:
        path = Path(app_root).expanduser().resolve()
        if not path.is_dir():
            raise ValueError(f"Project path does not exist: {path}")

        with self.lock:
            project_id = uuid.uuid4().hex[:12]
            now = datetime.now().isoformat(timespec="seconds")
            binding = ProjectBinding(
                project_id=project_id,
                name=name.strip() or path.name,
                app_root=str(path),
                docs_dir=docs_dir.strip() or "docs",
                ai_rules_dir=ai_rules_dir.strip() or "ai-rules",
                created_at=now,
                updated_at=now,
            )
            self.bindings[project_id] = binding
            self._save_bindings()
            return binding.to_dict()

    def update_binding(
        self,
        project_id: str,
        *,
        name: str,
        app_root: str,
        docs_dir: str,
        ai_rules_dir: str,
    ) -> dict[str, Any]:
        path = Path(app_root).expanduser().resolve()
        if not path.is_dir():
            raise ValueError(f"Project path does not exist: {path}")

        with self.lock:
            binding = self.bindings.get(project_id)
            if binding is None:
                raise KeyError(f"Unknown project_id: {project_id}")
            binding.name = name.strip() or path.name
            binding.app_root = str(path)
            binding.docs_dir = docs_dir.strip() or "docs"
            binding.ai_rules_dir = ai_rules_dir.strip() or "ai-rules"
            binding.updated_at = datetime.now().isoformat(timespec="seconds")
            self.bindings[project_id] = binding
            self._save_bindings()
            return binding.to_dict()

    def delete_binding(self, project_id: str) -> None:
        with self.lock:
            if project_id not in self.bindings:
                raise KeyError(f"Unknown project_id: {project_id}")
            del self.bindings[project_id]
            self.tasks_by_project.pop(project_id, None)
            stale_runs = [
                run_id for run_id, run in self.runs.items() if run.project_id == project_id
            ]
            for run_id in stale_runs:
                del self.runs[run_id]
            self._save_bindings()
            self._save_tasks()
            self._save_runs()

    def get_binding(self, project_id: str) -> ProjectBinding:
        with self.lock:
            binding = self.bindings.get(project_id)
        if binding is None:
            raise KeyError(f"Unknown project_id: {project_id}")
        return binding

    def update_rules(
        self,
        project_id: str,
        *,
        ai_rules_dir: str,
        node_rules: dict[str, list[str]],
    ) -> dict[str, Any]:
        with self.lock:
            binding = self.bindings.get(project_id)
            if binding is None:
                raise KeyError(f"Unknown project_id: {project_id}")
            binding.ai_rules_dir = ai_rules_dir.strip() or "ai-rules"
            binding.node_rules = {
                node_id: [item.strip() for item in rules if item.strip()]
                for node_id, rules in node_rules.items()
                if node_id in NODE_IDS
            }
            binding.updated_at = datetime.now().isoformat(timespec="seconds")
            self.bindings[project_id] = binding
            self._save_bindings()
            return binding.to_dict()

    def list_tasks(self, project_id: str) -> list[dict[str, Any]]:
        with self.lock:
            return list(self.tasks_by_project.get(project_id, []))

    def create_task(self, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            if project_id not in self.bindings:
                raise KeyError(f"Unknown project_id: {project_id}")
            now = datetime.now().isoformat(timespec="seconds")
            task = {
                "task_id": uuid.uuid4().hex,
                "task_name": str(payload.get("task_name") or "").strip(),
                "requirement_prd_path": str(payload.get("requirement_prd_path") or ""),
                "requirement_text": str(payload.get("requirement_text") or ""),
                "last_run_id": "",
                "created_at": now,
                "updated_at": now,
            }
            if not task["task_name"]:
                raise ValueError("task_name is required")
            self.tasks_by_project.setdefault(project_id, [])
            self.tasks_by_project[project_id].insert(0, task)
            self._save_tasks()
            return task

    def clone_task(
        self,
        project_id: str,
        task_id: str,
        *,
        name_suffix: str = " (副本)",
    ) -> dict[str, Any]:
        source = next(
            (
                item
                for item in self.list_tasks(project_id)
                if str(item.get("task_id")) == task_id
            ),
            None,
        )
        if source is None:
            raise KeyError(f"Unknown task_id: {task_id}")
        base_name = str(source.get("task_name") or "").strip() or "任务"
        return self.create_task(
            project_id,
            {
                "task_name": f"{base_name}{name_suffix}",
                "requirement_prd_path": str(source.get("requirement_prd_path") or ""),
                "requirement_text": str(source.get("requirement_text") or ""),
            },
        )

    def update_task(
        self, project_id: str, task_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        with self.lock:
            tasks = self.tasks_by_project.get(project_id, [])
            for idx, task in enumerate(tasks):
                if str(task.get("task_id")) != task_id:
                    continue
                updated = dict(task)
                if "task_name" in payload:
                    name = str(payload.get("task_name") or "").strip()
                    if not name:
                        raise ValueError("task_name is required")
                    updated["task_name"] = name
                if "requirement_prd_path" in payload:
                    updated["requirement_prd_path"] = str(
                        payload.get("requirement_prd_path") or ""
                    )
                if "requirement_text" in payload:
                    updated["requirement_text"] = str(
                        payload.get("requirement_text") or ""
                    )
                updated["updated_at"] = datetime.now().isoformat(timespec="seconds")
                tasks[idx] = updated
                self.tasks_by_project[project_id] = tasks
                self._save_tasks()
                return updated
        raise KeyError(f"Unknown task_id: {task_id}")

    def delete_task(self, project_id: str, task_id: str) -> None:
        with self.lock:
            tasks = self.tasks_by_project.get(project_id, [])
            updated = [task for task in tasks if str(task.get("task_id")) != task_id]
            if len(updated) == len(tasks):
                raise KeyError(f"Unknown task_id: {task_id}")
            self.tasks_by_project[project_id] = updated
            self._save_tasks()

    def set_task_last_run(self, project_id: str, task_id: str, run_id: str) -> None:
        with self.lock:
            tasks = self.tasks_by_project.get(project_id, [])
            for idx, task in enumerate(tasks):
                if str(task.get("task_id")) != task_id:
                    continue
                updated = dict(task)
                updated["last_run_id"] = run_id
                updated["updated_at"] = datetime.now().isoformat(timespec="seconds")
                tasks[idx] = updated
                self.tasks_by_project[project_id] = tasks
                self._save_tasks()
                return

    def list_runs(self) -> list[dict[str, Any]]:
        with self.lock:
            runs = sorted(self.runs.values(), key=lambda item: item.started_at, reverse=True)
            return [run.to_dict() for run in runs]

    def get_run(self, run_id: str) -> WorkflowRun:
        with self.lock:
            run = self.runs.get(run_id)
        if run is None:
            raise KeyError(f"Unknown run_id: {run_id}")
        return run

    def create_run(self, run: WorkflowRun) -> None:
        with self.lock:
            self.runs[run.run_id] = run
            self._save_runs()

    def update_run(self, run_id: str, **fields: Any) -> None:
        with self.lock:
            run = self.runs[run_id]
            for key, value in fields.items():
                setattr(run, key, value)
            run.updated_at = datetime.now().isoformat(timespec="seconds")
            self.runs[run_id] = run
            self._save_runs()
        callback = getattr(self, "on_run_changed", None)
        if callable(callback):
            callback(run_id, "update")

    def append_run_log(self, run_id: str, message: str) -> None:
        stamped = f"[{datetime.now().isoformat(timespec='seconds')}] {message}"
        with self.lock:
            run = self.runs[run_id]
            run.logs.append(stamped)
            run.updated_at = datetime.now().isoformat(timespec="seconds")
            self.runs[run_id] = run
            self._save_runs()
        callback = getattr(self, "on_run_changed", None)
        if callable(callback):
            callback(run_id, "log")

    def get_project_run_lock(self, project_id: str) -> threading.Lock:
        """Return a stable per-project lock for run serialization."""
        with self.lock:
            lock = self.project_run_locks.get(project_id)
            if lock is None:
                lock = threading.Lock()
                self.project_run_locks[project_id] = lock
            return lock

    def mark_project_lock_holder(self, project_id: str, run_id: str) -> None:
        with self.lock:
            self.project_lock_holders[project_id] = run_id

    def clear_project_lock_holder(self, project_id: str, run_id: str | None = None) -> None:
        with self.lock:
            holder = self.project_lock_holders.get(project_id)
            if holder is None:
                return
            if run_id is None or holder == run_id:
                self.project_lock_holders.pop(project_id, None)

    def force_release_project_lock(self, project_id: str, *, run_id: str | None = None) -> bool:
        """强制释放项目锁（用于「强制取消」后线程仍卡住占锁的情况）。

        threading.Lock 允许其它线程 release；释放后排队的 queued run 才能进入 running。
        """
        with self.lock:
            holder = self.project_lock_holders.get(project_id)
            if run_id is not None and holder is not None and holder != run_id:
                return False
            lock = self.project_run_locks.get(project_id)
            self.project_lock_holders.pop(project_id, None)
        if lock is None:
            return False
        released = False
        try:
            if lock.locked():
                lock.release()
                released = True
        except RuntimeError:
            released = False
        return released


class WebApp:
    def __init__(self, workflow_root: Path):
        self.workflow_root = workflow_root.resolve()
        self.static_dir = self.workflow_root / "webui"
        dist_dir = self.static_dir / "dist"
        self.assets_dir = dist_dir if dist_dir.is_dir() else self.static_dir
        self.state = WebState(self.workflow_root)
        self._workflow_config_path = self.workflow_root / "config" / "workflow.yaml"
        self._cancel_flags: dict[str, threading.Event] = {}
        self._cancel_lock = threading.Lock()
        self._workers: dict[str, threading.Thread] = {}
        self.state.on_run_changed = self._publish_run_event
        # 进程重启后，磁盘上残留的 running/cancelling 没有存活线程，启动时收尸
        self._heal_orphaned_runs(reason="server restarted")

    def _publish_run_event(self, run_id: str, event: str = "update") -> None:
        try:
            run = self.state.get_run(run_id)
        except KeyError:
            return
        EVENT_BUS.publish(
            run_id=run_id,
            project_id=run.project_id,
            event=event,
            payload=self._enriched_run_dict(run),
        )

    def _runtime_config_dir(self, project_id: str, run_id: str) -> Path:
        path = self.state.runtime_dir / project_id / run_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _resolve_rules_dir(self, project_id: str, ai_rules_dir: str | None = None) -> Path:
        binding = self.state.get_binding(project_id)
        rules_dir = (ai_rules_dir or binding.ai_rules_dir or "ai-rules").strip()
        path = Path(rules_dir).expanduser()
        if not path.is_absolute():
            path = Path(binding.app_root) / path

        return path.resolve()

    @staticmethod
    def _list_directory(path: Path, *, include_files: bool = False) -> dict[str, Any]:
        resolved = path.expanduser().resolve()
        if not resolved.exists() or not resolved.is_dir():
            raise ValueError(f"Directory does not exist: {resolved}")

        entries = list(resolved.iterdir())
        dirs = sorted(
            [{"name": item.name, "path": str(item.resolve())} for item in entries if item.is_dir()],
            key=lambda x: x["name"].lower(),
        )
        files: list[dict[str, str]] = []
        if include_files:
            files = sorted(
                [{"name": item.name, "path": str(item.resolve())} for item in entries if item.is_file()],
                key=lambda x: x["name"].lower(),
            )
        return {"path": str(resolved), "dirs": dirs, "files": files}

    def _rule_files(self, project_id: str, ai_rules_dir: str | None = None) -> dict[str, Any]:
        rules_dir = self._resolve_rules_dir(project_id, ai_rules_dir=ai_rules_dir)
        return self._rule_files_at_path(rules_dir)

    @staticmethod
    def _rule_files_at_path(rules_dir: Path) -> dict[str, Any]:
        files: list[str] = []
        if rules_dir.exists() and rules_dir.is_dir():
            files = sorted(
                [str(p.relative_to(rules_dir)) for p in rules_dir.rglob("*.md") if p.is_file()],
            )
        return {"dir": str(rules_dir), "files": files, "file_count": len(files)}

    def _task_insights(self, project_id: str, task_id: str) -> dict[str, Any]:
        binding = self.state.get_binding(project_id)
        task = next(
            (item for item in self.state.list_tasks(project_id) if item.get("task_id") == task_id),
            None,
        )
        if task is None:
            raise KeyError(f"Unknown task_id: {task_id}")

        run_docs_dir: str | None = None
        last_run_id = str(task.get("last_run_id") or "").strip()
        if last_run_id:
            try:
                run = self.state.get_run(last_run_id)
                result = run.result or {}
                if result.get("docs_dir"):
                    run_docs_dir = str(result.get("docs_dir") or "").strip() or None
            except KeyError:
                run_docs_dir = None

        insights = build_task_insights(
            binding.app_root,
            docs_base=binding.docs_dir or "docs",
            task_name=str(task.get("task_name") or ""),
            run_docs_dir=run_docs_dir,
        )
        insights["project_id"] = project_id
        insights["task_id"] = task_id
        insights["task_name"] = task.get("task_name") or ""
        return insights

    def _rule_set_system_md(self, rule_set_id: str) -> dict[str, Any]:
        rule_set = self.state.get_rule_set(rule_set_id)
        path = Path(rule_set.folder_path).expanduser().resolve() / "system.md"
        content = path.read_text(encoding="utf-8") if path.is_file() else ""
        return {
            "rule_set_id": rule_set_id,
            "path": str(path),
            "exists": path.is_file(),
            "content": content,
        }

    def _save_rule_set_system_md(self, rule_set_id: str, content: str) -> dict[str, Any]:
        rule_set = self.state.get_rule_set(rule_set_id)
        folder = Path(rule_set.folder_path).expanduser().resolve()
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "system.md"
        path.write_text(content if content.endswith("\n") else content + "\n", encoding="utf-8")
        return {
            "rule_set_id": rule_set_id,
            "path": str(path),
            "exists": True,
            "content": path.read_text(encoding="utf-8"),
        }

    def _projects_for_rule_path(self, folder_path: str) -> list[dict[str, Any]]:
        target = str(Path(folder_path).expanduser().resolve())
        projects: list[dict[str, Any]] = []
        for binding in self.state.bindings.values():
            try:
                current = str(self.state._resolve_binding_rules_dir(binding))
            except (OSError, ValueError):
                continue
            if current == target:
                projects.append(
                    {
                        "project_id": binding.project_id,
                        "name": binding.name,
                        "ai_rules_dir": binding.ai_rules_dir,
                    },
                )
        return projects

    def _enrich_rule_set(self, rule_set: RuleSet) -> dict[str, Any]:
        resolved = Path(rule_set.folder_path).expanduser().resolve()
        meta = self._rule_files_at_path(resolved)
        payload = rule_set.to_dict()
        payload.update(
            {
                "resolved_path": str(resolved),
                "ai_rules_dir": rule_set.name,
                "projects": self._projects_for_rule_path(str(resolved)),
                "file_count": meta["file_count"],
                "files": meta["files"],
                "exists": resolved.is_dir(),
            },
        )
        return payload

    def _list_rule_sets_catalog(self) -> list[dict[str, Any]]:
        items = [
            self._enrich_rule_set(rule_set)
            for rule_set in self.state.rule_sets.values()
        ]
        return sorted(items, key=lambda item: item["name"].lower())

    def _list_rule_dir_catalog(self) -> list[dict[str, Any]]:
        return self._list_rule_sets_catalog()

    def _bind_rule_dir(self, resolved_path: str, project_ids: list[str]) -> list[dict[str, Any]]:
        target = str(Path(resolved_path).expanduser().resolve())
        rule_set_id = ""
        for rule_set in self.state.rule_sets.values():
            if rule_set.folder_path == target:
                rule_set_id = rule_set.rule_set_id
                break
        if not rule_set_id:
            raise ValueError(f"Unknown rule directory: {target}")
        return self.state.bind_rule_set(rule_set_id, project_ids)

    @staticmethod
    def _send_json(handler: BaseHTTPRequestHandler, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        handler.send_response(status.value)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        handler.send_header("Pragma", "no-cache")
        handler.send_header("Expires", "0")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)

    @staticmethod
    def _send_text(
        handler: BaseHTTPRequestHandler,
        status: HTTPStatus,
        text: str,
        content_type: str = "text/plain; charset=utf-8",
    ) -> None:
        body = text.encode("utf-8")
        handler.send_response(status.value)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        handler.send_header("Pragma", "no-cache")
        handler.send_header("Expires", "0")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)

    @staticmethod
    def _send_bytes(
        handler: BaseHTTPRequestHandler,
        status: HTTPStatus,
        body: bytes,
        content_type: str,
        *,
        cache_control: str = "public, max-age=3600",
        filename: str | None = None,
    ) -> None:
        handler.send_response(status.value)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Cache-Control", cache_control)
        if filename:
            safe = filename.replace('"', "")
            handler.send_header(
                "Content-Disposition",
                f'attachment; filename="{safe}"',
            )
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)

    def export_rule_set_zip(self, rule_set_id: str) -> tuple[bytes, str]:
        rule_set = self.state.get_rule_set(rule_set_id)
        folder = Path(rule_set.folder_path).expanduser().resolve()
        data = build_export_zip(
            name=rule_set.name,
            node_rules=rule_set.node_rules,
            folder=folder,
        )
        safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in rule_set.name) or "ruleset"
        return data, f"{safe_name}.ruleset.zip"

    def export_project_zip(
        self,
        project_id: str,
        *,
        include_runs: bool = False,
        max_runs: int = 50,
    ) -> tuple[bytes, str]:
        """整包导出：项目绑定 + 任务 + 配置 + 可选 runs（默认不含 runs）。"""
        binding = self.state.get_binding(project_id)
        app_root = Path(binding.app_root).expanduser().resolve()
        try:
            rules_dir = self.state._resolve_binding_rules_dir(binding)
        except (OSError, ValueError):
            rules_dir = None
        tasks = [
            {
                "task_name": t.get("task_name") or "",
                "requirement_prd_path": t.get("requirement_prd_path") or "",
                "requirement_text": t.get("requirement_text") or "",
                "source_task_id": t.get("task_id") or "",
                "last_run_id": t.get("last_run_id") or "",
                "created_at": t.get("created_at") or "",
                "updated_at": t.get("updated_at") or "",
            }
            for t in self.state.list_tasks(project_id)
        ]
        runs_payload: list[dict[str, Any]] = []
        if include_runs:
            for item in self.state.list_runs():
                if item.get("project_id") != project_id:
                    continue
                try:
                    run = self.state.get_run(str(item["run_id"]))
                except KeyError:
                    continue
                runs_payload.append(self._enriched_run_dict(run))

        data = build_project_export_zip(
            project=binding.to_dict(),
            tasks=tasks,
            runs=runs_payload,
            app_root=app_root,
            rules_dir=rules_dir,
            include_runs=include_runs,
            max_runs=max_runs,
        )
        safe_name = (
            "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in binding.name)
            or "project"
        )
        return data, f"{safe_name}.project.zip"

    @staticmethod
    def _read_body_limited(
        handler: BaseHTTPRequestHandler,
        *,
        max_bytes: int,
    ) -> bytes:
        length = int(handler.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            raise ValueError("Content-Length is required")
        if length > max_bytes:
            raise ValueError(
                f"上传过大（{length} bytes），上限 {max_bytes // (1024 * 1024)}MB"
            )
        return handler.rfile.read(length)

    def delete_project(self, project_id: str) -> dict[str, Any]:
        """删除项目绑定/任务/runs，并清理 runtime 磁盘目录。"""
        import shutil

        self.state.delete_binding(project_id)
        runtime = self.state.runtime_dir / project_id
        cleaned = False
        if runtime.is_dir():
            shutil.rmtree(runtime, ignore_errors=True)
            cleaned = not runtime.exists()
        return {"deleted": project_id, "runtime_cleaned": cleaned}

    def import_project_zip(
        self,
        *,
        zip_bytes: bytes,
        app_root: str,
        name: str = "",
        create_app_root: bool = False,
        include_runs: bool = False,
        max_runs: int = 20,
    ) -> dict[str, Any]:
        """整包导入：写入目标 app_root 配置，新建项目绑定/任务/可选 runs。"""
        if not zip_bytes:
            raise ValueError("zip body is empty")
        if len(zip_bytes) > MAX_PROJECT_IMPORT_BYTES:
            raise ValueError(
                f"zip 过大（{len(zip_bytes)} bytes），上限 "
                f"{MAX_PROJECT_IMPORT_BYTES // (1024 * 1024)}MB"
            )
        app_root_raw = str(app_root or "").strip()
        if not app_root_raw:
            raise ValueError("app_root is required")
        app_root_path = Path(app_root_raw).expanduser().resolve()
        if not app_root_path.exists():
            if create_app_root:
                app_root_path.mkdir(parents=True, exist_ok=True)
            else:
                raise ValueError(f"app_root 不存在: {app_root_path}")
        if not app_root_path.is_dir():
            raise ValueError(f"app_root 不是目录: {app_root_path}")

        parsed = parse_project_import_zip(zip_bytes)
        project_meta = parsed.get("project") or {}
        resolved_name = str(name or project_meta.get("name") or app_root_path.name).strip()
        docs_dir = str(project_meta.get("docs_dir") or "docs").strip() or "docs"
        ai_rules_dir = str(project_meta.get("ai_rules_dir") or "ai-rules").strip() or "ai-rules"
        node_rules = project_meta.get("node_rules") or {}
        if not isinstance(node_rules, dict):
            node_rules = {}

        # 有 extra_rules 时统一落到 config/ai-rules
        files = parsed.get("files") or {}
        has_extra = any(str(k).startswith("extra_rules/") for k in files)
        if has_extra:
            ai_rules_dir = "ai-rules"

        written = write_project_pack_files(app_root_path, files)

        binding = self.state.create_binding(
            name=resolved_name,
            app_root=str(app_root_path),
            docs_dir=docs_dir,
            ai_rules_dir=ai_rules_dir,
        )
        project_id = str(binding["project_id"])
        if node_rules:
            binding = self.state.update_rules(
                project_id,
                ai_rules_dir=ai_rules_dir,
                node_rules={
                    str(k): [str(x) for x in (v if isinstance(v, list) else [])]
                    for k, v in node_rules.items()
                },
            )

        # 同步模板缺口（不覆盖已写入文件）
        try:
            self._sync_app_sdd_config(self.state.get_binding(project_id))
        except Exception:  # noqa: BLE001
            pass

        task_id_map: dict[str, str] = {}
        imported_tasks: list[dict[str, Any]] = []
        for raw_task in parsed.get("tasks") or []:
            created = self.state.create_task(
                project_id,
                {
                    "task_name": str(raw_task.get("task_name") or "导入任务").strip()
                    or "导入任务",
                    "requirement_prd_path": str(
                        raw_task.get("requirement_prd_path") or ""
                    ),
                    "requirement_text": str(raw_task.get("requirement_text") or ""),
                },
            )
            source_id = str(raw_task.get("source_task_id") or "").strip()
            if source_id:
                task_id_map[source_id] = str(created["task_id"])
            imported_tasks.append(created)

        imported_runs = 0
        run_id_map: dict[str, str] = {}
        if include_runs:
            runs_src = list(parsed.get("runs") or [])[: max(0, max_runs)]
            for raw_run in runs_src:
                old_run_id = str(raw_run.get("run_id") or "").strip()
                old_task_id = str(raw_run.get("task_id") or "").strip()
                new_task_id = task_id_map.get(old_task_id, "")
                new_run = WorkflowRun(
                    run_id=uuid.uuid4().hex,
                    project_id=project_id,
                    task_id=new_task_id,
                    status=str(raw_run.get("status") or "completed"),
                    requirement=str(raw_run.get("requirement") or ""),
                    requirement_path=str(
                        raw_run.get("requirement_path")
                        or raw_run.get("requirement_prd_path")
                        or ""
                    ),
                    requirement_name=str(raw_run.get("requirement_name") or ""),
                    tool=str(raw_run.get("tool") or self.state.get_default_tool()),
                    skip_clarification=bool(raw_run.get("skip_clarification", True)),
                    auto=bool(raw_run.get("auto", False)),
                    fresh=bool(raw_run.get("fresh", False)),
                    headless_all_nodes=bool(raw_run.get("headless_all_nodes", True)),
                    skip_mcp_setup=bool(raw_run.get("skip_mcp_setup", False)),
                    resume_from_node=str(raw_run.get("resume_from_node") or ""),
                    single_node=bool(raw_run.get("single_node", False)),
                    docs_dir=str(raw_run.get("docs_dir") or docs_dir),
                    started_at=str(
                        raw_run.get("started_at")
                        or datetime.now().isoformat(timespec="seconds")
                    ),
                    updated_at=str(
                        raw_run.get("updated_at")
                        or datetime.now().isoformat(timespec="seconds")
                    ),
                    ended_at=str(raw_run.get("ended_at") or ""),
                    result=raw_run.get("result")
                    if isinstance(raw_run.get("result"), dict)
                    else None,
                    error=str(raw_run.get("error") or ""),
                    logs=[str(x) for x in (raw_run.get("logs") or [])],
                )
                # 导入的历史 run 不应处于 running
                if new_run.status in {"queued", "running", "cancelling"}:
                    new_run.status = "cancelled"
                    new_run.error = new_run.error or "imported while active; marked cancelled"
                self.state.create_run(new_run)
                if old_run_id:
                    run_id_map[old_run_id] = new_run.run_id
                imported_runs += 1

            # 回填 task.last_run_id
            for raw_task in parsed.get("tasks") or []:
                source_id = str(raw_task.get("source_task_id") or "").strip()
                old_last = str(raw_task.get("last_run_id") or "").strip()
                new_task_id = task_id_map.get(source_id)
                new_run_id = run_id_map.get(old_last)
                if new_task_id and new_run_id:
                    self.state.set_task_last_run(project_id, new_task_id, new_run_id)

        return {
            "project": self.state.get_binding(project_id).to_dict(),
            "tasks": imported_tasks,
            "written": written,
            "file_count": len(written),
            "task_count": len(imported_tasks),
            "run_count": imported_runs,
            "include_runs": bool(include_runs),
            "zip_bytes": len(zip_bytes),
            "max_zip_bytes": MAX_PROJECT_IMPORT_BYTES,
            "manifest": parsed.get("manifest") or {},
        }

    def export_run_zip(self, run_id: str) -> tuple[bytes, str]:
        """打包 run 元数据、日志、timeline 与可读产物，便于排查/交接。"""
        import zipfile

        run = self.state.get_run(run_id)
        enriched = self._enriched_run_dict(run)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            manifest = {
                "format": "loop-ai-run-export-v1",
                "run_id": run.run_id,
                "project_id": run.project_id,
                "task_id": run.task_id,
                "status": run.status,
                "exported_at": datetime.now().isoformat(timespec="seconds"),
            }
            zf.writestr(
                "manifest.json",
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            )
            # 导出不含超长 requirement 正文时可裁切，仍保留路径与开关
            run_meta = {
                k: v
                for k, v in enriched.items()
                if k not in {"logs", "requirement"}
            }
            run_meta["requirement_preview"] = (run.requirement or "")[:2000]
            zf.writestr(
                "run.json",
                json.dumps(run_meta, ensure_ascii=False, indent=2) + "\n",
            )
            zf.writestr(
                "logs.txt",
                "\n".join(run.logs or []) + ("\n" if run.logs else ""),
            )
            zf.writestr(
                "timeline.json",
                json.dumps(enriched.get("timeline") or [], ensure_ascii=False, indent=2)
                + "\n",
            )
            zf.writestr(
                "explain.json",
                json.dumps(enriched.get("explain") or {}, ensure_ascii=False, indent=2)
                + "\n",
            )
            for node_id in NODE_IDS:
                try:
                    path = self._resolve_artifact_path(run, node_id)
                except (FileNotFoundError, KeyError, OSError, ValueError):
                    continue
                if not path.is_file():
                    continue
                # 限制单文件，避免把巨大二进制打进去
                try:
                    size = path.stat().st_size
                except OSError:
                    continue
                if size > 2_000_000:
                    zf.writestr(
                        f"artifacts/{node_id}.SKIPPED.txt",
                        f"file too large: {size} bytes\npath: {path}\n",
                    )
                    continue
                safe = "".join(
                    ch if ch.isalnum() or ch in "-_." else "_" for ch in path.name
                )
                arc = f"artifacts/{node_id}/{safe}"
                try:
                    zf.write(path, arcname=arc)
                except OSError:
                    continue

        short = run.run_id[:8] if run.run_id else "run"
        name = run.requirement_name or "run"
        safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name) or "run"
        return buffer.getvalue(), f"{safe_name}-{short}.run.zip"

    def import_rule_set_zip(self, payload: dict[str, Any]) -> dict[str, Any]:
        import base64

        raw_b64 = str(payload.get("zip_base64") or "").strip()
        if not raw_b64:
            raise ValueError("zip_base64 is required")
        try:
            raw = base64.b64decode(raw_b64)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"invalid zip_base64: {exc}") from exc
        parsed = parse_import_zip(raw)
        folder_path = str(payload.get("folder_path") or "").strip()
        if not folder_path:
            raise ValueError("folder_path is required")
        name = str(payload.get("name") or "").strip() or parsed["name"]
        create_folder = bool(payload.get("create_folder", True))
        folder = Path(folder_path).expanduser().resolve()
        if create_folder:
            folder.mkdir(parents=True, exist_ok=True)
        written = write_imported_files(folder, parsed["files"])
        created = self.state.create_rule_set(
            name=name,
            folder_path=str(folder),
            node_rules=parsed["node_rules"],
            create_folder=False,
        )
        enriched = self._enrich_rule_set(self.state.get_rule_set(created["rule_set_id"]))
        return {"rule_set": enriched, "written": written, "file_count": len(written)}

    def compare_artifact_content(
        self,
        left_id: str,
        right_id: str,
        node_id: str,
        *,
        max_chars: int = 120_000,
    ) -> dict[str, Any]:
        left = self.state.get_run(left_id)
        right = self.state.get_run(right_id)
        left_text = ""
        right_text = ""
        left_path = ""
        right_path = ""
        try:
            lp = self._resolve_artifact_path(left, node_id)
            left_text = lp.read_text(encoding="utf-8")
            left_path = str(lp)
        except (FileNotFoundError, KeyError, OSError):
            pass
        try:
            rp = self._resolve_artifact_path(right, node_id)
            right_text = rp.read_text(encoding="utf-8")
            right_path = str(rp)
        except (FileNotFoundError, KeyError, OSError):
            pass
        truncated = False
        if len(left_text) > max_chars:
            left_text = left_text[:max_chars]
            truncated = True
        if len(right_text) > max_chars:
            right_text = right_text[:max_chars]
            truncated = True
        return {
            "node_id": node_id,
            "left": {"run_id": left_id, "path": left_path, "content": left_text},
            "right": {"run_id": right_id, "path": right_path, "content": right_text},
            "same": bool(left_text) and left_text == right_text,
            "truncated": truncated,
        }

    @staticmethod
    def _read_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
        raw_len = int(handler.headers.get("Content-Length", "0") or "0")
        if raw_len <= 0:
            return {}
        data = handler.rfile.read(raw_len).decode("utf-8")
        return json.loads(data or "{}")

    @staticmethod
    def _open_path(path: Path) -> str:
        target = path.expanduser().resolve()
        if not target.exists():
            raise ValueError(f"Path does not exist: {target}")
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(target)])
        elif sys.platform.startswith("win"):
            subprocess.Popen(["cmd", "/c", "start", "", str(target)], shell=False)
        else:
            subprocess.Popen(["xdg-open", str(target)])
        return str(target)

    def _sync_app_sdd_config(self, binding: ProjectBinding) -> Path:
        """把操作台绑定的规则写入业务根 sdd-loop-workflow-config/（与引擎 loader 对齐）。"""
        from .config_loader import (
            AI_RULES_CONFIG_FILENAME,
            APP_CONFIG_DIR_NAME,
            APP_WORKFLOW_CONFIG_FILENAME,
            DEFAULT_AI_RULES_SUBDIR,
        )

        app_root = Path(binding.app_root).expanduser().resolve()
        config_dir = app_root / APP_CONFIG_DIR_NAME
        config_dir.mkdir(parents=True, exist_ok=True)

        # 首次可从引擎模板拷贝 suggestion-confidence / 示例规则
        template_dir = self.workflow_root / "config" / APP_CONFIG_DIR_NAME
        if template_dir.is_dir():
            for name in (
                "suggestion-confidence-rules.yaml",
                "ai-rules.yaml",
                APP_WORKFLOW_CONFIG_FILENAME,
            ):
                src = template_dir / name
                dst = config_dir / name
                if src.is_file() and not dst.is_file():
                    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            template_rules = template_dir / DEFAULT_AI_RULES_SUBDIR
            rules_dst = config_dir / DEFAULT_AI_RULES_SUBDIR
            if template_rules.is_dir() and not rules_dst.exists():
                import shutil

                shutil.copytree(template_rules, rules_dst)

        # 规则目录：绝对路径保留；相对路径相对 sdd-loop-workflow-config/
        rules_path = Path(binding.ai_rules_dir).expanduser()
        if rules_path.is_absolute():
            ai_rules_dir = str(rules_path.resolve())
        else:
            # 兼容旧绑定 ai-rules（相对 app_root）→ 优先落在 config 下
            under_config = config_dir / binding.ai_rules_dir
            under_app = app_root / binding.ai_rules_dir
            if under_config.is_dir() or not under_app.is_dir():
                ai_rules_dir = binding.ai_rules_dir.strip() or DEFAULT_AI_RULES_SUBDIR
            else:
                ai_rules_dir = str(under_app.resolve())

        nodes_payload: dict[str, list[str]] = {}
        for node_id, rules in (binding.node_rules or {}).items():
            cleaned = [str(item).strip() for item in rules if str(item).strip()]
            if cleaned:
                nodes_payload[str(node_id)] = cleaned

        rules_yaml = {
            "ai_rules_dir": ai_rules_dir,
            "nodes": nodes_payload,
        }
        (config_dir / AI_RULES_CONFIG_FILENAME).write_text(
            yaml.safe_dump(rules_yaml, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

        workflow_overlay = {
            "docs_dir": binding.docs_dir or "spec",
            "defaults": {"tool": "omp"},
        }
        overlay_path = config_dir / APP_WORKFLOW_CONFIG_FILENAME
        if overlay_path.is_file():
            existing = yaml.safe_load(overlay_path.read_text(encoding="utf-8")) or {}
            if isinstance(existing, dict):
                existing["docs_dir"] = binding.docs_dir or existing.get("docs_dir") or "spec"
                overlay_path.write_text(
                    yaml.safe_dump(existing, allow_unicode=True, sort_keys=False),
                    encoding="utf-8",
                )
            else:
                overlay_path.write_text(
                    yaml.safe_dump(workflow_overlay, allow_unicode=True, sort_keys=False),
                    encoding="utf-8",
                )
        else:
            overlay_path.write_text(
                yaml.safe_dump(workflow_overlay, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
        return config_dir

    def _build_runtime_configs(self, run: WorkflowRun, binding: ProjectBinding) -> Path:
        runtime_dir = self._runtime_config_dir(run.project_id, run.run_id)
        self._sync_app_sdd_config(binding)

        base_workflow = self.workflow_root / "config" / "workflow.yaml"
        workflow_raw = yaml.safe_load(base_workflow.read_text(encoding="utf-8")) or {}
        workflow_section = workflow_raw.setdefault("workflow", {})
        workflow_section["app_root"] = binding.app_root
        workflow_section["docs_dir"] = binding.docs_dir

        nodes = workflow_raw.get("nodes") or {}
        if isinstance(nodes, dict):
            for node_cfg in nodes.values():
                if isinstance(node_cfg, dict) and run.headless_all_nodes:
                    node_cfg["mode"] = "headless"

        # 本次 run 的默认工具写入业务配置 defaults（节点级 tool 优先于 defaults）
        from .config_loader import APP_CONFIG_DIR_NAME, APP_WORKFLOW_CONFIG_FILENAME

        overlay_path = (
            Path(binding.app_root).expanduser().resolve()
            / APP_CONFIG_DIR_NAME
            / APP_WORKFLOW_CONFIG_FILENAME
        )
        overlay = {}
        if overlay_path.is_file():
            overlay = yaml.safe_load(overlay_path.read_text(encoding="utf-8")) or {}
            if not isinstance(overlay, dict):
                overlay = {}
        defaults = overlay.get("defaults") if isinstance(overlay.get("defaults"), dict) else {}
        defaults["tool"] = run.tool
        overlay["defaults"] = defaults
        overlay["docs_dir"] = binding.docs_dir or overlay.get("docs_dir") or "spec"
        overlay_path.parent.mkdir(parents=True, exist_ok=True)
        overlay_path.write_text(
            yaml.safe_dump(overlay, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

        runtime_workflow = runtime_dir / "workflow.yaml"
        runtime_workflow.write_text(
            yaml.safe_dump(workflow_raw, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        return runtime_workflow

    def _cancel_event(self, run_id: str) -> threading.Event:
        with self._cancel_lock:
            event = self._cancel_flags.get(run_id)
            if event is None:
                event = threading.Event()
                self._cancel_flags[run_id] = event
            return event

    def _clear_cancel_event(self, run_id: str) -> None:
        with self._cancel_lock:
            self._cancel_flags.pop(run_id, None)

    def _worker_alive(self, run_id: str) -> bool:
        with self._cancel_lock:
            worker = self._workers.get(run_id)
        return bool(worker is not None and worker.is_alive())

    def _register_worker(self, run_id: str, worker: threading.Thread) -> None:
        with self._cancel_lock:
            self._workers[run_id] = worker

    def _unregister_worker(self, run_id: str) -> None:
        with self._cancel_lock:
            self._workers.pop(run_id, None)

    def _finalize_terminal(
        self,
        run_id: str,
        *,
        status: str,
        reason: str,
        log_message: str | None = None,
    ) -> dict[str, Any]:
        """结束无 worker 的 run：释放项目锁，写入终态（cancelled / interrupted 等）。"""
        run = self.state.get_run(run_id)
        # 强制收尸时工作线程可能仍卡在 omp/Warp，必须把项目锁让出来，否则后续全卡 queued
        if self.state.force_release_project_lock(run.project_id, run_id=run_id):
            self.state.append_run_log(
                run_id,
                "已强制释放项目锁（避免后续运行一直 queued）",
            )
        self.state.update_run(
            run_id,
            status=status,
            error=reason,
            ended_at=datetime.now().isoformat(timespec="seconds"),
        )
        self.state.append_run_log(run_id, log_message or reason)
        self._clear_cancel_event(run_id)
        self._unregister_worker(run_id)
        return self._enriched_run_dict(self.state.get_run(run_id))

    def _finalize_cancelled(
        self,
        run_id: str,
        *,
        reason: str,
        log_message: str | None = None,
    ) -> dict[str, Any]:
        return self._finalize_terminal(
            run_id,
            status="cancelled",
            reason=reason,
            log_message=log_message,
        )

    def _finalize_interrupted(
        self,
        run_id: str,
        *,
        reason: str,
        log_message: str | None = None,
    ) -> dict[str, Any]:
        """服务重启 / worker 丢失：标记中断（非用户取消），可一键续跑。"""
        return self._finalize_terminal(
            run_id,
            status="interrupted",
            reason=reason,
            log_message=log_message,
        )

    def _heal_orphaned_runs(self, *, reason: str = "orphaned run") -> int:
        """把没有存活 worker 的 queued/running/cancelling 收成 interrupted（可续跑）。

        不再标成 cancelled，避免「只是服务重启」被理解成用户取消。
        """
        healed = 0
        for item in self.state.list_runs():
            run_id = str(item.get("run_id") or "")
            status = str(item.get("status") or "")
            if status not in {"queued", "running", "cancelling"}:
                continue
            if self._worker_alive(run_id):
                continue
            self._finalize_interrupted(
                run_id,
                reason=reason,
                log_message=(
                    f"运行中断：{reason}（原状态 {status}）。"
                    "外部 Warp/omp 若仍在跑可忽略；本操作台可点「续跑/重试」从卡点继续。"
                ),
            )
            healed += 1
        if healed:
            logger.info("Interrupted %s orphaned runs (%s)", healed, reason)
        return healed

    def _acquire_project_lock(
        self,
        project_lock: threading.Lock,
        cancel_event: threading.Event,
        run_id: str,
    ) -> None:
        """可被取消打断的项目锁等待。"""
        warned = False
        while True:
            if cancel_event.is_set():
                raise RunCancelled("运行已被用户取消（等待项目锁）")
            acquired = project_lock.acquire(timeout=0.5)
            if acquired:
                # run 在 _run_workflow 里拿得到 project_id；此处用 state 回查
                try:
                    project_id = self.state.get_run(run_id).project_id
                    self.state.mark_project_lock_holder(project_id, run_id)
                except KeyError:
                    pass
                return
            if not warned:
                self.state.append_run_log(
                    run_id,
                    "Another run is active for this project, waiting for project lock",
                )
                warned = True

    def cancel_run(self, run_id: str) -> dict[str, Any]:
        run = self.state.get_run(run_id)
        if run.status not in {"queued", "running", "cancelling"}:
            raise ValueError(f"只能取消进行中的运行，当前状态: {run.status}")

        already_cancelling = run.status == "cancelling"
        self._cancel_event(run_id).set()
        killed = kill_active_processes()

        # 没有存活 worker（重启残留 / 线程已死）→ 立刻收成 cancelled，避免永远 cancelling
        if not self._worker_alive(run_id):
            return self._finalize_cancelled(
                run_id,
                reason="cancelled by user (no active worker)",
                log_message="用户取消：无存活执行线程，已立即结束",
            )

        if not already_cancelling:
            self.state.update_run(run_id, status="cancelling")
            self.state.append_run_log(
                run_id,
                f"用户请求取消：已尝试终止子进程 {killed} 个，等待工作线程退出",
            )
        else:
            self.state.append_run_log(
                run_id,
                f"用户再次请求取消（强杀子进程 {killed} 个）",
            )

        # Warp 等待等场景常无注册子进程：短等协作退出，再点取消则强制收尸
        if killed == 0:
            with self._cancel_lock:
                worker = self._workers.get(run_id)
            if worker is not None and worker.is_alive():
                worker.join(timeout=2.5)
            if not self._worker_alive(run_id):
                return self._finalize_cancelled(
                    run_id,
                    reason="cancelled by user",
                    log_message="用户取消：工作线程已退出",
                )
            if already_cancelling:
                return self._finalize_cancelled(
                    run_id,
                    reason="cancelled by user (forced, no subprocess)",
                    log_message="用户再次取消：无子进程可杀且线程未退出，已强制结束",
                )

        return self._enriched_run_dict(self.state.get_run(run_id))

    def _resolve_resume_node(self, source: WorkflowRun, requested: str = "") -> str:
        """解析可续跑节点；过滤 oh_my_pi 等工具名污染。"""
        valid = set(NODE_IDS) | {"parallel_plan_and_tests"}
        requested = (requested or "").strip()
        if requested in valid:
            return requested

        result = source.result if isinstance(source.result, dict) else {}
        candidates = [
            requested,
            str(result.get("current_node") or "").strip(),
            str(source.resume_from_node or "").strip(),
        ]
        # 时间线最后一次 enter 的真实节点
        for ev in reversed(list(result.get("timeline") or [])):
            if not isinstance(ev, dict):
                continue
            if ev.get("event") != "enter":
                continue
            nid = str(ev.get("node_id") or "").strip()
            if nid in valid:
                candidates.append(nid)
                break
        # 已完成节点的下一个
        done = {str(x) for x in (result.get("completed_nodes") or [])}
        for node_id in NODE_IDS:
            if node_id not in done:
                candidates.append(node_id)
                break

        for cand in candidates:
            if cand in valid:
                return cand
        return ""

    def retry_run(
        self,
        run_id: str,
        *,
        fresh: bool = False,
        resume_from_node: str = "",
        single_node: bool = False,
    ) -> dict[str, Any]:
        """基于历史 run 新建一次执行；默认续跑（复用 docs），fresh=True 清空产物重来。"""
        source = self.state.get_run(run_id)
        if source.status in {"queued", "running", "cancelling"}:
            raise ValueError("进行中的运行不能重试，请先取消")
        stuck = ""
        if not fresh:
            stuck = self._resolve_resume_node(source, resume_from_node)
        payload = {
            "project_id": source.project_id,
            "task_id": source.task_id,
            "requirement_name": source.requirement_name,
            "requirement": source.requirement,
            "requirement_prd_path": source.requirement_path,
            "tool": source.tool,
            "skip_clarification": source.skip_clarification,
            "auto": source.auto,
            "fresh": fresh,
            "headless_all_nodes": source.headless_all_nodes,
            "skip_mcp_setup": source.skip_mcp_setup,
            "resume_from_node": stuck if not fresh else "",
            "single_node": single_node,
            "source_run_id": source.run_id,
        }
        return self.start_run(payload)

    @staticmethod
    def _normalize_resume_node(node_id: str, *, single_node: bool) -> str:
        node = (node_id or "").strip()
        if not node:
            return ""
        valid = set(NODE_IDS) | {"parallel_plan_and_tests"}
        if node not in valid:
            # 拒绝工具名等脏数据（如 oh_my_pi）
            return ""
        if single_node:
            return node
        # 续跑整图：plan/test 并行入口统一为 parallel_plan_and_tests
        if node in {"create_plan", "design_test_cases"}:
            return "parallel_plan_and_tests"
        return node

    def clone_task(
        self,
        project_id: str,
        task_id: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        suffix = str((payload or {}).get("name_suffix") or " (副本)")
        return self.state.clone_task(project_id, task_id, name_suffix=suffix)

    def project_health(self, project_id: str) -> dict[str, Any]:
        import shutil

        binding = self.state.get_binding(project_id)
        app_root = Path(binding.app_root).expanduser().resolve()
        docs_path = app_root / (binding.docs_dir or "docs")
        rules_path = Path(binding.ai_rules_dir).expanduser()
        if not rules_path.is_absolute():
            under_config = app_root / "sdd-loop-workflow-config" / binding.ai_rules_dir
            under_app = app_root / binding.ai_rules_dir
            rules_path = under_config if under_config.is_dir() else under_app
        omp_cfg = app_root / ".omp"
        engine_omp = self.workflow_root / ".omp"

        checks: list[dict[str, Any]] = []

        def add(
            key: str,
            ok: bool,
            *,
            message: str,
            fixable: bool = False,
            level: str = "error",
        ) -> None:
            checks.append(
                {
                    "key": key,
                    "ok": ok,
                    "level": "ok" if ok else level,
                    "message": message,
                    "fixable": fixable and not ok,
                }
            )

        add(
            "app_root",
            app_root.is_dir(),
            message=f"项目根存在: {app_root}" if app_root.is_dir() else f"项目根不存在: {app_root}",
        )
        add(
            "docs_dir",
            docs_path.is_dir() or app_root.is_dir(),
            message=(
                f"文档目录就绪: {docs_path}"
                if docs_path.is_dir()
                else f"文档目录将在首次运行创建: {docs_path}"
            ),
            fixable=True,
            level="warn",
        )
        add(
            "ai_rules",
            rules_path.is_dir(),
            message=(
                f"规则目录存在: {rules_path}"
                if rules_path.is_dir()
                else f"规则目录缺失: {rules_path}"
            ),
            fixable=True,
        )
        add(
            "omp_app",
            omp_cfg.exists(),
            message=(
                f"业务根 .omp 已配置: {omp_cfg}"
                if omp_cfg.exists()
                else f"业务根缺少 .omp（MCP）: {omp_cfg}"
            ),
            fixable=True,
        )
        add(
            "omp_engine",
            engine_omp.exists(),
            message=(
                f"引擎 .omp 已配置: {engine_omp}"
                if engine_omp.exists()
                else f"引擎缺少 .omp: {engine_omp}"
            ),
            fixable=True,
            level="warn",
        )
        omp_bin = shutil.which("omp")
        add(
            "omp_cli",
            bool(omp_bin),
            message=f"omp CLI: {omp_bin}" if omp_bin else "PATH 中找不到 omp",
            level="warn",
        )
        sensitive = False
        try:
            from .agents.interactive_runner import _is_tcc_sensitive_path

            sensitive = bool(_is_tcc_sensitive_path(app_root))
        except Exception:  # noqa: BLE001
            sensitive = False
        add(
            "tcc_path",
            not sensitive,
            message=(
                "项目路径不在 Downloads/Desktop/Documents"
                if not sensitive
                else "项目在 Downloads/Desktop/Documents，Warp/omp 可能 EPERM（见 README）"
            ),
            level="warn",
        )

        ok_count = sum(1 for c in checks if c["ok"])
        fixable_count = sum(1 for c in checks if c.get("fixable"))
        return {
            "project_id": project_id,
            "app_root": str(app_root),
            "checks": checks,
            "ok": all(c["ok"] or c.get("level") == "warn" for c in checks if c["key"] != "tcc_path")
            and all(c["ok"] for c in checks if c["key"] in {"app_root"}),
            "summary": f"{ok_count}/{len(checks)} 通过，{fixable_count} 项可一键修",
            "fixable_count": fixable_count,
        }

    def fix_project_health(self, project_id: str) -> dict[str, Any]:
        binding = self.state.get_binding(project_id)
        app_root = Path(binding.app_root).expanduser().resolve()
        if not app_root.is_dir():
            raise ValueError(f"项目根不存在，无法修复: {app_root}")

        actions: list[str] = []
        docs_path = app_root / (binding.docs_dir or "docs")
        if not docs_path.exists():
            docs_path.mkdir(parents=True, exist_ok=True)
            actions.append(f"创建 docs: {docs_path}")

        try:
            self._sync_app_sdd_config(binding)
            actions.append("同步 sdd-loop-workflow-config / 规则模板")
        except Exception as exc:  # noqa: BLE001
            actions.append(f"同步配置失败: {exc}")

        try:
            init_result = settings_service.init_project(self.workflow_root, app_root)
            actions.append(
                "init_project: "
                f"skills={len(init_result.get('skills_written') or [])}, "
                f"mcp={bool(init_result.get('mcp'))}"
            )
        except Exception as exc:  # noqa: BLE001
            actions.append(f"init_project 失败: {exc}")

        try:
            ensure_mcp_for_agents(self.workflow_root, e2e_headless=True)
            actions.append("补齐引擎 .omp MCP")
        except Exception as exc:  # noqa: BLE001
            actions.append(f"引擎 MCP 失败: {exc}")
        try:
            ensure_mcp_for_agents(app_root, e2e_headless=True)
            actions.append("补齐业务根 .omp MCP")
        except Exception as exc:  # noqa: BLE001
            actions.append(f"业务根 MCP 失败: {exc}")

        health = self.project_health(project_id)
        health["actions"] = actions
        return health

    def create_project_wizard(self, payload: dict[str, Any]) -> dict[str, Any]:
        """新建项目向导：可选建目录、自动 bootstrap、可选绑定 RuleSet。"""
        name = str(payload.get("name") or "").strip()
        app_root_raw = str(payload.get("app_root") or "").strip()
        docs_dir = str(payload.get("docs_dir") or "docs")
        ai_rules_dir = str(payload.get("ai_rules_dir") or "ai-rules")
        create_app_root = bool(payload.get("create_app_root", False))
        bootstrap = bool(payload.get("bootstrap", True))
        rule_set_id = str(payload.get("rule_set_id") or "").strip()

        if not app_root_raw:
            raise ValueError("app_root is required")
        app_path = Path(app_root_raw).expanduser().resolve()
        actions: list[str] = []
        if not app_path.is_dir():
            if not create_app_root:
                raise ValueError(f"Project path does not exist: {app_path}")
            app_path.mkdir(parents=True, exist_ok=True)
            actions.append(f"创建 app_root: {app_path}")

        binding = self.state.create_binding(
            name=name,
            app_root=str(app_path),
            docs_dir=docs_dir,
            ai_rules_dir=ai_rules_dir,
        )
        project_id = str(binding["project_id"])

        if rule_set_id:
            try:
                self.state.bind_rule_set(rule_set_id, [project_id])
                binding = self.state.get_binding(project_id).to_dict()
                actions.append(f"绑定 RuleSet: {rule_set_id}")
            except Exception as exc:  # noqa: BLE001
                actions.append(f"绑定 RuleSet 失败: {exc}")

        bootstrap_result: dict[str, Any] | None = None
        if bootstrap:
            try:
                # 复用健康修复路径：sync 配置 + init + MCP
                health = self.fix_project_health(project_id)
                bootstrap_result = {
                    "ok": bool(health.get("ok")),
                    "summary": health.get("summary"),
                    "actions": health.get("actions") or [],
                }
                actions.extend(list(health.get("actions") or []))
            except Exception as exc:  # noqa: BLE001
                bootstrap_result = {"ok": False, "error": str(exc)}
                actions.append(f"bootstrap 失败: {exc}")

        return {
            "project": binding,
            "bootstrap": bootstrap_result,
            "actions": actions,
            "created_app_root": create_app_root and ("创建 app_root" in " ".join(actions)),
        }

    def run_metrics(
        self,
        *,
        days: int = 7,
        project_id: str = "",
    ) -> dict[str, Any]:
        """聚合近 N 日 run：状态分布、耗时分位、卡点节点。"""
        days = max(1, min(90, int(days or 7)))
        cutoff = datetime.now().timestamp() - days * 86400
        project_id = (project_id or "").strip()

        def _parse_ts(value: str) -> float | None:
            text = (value or "").strip()
            if not text:
                return None
            try:
                return datetime.fromisoformat(text).timestamp()
            except ValueError:
                return None

        def _percentile(sorted_vals: list[float], p: float) -> float | None:
            if not sorted_vals:
                return None
            if len(sorted_vals) == 1:
                return round(sorted_vals[0], 1)
            k = (len(sorted_vals) - 1) * p
            f = int(k)
            c = min(f + 1, len(sorted_vals) - 1)
            if f == c:
                return round(sorted_vals[f], 1)
            return round(sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f), 1)

        status_counts: dict[str, int] = {}
        durations: list[float] = []
        stuck_counter: dict[str, int] = {}
        daily: dict[str, dict[str, int]] = {}
        sample_runs: list[dict[str, Any]] = []
        total = 0

        for item in self.state.list_runs():
            if project_id and str(item.get("project_id") or "") != project_id:
                continue
            started = _parse_ts(str(item.get("started_at") or ""))
            if started is None or started < cutoff:
                continue
            total += 1
            status = str(item.get("status") or "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

            day_key = str(item.get("started_at") or "")[:10] or "unknown"
            bucket = daily.setdefault(
                day_key,
                {
                    "total": 0,
                    "completed": 0,
                    "failed": 0,
                    "cancelled": 0,
                    "interrupted": 0,
                },
            )
            bucket["total"] += 1
            if status in bucket:
                bucket[status] += 1

            ended = _parse_ts(str(item.get("ended_at") or "")) or _parse_ts(
                str(item.get("updated_at") or "")
            )
            duration_ms: float | None = None
            if started is not None and ended is not None and ended >= started:
                duration_ms = (ended - started) * 1000.0
                if status in {"completed", "failed", "cancelled", "interrupted"}:
                    durations.append(duration_ms)

            result = item.get("result") if isinstance(item.get("result"), dict) else {}
            stuck = str((result or {}).get("current_node") or "").strip()
            if status in {"failed", "cancelled", "cancelling", "interrupted"} and stuck:
                stuck_counter[stuck] = stuck_counter.get(stuck, 0) + 1

            sample_runs.append(
                {
                    "run_id": item.get("run_id"),
                    "project_id": item.get("project_id"),
                    "task_id": item.get("task_id"),
                    "status": status,
                    "started_at": item.get("started_at"),
                    "ended_at": item.get("ended_at") or "",
                    "duration_ms": round(duration_ms, 1) if duration_ms is not None else None,
                    "stuck_node": stuck
                    if status in {"failed", "cancelled", "interrupted"}
                    else "",
                    "tool": item.get("tool"),
                }
            )

        durations_sorted = sorted(durations)
        failed = (
            status_counts.get("failed", 0)
            + status_counts.get("cancelled", 0)
            + status_counts.get("interrupted", 0)
        )
        terminal = (
            status_counts.get("completed", 0)
            + failed
            + status_counts.get("cancelling", 0)
        )
        fail_rate = round(failed / terminal, 4) if terminal else 0.0
        stuck_nodes = [
            {"node_id": node_id, "count": count}
            for node_id, count in sorted(
                stuck_counter.items(), key=lambda kv: (-kv[1], kv[0])
            )
        ]
        daily_series = [
            {"date": day, **counts}
            for day, counts in sorted(daily.items(), key=lambda kv: kv[0])
        ]
        sample_runs.sort(key=lambda r: str(r.get("started_at") or ""), reverse=True)

        return {
            "days": days,
            "project_id": project_id or None,
            "total": total,
            "status_counts": status_counts,
            "fail_rate": fail_rate,
            "duration_ms": {
                "count": len(durations_sorted),
                "avg": round(sum(durations_sorted) / len(durations_sorted), 1)
                if durations_sorted
                else None,
                "p50": _percentile(durations_sorted, 0.5),
                "p95": _percentile(durations_sorted, 0.95),
                "max": round(durations_sorted[-1], 1) if durations_sorted else None,
            },
            "stuck_nodes": stuck_nodes,
            "daily": daily_series,
            "recent_runs": sample_runs[:30],
        }

    def task_priority_board(self, project_id: str = "") -> dict[str, Any]:
        """跨任务优先级：卡住 / 待确认 / 可发布 / 运行中 / 其他。"""
        buckets: dict[str, list[dict[str, Any]]] = {
            "stuck": [],
            "awaiting": [],
            "ready": [],
            "running": [],
            "other": [],
        }
        projects = (
            [self.state.get_binding(project_id).to_dict()]
            if project_id
            else self.state.list_bindings()
        )
        for proj in projects:
            pid = str(proj.get("project_id") or "")
            for task in self.state.list_tasks(pid):
                tid = str(task.get("task_id") or "")
                last_run_id = str(task.get("last_run_id") or "").strip()
                run_status = ""
                stuck_node = ""
                error = ""
                if last_run_id:
                    try:
                        run = self.state.get_run(last_run_id)
                        run_status = run.status
                        stuck_node = str((run.result or {}).get("current_node") or "")
                        error = run.error or ""
                    except KeyError:
                        run_status = ""
                qa_status = "missing"
                try:
                    insights = self._task_insights(pid, tid)
                    qa_status = str(
                        ((insights.get("qa_review") or {}).get("status")) or "missing"
                    )
                    conf = insights.get("release_confidence") or {}
                except Exception:  # noqa: BLE001
                    conf = {}

                item = {
                    "project_id": pid,
                    "project_name": proj.get("name") or "",
                    "task_id": tid,
                    "task_name": task.get("task_name") or "",
                    "last_run_id": last_run_id,
                    "run_status": run_status,
                    "stuck_node": stuck_node,
                    "error": (error or "")[:200],
                    "qa_status": qa_status,
                    "confidence": conf.get("score"),
                    "reached_0_8": conf.get("reached_0_8"),
                }
                if run_status in {"queued", "running", "cancelling"}:
                    buckets["running"].append(item)
                elif run_status in {"failed", "cancelled", "interrupted"}:
                    buckets["stuck"].append(item)
                elif qa_status == "pending":
                    buckets["awaiting"].append(item)
                elif run_status == "completed" and (
                    conf.get("reached_0_8") is True or qa_status == "approved"
                ):
                    buckets["ready"].append(item)
                else:
                    buckets["other"].append(item)

        return {
            "project_id": project_id,
            "buckets": buckets,
            "counts": {k: len(v) for k, v in buckets.items()},
        }

    def _docs_rel_for_run(self, run: WorkflowRun) -> str:
        """推断业务 docs 相对路径（如 docs/test02）。"""
        docs_rel = str((run.result or {}).get("docs_dir") or "").strip()
        if docs_rel:
            return docs_rel
        if run.requirement_name:
            from .requirement_dir import make_requirement_slug

            binding = self.state.get_binding(run.project_id)
            slug = make_requirement_slug(run.requirement_name, name=run.requirement_name)
            return str(Path(binding.docs_dir or "docs") / slug)
        return ""

    def _discover_artifacts_from_docs(self, run: WorkflowRun) -> dict[str, Any]:
        """从磁盘 docs 扫描已有节点产物，供续跑/展示回填（不依赖本 run 的 result）。"""
        binding = self.state.get_binding(run.project_id)
        app_root = Path(binding.app_root).expanduser().resolve()
        docs_rel = self._docs_rel_for_run(run)
        if not docs_rel:
            return {"docs_dir": "", "node_outputs": {}, "completed_nodes": []}
        docs_path = (app_root / docs_rel).resolve()
        if not docs_path.is_dir():
            return {"docs_dir": docs_rel, "node_outputs": {}, "completed_nodes": []}

        wf_cfg = load_workflow_config(self._workflow_config_path)
        outputs: dict[str, str] = {}
        completed: list[str] = []
        original = docs_path / "00-requirement.md"
        if original.is_file():
            try:
                outputs["original_requirement"] = str(original.relative_to(app_root))
            except ValueError:
                outputs["original_requirement"] = str(original)
        for node_id in NODE_IDS:
            node_cfg = wf_cfg.nodes.get(node_id)
            if node_cfg is None:
                continue
            path = docs_path / node_cfg.output_file
            if not path.is_file():
                continue
            try:
                rel = str(path.relative_to(app_root))
            except ValueError:
                rel = str(path)
            outputs[node_id] = rel
            completed.append(node_id)
        return {
            "docs_dir": docs_rel,
            "node_outputs": outputs,
            "completed_nodes": completed,
        }

    def _synthesize_timeline(
        self,
        run: WorkflowRun,
        *,
        completed: list[str],
        outputs: dict[str, str],
    ) -> list[dict[str, Any]]:
        """无历史 timeline 时，按已完成节点 + 文件 mtime 合成一条可读时间线。"""
        binding = self.state.get_binding(run.project_id)
        app_root = Path(binding.app_root).expanduser().resolve()
        events: list[dict[str, Any]] = []
        for node_id in NODE_IDS:
            if node_id not in completed and node_id not in outputs:
                continue
            at = run.started_at
            rel = str(outputs.get(node_id) or "").strip()
            if rel:
                path = (app_root / rel).resolve()
                if path.is_file():
                    try:
                        at = datetime.fromtimestamp(path.stat().st_mtime).isoformat(
                            timespec="seconds"
                        )
                    except OSError:
                        pass
            events.append(
                {
                    "node_id": node_id,
                    "event": "enter",
                    "at": at,
                    "duration_ms": None,
                    "synthetic": True,
                }
            )
            events.append(
                {
                    "node_id": node_id,
                    "event": "leave",
                    "at": at,
                    "duration_ms": None,
                    "success": True,
                    "synthetic": True,
                }
            )
        return events

    @staticmethod
    def _merge_timelines(
        prior: list[dict[str, Any]],
        current: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        seen = {
            (str(e.get("node_id") or ""), str(e.get("event") or ""), str(e.get("at") or ""))
            for e in current
            if isinstance(e, dict)
        }
        merged: list[dict[str, Any]] = []
        for item in prior:
            if not isinstance(item, dict):
                continue
            key = (
                str(item.get("node_id") or ""),
                str(item.get("event") or ""),
                str(item.get("at") or ""),
            )
            if key in seen:
                continue
            merged.append(item)
        merged.extend([e for e in current if isinstance(e, dict)])
        return merged[-200:]

    def _lineage_timeline(self, run: WorkflowRun) -> list[dict[str, Any]]:
        """取同源任务中「最完整」的 timeline（沿 source_run_id 链 + 同任务最长）。"""
        best: list[dict[str, Any]] = []

        def consider(tl: list[Any]) -> None:
            nonlocal best
            cleaned = [dict(e) for e in tl if isinstance(e, dict)]
            if len(cleaned) > len(best):
                best = cleaned

        # 沿续跑血缘往上找
        seen: set[str] = {run.run_id}
        cursor = str((run.result or {}).get("source_run_id") or "").strip()
        hops = 0
        while cursor and cursor not in seen and hops < 8:
            seen.add(cursor)
            hops += 1
            try:
                source = self.state.get_run(cursor)
            except KeyError:
                break
            consider(list((source.result or {}).get("timeline") or []))
            cursor = str((source.result or {}).get("source_run_id") or "").strip()

        # 同项目/任务/需求名里取最长（避免选到另一条短续跑）
        for item in self.state.list_runs():
            rid = str(item.get("run_id") or "")
            if not rid or rid in seen:
                continue
            if str(item.get("project_id") or "") != run.project_id:
                continue
            if run.task_id and str(item.get("task_id") or "") != run.task_id:
                continue
            if (
                run.requirement_name
                and str(item.get("requirement_name") or "") != run.requirement_name
            ):
                continue
            try:
                prior = self.state.get_run(rid)
            except KeyError:
                continue
            consider(list((prior.result or {}).get("timeline") or []))
        return best

    def _seed_run_artifacts_from_docs(
        self,
        run: WorkflowRun,
        *,
        source: WorkflowRun | None = None,
        resume_from_node: str = "",
    ) -> None:
        """续跑新建 run 时立刻写入已有产物 + 时间线，避免页面空白。"""
        if run.fresh:
            return
        discovered = self._discover_artifacts_from_docs(run)
        outputs = dict(discovered.get("node_outputs") or {})
        completed = list(discovered.get("completed_nodes") or [])
        docs_rel = str(discovered.get("docs_dir") or "")
        current = ""
        timeline: list[dict[str, Any]] = []
        source_run_id = ""
        if source and isinstance(source.result, dict):
            source_run_id = source.run_id
            src_out = source.result.get("node_outputs") or {}
            if isinstance(src_out, dict):
                for key, val in src_out.items():
                    outputs.setdefault(str(key), str(val))
            for node_id in source.result.get("completed_nodes") or []:
                nid = str(node_id)
                if nid and nid not in completed:
                    completed.append(nid)
            docs_rel = docs_rel or str(source.result.get("docs_dir") or "")
            current = str(source.result.get("current_node") or "")
            timeline = [
                dict(e)
                for e in (source.result.get("timeline") or [])
                if isinstance(e, dict)
            ]

        # 正在续跑的节点先不当作 completed，避免 UI 误显示已完成
        resume = (resume_from_node or run.resume_from_node or "").strip()
        if resume and resume != "parallel_plan_and_tests":
            completed = [n for n in completed if n != resume]
        elif resume == "parallel_plan_and_tests":
            completed = [
                n for n in completed if n not in {"create_plan", "design_test_cases"}
            ]

        if not timeline:
            timeline = self._synthesize_timeline(
                run, completed=completed, outputs=outputs
            )
        if timeline:
            timeline = list(timeline) + [
                {
                    "node_id": resume or current or "",
                    "event": "resume",
                    "at": datetime.now().isoformat(timespec="seconds"),
                    "duration_ms": None,
                    "note": "续跑接续",
                }
            ]

        if not outputs and not docs_rel and not timeline:
            return
        self.state.update_run(
            run.run_id,
            result={
                "docs_dir": docs_rel,
                "node_outputs": outputs,
                "completed_nodes": completed,
                "current_node": resume or current,
                "timeline": timeline[-200:],
                "source_run_id": source_run_id,
            },
        )

    def _resolve_artifact_path(self, run: WorkflowRun, node_id: str) -> Path:
        binding = self.state.get_binding(run.project_id)
        app_root = Path(binding.app_root).expanduser().resolve()
        outputs = (run.result or {}).get("node_outputs") or {}
        rel = str(outputs.get(node_id) or "").strip()
        if rel:
            path = (app_root / rel).resolve()
            if path.is_file():
                return path

        # 失败/无 result：按 docs_dir + 节点 output_file 回退
        docs_rel = self._docs_rel_for_run(run)
        if docs_rel:
            wf_cfg = load_workflow_config(self._workflow_config_path)
            node_cfg = wf_cfg.nodes.get(node_id)
            if node_cfg is not None:
                path = (app_root / docs_rel / node_cfg.output_file).resolve()
                if path.is_file():
                    return path
        raise FileNotFoundError(f"找不到节点产物: {node_id}")

    def preview_artifact(self, run_id: str, node_id: str, *, max_chars: int = 200_000) -> dict[str, Any]:
        run = self.state.get_run(run_id)
        path = self._resolve_artifact_path(run, node_id)
        content = path.read_text(encoding="utf-8")
        truncated = len(content) > max_chars
        if truncated:
            content = content[:max_chars]
        return {
            "run_id": run_id,
            "node_id": node_id,
            "path": str(path),
            "content": content,
            "truncated": truncated,
            "size": path.stat().st_size,
        }

    def compare_runs(self, left_id: str, right_id: str) -> dict[str, Any]:
        left = self.state.get_run(left_id)
        right = self.state.get_run(right_id)
        left_out = dict((left.result or {}).get("node_outputs") or {})
        right_out = dict((right.result or {}).get("node_outputs") or {})
        left_done = set((left.result or {}).get("completed_nodes") or [])
        right_done = set((right.result or {}).get("completed_nodes") or [])
        all_nodes = list(NODE_IDS)
        nodes: list[dict[str, Any]] = []
        for node_id in all_nodes:
            l_rel = str(left_out.get(node_id) or "")
            r_rel = str(right_out.get(node_id) or "")
            l_text = ""
            r_text = ""
            try:
                if l_rel or left.status == "completed":
                    l_text = self._resolve_artifact_path(left, node_id).read_text(encoding="utf-8")
            except (FileNotFoundError, KeyError, OSError):
                l_text = ""
            try:
                if r_rel or right.status == "completed":
                    r_text = self._resolve_artifact_path(right, node_id).read_text(encoding="utf-8")
            except (FileNotFoundError, KeyError, OSError):
                r_text = ""
            if l_text and r_text:
                same: bool | None = l_text == r_text
            elif l_text or r_text:
                same = False
            else:
                same = None
            nodes.append(
                {
                    "node_id": node_id,
                    "left_has": bool(l_text) or node_id in left_done,
                    "right_has": bool(r_text) or node_id in right_done,
                    "same_content": same,
                    "left_chars": len(l_text),
                    "right_chars": len(r_text),
                }
            )

        left_conf = None
        right_conf = None
        try:
            from .artifact_insights import build_task_insights

            lb = self.state.get_binding(left.project_id)
            rb = self.state.get_binding(right.project_id)
            left_conf = build_task_insights(
                lb.app_root,
                docs_base=lb.docs_dir or "docs",
                task_name=left.requirement_name,
                run_docs_dir=str((left.result or {}).get("docs_dir") or "") or None,
            ).get("release_confidence")
            right_conf = build_task_insights(
                rb.app_root,
                docs_base=rb.docs_dir or "docs",
                task_name=right.requirement_name,
                run_docs_dir=str((right.result or {}).get("docs_dir") or "") or None,
            ).get("release_confidence")
        except Exception:  # noqa: BLE001
            pass

        return {
            "left": self._enriched_run_dict(left),
            "right": self._enriched_run_dict(right),
            "nodes": nodes,
            "summary": {
                "left_completed": len(left_done),
                "right_completed": len(right_done),
                "nodes_same": sum(1 for n in nodes if n["same_content"] is True),
                "nodes_diff": sum(1 for n in nodes if n["same_content"] is False),
                "nodes_missing": sum(
                    1 for n in nodes if n["same_content"] is None and (n["left_has"] or n["right_has"])
                ),
            },
            "confidence": {"left": left_conf, "right": right_conf},
        }

    def _run_workflow(self, run_id: str) -> None:
        cancel_event = self._cancel_event(run_id)
        project_lock: threading.Lock | None = None
        lock_held = False
        try:
            run = self.state.get_run(run_id)
            if cancel_event.is_set():
                self._finalize_cancelled(
                    run_id,
                    reason="cancelled before start",
                    log_message="Workflow cancelled before start",
                )
                return

            binding = self.state.get_binding(run.project_id)
            project_lock = self.state.get_project_run_lock(run.project_id)
            self._acquire_project_lock(project_lock, cancel_event, run_id)
            lock_held = True

            if cancel_event.is_set():
                self._finalize_cancelled(
                    run_id,
                    reason="cancelled while waiting for lock",
                    log_message="Workflow cancelled while waiting for lock",
                )
                return

            self.state.update_run(run_id, status="running")
            self.state.append_run_log(
                run_id,
                f"Workflow started on {platform_label()} ({sys.platform})",
            )
            if not run.headless_all_nodes and sys.platform == "darwin":
                self.state.append_run_log(
                    run_id,
                    "交互节点经 Warp 启动 omp：已有窗口则复用，否则新开（需关闭「无界面」；系统需允许 Cursor/Terminal 自动化 Warp）",
                )

            config_path = self._build_runtime_configs(run, binding)
            wf_cfg = load_workflow_config(config_path)
            if not run.skip_mcp_setup:
                mcp_result = ensure_mcp_for_agents(
                    self.workflow_root,
                    e2e_headless=bool(run.headless_all_nodes),
                )
                self.state.append_run_log(
                    run_id,
                    f"MCP configured (engine): servers={mcp_result.get('servers', [])}",
                )
                # 业务项目根也写入 .omp，避免 Warp/omp --cwd 到 app_root 时缺 MCP
                app_root_path = Path(binding.app_root).expanduser().resolve()
                if app_root_path != self.workflow_root.resolve():
                    app_mcp = ensure_mcp_for_agents(
                        app_root_path,
                        e2e_headless=bool(run.headless_all_nodes),
                    )
                    self.state.append_run_log(
                        run_id,
                        f"MCP configured (app_root): servers={app_mcp.get('servers', [])}",
                    )
            self.state.append_run_log(
                run_id,
                f"工具={run.tool} auto={run.auto} docs_dir={wf_cfg.docs_dir} "
                f"节点数={len(wf_cfg.nodes)}",
            )
            if run.resume_from_node:
                self.state.append_run_log(
                    run_id,
                    f"{'只跑节点' if run.single_node else '从节点续跑'}: {run.resume_from_node}",
                )

            workflow = DevWorkflow(self.workflow_root, config_path)
            source_file = Path(run.requirement_path) if run.requirement_path else None
            if source_file and not source_file.exists():
                source_file = None

            interactive_runner.set_run_log_callback(
                lambda message: self.state.append_run_log(run_id, message),
            )
            set_progress_callback(lambda patch: self._apply_run_progress(run_id, patch))
            set_active_run(run_id, cancel_event.is_set)
            try:
                # docs_dir 仅写在 runtime workflow.yaml；此处传 None 才会生成 docs/<任务名>/
                result = workflow.run(
                    requirement=run.requirement,
                    docs_dir=None,
                    name=run.requirement_name or None,
                    source_file=source_file,
                    skip_clarification=run.skip_clarification,
                    auto=run.auto,
                    fresh=run.fresh,
                    resume_from_node=run.resume_from_node or None,
                    single_node=bool(run.single_node),
                )
            finally:
                set_active_run(None, None)
                set_progress_callback(None)
                interactive_runner.set_run_log_callback(None)

            if cancel_event.is_set():
                self.state.update_run(
                    run_id,
                    status="cancelled",
                    result=dict(result),
                    error="cancelled by user",
                    ended_at=datetime.now().isoformat(timespec="seconds"),
                )
                self.state.append_run_log(run_id, "Workflow cancelled after last node")
            else:
                self.state.update_run(
                    run_id,
                    status="completed",
                    result=dict(result),
                    ended_at=datetime.now().isoformat(timespec="seconds"),
                )
                self.state.append_run_log(run_id, "Workflow completed")
            if run.task_id:
                self.state.set_task_last_run(run.project_id, run.task_id, run_id)
        except RunCancelled as exc:
            self.state.update_run(
                run_id,
                status="cancelled",
                error=str(exc),
                ended_at=datetime.now().isoformat(timespec="seconds"),
            )
            self.state.append_run_log(run_id, f"Workflow cancelled: {exc}")
            run = self.state.get_run(run_id)
            if run.task_id:
                self.state.set_task_last_run(run.project_id, run.task_id, run_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Workflow run failed")
            self.state.update_run(
                run_id,
                status="failed",
                error=str(exc),
                ended_at=datetime.now().isoformat(timespec="seconds"),
            )
            self.state.append_run_log(run_id, f"Workflow failed: {exc}")
            run = self.state.get_run(run_id)
            if run.task_id:
                self.state.set_task_last_run(run.project_id, run.task_id, run_id)
        finally:
            set_active_run(None, None)
            set_progress_callback(None)
            if lock_held and project_lock is not None:
                try:
                    run = self.state.get_run(run_id)
                    self.state.clear_project_lock_holder(run.project_id, run_id)
                except KeyError:
                    pass
                try:
                    project_lock.release()
                except RuntimeError:
                    # 可能已被强制取消提前 release
                    pass
            self._clear_cancel_event(run_id)
            self._unregister_worker(run_id)

    def start_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        project_id = str(payload.get("project_id") or "").strip()
        if not project_id:
            raise ValueError("project_id is required")
        binding = self.state.get_binding(project_id)
        requirement = str(payload.get("requirement") or "").strip()
        requirement_path = str(payload.get("requirement_prd_path") or "").strip()
        if not requirement and not requirement_path:
            raise ValueError("requirement or requirement_prd_path is required")
        if not requirement and requirement_path:
            prd = resolve_prd_path(binding.app_root, requirement_path)
            if not prd.exists():
                raise ValueError(
                    f"PRD file does not exist on {platform_label()}: {prd}",
                )
            requirement = prd.read_text(encoding="utf-8")
            requirement_path = str(prd)

        task_id = str(payload.get("task_id") or "").strip()
        auto = bool(payload.get("auto", False))
        skip_clarification = bool(payload.get("skip_clarification", True))
        if auto:
            skip_clarification = True

        single_node = bool(payload.get("single_node", False))
        resume_from = self._normalize_resume_node(
            str(payload.get("resume_from_node") or ""),
            single_node=single_node,
        )
        run = WorkflowRun(
            run_id=uuid.uuid4().hex,
            project_id=project_id,
            task_id=task_id,
            requirement=requirement,
            requirement_path=requirement_path,
            requirement_name=str(payload.get("requirement_name") or "").strip(),
            tool=str(payload.get("tool") or self.state.get_default_tool()).strip()
            or self.state.get_default_tool(),
            skip_clarification=skip_clarification,
            auto=auto,
            fresh=bool(payload.get("fresh", False)),
            headless_all_nodes=bool(payload.get("headless_all_nodes", False)),
            skip_mcp_setup=bool(payload.get("skip_mcp_setup", False)),
            resume_from_node=resume_from,
            single_node=single_node,
            docs_dir=binding.docs_dir,
        )
        self.state.create_run(run)
        if task_id:
            self.state.set_task_last_run(project_id, task_id, run.run_id)
        # 非 fresh：立刻把磁盘已有产物写入 run.result，页面不会闪成空
        source_run: WorkflowRun | None = None
        source_id = str(payload.get("source_run_id") or "").strip()
        if source_id:
            try:
                source_run = self.state.get_run(source_id)
            except KeyError:
                source_run = None
        try:
            self._seed_run_artifacts_from_docs(
                self.state.get_run(run.run_id),
                source=source_run,
                resume_from_node=resume_from,
            )
            run = self.state.get_run(run.run_id)
        except Exception:  # noqa: BLE001
            logger.exception("seed run artifacts failed for %s", run.run_id)
        self._cancel_event(run.run_id)  # 预创建，便于启动前取消
        worker = threading.Thread(
            target=self._run_workflow,
            args=(run.run_id,),
            daemon=True,
            name=f"workflow-run-{run.run_id[:8]}",
        )
        self._register_worker(run.run_id, worker)
        worker.start()
        return self._enriched_run_dict(run)

    def _resolve_settings_app_root(self, query: dict[str, list[str]]) -> Path:
        project_id = str((query.get("project_id") or [""])[0]).strip()
        if project_id:
            binding = self.state.get_binding(project_id)
            return Path(binding.app_root).expanduser().resolve()
        app_root = str((query.get("app_root") or [""])[0]).strip()
        if app_root:
            return Path(app_root).expanduser().resolve()
        projects = self.state.list_bindings()
        if projects:
            return Path(projects[0]["app_root"]).expanduser().resolve()
        return self.workflow_root

    def _resolve_settings_app_root_from_payload(self, payload: dict[str, Any]) -> Path:
        project_id = str(payload.get("project_id") or "").strip()
        if project_id:
            binding = self.state.get_binding(project_id)
            return Path(binding.app_root).expanduser().resolve()
        app_root = str(payload.get("app_root") or "").strip()
        if app_root:
            return Path(app_root).expanduser().resolve()
        projects = self.state.list_bindings()
        if projects:
            return Path(projects[0]["app_root"]).expanduser().resolve()
        return self.workflow_root

    def _workflow_nodes(self) -> list[dict[str, Any]]:
        wf_cfg = load_workflow_config(self._workflow_config_path)
        nodes: list[dict[str, Any]] = []
        for node_id in NODE_IDS:
            node_cfg = wf_cfg.nodes.get(node_id)
            if node_cfg is None:
                continue
            nodes.append(
                {
                    "id": node_id,
                    "name": node_cfg.name,
                    "output": node_cfg.output_file,
                    "tool": node_cfg.tool,
                    "mode": node_cfg.mode,
                    "model": getattr(node_cfg, "model", "") or "",
                    "recommendation_threshold": getattr(
                        node_cfg, "recommendation_threshold", 0.8
                    ),
                }
            )
        return nodes

    def _enriched_run_dict(self, run: WorkflowRun) -> dict[str, Any]:
        payload = run.to_dict()
        result = dict(run.result or {})
        current_node = str(result.get("current_node") or "")
        completed = [str(x) for x in (result.get("completed_nodes") or [])]
        outputs = {
            str(k): str(v)
            for k, v in (result.get("node_outputs") or {}).items()
            if str(v).strip()
        }
        # 续跑新建 run 尚无 progress 时，用磁盘 docs 回填，避免产物列表空白
        if run.requirement_name and (not outputs or not result.get("docs_dir")):
            try:
                discovered = self._discover_artifacts_from_docs(run)
                for key, val in (discovered.get("node_outputs") or {}).items():
                    outputs.setdefault(str(key), str(val))
                for node_id in discovered.get("completed_nodes") or []:
                    nid = str(node_id)
                    if nid and nid not in completed:
                        completed.append(nid)
                if not result.get("docs_dir") and discovered.get("docs_dir"):
                    result["docs_dir"] = discovered["docs_dir"]
            except Exception:  # noqa: BLE001
                pass
        timeline = [e for e in (result.get("timeline") or []) if isinstance(e, dict)]
        # 续跑后 timeline 常只有新节点：拼上同源历史；必要时按产物合成
        if run.resume_from_node or result.get("source_run_id") or run.requirement_name:
            try:
                prior_tl = self._lineage_timeline(run)
                if prior_tl:
                    cur_enter = {
                        str(e.get("node_id") or "")
                        for e in timeline
                        if e.get("event") == "enter"
                    }
                    prior_enter = {
                        str(e.get("node_id") or "")
                        for e in prior_tl
                        if e.get("event") == "enter"
                    }
                    if prior_enter - cur_enter:
                        timeline = self._merge_timelines(prior_tl, timeline)
                elif not timeline and (completed or outputs):
                    timeline = self._synthesize_timeline(
                        run, completed=completed, outputs=outputs
                    )
            except Exception:  # noqa: BLE001
                pass
        payload["current_node"] = current_node
        payload["completed_nodes"] = completed
        payload["node_outputs"] = outputs
        payload["timeline"] = timeline
        payload["last_heartbeat_at"] = str(result.get("last_heartbeat_at") or "")
        try:
            payload["heartbeat_elapsed_ms"] = (
                int(result.get("heartbeat_elapsed_ms"))
                if result.get("heartbeat_elapsed_ms") is not None
                else None
            )
        except (TypeError, ValueError):
            payload["heartbeat_elapsed_ms"] = None
        logs = list(run.logs or [])
        terminal = run.status in {
            "failed",
            "cancelled",
            "cancelling",
            "interrupted",
        }
        permission_hint = WebApp._permission_hint(logs, run.error or "")
        manual_command = WebApp._extract_manual_command(logs)
        log_summary = WebApp._log_summary(logs, run.error or "")
        valid_nodes = set(NODE_IDS) | {"parallel_plan_and_tests"}
        stuck_node = ""
        if terminal:
            if current_node in valid_nodes:
                stuck_node = current_node
            else:
                # current_node 可能被心跳写成工具名，回退到可续跑节点
                stuck_node = self._resolve_resume_node(run, "")
        payload["explain"] = {
            "stuck_node": stuck_node,
            "last_logs": logs[-20:],
            "log_summary": log_summary,
            "can_retry": run.status
            in {"failed", "cancelled", "completed", "interrupted"},
            "error": run.error or "",
            "completed_count": len(completed),
            "permission_hint": permission_hint,
            "manual_command": manual_command,
        }
        # 展示用 current_node 也清洗，避免顶栏显示 oh_my_pi
        if current_node and current_node not in valid_nodes:
            payload["current_node"] = stuck_node or ""
        return payload

    @staticmethod
    def _extract_manual_command(logs: list[str]) -> str:
        markers = (
            "若未自动唤起，可在 Warp 中手动执行:",
            "] 手动执行:",
            "Warp 自动键入失败（请手动执行）:",
        )
        for line in reversed(logs or []):
            text = str(line or "")
            for marker in markers:
                if marker in text:
                    cmd = text.split(marker, 1)[1].strip()
                    if cmd:
                        return cmd
        return ""

    @staticmethod
    def _log_summary(logs: list[str], error: str, *, limit: int = 8) -> list[str]:
        keywords = (
            "error",
            "fail",
            "eperm",
            "cancelled",
            "进入节点",
            "离开节点",
            "手动执行",
            "warp",
            "operation not permitted",
        )
        picked: list[str] = []
        for line in reversed(logs or []):
            lower = line.lower()
            if any(k in lower for k in keywords) or "失败" in line or "取消" in line:
                picked.append(line)
            if len(picked) >= limit:
                break
        picked.reverse()
        if error and (not picked or error not in "\n".join(picked)):
            picked.append(error)
        return picked[-limit:]

    @staticmethod
    def _permission_hint(logs: list[str], error: str) -> str:
        blob = "\n".join([*(logs[-40:] if logs else []), error or ""]).lower()
        markers = (
            "eperm",
            "operation not permitted",
            "full disk access",
            "files & folders",
            "uv_cwd",
            "cannot change working directory",
        )
        if any(m in blob for m in markers):
            return (
                "macOS 权限不足：请给 Warp / omp 开启「完全磁盘访问」或「文稿和数据」，"
                "然后完全退出并重启 Warp。详见 README「13. Web 操作台 → Warp 权限（macOS）」。"
            )
        return ""

    def stream_run_events(
        self,
        handler: BaseHTTPRequestHandler,
        *,
        run_id: str = "",
        project_id: str = "",
    ) -> None:
        """SSE：推送 run 变更（长轮询式 wait + event-stream）。"""
        key = f"project:{project_id}" if project_id and not run_id else run_id
        if not key or key == "project:":
            raise ValueError("run_id or project_id is required")

        handler.send_response(HTTPStatus.OK.value)
        handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
        handler.send_header("Cache-Control", "no-cache, no-store")
        handler.send_header("Connection", "keep-alive")
        handler.send_header("X-Accel-Buffering", "no")
        handler.end_headers()

        last_seq = 0
        # 先推一份当前快照
        if run_id:
            try:
                run = self.state.get_run(run_id)
                snapshot = {
                    "seq": 0,
                    "event": "snapshot",
                    "run_id": run_id,
                    "project_id": run.project_id,
                    "payload": self._enriched_run_dict(run),
                }
                handler.wfile.write(
                    f"event: snapshot\ndata: {json.dumps(snapshot, ensure_ascii=False)}\n\n".encode(
                        "utf-8"
                    )
                )
                handler.wfile.flush()
            except KeyError:
                pass
        elif project_id:
            for item in self.state.list_runs():
                if item.get("project_id") != project_id:
                    continue
                if item.get("status") not in {"queued", "running", "cancelling"}:
                    continue
                try:
                    run = self.state.get_run(str(item["run_id"]))
                    snapshot = {
                        "seq": 0,
                        "event": "snapshot",
                        "run_id": run.run_id,
                        "project_id": run.project_id,
                        "payload": self._enriched_run_dict(run),
                    }
                    handler.wfile.write(
                        f"event: update\ndata: {json.dumps(snapshot, ensure_ascii=False)}\n\n".encode(
                            "utf-8"
                        )
                    )
                    handler.wfile.flush()
                except KeyError:
                    continue

        # 持续推送
        idle_rounds = 0
        while idle_rounds < 120:  # ~50 分钟上限（25s * 120）
            message = EVENT_BUS.wait(key, last_seq=last_seq, timeout=25.0)
            if message is None:
                idle_rounds += 1
                try:
                    handler.wfile.write(b": keepalive\n\n")
                    handler.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    return
                continue
            idle_rounds = 0
            last_seq = int(message.get("seq") or last_seq)
            event_name = str(message.get("event") or "update")
            try:
                handler.wfile.write(
                    f"event: {event_name}\ndata: {json.dumps(message, ensure_ascii=False)}\n\n".encode(
                        "utf-8"
                    )
                )
                handler.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                return
            # 终态后多推一会儿再结束
            payload = message.get("payload") or {}
            if run_id and str(payload.get("status") or "") in {
                "completed",
                "failed",
                "cancelled",
            }:
                return

    def _apply_run_progress(self, run_id: str, patch: dict[str, Any]) -> None:
        """节点心跳：合并写入 result，供前端流水线实时刷新。"""
        try:
            run = self.state.get_run(run_id)
        except KeyError:
            return
        if run.status not in {"queued", "running", "cancelling"}:
            return
        result = dict(run.result or {})
        phase = str(patch.get("phase") or "")
        current = str(patch.get("current_node") or "").strip()
        # 心跳里的 tool 名（oh_my_pi）绝不能覆盖工作流 current_node
        valid_nodes = set(NODE_IDS) | {"parallel_plan_and_tests"}
        now = datetime.now().isoformat(timespec="seconds")
        if current and phase != "heartbeat" and current in valid_nodes:
            result["current_node"] = current
        elif current and phase != "heartbeat" and current not in valid_nodes:
            # 忽略非法节点名，避免污染续跑
            current = str(result.get("current_node") or "").strip()
        docs_dir = str(patch.get("docs_dir") or "").strip()
        if docs_dir:
            result["docs_dir"] = docs_dir
        outs = dict(result.get("node_outputs") or {})
        patch_outs = patch.get("node_outputs") or {}
        if isinstance(patch_outs, dict):
            outs.update({str(k): str(v) for k, v in patch_outs.items() if v})
            result["node_outputs"] = outs
        done = list(result.get("completed_nodes") or [])
        for node_id in patch.get("completed_nodes") or []:
            node_id = str(node_id)
            if node_id and node_id not in done:
                done.append(node_id)
        result["completed_nodes"] = done
        if patch.get("last_error"):
            result["last_error"] = str(patch.get("last_error"))

        # 时间线
        timeline = list(result.get("timeline") or [])
        enter_at = dict(result.get("node_enter_at") or {})
        if phase == "enter" and current and current in valid_nodes:
            enter_at[current] = now
            timeline.append(
                {"node_id": current, "event": "enter", "at": now, "duration_ms": None}
            )
        elif phase == "leave" and current and current in valid_nodes:
            duration_ms = None
            started = enter_at.get(current)
            if started:
                try:
                    t0 = datetime.fromisoformat(str(started))
                    t1 = datetime.fromisoformat(now)
                    duration_ms = int((t1 - t0).total_seconds() * 1000)
                except ValueError:
                    duration_ms = None
            timeline.append(
                {
                    "node_id": current,
                    "event": "leave",
                    "at": now,
                    "duration_ms": duration_ms,
                    "success": patch.get("success"),
                }
            )
        elif phase == "heartbeat":
            result["last_heartbeat_at"] = now
            if patch.get("elapsed_ms") is not None:
                try:
                    result["heartbeat_elapsed_ms"] = int(patch.get("elapsed_ms"))
                except (TypeError, ValueError):
                    pass
            tool = str(patch.get("tool") or "").strip()
            if tool:
                result["heartbeat_tool"] = tool
            # 心跳不刷时间线，避免噪音；仅更新字段供 UI 显示「已运行 Xs」
        result["node_enter_at"] = enter_at
        result["timeline"] = timeline[-200:]

        self.state.update_run(run_id, result=result)
        if phase == "enter" and current and current in valid_nodes:
            self.state.append_run_log(run_id, f"进入节点: {current}")
        elif phase == "leave" and current and current in valid_nodes:
            ok = patch.get("success")
            mark = "完成" if ok is not False else "结束(有警告)"
            self.state.append_run_log(run_id, f"节点{mark}: {current}")
        elif phase == "heartbeat":
            # 每约 30s 写一行，避免日志爆炸
            elapsed_ms = int(result.get("heartbeat_elapsed_ms") or 0)
            if elapsed_ms > 0 and elapsed_ms // 30_000 != (elapsed_ms - 5000) // 30_000:
                node_label = str(result.get("current_node") or "current")
                tool = str(result.get("heartbeat_tool") or patch.get("tool") or "")
                suffix = f" ({tool})" if tool else ""
                self.state.append_run_log(
                    run_id,
                    f"心跳: {node_label}{suffix} 已运行 {elapsed_ms / 1000:.0f}s",
                )

    def _serve_index(self, handler: BaseHTTPRequestHandler) -> None:
        index_file = self.assets_dir / "index.html"
        if not index_file.exists():
            index_file = self.static_dir / "index.html"
        if not index_file.exists():
            self._send_text(
                handler,
                HTTPStatus.NOT_FOUND,
                "index.html not found under webui/",
            )
            return
        self._send_text(
            handler,
            HTTPStatus.OK,
            index_file.read_text(encoding="utf-8"),
            "text/html; charset=utf-8",
        )

    def _serve_static_asset(self, handler: BaseHTTPRequestHandler, route: str) -> bool:
        if route.startswith("/api/"):
            return False
        rel = route.lstrip("/")
        if not rel or rel == "index.html":
            return False
        asset_path = (self.assets_dir / rel).resolve()
        if not str(asset_path).startswith(str(self.assets_dir.resolve())):
            return False
        if not asset_path.is_file():
            return False
        content_type, _ = mimetypes.guess_type(str(asset_path))
        body = asset_path.read_bytes()
        self._send_bytes(
            handler,
            HTTPStatus.OK,
            body,
            content_type or "application/octet-stream",
        )
        return True

    def handle_get(self, handler: BaseHTTPRequestHandler) -> None:
        parsed = urlparse(handler.path)
        route = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)

        if route in ("/", "/index.html"):
            self._serve_index(handler)
            return

        if self._serve_static_asset(handler, route):
            return

        if route == "/api/system/info":
            self._send_json(handler, HTTPStatus.OK, platform_info())
            return

        if route == "/api/system/config":
            self._send_json(handler, HTTPStatus.OK, self.state.get_system_config())
            return

        if route == "/api/settings/nodes":
            app_root = self._resolve_settings_app_root(query)
            self._send_json(
                handler,
                HTTPStatus.OK,
                settings_service.get_node_runtime_config(self.workflow_root, app_root),
            )
            return

        if route == "/api/settings/confidence-rules":
            app_root = self._resolve_settings_app_root(query)
            self._send_json(
                handler,
                HTTPStatus.OK,
                settings_service.get_confidence_rules(self.workflow_root, app_root),
            )
            return

        if route == "/api/settings/mcp":
            self._send_json(
                handler,
                HTTPStatus.OK,
                settings_service.list_mcp_servers(self.workflow_root),
            )
            return

        if route == "/api/settings/skills":
            app_root = self._resolve_settings_app_root(query)
            self._send_json(
                handler,
                HTTPStatus.OK,
                settings_service.list_skills(self.workflow_root, app_root),
            )
            return

        if route == "/api/metrics/runs":
            days_raw = str((query.get("days") or ["7"])[0]).strip() or "7"
            try:
                days = int(days_raw)
            except ValueError:
                days = 7
            project_id = str((query.get("project_id") or [""])[0]).strip()
            self._send_json(
                handler,
                HTTPStatus.OK,
                self.run_metrics(days=days, project_id=project_id),
            )
            return

        if route in ("/api/rule-dirs", "/api/rule-sets"):
            self._send_json(
                handler,
                HTTPStatus.OK,
                {"rule_dirs": self._list_rule_dir_catalog(), "rule_sets": self._list_rule_sets_catalog()},
            )
            return

        if route == "/api/rule-files":
            target = str((query.get("path") or [""])[0]).strip()
            if not target:
                raise ValueError("path is required")
            self._send_json(
                handler,
                HTTPStatus.OK,
                self._rule_files_at_path(Path(target).expanduser().resolve()),
            )
            return

        if route == "/api/workflow/nodes":
            self._send_json(handler, HTTPStatus.OK, {"nodes": self._workflow_nodes()})
            return

        if route == "/api/projects":
            self._send_json(handler, HTTPStatus.OK, {"projects": self.state.list_bindings()})
            return

        if route == "/api/fs/roots":
            roots = [
                {"name": "Home", "path": str(Path.home().resolve())},
                {"name": "Workflow Root", "path": str(self.workflow_root)},
                {"name": "Root", "path": str(Path("/").resolve())},
            ]
            self._send_json(handler, HTTPStatus.OK, {"roots": roots})
            return

        if route == "/api/fs/list":
            target = str((query.get("path") or [""])[0]).strip() or str(Path.home())
            include_files = str((query.get("files") or ["0"])[0]).strip() == "1"
            listing = self._list_directory(Path(target), include_files=include_files)
            ext = str((query.get("ext") or [""])[0]).strip().lower()
            if ext and include_files:
                listing["files"] = [
                    item for item in listing["files"] if item["name"].lower().endswith(ext)
                ]
            self._send_json(handler, HTTPStatus.OK, listing)
            return

        parts = [segment for segment in route.split("/") if segment]
        if len(parts) >= 3 and parts[0] == "api" and parts[1] == "projects":
            project_id = parts[2]
            if len(parts) == 4 and parts[3] == "rules":
                binding = self.state.get_binding(project_id)
                self._send_json(
                    handler,
                    HTTPStatus.OK,
                    {
                        "project_id": binding.project_id,
                        "ai_rules_dir": binding.ai_rules_dir,
                        "node_rules": binding.node_rules,
                    },
                )
                return

            if len(parts) == 4 and parts[3] == "rule-files":
                ai_rules_dir = str((query.get("ai_rules_dir") or [""])[0]).strip() or None
                self._send_json(
                    handler,
                    HTTPStatus.OK,
                    self._rule_files(project_id, ai_rules_dir=ai_rules_dir),
                )
                return

            if len(parts) == 4 and parts[3] == "tasks":
                self._send_json(handler, HTTPStatus.OK, {"tasks": self.state.list_tasks(project_id)})
                return

            if len(parts) == 4 and parts[3] == "health":
                self._send_json(handler, HTTPStatus.OK, self.project_health(project_id))
                return

            if len(parts) == 4 and parts[3] == "board":
                self._send_json(
                    handler,
                    HTTPStatus.OK,
                    self.task_priority_board(project_id),
                )
                return

            if len(parts) == 4 and parts[3] == "export":
                # 默认不含 runs，显式 include_runs=1 才打包历史
                include_runs = str((query.get("include_runs") or ["0"])[0]).strip() in {
                    "1",
                    "true",
                    "yes",
                }
                max_runs_raw = str((query.get("max_runs") or ["50"])[0]).strip()
                try:
                    max_runs = max(0, min(200, int(max_runs_raw)))
                except ValueError:
                    max_runs = 50
                data, filename = self.export_project_zip(
                    project_id,
                    include_runs=include_runs,
                    max_runs=max_runs,
                )
                self._send_bytes(
                    handler,
                    HTTPStatus.OK,
                    data,
                    "application/zip",
                    cache_control="no-store",
                    filename=filename,
                )
                return

            if len(parts) == 6 and parts[3] == "tasks" and parts[5] == "insights":
                task_id = parts[4]
                self._send_json(
                    handler,
                    HTTPStatus.OK,
                    self._task_insights(project_id, task_id),
                )
                return

        if route == "/api/board":
            project_id = str((query.get("project_id") or [""])[0]).strip()
            self._send_json(handler, HTTPStatus.OK, self.task_priority_board(project_id))
            return

        if len(parts) == 4 and parts[0] == "api" and parts[1] == "rule-sets" and parts[3] == "system-md":
            self._send_json(handler, HTTPStatus.OK, self._rule_set_system_md(parts[2]))
            return

        if len(parts) == 4 and parts[0] == "api" and parts[1] == "rule-sets" and parts[3] == "export":
            data, filename = self.export_rule_set_zip(parts[2])
            self._send_bytes(
                handler,
                HTTPStatus.OK,
                data,
                "application/zip",
                cache_control="no-store",
                filename=filename,
            )
            return

        if route == "/api/runs":
            # 拉取列表时顺手收尸：避免页面长期显示 cancelling/running 僵尸
            self._heal_orphaned_runs(reason="orphaned on list")
            project_id = str((query.get("project_id") or [""])[0]).strip()
            task_id = str((query.get("task_id") or [""])[0]).strip()
            status = str((query.get("status") or [""])[0]).strip()
            runs = [
                self._enriched_run_dict(self.state.get_run(item["run_id"]))
                for item in self.state.list_runs()
            ]
            if project_id:
                runs = [r for r in runs if r.get("project_id") == project_id]
            if task_id:
                runs = [r for r in runs if r.get("task_id") == task_id]
            if status:
                runs = [r for r in runs if r.get("status") == status]
            self._send_json(handler, HTTPStatus.OK, {"runs": runs})
            return

        if route == "/api/runs/compare":
            left_id = str((query.get("left") or [""])[0]).strip()
            right_id = str((query.get("right") or [""])[0]).strip()
            if not left_id or not right_id:
                raise ValueError("left and right run ids are required")
            node_id = str((query.get("node_id") or [""])[0]).strip()
            if node_id:
                self._send_json(
                    handler,
                    HTTPStatus.OK,
                    self.compare_artifact_content(left_id, right_id, node_id),
                )
                return
            self._send_json(handler, HTTPStatus.OK, self.compare_runs(left_id, right_id))
            return

        if route == "/api/events":
            project_id = str((query.get("project_id") or [""])[0]).strip()
            run_id = str((query.get("run_id") or [""])[0]).strip()
            self.stream_run_events(handler, run_id=run_id, project_id=project_id)
            return

        if route.startswith("/api/runs/"):
            parts = [segment for segment in route.split("/") if segment]
            # /api/runs/{id}/events
            if len(parts) == 4 and parts[3] == "events":
                self.stream_run_events(handler, run_id=parts[2])
                return
            # /api/runs/{id}/export
            if len(parts) == 4 and parts[3] == "export":
                data, filename = self.export_run_zip(parts[2])
                self._send_bytes(
                    handler,
                    HTTPStatus.OK,
                    data,
                    "application/zip",
                    cache_control="no-store",
                    filename=filename,
                )
                return
            # /api/runs/{id}/artifacts/{node_id}
            if len(parts) == 5 and parts[3] == "artifacts":
                run_id = parts[2]
                node_id = parts[4]
                self._send_json(
                    handler,
                    HTTPStatus.OK,
                    self.preview_artifact(run_id, node_id),
                )
                return
            if len(parts) == 3:
                run_id = parts[2]
                run = self.state.get_run(run_id)
                self._send_json(handler, HTTPStatus.OK, {"run": self._enriched_run_dict(run)})
                return

        # Vue SPA fallback（hash 路由下 /workbench 等路径仍返回 index.html）
        if not route.startswith("/api/"):
            self._serve_index(handler)
            return

        self._send_json(handler, HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def handle_post(self, handler: BaseHTTPRequestHandler) -> None:
        parsed = urlparse(handler.path)
        route = parsed.path.rstrip("/") or "/"

        if route == "/api/rule-dirs/bind":
            payload = self._read_json_body(handler)
            resolved_path = str(payload.get("resolved_path") or "").strip()
            rule_set_id = str(payload.get("rule_set_id") or "").strip()
            project_ids = payload.get("project_ids") or []
            if not isinstance(project_ids, list):
                raise ValueError("project_ids must be a list")
            if rule_set_id:
                updated = self.state.bind_rule_set(rule_set_id, project_ids)
            elif resolved_path:
                updated = self._bind_rule_dir(resolved_path, project_ids)
            else:
                raise ValueError("rule_set_id or resolved_path is required")
            self._send_json(handler, HTTPStatus.OK, {"projects": updated})
            return

        if route == "/api/system/config":
            payload = self._read_json_body(handler)
            updated = self.state.update_system_config(payload)
            self._send_json(handler, HTTPStatus.OK, updated)
            return

        if route == "/api/settings/nodes":
            payload = self._read_json_body(handler)
            app_root = self._resolve_settings_app_root_from_payload(payload)
            updated = settings_service.update_node_runtime_config(
                self.workflow_root,
                app_root,
                payload,
            )
            self._send_json(handler, HTTPStatus.OK, updated)
            return

        if route == "/api/settings/confidence-rules":
            payload = self._read_json_body(handler)
            app_root = self._resolve_settings_app_root_from_payload(payload)
            updated = settings_service.update_confidence_rules(
                self.workflow_root,
                app_root,
                payload.get("nodes") if "nodes" in payload else payload,
            )
            self._send_json(handler, HTTPStatus.OK, updated)
            return

        if route == "/api/settings/mcp":
            payload = self._read_json_body(handler)
            action = str(payload.get("action") or "update").strip()
            if action == "sync":
                app_root = self._resolve_settings_app_root_from_payload(payload)
                result = settings_service.sync_mcp_to_project(
                    self.workflow_root,
                    app_root,
                    headless=bool(payload.get("headless", False)),
                )
                self._send_json(handler, HTTPStatus.OK, result)
                return
            if action == "upsert":
                server = payload.get("server")
                if not isinstance(server, dict):
                    raise ValueError("server must be an object")
                updated = settings_service.upsert_mcp_server(self.workflow_root, server)
                self._send_json(handler, HTTPStatus.OK, updated)
                return
            if action == "delete":
                updated = settings_service.delete_mcp_server(
                    self.workflow_root,
                    str(payload.get("name") or "").strip(),
                )
                self._send_json(handler, HTTPStatus.OK, updated)
                return
            servers = payload.get("servers") or []
            if not isinstance(servers, list):
                raise ValueError("servers must be a list")
            updated = settings_service.update_mcp_servers(self.workflow_root, servers)
            self._send_json(handler, HTTPStatus.OK, updated)
            return

        if route == "/api/settings/skills":
            payload = self._read_json_body(handler)
            app_root = self._resolve_settings_app_root_from_payload(payload)
            agents = payload.get("agents")
            if agents is not None and not isinstance(agents, list):
                raise ValueError("agents must be a list")
            result = settings_service.install_project_skills(
                self.workflow_root,
                app_root,
                agents=[str(a) for a in (agents or [])] or None,
            )
            self._send_json(handler, HTTPStatus.OK, result)
            return

        if route == "/api/settings/init":
            payload = self._read_json_body(handler)
            app_root = self._resolve_settings_app_root_from_payload(payload)
            result = settings_service.init_project(self.workflow_root, app_root)
            self._send_json(handler, HTTPStatus.OK, result)
            return

        if route == "/api/settings/probe":
            payload = self._read_json_body(handler)
            app_root = self._resolve_settings_app_root_from_payload(payload)
            result = settings_service.probe_connectivity(self.workflow_root, app_root)
            self._send_json(handler, HTTPStatus.OK, result)
            return

        if route == "/api/rule-sets":
            payload = self._read_json_body(handler)
            node_rules = payload.get("node_rules") or {}
            if not isinstance(node_rules, dict):
                raise ValueError("node_rules must be an object")
            created = self.state.create_rule_set(
                name=str(payload.get("name") or "").strip(),
                folder_path=str(payload.get("folder_path") or "").strip(),
                node_rules={
                    str(k): [str(item) for item in (v if isinstance(v, list) else [])]
                    for k, v in node_rules.items()
                },
                create_folder=bool(payload.get("create_folder", False)),
            )
            self._send_json(handler, HTTPStatus.CREATED, {"rule_set": created})
            return

        if route == "/api/rule-sets/import":
            payload = self._read_json_body(handler)
            imported = self.import_rule_set_zip(payload)
            self._send_json(handler, HTTPStatus.CREATED, imported)
            return

        parts = [segment for segment in route.split("/") if segment]
        if len(parts) == 4 and parts[0] == "api" and parts[1] == "rule-sets" and parts[3] == "bind":
            rule_set_id = parts[2]
            payload = self._read_json_body(handler)
            project_ids = payload.get("project_ids") or []
            if not isinstance(project_ids, list):
                raise ValueError("project_ids must be a list")
            updated = self.state.bind_rule_set(rule_set_id, project_ids)
            self._send_json(handler, HTTPStatus.OK, {"projects": updated})
            return

        if route == "/api/projects":
            payload = self._read_json_body(handler)
            # 向导：create_app_root / bootstrap(默认 true) / rule_set_id
            created = self.create_project_wizard(payload)
            self._send_json(handler, HTTPStatus.CREATED, created)
            return

        if route == "/api/projects/import":
            # 优先：原始 zip body（Content-Type: application/zip），query 传元数据
            # 兼容：JSON + zip_base64（仍受大小上限约束）
            content_type = (handler.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            query = parse_qs(urlparse(handler.path).query)
            if content_type in {"application/zip", "application/octet-stream"} or (
                content_type == "" and (query.get("app_root") or [""])[0]
            ):
                zip_bytes = self._read_body_limited(
                    handler, max_bytes=MAX_PROJECT_IMPORT_BYTES
                )
                imported = self.import_project_zip(
                    zip_bytes=zip_bytes,
                    app_root=str((query.get("app_root") or [""])[0]).strip(),
                    name=str((query.get("name") or [""])[0]).strip(),
                    create_app_root=str((query.get("create_app_root") or ["0"])[0]).strip()
                    in {"1", "true", "yes"},
                    include_runs=str((query.get("include_runs") or ["0"])[0]).strip()
                    in {"1", "true", "yes"},
                    max_runs=int(str((query.get("max_runs") or ["20"])[0]).strip() or "20"),
                )
            else:
                payload = self._read_json_body(handler)
                import base64

                zip_b64 = str(payload.get("zip_base64") or "").strip()
                if not zip_b64:
                    raise ValueError(
                        "请使用 application/zip 直传，或提供 zip_base64（不推荐）"
                    )
                zip_bytes = base64.b64decode(zip_b64)
                if len(zip_bytes) > MAX_PROJECT_IMPORT_BYTES:
                    raise ValueError(
                        f"zip 解码后过大，上限 "
                        f"{MAX_PROJECT_IMPORT_BYTES // (1024 * 1024)}MB"
                    )
                imported = self.import_project_zip(
                    zip_bytes=zip_bytes,
                    app_root=str(payload.get("app_root") or ""),
                    name=str(payload.get("name") or ""),
                    create_app_root=bool(payload.get("create_app_root", False)),
                    include_runs=bool(payload.get("include_runs", False)),
                    max_runs=int(payload.get("max_runs") or 20),
                )
            self._send_json(handler, HTTPStatus.CREATED, imported)
            return

        parts = [segment for segment in route.split("/") if segment]
        if len(parts) >= 3 and parts[0] == "api" and parts[1] == "projects":
            project_id = parts[2]

            if len(parts) == 4 and parts[3] == "rules":
                payload = self._read_json_body(handler)
                node_rules = payload.get("node_rules") or {}
                if not isinstance(node_rules, dict):
                    raise ValueError("node_rules must be an object")
                updated = self.state.update_rules(
                    project_id,
                    ai_rules_dir=str(payload.get("ai_rules_dir") or "ai-rules"),
                    node_rules={
                        str(k): [str(item) for item in (v if isinstance(v, list) else [])]
                        for k, v in node_rules.items()
                    },
                )
                self._send_json(handler, HTTPStatus.OK, {"project": updated})
                return

            if len(parts) == 4 and parts[3] == "tasks":
                payload = self._read_json_body(handler)
                task = self.state.create_task(project_id, payload)
                self._send_json(handler, HTTPStatus.CREATED, {"task": task})
                return

            if len(parts) == 4 and parts[3] == "health-fix":
                self._send_json(handler, HTTPStatus.OK, self.fix_project_health(project_id))
                return

            if (
                len(parts) == 6
                and parts[3] == "tasks"
                and parts[5] == "clone"
            ):
                task_id = parts[4]
                payload = self._read_json_body(handler)
                task = self.clone_task(project_id, task_id, payload)
                self._send_json(handler, HTTPStatus.CREATED, {"task": task})
                return

            if (
                len(parts) == 6
                and parts[3] == "tasks"
                and parts[5] == "qa-approval"
            ):
                task_id = parts[4]
                payload = self._read_json_body(handler)
                insights = self._task_insights(project_id, task_id)
                docs_path = Path(str(insights.get("docs_path") or ""))
                result = set_test_cases_approval(
                    docs_path,
                    status=str(payload.get("status") or "approved").strip(),
                    user_note=str(payload.get("user_note") or "").strip(),
                )
                refreshed = self._task_insights(project_id, task_id)
                self._send_json(
                    handler,
                    HTTPStatus.OK,
                    {"approval": result, "insights": refreshed},
                )
                return

        if route == "/api/runs":
            payload = self._read_json_body(handler)
            run = self.start_run(payload)
            self._send_json(handler, HTTPStatus.CREATED, {"run": run})
            return

        if route.startswith("/api/runs/"):
            parts = [segment for segment in route.split("/") if segment]
            if len(parts) == 4 and parts[3] == "cancel":
                run_id = parts[2]
                self._send_json(handler, HTTPStatus.OK, {"run": self.cancel_run(run_id)})
                return
            if len(parts) == 4 and parts[3] == "retry":
                run_id = parts[2]
                payload = self._read_json_body(handler)
                fresh = bool(payload.get("fresh", False))
                resume_from_node = str(payload.get("resume_from_node") or "").strip()
                single_node = bool(payload.get("single_node", False))
                self._send_json(
                    handler,
                    HTTPStatus.CREATED,
                    {
                        "run": self.retry_run(
                            run_id,
                            fresh=fresh,
                            resume_from_node=resume_from_node,
                            single_node=single_node,
                        )
                    },
                )
                return
            if len(parts) == 4 and parts[3] == "open-artifact":
                run_id = parts[2]
                payload = self._read_json_body(handler)
                node_id = str(payload.get("node_id") or "").strip()
                if not node_id:
                    raise ValueError("node_id is required")
                run = self.state.get_run(run_id)
                artifact_path = self._resolve_artifact_path(run, node_id)
                opened = self._open_path(artifact_path)
                self._send_json(
                    handler,
                    HTTPStatus.OK,
                    {"opened": opened, "artifact": str(artifact_path)},
                )
                return

        self._send_json(handler, HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def handle_put(self, handler: BaseHTTPRequestHandler) -> None:
        parsed = urlparse(handler.path)
        route = parsed.path.rstrip("/") or "/"

        parts = [segment for segment in route.split("/") if segment]
        if len(parts) == 5 and parts[0] == "api" and parts[1] == "projects" and parts[3] == "tasks":
            project_id = parts[2]
            task_id = parts[4]
            payload = self._read_json_body(handler)
            updated = self.state.update_task(project_id, task_id, payload)
            self._send_json(handler, HTTPStatus.OK, {"task": updated})
            return

        if len(parts) == 3 and parts[0] == "api" and parts[1] == "projects":
            project_id = parts[2]
            payload = self._read_json_body(handler)
            updated = self.state.update_binding(
                project_id,
                name=str(payload.get("name") or "").strip(),
                app_root=str(payload.get("app_root") or "").strip(),
                docs_dir=str(payload.get("docs_dir") or "docs"),
                ai_rules_dir=str(payload.get("ai_rules_dir") or "ai-rules"),
            )
            self._send_json(handler, HTTPStatus.OK, {"project": updated})
            return

        if len(parts) == 3 and parts[0] == "api" and parts[1] == "rule-sets":
            rule_set_id = parts[2]
            payload = self._read_json_body(handler)
            node_rules = payload.get("node_rules")
            if node_rules is not None and not isinstance(node_rules, dict):
                raise ValueError("node_rules must be an object")
            updated = self.state.update_rule_set(
                rule_set_id,
                name=str(payload.get("name")).strip() if "name" in payload else None,
                folder_path=str(payload.get("folder_path")).strip()
                if "folder_path" in payload
                else None,
                node_rules={
                    str(k): [str(item) for item in (v if isinstance(v, list) else [])]
                    for k, v in (node_rules or {}).items()
                }
                if node_rules is not None
                else None,
                create_folder=bool(payload.get("create_folder", False)),
            )
            self._send_json(handler, HTTPStatus.OK, {"rule_set": updated})
            return

        if len(parts) == 4 and parts[0] == "api" and parts[1] == "rule-sets" and parts[3] == "system-md":
            payload = self._read_json_body(handler)
            if "content" not in payload:
                raise ValueError("content is required")
            saved = self._save_rule_set_system_md(parts[2], str(payload.get("content") or ""))
            self._send_json(handler, HTTPStatus.OK, saved)
            return

        self._send_json(handler, HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def handle_delete(self, handler: BaseHTTPRequestHandler) -> None:
        parsed = urlparse(handler.path)
        route = parsed.path.rstrip("/") or "/"

        parts = [segment for segment in route.split("/") if segment]
        if len(parts) == 5 and parts[0] == "api" and parts[1] == "projects" and parts[3] == "tasks":
            project_id = parts[2]
            task_id = parts[4]
            self.state.delete_task(project_id, task_id)
            self._send_json(handler, HTTPStatus.OK, {"deleted": task_id})
            return

        if len(parts) == 3 and parts[0] == "api" and parts[1] == "projects":
            project_id = parts[2]
            self._send_json(handler, HTTPStatus.OK, self.delete_project(project_id))
            return

        if len(parts) == 3 and parts[0] == "api" and parts[1] == "rule-sets":
            rule_set_id = parts[2]
            self.state.delete_rule_set(rule_set_id)
            self._send_json(handler, HTTPStatus.OK, {"deleted": rule_set_id})
            return

        self._send_json(handler, HTTPStatus.NOT_FOUND, {"error": "Not found"})



def create_handler(app: WebApp):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            try:
                app.handle_get(self)
            except (KeyError, FileNotFoundError) as exc:
                app._send_json(self, HTTPStatus.NOT_FOUND, {"error": str(exc)})
            except ValueError as exc:
                app._send_json(self, HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            except Exception as exc:  # noqa: BLE001
                logger.exception("GET failed")
                app._send_json(self, HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

        def do_POST(self) -> None:  # noqa: N802
            try:
                app.handle_post(self)
            except (ValueError, json.JSONDecodeError) as exc:
                app._send_json(self, HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            except KeyError as exc:
                app._send_json(self, HTTPStatus.NOT_FOUND, {"error": str(exc)})
            except Exception as exc:  # noqa: BLE001
                logger.exception("POST failed")
                app._send_json(self, HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

        def do_PUT(self) -> None:  # noqa: N802
            try:
                app.handle_put(self)
            except (ValueError, json.JSONDecodeError) as exc:
                app._send_json(self, HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            except KeyError as exc:
                app._send_json(self, HTTPStatus.NOT_FOUND, {"error": str(exc)})
            except Exception as exc:  # noqa: BLE001
                logger.exception("PUT failed")
                app._send_json(self, HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

        def do_DELETE(self) -> None:  # noqa: N802
            try:
                app.handle_delete(self)
            except KeyError as exc:
                app._send_json(self, HTTPStatus.NOT_FOUND, {"error": str(exc)})
            except Exception as exc:  # noqa: BLE001
                logger.exception("DELETE failed")
                app._send_json(self, HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            logger.info("%s - %s", self.address_string(), format % args)

    return Handler


def serve_web_ui(workflow_root: Path, host: str = "127.0.0.1", port: int = 8787) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    app = WebApp(workflow_root)
    handler_cls = create_handler(app)
    server = ThreadingHTTPServer((host, port), handler_cls)
    logger.info("Web UI served at http://%s:%s", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down Web UI server")
    finally:
        server.server_close()
