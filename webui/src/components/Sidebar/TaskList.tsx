import { useState } from "react";
import { useWorkflowStore } from "../../store/workflowStore";
import { TaskModal } from "../Modals/TaskModal";

export function TaskList() {
  const projects = useWorkflowStore((s) => s.projects);
  const selectedProjectId = useWorkflowStore((s) => s.selectedProjectId);
  const selectedTaskId = useWorkflowStore((s) => s.selectedTaskId);
  const tasksByProject = useWorkflowStore((s) => s.tasksByProject);
  const runs = useWorkflowStore((s) => s.runs);
  const selectTask = useWorkflowStore((s) => s.selectTask);
  const loadRuns = useWorkflowStore((s) => s.loadRuns);
  const deleteTask = useWorkflowStore((s) => s.deleteTask);

  const [taskModal, setTaskModal] = useState<{ mode: "create" | "edit"; taskId?: string } | null>(
    null,
  );

  const project = projects.find((p) => p.project_id === selectedProjectId);
  const tasks = tasksByProject[selectedProjectId] || [];

  const runStatusForTask = (taskId: string, taskName: string) => {
    const task = tasks.find((t) => t.task_id === taskId);
    const run =
      runs.find((r) => r.run_id === task?.last_run_id) ||
      runs.find(
        (r) => r.project_id === selectedProjectId && r.requirement_name === taskName,
      );
    return run?.status || "";
  };

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>任务列表</h2>
      </div>
      <div className="panel-body">
        <p className="panel-sub">
          {project ? `${project.name} · ${project.app_root}` : "未选择项目"}
        </p>
        <div className="actions">
          <button
            type="button"
            className="btn btn-primary"
            disabled={!selectedProjectId}
            onClick={() => setTaskModal({ mode: "create" })}
          >
            + 新建任务
          </button>
          <button type="button" className="btn" onClick={() => loadRuns()}>
            刷新状态
          </button>
        </div>

        <div style={{ display: "grid", gap: 6, marginTop: 10 }}>
          {!selectedProjectId && <div className="empty">请先在左侧选择项目。</div>}
          {selectedProjectId && tasks.length === 0 && (
            <div className="empty">暂无任务，点击「新建任务」。</div>
          )}
          {tasks.map((task) => {
            const status = runStatusForTask(task.task_id, task.task_name);
            return (
              <div
                key={task.task_id}
                className={`list-item ${selectedTaskId === task.task_id ? "active" : ""}`}
                onClick={() => selectTask(task.task_id)}
              >
                <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                  <div className="list-item-title" title={task.task_name}>
                    {task.task_name || "未命名任务"}
                  </div>
                  <div style={{ display: "flex", gap: 4 }}>
                    <button
                      type="button"
                      className="btn btn-sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        setTaskModal({ mode: "edit", taskId: task.task_id });
                      }}
                    >
                      编辑
                    </button>
                    <button
                      type="button"
                      className="btn btn-sm"
                      onClick={async (e) => {
                        e.stopPropagation();
                        if (!window.confirm("确认删除该任务吗？")) return;
                        await deleteTask(selectedProjectId, task.task_id);
                      }}
                    >
                      删除
                    </button>
                  </div>
                </div>
                <div className="list-item-meta">
                  创建于: {new Date(task.created_at).toLocaleString()}
                  {status && (
                    <>
                      {" "}
                      · <span className={`chip chip-${status === "running" ? "running" : status === "completed" ? "completed" : status === "failed" ? "failed" : "queued"}`}>{status}</span>
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {taskModal && (
        <TaskModal
          mode={taskModal.mode}
          taskId={taskModal.taskId}
          onClose={() => setTaskModal(null)}
        />
      )}
    </section>
  );
}
