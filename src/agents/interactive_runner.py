"""交互式 CLI 公共逻辑 — 轮询产出、自动结束进程组。"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote

from .base import AIToolResult, CompletionCheck

logger = logging.getLogger(__name__)

_POLL_SECONDS = 1.0
_WARP_LAUNCH_TIMEOUT_SECONDS = 45 * 60
_WARP_LAUNCHER_PATH = Path("/tmp/ai4se_warp_launch.sh")


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
    # Web UI 服务可能从终端/PTY 启动，进程 stdin/stdout 是 TTY；若按 TTY 判断会误判为“内联执行”，
    # 导致交互节点不开 Warp 窗口（原版也因此最初不弹窗）。因此 darwin 下默认一律桥接到新 Warp 窗口，
    # 让每个交互节点可见可交互。纯 CLI 想内联跑: export AI4SE_WARP_BRIDGE=0
    if completion_check is None:
        return False
    if os.getenv("AI4SE_WARP_BRIDGE", "1").strip() in {"0", "false", "False"}:
        return False
    if sys.platform != "darwin":
        return False
    return True


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
    _send_command_to_frontmost_warp(f"bash {shlex_quote(str(launcher))}")

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
    lines = [
        "#!/usr/bin/env bash",
        "set -e",
    ]
    lines.append(f"cd {shlex_quote(str(Path(cwd).resolve()))}")

    if env:
        for key in ("OMP_MCP_TIMEOUT_MS", "PATH"):
            value = env.get(key)
            if value:
                lines.append(f"export {key}={shlex_quote(value)}")

    lines.append(" ".join(shlex_quote(part) for part in cmd))
    _WARP_LAUNCHER_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _WARP_LAUNCHER_PATH.chmod(0o700)
    launcher = _WARP_LAUNCHER_PATH
    return launcher


def _send_command_to_frontmost_warp(command_line: str) -> None:
    # 用剪贴板粘贴命令，避免 keystroke 逐字输入丢字符（如 bsh 少 a）。
    subprocess.run(["pbcopy"], input=command_line.encode("utf-8"), check=False)
    script = [
        'tell application "Warp" to activate',
        "delay 0.3",
        'tell application "System Events"',
        'keystroke "v" using command down',
        "delay 0.1",
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
