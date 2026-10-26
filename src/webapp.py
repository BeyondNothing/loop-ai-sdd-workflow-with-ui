"""Lightweight web UI backend for project binding and workflow orchestration."""

from __future__ import annotations

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

from .agents.registry import DEFAULT_AI_TOOL, list_ai_tools
from .config_loader import load_workflow_config
from .mcp import ensure_mcp_for_agents
from .platform_util import platform_info, platform_label, resolve_prd_path
from .workflow import DevWorkflow

logger = logging.getLogger(__name__)

NODE_IDS = (
    "analyze_requirements",
    "create_plan",
    "design_test_cases",
    "review_plan_and_tests",
    "split_tasks",
    "implement_code",
    "verify_tests",
    "ai_review",
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

    def append_run_log(self, run_id: str, message: str) -> None:
        stamped = f"[{datetime.now().isoformat(timespec='seconds')}] {message}"
        with self.lock:
            run = self.runs[run_id]
            run.logs.append(stamped)
            run.updated_at = datetime.now().isoformat(timespec="seconds")
            self.runs[run_id] = run
            self._save_runs()

    def get_project_run_lock(self, project_id: str) -> threading.Lock:
        """Return a stable per-project lock for run serialization."""
        with self.lock:
            lock = self.project_run_locks.get(project_id)
            if lock is None:
                lock = threading.Lock()
                self.project_run_locks[project_id] = lock
            return lock


class WebApp:
    def __init__(self, workflow_root: Path):
        self.workflow_root = workflow_root.resolve()
        self.static_dir = self.workflow_root / "webui"
        dist_dir = self.static_dir / "dist"
        self.assets_dir = dist_dir if dist_dir.is_dir() else self.static_dir
        self.state = WebState(self.workflow_root)
        self._workflow_config_path = self.workflow_root / "config" / "workflow.yaml"

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
    ) -> None:
        handler.send_response(status.value)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Cache-Control", cache_control)
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)

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

    def _build_runtime_configs(self, run: WorkflowRun, binding: ProjectBinding) -> Path:
        runtime_dir = self._runtime_config_dir(run.project_id, run.run_id)
        base_workflow = self.workflow_root / "config" / "workflow.yaml"
        workflow_raw = yaml.safe_load(base_workflow.read_text(encoding="utf-8")) or {}
        workflow_section = workflow_raw.setdefault("workflow", {})
        workflow_section["app_root"] = binding.app_root
        workflow_section["docs_dir"] = binding.docs_dir
        e2e_section = workflow_section.setdefault("e2e", {})
        if isinstance(e2e_section, dict):
            e2e_section["headless"] = bool(run.headless_all_nodes)

        nodes = workflow_raw.get("nodes") or {}
        if isinstance(nodes, dict):
            for node_cfg in nodes.values():
                if isinstance(node_cfg, dict):
                    node_cfg["tool"] = run.tool
                    if run.headless_all_nodes:
                        node_cfg["mode"] = "headless"

        runtime_workflow = runtime_dir / "workflow.yaml"
        runtime_workflow.write_text(
            yaml.safe_dump(workflow_raw, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

        runtime_rules = {
            "ai_rules_dir": binding.ai_rules_dir,
            "node_rules": binding.node_rules,
        }
        (runtime_dir / "ai-rules.yaml").write_text(
            yaml.safe_dump(runtime_rules, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        return runtime_workflow

    def _run_workflow(self, run_id: str) -> None:
        try:
            run = self.state.get_run(run_id)
            binding = self.state.get_binding(run.project_id)
            project_lock = self.state.get_project_run_lock(run.project_id)
            if project_lock.locked():
                self.state.append_run_log(
                    run_id,
                    "Another run is active for this project, waiting for project lock",
                )

            with project_lock:
                self.state.update_run(run_id, status="running")
                self.state.append_run_log(
                    run_id,
                    f"Workflow started on {platform_label()} ({sys.platform})",
                )

                config_path = self._build_runtime_configs(run, binding)
                wf_cfg = load_workflow_config(config_path)
                if not run.skip_mcp_setup and wf_cfg.e2e_enabled:
                    mcp_result = ensure_mcp_for_agents(
                        self.workflow_root,
                        e2e_headless=wf_cfg.e2e_headless,
                    )
                    self.state.append_run_log(
                        run_id,
                        f"MCP configured: servers={mcp_result.get('servers', [])}",
                    )

                workflow = DevWorkflow(self.workflow_root, config_path)
                source_file = Path(run.requirement_path) if run.requirement_path else None
                if source_file and not source_file.exists():
                    source_file = None

                result = workflow.run(
                    requirement=run.requirement,
                    docs_dir=binding.docs_dir,
                    name=run.requirement_name or None,
                    source_file=source_file,
                    skip_clarification=run.skip_clarification,
                    auto=run.auto,
                    fresh=run.fresh,
                )
                self.state.update_run(
                    run_id,
                    status="completed",
                    result=dict(result),
                    ended_at=datetime.now().isoformat(timespec="seconds"),
                )
                self.state.append_run_log(run_id, "Workflow completed")
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
            headless_all_nodes=bool(payload.get("headless_all_nodes", True)),
            skip_mcp_setup=bool(payload.get("skip_mcp_setup", False)),
            docs_dir=binding.docs_dir,
        )
        self.state.create_run(run)
        if task_id:
            self.state.set_task_last_run(project_id, task_id, run.run_id)
        worker = threading.Thread(target=self._run_workflow, args=(run.run_id,), daemon=True)
        worker.start()
        return self._enriched_run_dict(run)

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
                }
            )
        return nodes

    @staticmethod
    def _enriched_run_dict(run: WorkflowRun) -> dict[str, Any]:
        payload = run.to_dict()
        result = run.result or {}
        payload["current_node"] = result.get("current_node") or ""
        payload["completed_nodes"] = result.get("completed_nodes") or []
        payload["node_outputs"] = result.get("node_outputs") or {}
        return payload

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

        if route == "/api/runs":
            runs = [
                self._enriched_run_dict(self.state.get_run(item["run_id"]))
                for item in self.state.list_runs()
            ]
            self._send_json(handler, HTTPStatus.OK, {"runs": runs})
            return

        if route.startswith("/api/runs/"):
            run_id = route.split("/")[3]
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
            binding = self.state.create_binding(
                name=str(payload.get("name") or "").strip(),
                app_root=str(payload.get("app_root") or "").strip(),
                docs_dir=str(payload.get("docs_dir") or "docs"),
                ai_rules_dir=str(payload.get("ai_rules_dir") or "ai-rules"),
            )
            self._send_json(handler, HTTPStatus.CREATED, {"project": binding})
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

        if route == "/api/runs":
            payload = self._read_json_body(handler)
            run = self.start_run(payload)
            self._send_json(handler, HTTPStatus.CREATED, {"run": run})
            return

        if route.startswith("/api/runs/") and route.endswith("/open-artifact"):
            run_id = route.split("/")[3]
            payload = self._read_json_body(handler)
            node_id = str(payload.get("node_id") or "").strip()
            if not node_id:
                raise ValueError("node_id is required")

            run = self.state.get_run(run_id)
            outputs = (run.result or {}).get("node_outputs") or {}
            rel = str(outputs.get(node_id) or "").strip()
            if not rel:
                raise ValueError(f"No artifact for node: {node_id}")

            binding = self.state.get_binding(run.project_id)
            artifact_path = (Path(binding.app_root) / rel).resolve()
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
            self.state.delete_binding(project_id)
            self._send_json(handler, HTTPStatus.OK, {"deleted": project_id})
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
            except KeyError as exc:
                app._send_json(self, HTTPStatus.NOT_FOUND, {"error": str(exc)})
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
