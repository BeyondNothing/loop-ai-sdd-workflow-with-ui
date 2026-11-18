"""Web 运行控制：协作式取消标记 + 节点进度心跳 + 可取消子进程。"""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from typing import Any, Callable


class RunCancelled(Exception):
    """用户请求取消当前工作流。"""


ProgressCallback = Callable[[dict[str, Any]], None]

_lock = threading.Lock()
_active_run_id: str | None = None
_global_cancel_check: Callable[[], bool] | None = None
_progress_callback: ProgressCallback | None = None
_active_procs: list[subprocess.Popen] = []


def set_active_run(run_id: str | None, cancel_check: Callable[[], bool] | None = None) -> None:
    global _active_run_id, _global_cancel_check
    with _lock:
        _active_run_id = run_id
        _global_cancel_check = cancel_check


def set_progress_callback(callback: ProgressCallback | None) -> None:
    global _progress_callback
    with _lock:
        _progress_callback = callback


def emit_progress(payload: dict[str, Any]) -> None:
    with _lock:
        callback = _progress_callback
    if callback is None:
        return
    try:
        callback(payload)
    except Exception:  # noqa: BLE001
        pass


def is_cancel_requested() -> bool:
    with _lock:
        check = _global_cancel_check
    if check is None:
        return False
    try:
        return bool(check())
    except Exception:  # noqa: BLE001
        return False


def raise_if_cancelled(context: str = "") -> None:
    if is_cancel_requested():
        suffix = f"（{context}）" if context else ""
        raise RunCancelled(f"运行已被用户取消{suffix}")


def register_process(proc: subprocess.Popen) -> None:
    with _lock:
        _active_procs.append(proc)


def unregister_process(proc: subprocess.Popen) -> None:
    with _lock:
        if proc in _active_procs:
            _active_procs.remove(proc)


def kill_active_processes() -> int:
    """取消时强杀当前注册的子进程组。"""
    with _lock:
        procs = list(_active_procs)
    killed = 0
    for proc in procs:
        if _stop_process(proc):
            killed += 1
        unregister_process(proc)
    return killed


def _stop_process(proc: subprocess.Popen) -> bool:
    if proc.poll() is not None:
        return False
    try:
        if hasattr(os, "killpg"):
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        else:
            proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if hasattr(os, "killpg"):
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            else:
                proc.kill()
            proc.wait(timeout=3)
        return True
    except (ProcessLookupError, OSError, subprocess.TimeoutExpired):
        return False


def run_cancellable_subprocess(
    cmd: list[str],
    *,
    cwd: str,
    env: dict[str, str] | None = None,
    timeout: float | None = 620,
    poll_seconds: float = 0.5,
    heartbeat_seconds: float = 5.0,
    current_node: str = "",
) -> subprocess.CompletedProcess[str]:
    """可取消的 headless 子进程（替代阻塞的 subprocess.run）。"""
    raise_if_cancelled("启动子进程前")
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    register_process(proc)
    started = time.time()
    last_heartbeat = 0.0
    try:
        while proc.poll() is None:
            if is_cancel_requested():
                _stop_process(proc)
                raise RunCancelled("运行已被用户取消（headless 子进程）")
            elapsed = time.time() - started
            if timeout is not None and elapsed > timeout:
                _stop_process(proc)
                raise subprocess.TimeoutExpired(cmd, timeout)
            if heartbeat_seconds > 0 and (elapsed - last_heartbeat) >= heartbeat_seconds:
                last_heartbeat = elapsed
                payload: dict[str, Any] = {
                    "phase": "heartbeat",
                    "elapsed_ms": int(elapsed * 1000),
                }
                if current_node:
                    payload["current_node"] = current_node
                emit_progress(payload)
            time.sleep(poll_seconds)
        stdout, stderr = proc.communicate()
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=proc.returncode if proc.returncode is not None else -1,
            stdout=stdout or "",
            stderr=stderr or "",
        )
    finally:
        unregister_process(proc)
