import { useEffect, useState } from "react";
import { useWorkflowStore } from "../../store/workflowStore";

const RULE_NODE_OPTIONS = [
  { id: "analyze_requirements", label: "需求分析与澄清" },
  { id: "create_plan", label: "制定计划" },
  { id: "design_test_cases", label: "设计测试用例" },
  { id: "review_plan_and_tests", label: "计划与用例评审" },
  { id: "split_tasks", label: "任务拆分" },
  { id: "implement_code", label: "代码实现" },
  { id: "verify_tests", label: "测试自验证" },
  { id: "ai_review", label: "AI 代码评审" },
];

interface Props {
  mode: "create" | "edit";
  taskId?: string;
  onClose: () => void;
}

export function TaskModal({ mode, taskId, onClose }: Props) {
  const selectedProjectId = useWorkflowStore((s) => s.selectedProjectId);
  const tasksByProject = useWorkflowStore((s) => s.tasksByProject);
  const createTask = useWorkflowStore((s) => s.createTask);
  const updateTask = useWorkflowStore((s) => s.updateTask);

  const task = (tasksByProject[selectedProjectId] || []).find((t) => t.task_id === taskId);

  const [name, setName] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (mode === "edit" && task) setName(task.task_name);
  }, [mode, task]);

  const submit = async () => {
    const trimmed = name.trim();
    if (!trimmed) {
      setError("请输入任务名称");
      return;
    }
    setError("");
    try {
      if (mode === "edit" && taskId) {
        await updateTask(selectedProjectId, taskId, { task_name: trimmed });
      } else {
        await createTask(selectedProjectId, trimmed);
      }
      onClose();
    } catch (err) {
      setError(String(err));
    }
  };

  return (
    <div className="modal-mask" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>{mode === "edit" ? "编辑任务" : "新建任务"}</h3>
        <p className="panel-sub">任务先在 UI 创建，再进入右侧工作台编辑执行内容。</p>
        <div className="field">
          <label>任务名称</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="例如: 登录流程改造"
          />
        </div>
        <div className="actions">
          <button type="button" className="btn btn-primary" onClick={submit}>
            {mode === "edit" ? "保存修改" : "创建任务"}
          </button>
          <button type="button" className="btn" onClick={onClose}>
            取消
          </button>
        </div>
        {error && <p className="msg msg-error">{error}</p>}
      </div>
    </div>
  );
}

// exported for RulesModal reuse
export { RULE_NODE_OPTIONS };
