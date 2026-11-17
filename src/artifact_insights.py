"""从任务产出文档解析 UI 洞察：发布置信度、用例 QA 审批状态。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .parsers.approval_parser import parse_test_cases_approval
from .parsers.test_report_parser import last_result_table, parse_test_passed
from .requirement_dir import make_requirement_slug, resolve_docs_path

_CONF_PATTERNS = (
    re.compile(r"最终置信度[：:\s]*([01](?:\.\d+)?)"),
    re.compile(r"发布置信度[：:\s]*([01](?:\.\d+)?)"),
    re.compile(r"置信度[：:\s]*([01](?:\.\d+)?)"),
    re.compile(r"release[_\s-]?confidence[：:\s]*([01](?:\.\d+)?)", re.I),
)
_REACH_PATTERNS = (
    re.compile(r"是否达到\s*0\.8[：:\s]*(是|否|true|false|yes|no)", re.I),
    re.compile(r"达到\s*0\.8[：:\s]*(是|否|true|false|yes|no)", re.I),
)


def resolve_task_docs_path(
    app_root: str | Path,
    *,
    docs_base: str = "spec",
    task_name: str = "",
    run_docs_dir: str | None = None,
) -> Path:
    app = Path(app_root).expanduser().resolve()
    if run_docs_dir:
        return resolve_docs_path(app, run_docs_dir)
    slug = make_requirement_slug(task_name or "task", name=task_name or None)
    base = Path(docs_base)
    relative = str(base / slug) if not base.is_absolute() else str(Path(base) / slug)
    return resolve_docs_path(app, relative)


def parse_release_confidence(content: str) -> dict[str, Any]:
    score: float | None = None
    for pattern in _CONF_PATTERNS:
        match = pattern.search(content)
        if match:
            try:
                score = float(match.group(1))
                break
            except ValueError:
                continue

    reached: bool | None = None
    if score is not None:
        reached = score >= 0.8
    for pattern in _REACH_PATTERNS:
        match = pattern.search(content)
        if match:
            token = match.group(1).strip().lower()
            reached = token in {"是", "true", "yes"}
            break

    reasons: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if any(key in stripped for key in ("评分依据", "置信度依据", "残余风险", "补测")):
            if len(stripped) > 4:
                reasons.append(stripped[:200])
        if len(reasons) >= 5:
            break

    return {
        "score": score,
        "reached_0_8": reached,
        "has_report": bool(content.strip()),
        "test_passed": parse_test_passed(content) if content.strip() else None,
        "result_rows": _summarize_result_table(content),
        "highlights": reasons,
    }


def _summarize_result_table(content: str) -> dict[str, int]:
    table = last_result_table(content)
    summary = {"pass": 0, "skip": 0, "fail": 0, "blocked": 0, "other": 0}
    if not table or len(table) < 2:
        return summary
    # find result column
    header = [cell.lower() for cell in table[0]]
    result_idx = 1
    for idx, cell in enumerate(header):
        if cell in {"结果", "判定", "结论", "result", "status"}:
            result_idx = idx
            break
    for row in table[1:]:
        if result_idx >= len(row):
            summary["other"] += 1
            continue
        value = row[result_idx].strip().lower()
        if value in summary:
            summary[value] += 1
        elif value in {"passed", "ok", "通过"}:
            summary["pass"] += 1
        elif value in {"skipped", "跳过"}:
            summary["skip"] += 1
        elif value in {"failed", "失败"}:
            summary["fail"] += 1
        else:
            summary["other"] += 1
    return summary


def build_task_insights(
    app_root: str | Path,
    *,
    docs_base: str,
    task_name: str,
    run_docs_dir: str | None = None,
) -> dict[str, Any]:
    docs_path = resolve_task_docs_path(
        app_root,
        docs_base=docs_base,
        task_name=task_name,
        run_docs_dir=run_docs_dir,
    )
    test_cases_path = docs_path / "02-test-cases.md"
    report_path = docs_path / "05-test-report.md"

    qa_status = "missing"
    qa_note = ""
    if test_cases_path.is_file():
        approval = parse_test_cases_approval(test_cases_path.read_text(encoding="utf-8"))
        qa_status = approval.status
        qa_note = approval.user_note

    confidence = {
        "score": None,
        "reached_0_8": None,
        "has_report": False,
        "test_passed": None,
        "result_rows": {"pass": 0, "skip": 0, "fail": 0, "blocked": 0, "other": 0},
        "highlights": [],
    }
    if report_path.is_file():
        confidence = parse_release_confidence(report_path.read_text(encoding="utf-8"))

    return {
        "docs_path": str(docs_path),
        "exists": docs_path.is_dir(),
        "qa_review": {
            "status": qa_status,
            "user_note": qa_note,
            "file": str(test_cases_path) if test_cases_path.is_file() else "",
            "async": True,
            "blocks_core_flow": False,
        },
        "release_confidence": {
            **confidence,
            "file": str(report_path) if report_path.is_file() else "",
            "threshold": 0.8,
        },
    }


def set_test_cases_approval(
    docs_path: Path,
    *,
    status: str = "approved",
    user_note: str = "",
) -> dict[str, Any]:
    """更新 02-test-cases.md 中的 test_cases_approval（QA 异步审批）。"""
    status = status.strip().lower() or "approved"
    if status not in {"pending", "approved"}:
        raise ValueError("status must be pending or approved")
    target = docs_path / "02-test-cases.md"
    if not target.is_file():
        raise FileNotFoundError(f"找不到测试用例文档: {target}")

    import yaml

    content = target.read_text(encoding="utf-8")
    body = yaml.safe_dump(
        {
            "status": status,
            "confirmed_at": "",
            "user_note": user_note,
        },
        allow_unicode=True,
        sort_keys=False,
    ).strip()
    block = f"```yaml test_cases_approval\n{body}\n```"
    pattern = re.compile(
        r"```yaml\s+test_cases_approval\s*\n.*?```",
        re.DOTALL | re.IGNORECASE,
    )
    if pattern.search(content):
        content = pattern.sub(block, content, count=1)
    else:
        content = content.rstrip() + "\n\n" + block + "\n"
    target.write_text(content, encoding="utf-8")
    approval = parse_test_cases_approval(content)
    return {"status": approval.status, "user_note": approval.user_note, "file": str(target)}
