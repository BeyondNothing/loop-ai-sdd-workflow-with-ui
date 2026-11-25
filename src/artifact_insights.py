"""从任务产出文档解析 UI 洞察：发布置信度、用例 QA 审批状态。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .parsers.approval_parser import parse_test_cases_approval
from .parsers.test_report_parser import (
    _RESULT_HEADERS,
    _classify,
    _norm_header,
    extract_markdown_tables,
    last_result_table,
    parse_test_passed,
)
from .requirement_dir import make_requirement_slug, resolve_docs_path

_CONF_PATTERNS = (
    re.compile(r"最终置信度[：:\s]*[*`_\s]*([01](?:\.\d+)?)"),
    re.compile(r"发布置信度[：:\s]*[*`_\s]*([01](?:\.\d+)?)"),
    re.compile(r"置信度[：:\s]*[*`_\s]*([01](?:\.\d+)?)"),
    re.compile(r"release[_\s-]?confidence[：:\s]*[*`_\s]*([01](?:\.\d+)?)", re.I),
)
_REACH_PATTERNS = (
    re.compile(r"是否达到\s*0\.8[：:\s]*(是|否|true|false|yes|no)", re.I),
    re.compile(r"达到\s*0\.8[：:\s]*(是|否|true|false|yes|no)", re.I),
    # 「最终置信度：0.82（达到 0.8 阈值）」这类写法
    re.compile(r"[（(]\s*未?\s*达到\s*0\.8", re.I),
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
        if not match:
            continue
        # 无捕获组时（如「（未达到 0.8 阈值）」）按整段文本判断是否带「未」
        if match.re.groups >= 1:
            token = match.group(1).strip().lower()
            reached = token in {"是", "true", "yes"}
        else:
            reached = "未" not in match.group(0)
        break

    reasons: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("|"):
            continue
        text = stripped.lstrip("-*• ").strip()
        # 只收「扣分 / 风险 / 盲区」这类结论条目，跳过引导句
        if any(key in text for key in ("扣分", "残余风险", "盲区", "没做", "未做")):
            if len(text) > 10 and not text.endswith(("：", ":")):
                reasons.append(text[:200])
        if len(reasons) >= 4:
            break

    rows = parse_result_rows(content)
    return {
        "score": score,
        "reached_0_8": reached,
        "has_report": bool(content.strip()),
        "test_passed": parse_test_passed(content) if content.strip() else None,
        "result_rows": _summarize_result_table(content),
        "highlights": reasons,
        "basis": _extract_confidence_section(content),
        "rows": rows,
        "issues": _collect_issues(content, rows),
    }


_CONFIDENCE_HEADINGS = ("置信度评估", "置信度", "评分依据")
_ANY_HEADING = re.compile(r"^(#{1,6})\s*(.*)$")


def _extract_confidence_section(content: str) -> str:
    """抽取报告里的「置信度评估」整段 markdown（含评分依据、补测说明）。"""
    body = _strip_workflow_status(content)
    lines = body.splitlines()
    start = -1
    start_level = 0
    for idx, line in enumerate(lines):
        match = _ANY_HEADING.match(line.strip())
        if not match:
            continue
        title = match.group(2)
        if any(key in title for key in _CONFIDENCE_HEADINGS):
            start = idx
            start_level = len(match.group(1))
            break
    if start < 0:
        return ""

    collected: list[str] = []
    collected.append(lines[start])
    for line in lines[start + 1 :]:
        match = _ANY_HEADING.match(line.strip())
        if match:
            level = len(match.group(1))
            title = match.group(2)
            same_block = any(key in title for key in _CONFIDENCE_HEADINGS)
            # 同级仍是「置信度/评分依据」小标题 → 属同一段；否则同级或更高标题即结束
            if level <= start_level and not same_block:
                break
        collected.append(line)
    return "\n".join(collected).strip()


_ISSUE_SECTION = re.compile(r"^#{2,4}\s*.*(问题|缺陷|风险).*$", re.M)
_HEADING = re.compile(r"^#{1,6}\s")


def _collect_issues(content: str, rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """汇总质量问题：未通过用例 + 报告「问题与建议」章节条目。"""
    issues: list[dict[str, str]] = [
        {"source": "case", "level": row["result"], "text": row["id"]}
        for row in rows
        if row["result"] in {"fail", "blocked"}
    ]

    body = _strip_workflow_status(content)
    match = _ISSUE_SECTION.search(body)
    if match:
        collected = 0
        for raw in body[match.end() :].splitlines():
            line = raw.strip()
            if not line:
                continue
            if _HEADING.match(line) and collected:
                break
            if line.startswith(("-", "*", "|")) or re.match(r"^\d+[.、)]", line):
                text = line.lstrip("-*|• ").strip()
                if len(text) >= 8 and not text.startswith(("---", ":")):
                    issues.append({"source": "report", "level": "note", "text": text[:200]})
                    collected += 1
            if collected >= 10:
                break
    return issues


def _strip_workflow_status(content: str) -> str:
    marker = "## Workflow 状态"
    return content.split(marker, 1)[0]


# --- 测试用例文档解析（02-test-cases.md）---

_CASE_ID = re.compile(r"\bTC-[A-Z]+-\d+\b")
_CASE_HEADING = re.compile(r"^#{2,6}\s+(TC-[A-Z]+-\d+)\s*(.*)$")


def parse_case_catalog(content: str) -> dict[str, dict[str, str]]:
    """解析测试用例文档：总览表补元信息，明细章节作为 detail markdown。

    返回 {用例编号: {name, case_type, priority, auto, detail}}。
    """
    body = _strip_workflow_status(content)
    catalog: dict[str, dict[str, str]] = {}

    for table in extract_markdown_tables(body):
        if len(table) < 2:
            continue
        header = [_norm_header(cell) for cell in table[0]]
        id_idx = _find_header(header, ("编号", "用例编号", "id", "case"))
        if id_idx is None:
            continue
        name_idx = _find_header(header, ("名称", "用例名称", "name", "标题"))
        type_idx = _find_header(header, ("类型", "type", "层级"))
        priority_idx = _find_header(header, ("优先级", "priority"))
        auto_idx = _find_header(header, ("可自动执行", "自动化", "auto"))
        for row in table[1:]:
            if id_idx >= len(row):
                continue
            case_id = row[id_idx].strip()
            if not _CASE_ID.fullmatch(case_id):
                continue
            entry = catalog.setdefault(case_id, {})
            entry["name"] = _cell(row, name_idx)
            entry["case_type"] = _cell(row, type_idx)
            entry["priority"] = _cell(row, priority_idx)
            entry["auto"] = _cell(row, auto_idx)

    for case_id, title, detail in _iter_case_sections(body):
        entry = catalog.setdefault(case_id, {})
        entry.setdefault("name", title)
        if not entry.get("name"):
            entry["name"] = title
        entry["detail"] = detail

    for entry in catalog.values():
        entry.setdefault("name", "")
        entry.setdefault("case_type", "")
        entry.setdefault("priority", "")
        entry.setdefault("auto", "")
        entry.setdefault("detail", "")
    return catalog


def _find_header(header: list[str], names: tuple[str, ...]) -> int | None:
    for idx, cell in enumerate(header):
        if cell in names:
            return idx
    return None


def _cell(row: list[str], idx: int | None) -> str:
    if idx is None or idx >= len(row):
        return ""
    return row[idx].strip()


def _iter_case_sections(body: str):
    """按 `### TC-XXX-001 标题` 切分明细章节，产出 (编号, 标题, 正文 markdown)。"""
    lines = body.splitlines()
    current_id = ""
    current_title = ""
    buffer: list[str] = []

    def flush():
        if current_id:
            text = "\n".join(buffer).strip()
            if text:
                yield current_id, current_title, text

    for line in lines:
        match = _CASE_HEADING.match(line.strip())
        if match:
            yield from flush()
            current_id, current_title = match.group(1), match.group(2).strip()
            buffer = []
            continue
        if current_id and re.match(r"^#{1,2}\s", line.strip()):
            # 更高层级标题（如 `## 4. API 测试明细`）结束当前用例
            yield from flush()
            current_id, current_title, buffer = "", "", []
            continue
        if current_id:
            buffer.append(line)
    yield from flush()



def _summarize_result_table(content: str) -> dict[str, int]:
    summary = {"pass": 0, "skip": 0, "fail": 0, "blocked": 0, "other": 0}
    for row in parse_result_rows(content):
        summary[row["result"]] = summary.get(row["result"], 0) + 1
    return summary


def parse_result_rows(content: str) -> list[dict[str, str]]:
    """解析测试报告末尾的用例结果表，返回 [{id, result}]（result 已归一）。"""
    table = last_result_table(content)
    if not table or len(table) < 2:
        return []
    header = [_norm_header(cell) for cell in table[0]]
    id_idx = 0
    result_idx = 1
    for idx, cell in enumerate(header):
        if cell in _RESULT_HEADERS:
            result_idx = idx
            break
    rows: list[dict[str, str]] = []
    for row in table[1:]:
        if result_idx >= len(row) or id_idx >= len(row):
            continue
        raw = row[result_idx]
        lowered = raw.strip().lower()
        # blocked 与 fail 在 test_passed 判定里等价，这里拆开供 QA 面板区分
        if "blocked" in lowered or "阻塞" in raw:
            verdict = "blocked"
        else:
            verdict = _classify(raw) or "other"
        rows.append({"id": row[id_idx].strip(), "result": verdict})
    return rows



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
    case_catalog: dict[str, dict[str, str]] = {}
    if test_cases_path.is_file():
        cases_content = test_cases_path.read_text(encoding="utf-8")
        approval = parse_test_cases_approval(cases_content)
        qa_status = approval.status
        qa_note = approval.user_note
        case_catalog = parse_case_catalog(cases_content)

    confidence = {
        "score": None,
        "reached_0_8": None,
        "has_report": False,
        "test_passed": None,
        "result_rows": {"pass": 0, "skip": 0, "fail": 0, "blocked": 0, "other": 0},
        "highlights": [],
        "rows": [],
        "issues": [],
    }
    if report_path.is_file():
        confidence = parse_release_confidence(report_path.read_text(encoding="utf-8"))

    # 把用例文档里的名称/类型/优先级/明细挂到结果行上，供前端点击查看
    for row in confidence["rows"]:
        meta = case_catalog.get(row["id"]) or {}
        row["name"] = meta.get("name", "")
        row["case_type"] = meta.get("case_type", "")
        row["priority"] = meta.get("priority", "")
        row["auto"] = meta.get("auto", "")
        row["detail"] = meta.get("detail", "")
        row["in_doc"] = bool(meta)

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
        "case_catalog_size": len(case_catalog),
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
