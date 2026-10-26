import { useWorkflowStore } from "../../store/workflowStore";

export function RunLog() {
  const selectedRun = useWorkflowStore((s) => s.selectedRun);

  if (!selectedRun) {
    return (
      <article className="card" style={{ flex: 1, minHeight: 0 }}>
        <h2 style={{ margin: "0 0 8px", fontSize: "var(--text-lg)" }}>执行详情</h2>
        <pre
          style={{
            margin: 0,
            whiteSpace: "pre-wrap",
            fontSize: "var(--text-xs)",
            color: "var(--color-text-muted)",
          }}
        >
          选择任务后可查看日志与错误信息。
        </pre>
      </article>
    );
  }

  const logs = (selectedRun.logs || []).slice(-20).join("\n") || "(无日志)";
  const err = selectedRun.error ? `\n\n[error]\n${selectedRun.error}` : "";
  const meta = [
    `run_id: ${selectedRun.run_id}`,
    `status: ${selectedRun.status}`,
    `tool: ${selectedRun.tool}`,
    `auto: ${selectedRun.auto}`,
    `task_id: ${selectedRun.task_id || ""}`,
    `requirement_name: ${selectedRun.requirement_name || ""}`,
    `requirement_path: ${selectedRun.requirement_path || ""}`,
    `current_node: ${selectedRun.current_node || ""}`,
  ].join("\n");

  return (
    <article className="card" style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column" }}>
      <h2 style={{ margin: "0 0 8px", fontSize: "var(--text-lg)" }}>执行详情</h2>
      <pre
        style={{
          margin: 0,
          flex: 1,
          overflow: "auto",
          whiteSpace: "pre-wrap",
          fontSize: "var(--text-xs)",
          lineHeight: 1.45,
          background: "var(--color-surface-sunken)",
          border: "1px solid var(--color-border-subtle)",
          borderRadius: "var(--radius-md)",
          padding: 10,
        }}
      >
        {`${meta}\n\n[logs]\n${logs}${err}`}
      </pre>
    </article>
  );
}
