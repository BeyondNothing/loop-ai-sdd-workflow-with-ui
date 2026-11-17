/** 直连 Python 操作台 API（非 Vben 标准响应包装） */

async function rawFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error((data as { error?: string }).error || `HTTP ${res.status}`);
  }
  return data as T;
}

export interface WorkflowNodeDef {
  id: string;
  name: string;
  output: string;
  tool: string;
  mode: string;
  model?: string;
  recommendation_threshold?: number;
}

export interface ProjectBinding {
  project_id: string;
  name: string;
  app_root: string;
  docs_dir: string;
  ai_rules_dir: string;
  node_rules: Record<string, string[]>;
}

export interface TaskItem {
  task_id: string;
  task_name: string;
  requirement_prd_path: string;
  requirement_text: string;
  last_run_id?: string;
  created_at: string;
  updated_at: string;
}

export interface WorkflowRun {
  run_id: string;
  project_id: string;
  task_id?: string;
  status: string;
  requirement_name: string;
  requirement_path: string;
  tool: string;
  auto: boolean;
  error: string;
  logs: string[];
  current_node?: string;
  completed_nodes?: string[];
  node_outputs?: Record<string, string>;
  result?: Record<string, unknown> | null;
}

export interface SystemInfo {
  platform: string;
  os_name: string;
  is_mac: boolean;
  is_windows: boolean;
  path_sep: string;
}

export interface AiToolOption {
  id: string;
  name: string;
  description: string;
}

export interface SystemConfig {
  default_tool: string;
  available_tools: AiToolOption[];
}

export interface NodeRuntimeRow {
  id: string;
  name: string;
  tool: string;
  model: string;
  recommendation_threshold: number;
  mode: string;
}

export interface NodeRuntimeConfig {
  app_root: string;
  docs_dir: string;
  defaults: { tool: string; model: string };
  nodes: NodeRuntimeRow[];
  available_tools: AiToolOption[];
}

export interface McpServerItem {
  name: string;
  enabled: boolean;
  command: string;
  wrapper: string;
  args: string[];
  url: string;
  description: string;
}

export interface TaskInsights {
  project_id: string;
  task_id: string;
  task_name: string;
  docs_path: string;
  exists: boolean;
  qa_review: {
    status: string;
    user_note: string;
    file: string;
    async: boolean;
    blocks_core_flow: boolean;
  };
  release_confidence: {
    score: number | null;
    reached_0_8: boolean | null;
    has_report: boolean;
    test_passed: boolean | null;
    result_rows: Record<string, number>;
    highlights: string[];
    file: string;
    threshold: number;
  };
}

export interface SystemMdContent {
  rule_set_id: string;
  path: string;
  exists: boolean;
  content: string;
}

export interface McpSettings {
  path: string;
  meta: Record<string, string>;
  servers: McpServerItem[];
}

export interface SkillAgentItem {
  agent: string;
  tool: string;
  path: string;
  relative_dir: string;
  installed: boolean;
}

export interface SkillSettings {
  skill_name: string;
  template_exists: boolean;
  template_path: string;
  agents: SkillAgentItem[];
}

export interface RuleSetItem {
  rule_set_id: string;
  name: string;
  folder_path: string;
  resolved_path: string;
  ai_rules_dir: string;
  node_rules: Record<string, string[]>;
  projects: Array<{ project_id: string; name: string; ai_rules_dir: string }>;
  file_count: number;
  files: string[];
  exists: boolean;
}

/** @deprecated 使用 RuleSetItem */
export type RuleDirCatalogItem = RuleSetItem;

export const workflowApi = {
  getSystemInfo: () => rawFetch<SystemInfo>('/api/system/info'),
  getSystemConfig: () => rawFetch<SystemConfig>('/api/system/config'),
  updateSystemConfig: (body: { default_tool: string }) =>
    rawFetch<SystemConfig>('/api/system/config', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  getNodeSettings: (projectId?: string) => {
    const q = projectId ? `?project_id=${encodeURIComponent(projectId)}` : '';
    return rawFetch<NodeRuntimeConfig>(`/api/settings/nodes${q}`);
  },
  updateNodeSettings: (body: {
    project_id?: string;
    docs_dir?: string;
    defaults?: { tool?: string; model?: string };
    nodes?: Array<{
      id: string;
      tool?: string;
      model?: string;
      recommendation_threshold?: number;
    }>;
  }) =>
    rawFetch<NodeRuntimeConfig>('/api/settings/nodes', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  getMcpSettings: () => rawFetch<McpSettings>('/api/settings/mcp'),
  updateMcpSettings: (servers: Array<{ name: string; enabled: boolean }>) =>
    rawFetch<McpSettings>('/api/settings/mcp', {
      method: 'POST',
      body: JSON.stringify({ action: 'update', servers }),
    }),
  upsertMcpServer: (server: Partial<McpServerItem> & { name: string }) =>
    rawFetch<McpSettings>('/api/settings/mcp', {
      method: 'POST',
      body: JSON.stringify({ action: 'upsert', server }),
    }),
  deleteMcpServer: (name: string) =>
    rawFetch<McpSettings>('/api/settings/mcp', {
      method: 'POST',
      body: JSON.stringify({ action: 'delete', name }),
    }),
  syncMcpSettings: (projectId?: string, headless = false) =>
    rawFetch<Record<string, unknown>>('/api/settings/mcp', {
      method: 'POST',
      body: JSON.stringify({ action: 'sync', project_id: projectId, headless }),
    }),
  getSkillSettings: (projectId?: string) => {
    const q = projectId ? `?project_id=${encodeURIComponent(projectId)}` : '';
    return rawFetch<SkillSettings>(`/api/settings/skills${q}`);
  },
  installSkills: (projectId?: string, agents?: string[]) =>
    rawFetch<{ written: string[]; skills: SkillSettings }>('/api/settings/skills', {
      method: 'POST',
      body: JSON.stringify({ project_id: projectId, agents }),
    }),
  initProjectSettings: (projectId?: string) =>
    rawFetch<Record<string, unknown>>('/api/settings/init', {
      method: 'POST',
      body: JSON.stringify({ project_id: projectId }),
    }),
  getNodes: () => rawFetch<{ nodes: WorkflowNodeDef[] }>('/api/workflow/nodes'),
  getProjects: () => rawFetch<{ projects: ProjectBinding[] }>('/api/projects'),
  createProject: (body: Record<string, string>) =>
    rawFetch<{ project: ProjectBinding }>('/api/projects', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  updateProject: (id: string, body: Record<string, string>) =>
    rawFetch<{ project: ProjectBinding }>(`/api/projects/${id}`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),
  deleteProject: (id: string) =>
    rawFetch<{ deleted: string }>(`/api/projects/${id}`, { method: 'DELETE' }),
  getTasks: (projectId: string) =>
    rawFetch<{ tasks: TaskItem[] }>(`/api/projects/${projectId}/tasks`),
  getTaskInsights: (projectId: string, taskId: string) =>
    rawFetch<TaskInsights>(`/api/projects/${projectId}/tasks/${taskId}/insights`),
  approveTaskQa: (
    projectId: string,
    taskId: string,
    body: { status?: string; user_note?: string } = {},
  ) =>
    rawFetch<{ approval: { status: string; user_note: string }; insights: TaskInsights }>(
      `/api/projects/${projectId}/tasks/${taskId}/qa-approval`,
      {
        method: 'POST',
        body: JSON.stringify(body),
      },
    ),
  createTask: (projectId: string, body: Record<string, string>) =>
    rawFetch<{ task: TaskItem }>(`/api/projects/${projectId}/tasks`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  updateTask: (projectId: string, taskId: string, body: Record<string, string>) =>
    rawFetch<{ task: TaskItem }>(`/api/projects/${projectId}/tasks/${taskId}`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),
  deleteTask: (projectId: string, taskId: string) =>
    rawFetch<{ deleted: string }>(`/api/projects/${projectId}/tasks/${taskId}`, {
      method: 'DELETE',
    }),
  getRuns: () => rawFetch<{ runs: WorkflowRun[] }>('/api/runs'),
  getRun: (runId: string) => rawFetch<{ run: WorkflowRun }>(`/api/runs/${runId}`),
  startRun: (body: Record<string, unknown>) =>
    rawFetch<{ run: WorkflowRun }>('/api/runs', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  openArtifact: (runId: string, nodeId: string) =>
    rawFetch<{ opened: string }>(`/api/runs/${runId}/open-artifact`, {
      method: 'POST',
      body: JSON.stringify({ node_id: nodeId }),
    }),
  getRuleSets: () =>
    rawFetch<{ rule_sets: RuleSetItem[]; rule_dirs: RuleSetItem[] }>('/api/rule-sets'),
  getRuleDirs: () =>
    rawFetch<{ rule_sets: RuleSetItem[]; rule_dirs: RuleSetItem[] }>('/api/rule-dirs'),
  createRuleSet: (body: {
    name: string;
    folder_path: string;
    create_folder?: boolean;
    node_rules?: Record<string, string[]>;
  }) =>
    rawFetch<{ rule_set: RuleSetItem }>('/api/rule-sets', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  updateRuleSet: (
    id: string,
    body: {
      name?: string;
      folder_path?: string;
      create_folder?: boolean;
      node_rules?: Record<string, string[]>;
    },
  ) =>
    rawFetch<{ rule_set: RuleSetItem }>(`/api/rule-sets/${id}`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),
  deleteRuleSet: (id: string) =>
    rawFetch<{ deleted: string }>(`/api/rule-sets/${id}`, { method: 'DELETE' }),
  bindRuleSet: (ruleSetId: string, projectIds: string[]) =>
    rawFetch<{ projects: ProjectBinding[] }>(`/api/rule-sets/${ruleSetId}/bind`, {
      method: 'POST',
      body: JSON.stringify({ project_ids: projectIds }),
    }),
  bindRuleDir: (resolvedPath: string, projectIds: string[], ruleSetId?: string) =>
    rawFetch<{ projects: ProjectBinding[] }>('/api/rule-dirs/bind', {
      method: 'POST',
      body: JSON.stringify({
        resolved_path: resolvedPath,
        rule_set_id: ruleSetId,
        project_ids: projectIds,
      }),
    }),
  getRuleFiles: (path: string) =>
    rawFetch<{ dir: string; files: string[]; file_count: number }>(
      `/api/rule-files?path=${encodeURIComponent(path)}`,
    ),
  getRuleSetSystemMd: (ruleSetId: string) =>
    rawFetch<SystemMdContent>(`/api/rule-sets/${ruleSetId}/system-md`),
  saveRuleSetSystemMd: (ruleSetId: string, content: string) =>
    rawFetch<SystemMdContent>(`/api/rule-sets/${ruleSetId}/system-md`, {
      method: 'PUT',
      body: JSON.stringify({ content }),
    }),
  getProjectRules: (projectId: string) =>
    rawFetch<{ project_id: string; ai_rules_dir: string; node_rules: Record<string, string[]> }>(
      `/api/projects/${projectId}/rules`,
    ),
  updateProjectRules: (
    projectId: string,
    body: { ai_rules_dir: string; node_rules?: Record<string, string[]> },
  ) =>
    rawFetch<{ project: ProjectBinding }>(`/api/projects/${projectId}/rules`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  getFsRoots: () =>
    rawFetch<{ roots: Array<{ name: string; path: string }> }>('/api/fs/roots'),
  listDir: (path: string, includeFiles = true, ext = '') => {
    const params = new URLSearchParams({
      path,
      files: includeFiles ? '1' : '0',
    });
    if (ext) params.set('ext', ext);
    return rawFetch<{
      path: string;
      dirs: Array<{ name: string; path: string }>;
      files: Array<{ name: string; path: string }>;
    }>(`/api/fs/list?${params}`);
  },
};
