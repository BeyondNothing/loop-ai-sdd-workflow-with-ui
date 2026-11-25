"""测试用例文档解析测试（QA 面板点击用例看详情）。

运行：
    .venv/bin/python -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.artifact_insights import parse_case_catalog  # noqa: E402

CASES_DOC = """# 设计测试用例

## 1. 覆盖范围说明

不涉及 UI 测试。

## 2. 用例总览

| 编号 | 名称 | 类型 | 优先级 | 可自动执行 |
|---|---|---|---|---|
| TC-UNIT-001 | 图片类型识别为图片 | 单元 | P0 | 是 |
| TC-UNIT-002 | 内容类型为空时归入其它 | 单元 | P1 | 是 |
| TC-API-001 | 上传接口归类一致 | API | P2 | 否（需中间件） |

## 3. 单元测试明细

### TC-UNIT-001 图片识别

- 输入：内容类型 `image/png`，文件名 `a.png`。
- 期望：返回图片大类。

### TC-UNIT-002 空内容类型

- 输入：内容类型为空。
- 期望：返回其它大类，不抛异常。

## 4. API 测试明细

### TC-API-001 上传接口归类一致

- 前置：具备可运行环境。
- 期望：与单元用例口径一致。

## Workflow 状态

| 字段 | 值 |
|------|-----|
| node | design_test_cases |
"""


class CaseCatalogTest(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = parse_case_catalog(CASES_DOC)

    def test_parses_all_cases(self) -> None:
        self.assertEqual(
            sorted(self.catalog), ["TC-API-001", "TC-UNIT-001", "TC-UNIT-002"]
        )

    def test_metadata_from_overview_table(self) -> None:
        entry = self.catalog["TC-UNIT-001"]
        self.assertEqual(entry["name"], "图片类型识别为图片")
        self.assertEqual(entry["case_type"], "单元")
        self.assertEqual(entry["priority"], "P0")
        self.assertEqual(entry["auto"], "是")

    def test_detail_is_case_section_markdown(self) -> None:
        detail = self.catalog["TC-UNIT-001"]["detail"]
        self.assertIn("image/png", detail)
        self.assertIn("返回图片大类", detail)
        # 不应把下一节或更高层级标题吃进来
        self.assertNotIn("TC-UNIT-002", detail)
        self.assertNotIn("API 测试明细", detail)

    def test_api_case_detail_stops_at_next_section(self) -> None:
        detail = self.catalog["TC-API-001"]["detail"]
        self.assertIn("可运行环境", detail)
        self.assertNotIn("Workflow 状态", detail)

    def test_missing_detail_degrades_to_empty(self) -> None:
        doc = """## 用例总览

| 编号 | 名称 |
|---|---|
| TC-UNIT-009 | 只有总览没有明细 |
"""
        catalog = parse_case_catalog(doc)
        self.assertEqual(catalog["TC-UNIT-009"]["name"], "只有总览没有明细")
        self.assertEqual(catalog["TC-UNIT-009"]["detail"], "")

    def test_empty_doc_returns_empty_catalog(self) -> None:
        self.assertEqual(parse_case_catalog(""), {})

    def test_ignores_non_case_tables(self) -> None:
        doc = """## 追溯关系

| 验收条目 | 内容 |
|---|---|
| A7-1 | 测试类位于标准目录 |
"""
        self.assertEqual(parse_case_catalog(doc), {})


if __name__ == "__main__":
    unittest.main()
