"""交互式 CLI 公共逻辑 — 轮询产出、自动结束进程组；Web UI 无 TTY 时经 Warp 唤起 omp。"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import quote

from collections.abc import Callable

from .base import AIToolResult, CompletionCheck

logger = logging.getLogger(__name__)

_run_log: Callable[[str], None] | None = None


def set_run_log_callback(callback: Callable[[str], None] | None) -> None:
    global _run_log
    _run_log = callback


def _emit_run_log(message: str) -> None:
    logger.info(message)
    if _run_log is not None:
        _run_log(message)


def format_shell_command(cmd: list[str]) -> str:
    return " ".join(shlex_quote(part) for part in cmd)


def log_launch_command(cmd: list[str], cwd: str, *, label: str = "CLI") -> str:
    """把可复制的启动命令写入运行日志，方便手动执行。"""
    rendered = format_shell_command(cmd)
    workdir = str(Path(cwd).resolve())
    manual = f"cd {shlex_quote(workdir)} && {rendered}"
    _emit_run_log(f"[{label}] 工作目录: {workdir}")
    _emit_run_log(f"[{label}] 启动命令: {rendered}")
    _emit_run_log(f"[{label}] 手动执行: {manual}")
    print(f"[{label}] 启动命令:\n  {manual}\n", flush=True)
    return manual


_POLL_SECONDS = 1.0
_WARP_LAUNCH_TIMEOUT_SECONDS = 45 * 60


def run_interactive_subprocess(
    cmd: list[str],
    cwd: str,
    *,
    tool_name: str,
    banner_title: str,
    completion_hint: str,
    completion_check: CompletionCheck | None = None,
    env: dict[str, str] | None = None,
) -> AIToolResult:
    print("\n" + "=" * 60)
    print(banner_title)
    if completion_check:
        print(completion_hint)
    else:
        print("退出 CLI 后 workflow 继续")
    print("=" * 60 + "\n")

    log_launch_command(cmd, cwd, label=tool_name)

    if _should_bridge_to_warp(completion_check):
        try:
            return _run_interactive_via_warp_window(
                cmd=cmd,
                cwd=cwd,
                tool_name=tool_name,
                completion_check=completion_check,
                env=env,
            )
        except Exception as exc:  # noqa: BLE001
            _emit_run_log(f"Warp 启动失败，回退后台子进程: {exc}")
            logger.warning("Warp bridge launch failed, fallback to local subprocess: %s", exc)

    proc = subprocess.Popen(cmd, cwd=cwd, env=env, start_new_session=True)
    try:
        while proc.poll() is None:
            if completion_check and completion_check():
                logger.info("检测到节点产出已完成，结束交互 CLI")
                print("\n节点产出已完成，自动退出 CLI，workflow 继续…\n")
                _stop_process(proc)
                return AIToolResult(
                    content="",
                    tool_name=tool_name,
                    success=True,
                    message="节点产出已完成，已自动退出 CLI",
                )
            time.sleep(_POLL_SECONDS)
    except KeyboardInterrupt:
        _stop_process(proc)
        raise

    return AIToolResult(
        content="",
        tool_name=tool_name,
        success=proc.returncode == 0,
        message="" if proc.returncode == 0 else f"CLI 退出码 {proc.returncode}",
    )


def _should_bridge_to_warp(completion_check: CompletionCheck | None) -> bool:
    if completion_check is None:
        return False
    if os.getenv("AI4SE_WARP_BRIDGE", "1").strip().lower() in {"0", "false", "no", "off"}:
        return False
    if sys.platform != "darwin":
        return False
    return not (sys.stdin.isatty() and sys.stdout.isatty())


def _run_interactive_via_warp_window(
    *,
    cmd: list[str],
    cwd: str,
    tool_name: str,
    completion_check: CompletionCheck,
    env: dict[str, str] | None,
) -> AIToolResult:
    launch_uri = f"warp://action/new_window?path={quote(str(Path(cwd).resolve()))}"
    subprocess.run(["open", launch_uri], check=False)
    time.sleep(1.0)
    launcher = _write_warp_launcher_script(cmd, cwd, env)
    logger.info("Warp 启动脚本已生成: %s", launcher)
    _emit_run_log(f"已在 Warp 新窗口注入启动脚本: {launcher}")
    _emit_run_log(f"若未自动唤起，可在 Warp 中手动执行: {shlex_quote(str(launcher))}")
    print(f"[warp] 新窗口已打开，正在注入启动脚本: {launcher}", flush=True)
    _send_command_to_frontmost_warp(shlex_quote(str(launcher)))

    start = time.time()
    while True:
        if completion_check():
            return AIToolResult(
                content="",
                tool_name=tool_name,
                success=True,
                message="已在 Warp 新窗口启动交互会话",
            )
        if time.time() - start > _WARP_LAUNCH_TIMEOUT_SECONDS:
            return AIToolResult(
                content="",
                tool_name=tool_name,
                success=False,
                message="Warp 交互会话超时，未检测到节点产出",
            )
        time.sleep(_POLL_SECONDS)


def _write_warp_launcher_script(
    cmd: list[str],
    cwd: str,
    env: dict[str, str] | None,
) -> Path:
    fd, path = tempfile.mkstemp(prefix="ai4se_warp_", suffix=".sh")
    launcher = Path(path)
    try:
        lines = [
            "#!/usr/bin/env bash",
            "set -e",
            "trap 'rm -f -- \"$0\"' EXIT",
        ]
        lines.append(f"cd {shlex_quote(str(Path(cwd).resolve()))}")

        if env:
            for key in ("OMP_MCP_TIMEOUT_MS", "PATH"):
                value = env.get(key)
                if value:
                    lines.append(f"export {key}={shlex_quote(value)}")

        lines.append(" ".join(shlex_quote(part) for part in cmd))
        os.write(fd, ("\n".join(lines) + "\n").encode("utf-8"))
    finally:
        os.close(fd)
    launcher.chmod(0o700)
    return launcher


def _send_command_to_frontmost_warp(command_line: str) -> None:
    script = [
        'tell application "Warp" to activate',
        'tell application "System Events"',
        f'keystroke "{_escape_applescript_text(command_line)}"',
        "key code 36",
        "end tell",
    ]
    result = subprocess.run(
        ["osascript", *sum([["-e", line] for line in script], [])],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "osascript failed").strip())


def _escape_applescript_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def shlex_quote(value: str) -> str:
    if value == "":
        return "''"
    if all(ch.isalnum() or ch in "@%_+=:,./-" for ch in value):
        return value
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _stop_process(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        if hasattr(os, "killpg"):
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        else:
            proc.terminate()
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            if hasattr(os, "killpg"):
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            else:
                proc.kill()
            proc.wait(timeout=5)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            pass
    except ProcessLookupError:
        pass
