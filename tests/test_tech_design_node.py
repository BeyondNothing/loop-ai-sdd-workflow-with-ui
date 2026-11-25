"""技术方案节点（design_tech_solution）的编排 / 门禁 / 续跑测试。

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

from src.config_loader import load_workflow_config  # noqa: E402
from src.phase_gate import phase_complete, phase_content_ready  # noqa: E402
from src.router import determine_start_node  # noqa: E402
from src.workflow import DevWorkflow  # noqa: E402

TECH_DESIGN_BODY = """# 技术方案：订单导出

## 背景与目标

- 做什么：导出改为异步，支持按条件导出大数据量
- 不做什么：不做实时推送、不做导出格式自定义

## 领域模型与术语

### 术语清单

| 术语 | 英文命名 | 定义 | 与现有概念的关系 |
|------|----------|------|------------------|
| 导出任务 | ExportTask | 一次导出请求的执行记录 | 新增，不复用现有 Job |
| 导出状态 | ExportStatus | 任务的流转状态 | 新增枚举 |

### 领域模型

```mermaid
classDiagram
  class ExportTask {
    +id
    +status
  }
```

ExportTask 为聚合根，状态由 ExportStatus 约束流转。

## 数据结构及说明

```sql
CREATE TABLE export_task (
  id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  status VARCHAR(32) NOT NULL COMMENT '导出状态',
  PRIMARY KEY (id),
  KEY idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='导出任务';
```

| 字段 | 类型 | 允许空 | 默认值 | 说明 |
|------|------|--------|--------|------|
| id | BIGINT | 否 | 自增 | 主键 |
| status | VARCHAR(32) | 否 | 无 | 导出状态 |

## 实现方向

- 提交后写 ExportTask，异步执行器分片导出并回写结果地址
- 采用领域服务 + 仓储，状态流转收敛在聚合根内
- 取舍：异步换来复杂度，需要前端轮询

## 关键接口

| 方法 | 路径 | 用途 | 入参要点 | 出参要点 |
|------|------|------|----------|----------|
| POST | /api/export | 提交导出 | 过滤条件 | 任务 ID |

## 兼容性与风险

无存量影响，新增表与接口。

## 人工后续事项

- 在 dev/test 执行上面的 DDL
"""

TECH_DESIGN_APPROVED = (
    TECH_DESIGN_BODY
    + """
```yaml tech_design_approval
status: approved
confirmed_at: "2026-11-25T10:00:00"
user_note: "确认"
```
"""
)

TECH_DESIGN_PENDING = (
    TECH_DESIGN_BODY
    + """
```yaml tech_design_approval
status: pending
confirmed_at: ""
user_note: ""
```
"""
)

TASKS_APPROVED = """# 任务拆分

## 任务总览

| 编号 | 任务 | 归属 |
|------|------|------|
| T1 | 导出任务表与异步执行器 | 后端 |
| T2 | 导出进度查询接口 | 后端 |

## 详情

导出走异步任务表，用户提交后落一条任务记录，后台执行器分片读取数据写文件，
完成后回写文件地址；前端轮询进度接口拿状态。这里只做后端，前端不在本次范围。

## 依赖与执行顺序

T1 先落地建表与执行器骨架，T2 在 T1 的任务表之上补查询接口，无循环依赖。

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
confirmed_at: "2026-11-25T09:00:00"
user_note: "确认"
```
"""


class TechDesignGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.docs = Path(self._tmp.name)
        self.state = {"auto": True, "skip_clarification": True}

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_pending_approval_blocks_gate(self) -> None:
        (self.docs / "03-technical-design.md").write_text(
            TECH_DESIGN_PENDING, encoding="utf-8"
        )
        self.assertTrue(
            phase_content_ready(self.docs, "design_tech_solution", self.state)
        )
        # 人工模式未 approved → 门禁不过
        manual = {"auto": False, "skip_clarification": True}
        self.assertFalse(phase_complete(self.docs, "design_tech_solution", manual))
        # --auto 内容就绪即通过
        self.assertTrue(phase_complete(self.docs, "design_tech_solution", self.state))

    def test_approved_tech_design_passes_gate(self) -> None:
        (self.docs / "03-technical-design.md").write_text(
            TECH_DESIGN_APPROVED, encoding="utf-8"
        )
        self.assertTrue(
            phase_complete(
                self.docs,
                "design_tech_solution",
                {"auto": False, "skip_clarification": True},
            )
        )

    def test_missing_section_blocks_gate(self) -> None:
        broken = TECH_DESIGN_APPROVED.replace("数据结构及说明", "其它说明")
        (self.docs / "03-technical-design.md").write_text(broken, encoding="utf-8")
        self.assertFalse(
            phase_content_ready(self.docs, "design_tech_solution", self.state)
        )

    def test_missing_glossary_blocks_gate(self) -> None:
        broken = TECH_DESIGN_APPROVED.replace("### 术语清单", "### 名词")
        (self.docs / "03-technical-design.md").write_text(broken, encoding="utf-8")
        self.assertFalse(
            phase_content_ready(self.docs, "design_tech_solution", self.state)
        )

    def test_pending_approval_not_treated_as_confirmed(self) -> None:
        """人工模式下 pending 必须挡住，不能因内容完整就放行。"""
        (self.docs / "03-technical-design.md").write_text(
            TECH_DESIGN_PENDING, encoding="utf-8"
        )
        manual = {"auto": False, "skip_clarification": True}
        self.assertTrue(
            phase_content_ready(self.docs, "design_tech_solution", manual)
        )
        self.assertFalse(phase_complete(self.docs, "design_tech_solution", manual))

    def test_too_short_blocks_gate(self) -> None:
        (self.docs / "03-technical-design.md").write_text(
            "# 技术方案\n\n## 背景\n\n短\n", encoding="utf-8"
        )
        self.assertFalse(
            phase_content_ready(self.docs, "design_tech_solution", self.state)
        )


class TechDesignResumeTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.docs = Path(self._tmp.name)
        (self.docs / "03-tasks.md").write_text(TASKS_APPROVED, encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_tasks_done_without_tech_design_resumes_tech_design(self) -> None:
        node = determine_start_node(self.docs, skip_clarification=True, auto=True)
        self.assertEqual(node, "design_tech_solution")

    def test_tasks_done_with_tech_design_resumes_implement(self) -> None:
        (self.docs / "03-technical-design.md").write_text(
            TECH_DESIGN_APPROVED, encoding="utf-8"
        )
        node = determine_start_node(self.docs, skip_clarification=True, auto=True)
        self.assertEqual(node, "implement_code")

    def test_tech_design_pending_resumes_tech_design(self) -> None:
        (self.docs / "03-technical-design.md").write_text(
            TECH_DESIGN_PENDING, encoding="utf-8"
        )
        node = determine_start_node(self.docs, skip_clarification=False, auto=False)
        self.assertEqual(node, "design_tech_solution")


class TechDesignGraphTest(unittest.TestCase):
    def test_node_registered_in_config_and_graph(self) -> None:
        wf = DevWorkflow(PROJECT_ROOT)
        node_cfg = wf.workflow_config.nodes.get("design_tech_solution")
        self.assertIsNotNone(node_cfg)
        self.assertEqual(node_cfg.output_file, "03-technical-design.md")
        self.assertEqual(node_cfg.mode, "interactive")
        prompt = (PROJECT_ROOT / node_cfg.prompt_file).read_text(encoding="utf-8")
        self.assertIn("tech_design_approval", prompt)
        self.assertIn("classDiagram", prompt)
        self.assertIn("术语清单", prompt)
        self.assertIn("CREATE TABLE", prompt)
        # 人工确认必须是显式门禁，且禁止 AI 自行 approved
        self.assertIn("等用户确认", prompt)
        self.assertIn("不得自行 approved", prompt)
        # 篇幅约束：不要写成实现清单
        self.assertIn("150 行以内", prompt)

    def test_auto_prompt_self_approves(self) -> None:
        wf = DevWorkflow(PROJECT_ROOT)
        node_cfg = wf.workflow_config.nodes["design_tech_solution"]
        prompt = (PROJECT_ROOT / node_cfg.prompt_file_auto).read_text(encoding="utf-8")
        self.assertIn("禁止", prompt)
        self.assertIn("自动通过", prompt)

    def test_gate_routing_skips_implement_without_tech_design(self) -> None:
        wf = DevWorkflow(PROJECT_ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp)
            (docs / "03-tasks.md").write_text(TASKS_APPROVED, encoding="utf-8")
            state = {"docs_dir": str(docs), "app_root": str(docs), "auto": True,
                     "skip_clarification": True}
            self.assertEqual(wf._route_after_split_tasks(state), "design_tech_solution")


class PromptContextTest(unittest.TestCase):
    def test_implement_prompt_receives_tech_design(self) -> None:
        wf = DevWorkflow(PROJECT_ROOT)
        runner = wf.node_runner
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp)
            (docs / "03-technical-design.md").write_text(
                TECH_DESIGN_APPROVED, encoding="utf-8"
            )
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
            self.assertIn("export_task", rendered)
            self.assertNotIn("{{doc_03-technical-design.md}}", rendered)


if __name__ == "__main__":
    unittest.main()
