import { useState } from "react";
import { useWorkflowStore } from "../../store/workflowStore";
import { ProjectModal } from "../Modals/ProjectModal";
import { RulesModal } from "../Modals/RulesModal";

export function ProjectList() {
  const projects = useWorkflowStore((s) => s.projects);
  const selectedProjectId = useWorkflowStore((s) => s.selectedProjectId);
  const selectProject = useWorkflowStore((s) => s.selectProject);
  const deleteProject = useWorkflowStore((s) => s.deleteProject);
  const leftCollapsed = useWorkflowStore((s) => s.leftCollapsed);
  const toggleLeftCollapsed = useWorkflowStore((s) => s.toggleLeftCollapsed);

  const [projectModal, setProjectModal] = useState<"create" | "edit" | null>(null);
  const [rulesOpen, setRulesOpen] = useState(false);

  if (leftCollapsed) {
    return (
      <aside className="panel">
        <div className="rail">
          <button type="button" className="btn btn-sm" onClick={toggleLeftCollapsed}>
            展开
          </button>
          项目
        </div>
      </aside>
    );
  }

  return (
    <aside className="panel">
      <div className="panel-header">
        <h1>项目</h1>
        <button type="button" className="btn btn-sm btn-ghost" onClick={toggleLeftCollapsed}>
          缩起
        </button>
      </div>
      <div className="panel-body">
        <p className="panel-sub">选择项目后可创建并管理任务</p>
        <div className="actions">
          <button type="button" className="btn btn-primary" onClick={() => setProjectModal("create")}>
            + 新建项目
          </button>
          <button
            type="button"
            className="btn"
            disabled={!selectedProjectId}
            onClick={() => setProjectModal("edit")}
          >
            编辑
          </button>
          <button
            type="button"
            className="btn"
            disabled={!selectedProjectId}
            onClick={async () => {
              const project = projects.find((p) => p.project_id === selectedProjectId);
              if (!project || !window.confirm(`确认删除项目 ${project.name} 吗？`)) return;
              await deleteProject(selectedProjectId);
            }}
          >
            删除
          </button>
          <button
            type="button"
            className="btn"
            disabled={!selectedProjectId}
            onClick={() => setRulesOpen(true)}
          >
            规则
          </button>
        </div>

        <div style={{ display: "grid", gap: 6, marginTop: 10 }}>
          {projects.length === 0 && <div className="empty">暂无项目，先创建一个。</div>}
          {projects.map((project) => (
            <div
              key={project.project_id}
              className={`list-item ${selectedProjectId === project.project_id ? "active" : ""}`}
              onClick={() => selectProject(project.project_id)}
            >
              <div className="list-item-title">{project.name}</div>
              <div className="list-item-meta">{project.app_root}</div>
            </div>
          ))}
        </div>
      </div>

      {projectModal && (
        <ProjectModal mode={projectModal} onClose={() => setProjectModal(null)} />
      )}
      {rulesOpen && <RulesModal onClose={() => setRulesOpen(false)} />}
    </aside>
  );
}
