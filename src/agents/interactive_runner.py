"""交互式 CLI 公共逻辑 — 轮询产出、自动结束进程组；Web UI 无 TTY 时经 Warp 唤起。

macOS：交互节点经 Warp 执行启动脚本。已有 Warp 进程时复用当前窗口注入下一节点；
仅在 Warp 未运行时才 new_window。项目若在 Downloads/Desktop/Documents，
须给 Warp / omp 开启「文稿和数据」或「完全磁盘访问」，否则 omp --cwd 会 EPERM。
详见 README「Web 操作台 → Warp 权限（macOS）」。
"""

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

    from ..run_control import (
        RunCancelled,
        is_cancel_requested,
        register_process,
        unregister_process,
    )

    proc = subprocess.Popen(cmd, cwd=cwd, env=env, start_new_session=True)
    register_process(proc)
    try:
        while proc.poll() is None:
            if is_cancel_requested():
                _emit_run_log("收到取消请求，终止交互 CLI")
                _stop_process(proc)
                raise RunCancelled("运行已被用户取消（交互 CLI）")
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
    finally:
        unregister_process(proc)

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


_TCC_SENSITIVE_HOME_DIRS = frozenset({"Downloads", "Desktop", "Documents"})


def _warp_launcher_dir() -> Path:
    path = Path.home() / ".ai4se" / "warp"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cleanup_warp_launchers(out_dir: Path, *, keep: int = 20) -> None:
    """只保留最近 keep 个启动脚本，避免 ~/.ai4se/warp 无限堆积。"""
    patterns = ("ai4se_warp_*.sh", "ai4se_warp_*.command")
    files: list[Path] = []
    for pattern in patterns:
        files.extend(out_dir.glob(pattern))
    files.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    for old in files[keep:]:
        try:
            old.unlink(missing_ok=True)
        except OSError:
            pass


def _is_tcc_sensitive_path(path: Path) -> bool:
    """Downloads/Desktop/Documents 下路径：Warp 内 omp --cwd 极易 EPERM。"""
    try:
        resolved = path.expanduser().resolve()
        rel = resolved.relative_to(Path.home().resolve())
    except (ValueError, OSError, RuntimeError):
        return False
    return bool(rel.parts) and rel.parts[0] in _TCC_SENSITIVE_HOME_DIRS


def _wait_external_interactive(
    *,
    tool_name: str,
    completion_check: CompletionCheck,
    label: str,
) -> AIToolResult:
    from ..run_control import RunCancelled, emit_progress, is_cancel_requested

    start = time.time()
    last_heartbeat = 0.0
    while True:
        if is_cancel_requested():
            _emit_run_log(f"收到取消请求，停止等待 {label} 交互产出")
            raise RunCancelled(f"运行已被用户取消（{label} 等待）")
        if completion_check():
            return AIToolResult(
                content="",
                tool_name=tool_name,
                success=True,
                message=f"已在 {label} 启动交互会话",
            )
        elapsed = time.time() - start
        if elapsed > _WARP_LAUNCH_TIMEOUT_SECONDS:
            return AIToolResult(
                content="",
                tool_name=tool_name,
                success=False,
                message=f"{label} 交互会话超时，未检测到节点产出",
            )
        if elapsed - last_heartbeat >= 5.0:
            last_heartbeat = elapsed
            # 不要写 current_node=tool_name（如 oh_my_pi），否则续跑会当成未知节点
            emit_progress(
                {
                    "phase": "heartbeat",
                    "elapsed_ms": int(elapsed * 1000),
                    "tool": tool_name,
                }
            )
        time.sleep(_POLL_SECONDS)


def _is_warp_running() -> bool:
    """Warp 稳定版进程名常为 stable，不能用 name contains "Warp" 判断。"""
    probes = [
        # exists process "Warp" 可解析应用名，即使 displayed name 是 stable
        'tell application "System Events" to exists process "Warp"',
        'tell application "System Events" to '
        'exists (first process whose bundle identifier contains "dev.warp")',
    ]
    for probe in probes:
        try:
            result = subprocess.run(
                ["osascript", "-e", probe],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            continue
        if result.stdout.strip().lower() == "true":
            return True
    # 无辅助功能权限时仍可用路径兜底
    try:
        result = subprocess.run(
            ["pgrep", "-f", "/Applications/Warp.app/"],
            capture_output=True,
            check=False,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False
    return result.returncode == 0


def _ensure_warp_window(safe_dir: Path) -> bool:
    """确保有可用 Warp 窗口。返回 True=复用已有，False=新开窗口。"""
    if _is_warp_running():
        _emit_run_log("复用已有 Warp 窗口（不再 new_window）")
        try:
            subprocess.run(
                ["osascript", "-e", 'tell application "Warp" to activate'],
                capture_output=True,
                check=False,
                timeout=5,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass
        time.sleep(0.4)
        return True

    launch_uri = f"warp://action/new_window?path={quote(str(safe_dir))}"
    _emit_run_log(f"Warp 未运行，打开新窗口: {launch_uri}")
    subprocess.run(["open", launch_uri], check=False)
    time.sleep(1.0)
    return False


def _run_interactive_via_warp_window(
    *,
    cmd: list[str],
    cwd: str,
    tool_name: str,
    completion_check: CompletionCheck,
    env: dict[str, str] | None,
) -> AIToolResult:
    # Warp 窗口开在 ~/.ai4se/warp；业务根靠 omp --cwd（勿把 shell cwd 直接放 Downloads）
    workdir = Path(cwd).expanduser().resolve()
    safe_dir = _warp_launcher_dir()
    reused = _ensure_warp_window(safe_dir)
    launcher = _write_warp_launcher_script(cmd, cwd, env)
    logger.info("Warp 启动脚本已生成: %s", launcher)
    _emit_run_log(f"Warp 启动脚本已生成: {launcher}")
    _emit_run_log(f"Warp 窗口工作目录: {safe_dir}")
    if _is_tcc_sensitive_path(workdir):
        _emit_run_log(
            "提示: 项目在 Downloads/Desktop/Documents。"
            "若 omp 报 EPERM，请按 README「Warp 权限（macOS）」给 Warp/omp 开磁盘访问后重试。"
        )
    mode = "复用窗口" if reused else "新窗口"
    print(f"[warp] {mode}，正在注入启动脚本: {launcher}", flush=True)
    launch_cmd = f"bash {shlex_quote(str(launcher))}"
    _emit_run_log(f"若未自动唤起，可在 Warp 中手动执行: {launch_cmd}")
    try:
        # 复用时先 Ctrl+C，避免上一节点 omp 仍占着会话导致命令打进对话里
        _send_command_to_frontmost_warp(launch_cmd, interrupt_first=reused)
        _emit_run_log(f"已向 Warp 注入启动命令: {launch_cmd}")
    except Exception as exc:  # noqa: BLE001
        _emit_run_log(f"Warp 自动键入失败（请手动执行）: {exc}")
        logger.warning("Warp osascript inject failed: %s", exc)

    return _wait_external_interactive(
        tool_name=tool_name,
        completion_check=completion_check,
        label="Warp",
    )


def _write_warp_launcher_script(
    cmd: list[str],
    cwd: str,
    env: dict[str, str] | None,
    *,
    shell_cwd: Path | None = None,
) -> Path:
    # 脚本文件仍落在 ~/.ai4se/warp；shell_cwd 可指向项目根（Terminal）或安全目录（Warp）
    workdir = Path(cwd).expanduser().resolve()
    out_dir = _warp_launcher_dir()
    _cleanup_warp_launchers(out_dir, keep=20)
    run_cwd = (shell_cwd or out_dir).expanduser().resolve()
    fd, path = tempfile.mkstemp(prefix="ai4se_warp_", suffix=".sh", dir=str(out_dir))
    launcher = Path(path)
    try:
        lines = [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            f"cd {shlex_quote(str(run_cwd))}",
            f"export PWD={shlex_quote(str(run_cwd))}",
        ]

        if env:
            for key in ("OMP_MCP_TIMEOUT_MS", "PATH"):
                value = env.get(key)
                if value:
                    lines.append(f"export {key}={shlex_quote(value)}")

        lines.append(f"# project app_root: {workdir}")
        # 不用 exec：omp 退出后留在同一 shell，下一节点可复用本窗注入
        lines.append(" ".join(shlex_quote(part) for part in cmd))
        os.write(fd, ("\n".join(lines) + "\n").encode("utf-8"))
    finally:
        os.close(fd)
    launcher.chmod(0o700)
    try:
        subprocess.run(
            ["xattr", "-c", str(launcher)],
            capture_output=True,
            check=False,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return launcher


def _send_command_to_frontmost_warp(
    command_line: str,
    *,
    interrupt_first: bool = False,
) -> None:
    script = [
        'tell application "Warp" to activate',
        "delay 0.25",
        'tell application "System Events"',
    ]
    if interrupt_first:
        # 打断上一节点仍在跑的 omp，回到 shell 再注入
        script.extend(
            [
                'keystroke "c" using control down',
                "delay 0.35",
                'keystroke "c" using control down',
                "delay 0.45",
            ]
        )
    script.extend(
        [
            f'keystroke "{_escape_applescript_text(command_line)}"',
            "key code 36",
            "end tell",
        ]
    )
    try:
        result = subprocess.run(
            ["osascript", *sum([["-e", line] for line in script], [])],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("osascript 向 Warp 注入命令超时（20s）") from exc
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
