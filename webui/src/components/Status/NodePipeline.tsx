import { useWorkflowStore } from "../../store/workflowStore";
import { deriveNodeStatuses, statusChipClass } from "../../utils/nodeStatus";

export function NodePipeline() {
  const selectedRun = useWorkflowStore((s) => s.selectedRun);
  const nodeDefinitions = useWorkflowStore((s) => s.nodeDefinitions);
  const openArtifact = useWorkflowStore((s) => s.openArtifact);

  const nodes = deriveNodeStatuses(selectedRun, nodeDefinitions);

  const completed = nodes.filter((n) => n.status === "completed").length;
  const running = nodes.filter((n) => n.status === "running").length;
  const failed = nodes.filter((n) => n.status === "failed").length;

  return (
    <article className="card">
      <div style={{ marginBottom: 10 }}>
        <h2 style={{ margin: "0 0 6px", fontSize: "var(--text-lg)" }}>节点状态</h2>
        {!selectedRun ? (
          <span className="panel-sub">尚未选择任务</span>
        ) : (
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            <span className="chip chip-completed">completed {completed}</span>
            <span className="chip chip-running">running {running}</span>
            <span className="chip chip-failed">failed {failed}</span>
            <span className="chip chip-queued">status {selectedRun.status}</span>
          </div>
        )}
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
          gap: 8,
        }}
      >
        {nodes.map((node, index) => {
          const hasArtifact = node.artifact && node.artifact !== "等待产物";
          return (
            <div
              key={node.nodeId}
              className="list-item"
              style={{ cursor: "default", minHeight: 120 }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span
                  style={{
                    width: 20,
                    height: 20,
                    borderRadius: "50%",
                    background: "var(--color-surface-elevated)",
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: "var(--text-xs)",
                    color: "var(--color-text-muted)",
                  }}
                >
                  {index + 1}
                </span>
                <div className="list-item-title">{node.title}</div>
              </div>
              <div className="list-item-meta">{node.nodeId}</div>
              <div style={{ marginTop: 8 }}>
                <span className={statusChipClass(node.status)}>{node.status}</span>
              </div>
              <div style={{ marginTop: "auto", paddingTop: 8, fontSize: "var(--text-xs)" }}>
                {hasArtifact ? (
                  <button
                    type="button"
                    className="btn btn-sm btn-ghost"
                    style={{ padding: 0, color: "var(--color-primary-hover)", textDecoration: "underline" }}
                    onClick={() => openArtifact(node.nodeId)}
                  >
                    {node.artifact}
                  </button>
                ) : (
                  <span className="panel-sub">等待产物</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </article>
  );
}
