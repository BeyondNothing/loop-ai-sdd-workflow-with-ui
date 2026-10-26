"""AI 工具注册表。"""

from .base import AITool
from .claude_code_agent import ClaudeCodeTool
from .cursor_agent import CursorTool
from .echo_agent import EchoTool
from .oh_my_pi_agent import OhMyPiTool

_OH_MY_PI = OhMyPiTool()

_TOOLS: dict[str, AITool] = {
    "cursor": CursorTool(),
    "claude_code": ClaudeCodeTool(),
    "echo": EchoTool(),
    "oh_my_pi": _OH_MY_PI,
    "omp": _OH_MY_PI,
}


def get_ai_tool(name: str) -> AITool:
    if name not in _TOOLS:
        raise ValueError(
            f"Unknown AI tool: {name}. Available: {', '.join(_TOOLS.keys())}"
        )
    return _TOOLS[name]


def list_ai_tools() -> list[dict[str, str]]:
    """返回 UI 可选工具列表（去重别名，默认顺序）。"""
    catalog: list[dict[str, str]] = [
        {
            "id": "omp",
            "name": "Oh My Pi",
            "description": "omp CLI，Headless 与交互模式",
        },
        {
            "id": "cursor",
            "name": "Cursor",
            "description": "Cursor Agent CLI（agent / cursor-agent）",
        },
        {
            "id": "claude_code",
            "name": "Claude Code",
            "description": "Claude Code CLI（claude / claude-code）",
        },
        {
            "id": "echo",
            "name": "Echo",
            "description": "调试占位，不调用外部 AI",
        },
    ]
    return [item for item in catalog if item["id"] in _TOOLS]


DEFAULT_AI_TOOL = "omp"
