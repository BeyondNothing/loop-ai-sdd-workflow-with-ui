"""API 设计节点（design_api）的编排 / 门禁 / 续跑测试。

链路：split_tasks → design_tech_solution → design_api → implement_code

运行：
    .venv/bin/python -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.phase_gate import phase_complete, phase_content_ready  # noqa: E402
from src.router import determine_start_node  # noqa: E402
from src.workflow import DevWorkflow  # noqa: E402

API_BODY = """# API 设计：订单导出

## 契约概览

- 路径前缀：`/api/v1`
- 鉴权：Bearer Token
- 分页：page / page_size
- 错误结构：`{"code": ..., "message": ...}`

## 接口清单

| # | 方法 | 路径 | 用途 | 归属 |
|---|------|------|------|------|
| 1 | POST | /api/v1/export-tasks | 提交导出任务 | 后端 |
| 2 | GET | /api/v1/export-tasks/{id} | 查询导出进度 | 后端 |

## 请求

### POST /api/v1/export-tasks

| 字段 | 类型 | 必填 | 约束 | 说明 |
|------|------|------|------|------|
| filters | object | 是 | 非空 | 导出过滤条件 |

## 响应

### POST /api/v1/export-tasks

```json
{"task_id": 1, "status": "pending"}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | integer | 任务 ID |
| status | string | 任务状态 |

## 错误码

| 错误码 | HTTP | 触发条件 | 前端处理建议 |
|--------|------|----------|--------------|
| BIZ_FILTER_EMPTY | 400 | 过滤条件为空 | 提示补全条件 |

## 兼容性与变更

新增接口，无存量影响。
"""

API_APPROVED = (
    API_BODY
    + """
```yaml api_design_approval
status: approved
confirmed_at: "2026-11-25T18:00:00"
user_note: "确认"
```
"""
)

API_PENDING = (
    API_BODY
    + """
```yaml api_design_approval
status: pending
confirmed_at: ""
user_note: ""
```
"""
)

TECH_APPROVED = """# 技术方案：订单导出

## 背景与目标

- 做什么：导出改为异步
- 不做什么：不做实时推送

## 领域模型与术语

### 术语清单

| 术语 | 英文命名 | 定义 | 与现有概念的关系 |
|------|----------|------|------------------|
| 导出任务 | ExportTask | 一次导出请求 | 新增 |

## 数据结构及说明

```sql
CREATE TABLE export_task (
  id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='导出任务';
```

## 实现方向

- 提交写任务表，异步执行器分片导出

```yaml tech_design_approval
status: approved
confirmed_at: "2026-11-25T17:00:00"
user_note: "确认"
```
"""

TASKS_APPROVED = """# 任务拆分

## 任务总览

| 编号 | 任务 | 归属 |
|------|------|------|
| T1 | 导出任务表与异步执行器 | 后端 |
| T2 | 导出进度查询接口 | 后端 |

## 详情

导出走异步任务表：用户提交后落一条任务记录，后台执行器分片读取数据写文件，
完成后回写文件地址；前端轮询进度接口拿状态。本次只做后端，前端不在范围内。
任务一的产出是建表语句与执行器骨架，任务二在任务一的表之上补查询接口。

## 依赖与执行顺序

T1 先落地建表与执行器骨架，T2 在 T1 的任务表之上补查询接口，两者无循环依赖，
可以串行推进；接口契约统一以技术方案与 API 设计为准。

## Workflow 状态

| 字段 | 值 |
|------|-----|
| node | split_tasks |
| status | completed |
| next_node | design_tech_solution |
| phase | tasks |
| pending_count | 0 |
| all_resolved | true |

```yaml tasks_approval
status: approved
confirmed_at: "2026-11-25T16:00:00"
user_note: "确认"
```
"""


class ApiDesignGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.docs = Path(self._tmp.name)
        self.auto = {"auto": True, "skip_clarification": True}
        self.manual = {"auto": False, "skip_clarification": True}

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_approved_passes_gate(self) -> None:
        (self.docs / "03-api-design.md").write_text(API_APPROVED, encoding="utf-8")
        self.assertTrue(phase_complete(self.docs, "design_api", self.manual))

    def test_pending_blocks_manual_gate(self) -> None:
        (self.docs / "03-api-design.md").write_text(API_PENDING, encoding="utf-8")
        self.assertTrue(phase_content_ready(self.docs, "design_api", self.manual))
        self.assertFalse(phase_complete(self.docs, "design_api", self.manual))
        # --auto 下内容就绪即通过
        self.assertTrue(phase_complete(self.docs, "design_api", self.auto))

    def test_missing_error_code_section_blocks(self) -> None:
        broken = API_APPROVED.replace("## 错误码", "## 其它").replace(
            "| 错误码 |", "| 编码 |"
        )
        (self.docs / "03-api-design.md").write_text(broken, encoding="utf-8")
        self.assertFalse(phase_content_ready(self.docs, "design_api", self.auto))

    def test_missing_response_section_blocks(self) -> None:
        broken = API_APPROVED.replace("## 响应", "## 结果")
        (self.docs / "03-api-design.md").write_text(broken, encoding="utf-8")
        self.assertFalse(phase_content_ready(self.docs, "design_api", self.auto))

    def test_no_api_needed_doc_passes(self) -> None:
        doc = (
            "# API 设计：纯前端改造\n\n"
            "## 契约概览\n\n"
            "本次不涉及新增接口。前端只调整导出按钮的交互与轮询节奏，"
            "调用的仍是既有的提交导出与查询进度两个接口，字段无需改动。\n\n"
            "## 兼容性与变更\n\n"
            "无新增接口，也不改动既有接口的路径、字段与错误码，存量调用方不受影响。\n"
        )
        (self.docs / "03-api-design.md").write_text(doc, encoding="utf-8")
        self.assertTrue(phase_content_ready(self.docs, "design_api", self.auto))

    def test_too_short_blocks(self) -> None:
        (self.docs / "03-api-design.md").write_text("# API 设计\n\n## 接口清单\n\n无\n", encoding="utf-8")
        self.assertFalse(phase_content_ready(self.docs, "design_api", self.auto))


class ApiDesignResumeTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.docs = Path(self._tmp.name)
        (self.docs / "03-tasks.md").write_text(TASKS_APPROVED, encoding="utf-8")
        (self.docs / "03-technical-design.md").write_text(TECH_APPROVED, encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_tech_done_without_api_resumes_api(self) -> None:
        node = determine_start_node(self.docs, skip_clarification=True, auto=True)
        self.assertEqual(node, "design_api")

    def test_api_approved_resumes_implement(self) -> None:
        (self.docs / "03-api-design.md").write_text(API_APPROVED, encoding="utf-8")
        node = determine_start_node(self.docs, skip_clarification=True, auto=True)
        self.assertEqual(node, "implement_code")

    def test_api_pending_resumes_api(self) -> None:
        (self.docs / "03-api-design.md").write_text(API_PENDING, encoding="utf-8")
        node = determine_start_node(self.docs, skip_clarification=False, auto=False)
        self.assertEqual(node, "design_api")

    def test_tasks_done_without_tech_resumes_tech(self) -> None:
        (self.docs / "03-technical-design.md").unlink()
        node = determine_start_node(self.docs, skip_clarification=True, auto=True)
        self.assertEqual(node, "design_tech_solution")


class ApiDesignGraphTest(unittest.TestCase):
    def test_node_registered(self) -> None:
        wf = DevWorkflow(PROJECT_ROOT)
        node_cfg = wf.workflow_config.nodes.get("design_api")
        self.assertIsNotNone(node_cfg)
        self.assertEqual(node_cfg.output_file, "03-api-design.md")
        self.assertEqual(node_cfg.mode, "interactive")
        # 必须能拿到技术方案作为输入
        doc_inputs = [i.key for i in node_cfg.inputs if i.kind == "doc"]
        self.assertIn("03-technical-design.md", doc_inputs)

    def test_prompt_requires_contract_sections(self) -> None:
        wf = DevWorkflow(PROJECT_ROOT)
        node_cfg = wf.workflow_config.nodes["design_api"]
        prompt = (PROJECT_ROOT / node_cfg.prompt_file).read_text(encoding="utf-8")
        for section in ("接口清单", "请求", "响应", "错误码", "api_design_approval"):
            self.assertIn(section, prompt)
        self.assertIn("不得自行 approved", prompt)

    def test_route_after_tech_goes_to_api(self) -> None:
        wf = DevWorkflow(PROJECT_ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp)
            (docs / "03-technical-design.md").write_text(TECH_APPROVED, encoding="utf-8")
            state = {
                "docs_dir": str(docs),
                "app_root": str(docs),
                "auto": True,
                "skip_clarification": True,
            }
            self.assertEqual(wf._route_after_tech_design(state), "design_api")

    def test_route_after_api_goes_to_implement(self) -> None:
        wf = DevWorkflow(PROJECT_ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp)
            (docs / "03-api-design.md").write_text(API_APPROVED, encoding="utf-8")
            state = {
                "docs_dir": str(docs),
                "app_root": str(docs),
                "auto": True,
                "skip_clarification": True,
            }
            self.assertEqual(wf._route_after_api_design(state), "implement_code")

    def test_implement_prompt_receives_api_design(self) -> None:
        wf = DevWorkflow(PROJECT_ROOT)
        runner = wf.node_runner
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp)
            (docs / "03-api-design.md").write_text(API_APPROVED, encoding="utf-8")
            node_cfg = wf.workflow_config.nodes["implement_code"]
            state = {
                "docs_dir": str(docs),
                "app_root": str(docs),
                "requirement": "导出",
                "auto": True,
                "skip_clarification": True,
            }
            context = runner._build_context(node_cfg, state, docs)
            rendered = runner._render_prompt(
                (PROJECT_ROOT / node_cfg.prompt_file).read_text(encoding="utf-8"),
                context,
            )
            self.assertIn("/api/v1/export-tasks", rendered)
            self.assertNotIn("{{doc_03-api-design.md}}", rendered)


if __name__ == "__main__":
    unittest.main()
