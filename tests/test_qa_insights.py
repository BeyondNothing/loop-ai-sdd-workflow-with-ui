"""QA 质量面板数据解析测试（artifact_insights）。

运行：
    .venv/bin/python -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.artifact_insights import (  # noqa: E402
    _summarize_result_table,
    parse_release_confidence,
    parse_result_rows,
)

REPORT_WITH_FAILURES = """# 测试验证报告

### 最终置信度：**0.62**（未达到 0.8 阈值）

### 评分依据

- 覆盖不足
- 接口未联调

## 6. 问题与建议

- TC-API-01 返回码与契约不一致，需要确认是否改为 400。
- 缺少并发场景用例，建议补 1 条。
- 构建链路父 POM 缺失，属环境缺口。

## 7. 用例结果表

| 用例编号 | 结果 |
|----------|------|
| TC-UNIT-01 | pass |
| TC-API-01 | fail |
| TC-E2E-01 | blocked |
| TC-API-02 | skip |

## Workflow 状态

| 字段 | 值 |
|------|-----|
| test_passed | false |
"""

REPORT_ALL_GREEN = """# 报告

### 最终置信度：0.93（达到 0.8 阈值）

| 用例编号 | 结果 |
|---|---|
| TC-UNIT-01 | pass |
| TC-UNIT-02 | pass |

## Workflow 状态

| 字段 | 值 |
|------|-----|
| test_passed | true |
"""


class ReleaseConfidenceTest(unittest.TestCase):
    def test_parses_bold_confidence_and_reach(self) -> None:
        data = parse_release_confidence(REPORT_WITH_FAILURES)
        self.assertEqual(data["score"], 0.62)
        self.assertIs(data["reached_0_8"], False)
        self.assertIs(data["test_passed"], False)

    def test_basis_is_whole_confidence_section(self) -> None:
        data = parse_release_confidence(REPORT_WITH_FAILURES)
        basis = data["basis"]
        self.assertIn("评分依据", basis)
        self.assertIn("覆盖不足", basis)
        # 不应把后面的「问题与建议」章节吞进来
        self.assertNotIn("父 POM", basis)
        # 也不应包含标题行本身
        self.assertFalse(basis.startswith("## 5."), basis[:20])

    def test_basis_absent_when_no_section(self) -> None:
        self.assertEqual(parse_release_confidence("")["basis"], "")

    def test_highlights_skip_heading_and_lead_in(self) -> None:
        data = parse_release_confidence(REPORT_WITH_FAILURES)
        for line in data["highlights"]:
            self.assertFalse(line.startswith("#"), line)
            self.assertFalse(line.endswith(("：", ":")), line)

    def test_counts_rows_with_by_kind(self) -> None:
        data = parse_release_confidence(REPORT_WITH_FAILURES)
        self.assertEqual(
            data["result_rows"],
            {"pass": 1, "skip": 1, "fail": 1, "blocked": 1, "other": 0},
        )
        self.assertEqual(len(data["rows"]), 4)

    def test_blocked_is_kept_separate_from_fail(self) -> None:
        rows = parse_result_rows(REPORT_WITH_FAILURES)
        by_id = {row["id"]: row["result"] for row in rows}
        self.assertEqual(by_id["TC-E2E-01"], "blocked")
        self.assertEqual(by_id["TC-API-01"], "fail")

    def test_collects_case_and_report_issues(self) -> None:
        data = parse_release_confidence(REPORT_WITH_FAILURES)
        case_issues = [i for i in data["issues"] if i["source"] == "case"]
        report_issues = [i for i in data["issues"] if i["source"] == "report"]
        self.assertEqual(len(case_issues), 2)
        self.assertEqual(len(report_issues), 3)
        self.assertTrue(any("父 POM" in i["text"] for i in report_issues))

    def test_all_green_has_no_issues(self) -> None:
        data = parse_release_confidence(REPORT_ALL_GREEN)
        self.assertEqual(data["score"], 0.93)
        self.assertIs(data["reached_0_8"], True)
        self.assertEqual(data["issues"], [])
        self.assertEqual(data["result_rows"]["pass"], 2)

    def test_missing_report_is_empty_not_error(self) -> None:
        data = parse_release_confidence("")
        self.assertFalse(data["has_report"])
        self.assertIsNone(data["score"])
        self.assertEqual(data["rows"], [])
        self.assertEqual(data["issues"], [])

    def test_summary_matches_rows(self) -> None:
        rows = parse_result_rows(REPORT_WITH_FAILURES)
        summary = {k: 0 for k in ("pass", "skip", "fail", "blocked", "other")}
        for row in rows:
            summary[row["result"]] += 1
        self.assertEqual(_summarize_result_table(REPORT_WITH_FAILURES), summary)


if __name__ == "__main__":
    unittest.main()
