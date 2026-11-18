"""Run 事件总线：供 SSE 推送进度。"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Any


class RunEventBus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._seq = 0
        self._latest: dict[str, dict[str, Any]] = {}
        self._waiters: dict[str, list[threading.Event]] = defaultdict(list)
        self._project_index: dict[str, set[str]] = defaultdict(set)

    def publish(self, *, run_id: str, project_id: str, event: str, payload: dict[str, Any]) -> int:
        with self._lock:
            self._seq += 1
            seq = self._seq
            message = {
                "seq": seq,
                "event": event,
                "run_id": run_id,
                "project_id": project_id,
                "ts": time.time(),
                "payload": payload,
            }
            self._latest[run_id] = message
            self._project_index[project_id].add(run_id)
            waiters = list(self._waiters.get(run_id, []))
            waiters.extend(self._waiters.get(f"project:{project_id}", []))
        for event_flag in waiters:
            event_flag.set()
        return seq

    def latest(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            item = self._latest.get(run_id)
            return dict(item) if item else None

    def wait(self, key: str, *, last_seq: int, timeout: float = 25.0) -> dict[str, Any] | None:
        """key = run_id 或 project:{project_id}。"""
        deadline = time.time() + timeout
        while True:
            with self._lock:
                if key.startswith("project:"):
                    project_id = key.split(":", 1)[1]
                    candidates = [
                        self._latest[rid]
                        for rid in self._project_index.get(project_id, set())
                        if rid in self._latest
                    ]
                    newer = [c for c in candidates if int(c.get("seq") or 0) > last_seq]
                    if newer:
                        return dict(max(newer, key=lambda c: int(c.get("seq") or 0)))
                else:
                    item = self._latest.get(key)
                    if item and int(item.get("seq") or 0) > last_seq:
                        return dict(item)
                flag = threading.Event()
                self._waiters[key].append(flag)
            remaining = deadline - time.time()
            if remaining <= 0:
                with self._lock:
                    waiters = self._waiters.get(key, [])
                    if flag in waiters:
                        waiters.remove(flag)
                return None
            flag.wait(timeout=min(remaining, 1.0))
            with self._lock:
                waiters = self._waiters.get(key, [])
                if flag in waiters:
                    waiters.remove(flag)


EVENT_BUS = RunEventBus()
