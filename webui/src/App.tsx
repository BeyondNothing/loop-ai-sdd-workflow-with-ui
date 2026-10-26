import { useEffect } from "react";
import { ProjectList } from "./components/Sidebar/ProjectList";
import { TaskList } from "./components/Sidebar/TaskList";
import { RunForm } from "./components/Workbench/RunForm";
import { NodePipeline } from "./components/Status/NodePipeline";
import { RunLog } from "./components/Status/RunLog";
import { useRunPolling } from "./hooks/useRunPolling";
import { useWorkflowStore } from "./store/workflowStore";

export default function App() {
  const loadInitial = useWorkflowStore((s) => s.loadInitial);
  const leftCollapsed = useWorkflowStore((s) => s.leftCollapsed);

  useEffect(() => {
    loadInitial().catch(console.error);
  }, [loadInitial]);

  useRunPolling(3000);

  return (
    <div className={`layout ${leftCollapsed ? "left-collapsed" : ""}`}>
      <ProjectList />
      <TaskList />
      <main
        className="panel panel-main"
        style={{
          display: "grid",
          gridTemplateRows: "auto minmax(0, 1fr)",
          gap: 10,
          padding: 10,
          overflow: "auto",
        }}
      >
        <RunForm />
        <div
          style={{
            display: "grid",
            gridTemplateRows: "auto minmax(0, 1fr)",
            gap: 10,
            minHeight: 0,
          }}
        >
          <NodePipeline />
          <RunLog />
        </div>
      </main>
    </div>
  );
}
