import type { NodeStatus, WorkflowNodeDef, WorkflowRun } from "../types";

export interface NodeView {
  nodeId: string;
  title: string;
  status: NodeStatus;
  artifact: string;
}

export function deriveNodeStatuses(
  run: WorkflowRun | null,
  nodes: WorkflowNodeDef[],
): NodeView[] {
  const result = run?.result || {};
  const outputs =
    run?.node_outputs || (result.node_outputs as Record<string, string> | undefined) || {};
  const completed = new Set(
    run?.completed_nodes || (result.completed_nodes as string[] | undefined) || [],
  );
  const currentNode =
    run?.current_node || (result.current_node as string | undefined) || "";

  return nodes.map((node) => {
    let status: NodeStatus = "queued";
    if (run?.status === "completed") {
      status = outputs[node.id] || completed.has(node.id) ? "completed" : "skipped";
    } else if (run?.status === "failed") {
      if (outputs[node.id] || completed.has(node.id)) status = "completed";
      else if (currentNode === node.id) status = "failed";
    } else if (run?.status === "running") {
      if (outputs[node.id] || completed.has(node.id)) status = "completed";
      else if (currentNode === node.id) status = "running";
    } else if (run?.status === "queued") {
      status = "queued";
    }

    return {
      nodeId: node.id,
      title: node.name,
      status,
      artifact: outputs[node.id] || "等待产物",
    };
  });
}

export function statusChipClass(status: NodeStatus): string {
  const safe: NodeStatus[] = ["queued", "running", "completed", "failed", "skipped"];
  return `chip chip-${safe.includes(status) ? status : "queued"}`;
}
