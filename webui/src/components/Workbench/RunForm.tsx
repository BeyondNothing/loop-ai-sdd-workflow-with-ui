import { useEffect, useState } from "react";
import { useWorkflowStore } from "../../store/workflowStore";

export function RunForm() {
  const selectedProjectId = useWorkflowStore((s) => s.selectedProjectId);
  const selectedTaskId = useWorkflowStore((s) => s.selectedTaskId);
  const tasksByProject = useWorkflowStore((s) => s.tasksByProject);
  const flags = useWorkflowStore((s) => s.flags);
  const toggleFlag = useWorkflowStore((s) => s.toggleFlag);
  const startRun = useWorkflowStore((s) => s.startRun);
  const loadRuns = useWorkflowStore((s) => s.loadRuns);
  const message = useWorkflowStore((s) => s.message);
  const setMessage = useWorkflowStore((s) => s.setMessage);

  const task = (tasksByProject[selectedProjectId] || []).find(
    (t) => t.task_id === selectedTaskId,
  );

  const [taskName, setTaskName] = useState("");
  const [prdPath, setPrdPath] = useState("");
  const [requirement, setRequirement] = useState("");
  const [localError, setLocalError] = useState("");

  useEffect(() => {
    setTaskName(task?.task_name || "");
    setPrdPath(task?.requirement_prd_path || "");
    setRequirement(task?.requirement_text || "");
  }, [task?.task_id, task?.task_name, task?.requirement_prd_path, task?.requirement_text]);

  const onStart = async () => {
    setLocalError("");
    setMessage("");
    try {
      await startRun({
        taskName: taskName.trim(),
        requirement: requirement.trim(),
        requirementPrdPath: prdPath.trim(),
      });
    } catch (err) {
      setLocalError(String(err));
    }
  };

  return (
    <article className="card">
      <div className="panel-header" style={{ padding: "0 0 10px", border: "none" }}>
        <h2>任务工作台</h2>
      </div>

      <div className="field">
        <label htmlFor="run-name">当前任务</label>
        <input
          id="run-name"
          value={taskName}
          onChange={(e) => setTaskName(e.target.value)}
          placeholder="请先在中间列创建并选择任务"
        />
      </div>

      <div className="field">
        <label htmlFor="run-prd">PRD 路径（可选，优先读取）</label>
        <input
          id="run-prd"
          value={prdPath}
          onChange={(e) => setPrdPath(e.target.value)}
          placeholder="可填写绝对路径或相对项目路径"
        />
      </div>

      <div className="field">
        <label htmlFor="run-req">需求文本（当 PRD 路径为空时使用）</label>
        <textarea
          id="run-req"
          value={requirement}
          onChange={(e) => setRequirement(e.target.value)}
          placeholder="输入或粘贴需求内容..."
        />
      </div>

      <div className="actions">
        <button
          type="button"
          className={`btn btn-toggle ${flags.headless ? "active" : ""}`}
          onClick={() => toggleFlag("headless")}
        >
          无界面模式: {flags.headless ? "开" : "关"}
        </button>
        <button
          type="button"
          className={`btn btn-toggle ${flags.skipClar ? "active" : ""}`}
          onClick={() => toggleFlag("skipClar")}
        >
          跳过澄清: {flags.skipClar ? "开" : "关"}
        </button>
        <button
          type="button"
          className={`btn btn-toggle ${flags.auto ? "active" : ""}`}
          onClick={() => toggleFlag("auto")}
        >
          无人值守: {flags.auto ? "开" : "关"}
        </button>
        <button type="button" className="btn btn-primary" onClick={onStart}>
          执行任务
        </button>
        <button type="button" className="btn" onClick={() => loadRuns()}>
          刷新状态
        </button>
      </div>

      {(localError || message) && (
        <p className={`msg ${localError ? "msg-error" : ""}`}>{localError || message}</p>
      )}
    </article>
  );
}
