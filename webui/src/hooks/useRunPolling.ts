import { useEffect } from "react";
import { useWorkflowStore } from "../store/workflowStore";

export function useRunPolling(intervalMs = 3000) {
  const loadRuns = useWorkflowStore((s) => s.loadRuns);
  const selectedRunId = useWorkflowStore((s) => s.selectedRunId);
  const loadRunDetail = useWorkflowStore((s) => s.loadRunDetail);

  useEffect(() => {
    const tick = async () => {
      await loadRuns();
      if (selectedRunId) {
        await loadRunDetail(selectedRunId);
      }
    };
    tick();
    const id = window.setInterval(tick, intervalMs);
    return () => window.clearInterval(id);
  }, [loadRuns, loadRunDetail, selectedRunId, intervalMs]);
}
