async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error((data as { error?: string }).error || `HTTP ${res.status}`);
  }
  return data as T;
}

export const client = {
  getProjects: () => api<{ projects: import("../types").Project[] }>("/api/projects"),
  createProject: (payload: Record<string, string>) =>
    api<{ project: import("../types").Project }>("/api/projects", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateProject: (id: string, payload: Record<string, string>) =>
    api<{ project: import("../types").Project }>(`/api/projects/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  deleteProject: (id: string) =>
    api<{ deleted: string }>(`/api/projects/${id}`, { method: "DELETE" }),

  getTasks: (projectId: string) =>
    api<{ tasks: import("../types").Task[] }>(`/api/projects/${projectId}/tasks`),
  createTask: (projectId: string, payload: Record<string, string>) =>
    api<{ task: import("../types").Task }>(`/api/projects/${projectId}/tasks`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateTask: (projectId: string, taskId: string, payload: Record<string, string>) =>
    api<{ task: import("../types").Task }>(`/api/projects/${projectId}/tasks/${taskId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  deleteTask: (projectId: string, taskId: string) =>
    api<{ deleted: string }>(`/api/projects/${projectId}/tasks/${taskId}`, {
      method: "DELETE",
    }),

  getRules: (projectId: string) =>
    api<{ ai_rules_dir: string; node_rules: Record<string, string[]> }>(
      `/api/projects/${projectId}/rules`,
    ),
  saveRules: (projectId: string, payload: Record<string, unknown>) =>
    api<{ project: import("../types").Project }>(`/api/projects/${projectId}/rules`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  scanRuleFiles: (projectId: string, aiRulesDir: string) =>
    api<{ files: string[] }>(
      `/api/projects/${projectId}/rule-files?ai_rules_dir=${encodeURIComponent(aiRulesDir)}`,
    ),

  getWorkflowNodes: () =>
    api<{ nodes: import("../types").WorkflowNodeDef[] }>("/api/workflow/nodes"),
  getRuns: () => api<{ runs: import("../types").WorkflowRun[] }>("/api/runs"),
  getRun: (runId: string) =>
    api<{ run: import("../types").WorkflowRun }>(`/api/runs/${runId}`),
  startRun: (payload: Record<string, unknown>) =>
    api<{ run: import("../types").WorkflowRun }>("/api/runs", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  openArtifact: (runId: string, nodeId: string) =>
    api<{ opened: string }>(`/api/runs/${runId}/open-artifact`, {
      method: "POST",
      body: JSON.stringify({ node_id: nodeId }),
    }),
};
