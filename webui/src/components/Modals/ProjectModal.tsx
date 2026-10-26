import { useEffect, useState } from "react";
import { useWorkflowStore } from "../../store/workflowStore";

interface Props {
  mode: "create" | "edit";
  onClose: () => void;
}

export function ProjectModal({ mode, onClose }: Props) {
  const projects = useWorkflowStore((s) => s.projects);
  const selectedProjectId = useWorkflowStore((s) => s.selectedProjectId);
  const createProject = useWorkflowStore((s) => s.createProject);
  const updateProject = useWorkflowStore((s) => s.updateProject);

  const project = projects.find((p) => p.project_id === selectedProjectId);

  const [name, setName] = useState("");
  const [appRoot, setAppRoot] = useState("");
  const [docsDir, setDocsDir] = useState("docs");
  const [rulesDir, setRulesDir] = useState("ai-rules");
  const [error, setError] = useState("");

  useEffect(() => {
    if (mode === "edit" && project) {
      setName(project.name);
      setAppRoot(project.app_root);
      setDocsDir(project.docs_dir);
      setRulesDir(project.ai_rules_dir);
    }
  }, [mode, project]);

  const submit = async () => {
    setError("");
    const payload = {
      name,
      app_root: appRoot,
      docs_dir: docsDir,
      ai_rules_dir: rulesDir,
    };
    try {
      if (mode === "edit" && selectedProjectId) {
        await updateProject(selectedProjectId, payload);
      } else {
        await createProject(payload);
      }
      onClose();
    } catch (err) {
      setError(String(err));
    }
  };

  return (
    <div className="modal-mask" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>{mode === "edit" ? "编辑项目" : "新建项目"}</h3>
        <div className="field">
          <label>项目名称</label>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="my-project" />
        </div>
        <div className="field">
          <label>项目根目录（绝对路径）</label>
          <input value={appRoot} onChange={(e) => setAppRoot(e.target.value)} placeholder="/path/to/project" />
        </div>
        <div className="field">
          <label>文档目录（相对路径）</label>
          <input value={docsDir} onChange={(e) => setDocsDir(e.target.value)} />
        </div>
        <div className="field">
          <label>规则目录（相对路径）</label>
          <input value={rulesDir} onChange={(e) => setRulesDir(e.target.value)} />
        </div>
        <div className="actions">
          <button type="button" className="btn btn-primary" onClick={submit}>
            {mode === "edit" ? "保存修改" : "创建并进入"}
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
