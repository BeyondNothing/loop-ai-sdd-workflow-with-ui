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

export interface RunExplain {
  stuck_node: string;
  last_logs: string[];
  log_summary?: string[];
  can_retry: boolean;
  error: string;
  completed_count: number;
  permission_hint?: string;
  manual_command?: string;
}

export interface ProjectHealthCheck {
  key: string;
  ok: boolean;
  level: string;
  message: string;
  fixable: boolean;
}

export interface ProjectHealth {
  project_id: string;
  app_root: string;
  checks: ProjectHealthCheck[];
  ok: boolean;
  summary: string;
  fixable_count: number;
  actions?: string[];
}

export interface BoardTaskItem {
  project_id: string;
  project_name: string;
  task_id: string;
  task_name: string;
  last_run_id: string;
  run_status: string;
  stuck_node: string;
  error: string;
  qa_status: string;
  confidence: number | null;
  reached_0_8: boolean | null;
}

export interface TaskPriorityBoard {
  project_id: string;
  buckets: {
    stuck: BoardTaskItem[];
    awaiting: BoardTaskItem[];
    ready: BoardTaskItem[];
    running: BoardTaskItem[];
    other: BoardTaskItem[];
  };
  counts: Record<string, number>;
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
  explain?: RunExplain;
  last_heartbeat_at?: string;
  heartbeat_elapsed_ms?: number | null;
  timeline?: Array<{
    node_id: string;
    event: string;
    at: string;
    duration_ms?: number | null;
    success?: boolean;
  }>;
}

export interface ConfidenceRuleItem {
  condition: string;
  reason: string;
}

export interface ConfidenceNodeRules {
  node_id: string;
  description: string;
  high_confidence_rules: ConfidenceRuleItem[];
  low_confidence_rules: ConfidenceRuleItem[];
}

export interface ConfidenceRulesConfig {
  app_root: string;
  engine_path: string;
  path: string;
  exists: boolean;
  engine_nodes: ConfidenceNodeRules[];
  nodes: ConfidenceNodeRules[];
  merged_nodes: ConfidenceNodeRules[];
  node_order: string[];
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
  getConfidenceRules: (projectId?: string) => {
    const q = projectId ? `?project_id=${encodeURIComponent(projectId)}` : '';
    return rawFetch<ConfidenceRulesConfig>(`/api/settings/confidence-rules${q}`);
  },
  updateConfidenceRules: (body: {
    project_id?: string;
    nodes: ConfidenceNodeRules[];
  }) =>
    rawFetch<ConfidenceRulesConfig>('/api/settings/confidence-rules', {
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
  probeConnectivity: (projectId?: string) =>
    rawFetch<{
      ok: boolean;
      app_root: string;
      mcp: {
        ok: boolean;
        summary: string;
        path?: string;
        servers: Array<{
          name: string;
          enabled: boolean;
          ok: boolean;
          skipped?: boolean;
          message?: string;
          checks?: Array<Record<string, unknown>>;
        }>;
        agent_sync: Array<{ path: string; ok: boolean; message: string }>;
      };
      skills: {
        ok: boolean;
        summary: string;
        skill_name?: string;
        template_exists?: boolean;
        agents: Array<{
          agent: string;
          tool?: string;
          path: string;
          installed: boolean;
          ok: boolean;
          size?: number;
          stale_hint?: boolean;
          message: string;
        }>;
      };
    }>('/api/settings/probe', {
      method: 'POST',
      body: JSON.stringify({ project_id: projectId }),
    }),
  getRunMetrics: (opts: { days?: number; project_id?: string } = {}) => {
    const q = new URLSearchParams();
    if (opts.days != null) q.set('days', String(opts.days));
    if (opts.project_id) q.set('project_id', opts.project_id);
    const suffix = q.toString() ? `?${q}` : '';
    return rawFetch<{
      days: number;
      project_id: string | null;
      total: number;
      status_counts: Record<string, number>;
      fail_rate: number;
      duration_ms: {
        count: number;
        avg: number | null;
        p50: number | null;
        p95: number | null;
        max: number | null;
      };
      stuck_nodes: Array<{ node_id: string; count: number }>;
      daily: Array<{
        date: string;
        total: number;
        completed: number;
        failed: number;
        cancelled: number;
      }>;
      recent_runs: Array<{
        run_id: string;
        project_id: string;
        task_id?: string;
        status: string;
        started_at: string;
        ended_at?: string;
        duration_ms: number | null;
        stuck_node?: string;
        tool?: string;
      }>;
    }>(`/api/metrics/runs${suffix}`);
  },
  getNodes: () => rawFetch<{ nodes: WorkflowNodeDef[] }>('/api/workflow/nodes'),
  getProjects: () => rawFetch<{ projects: ProjectBinding[] }>('/api/projects'),
  createProject: (body: Record<string, unknown>) =>
    rawFetch<{
      project: ProjectBinding;
      bootstrap?: { ok?: boolean; summary?: string; actions?: string[]; error?: string };
      actions?: string[];
    }>('/api/projects', {
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
  exportProject: async (projectId: string, opts: { include_runs?: boolean } = {}) => {
    const q = new URLSearchParams();
    // 默认不含 runs，减小体积
    q.set('include_runs', opts.include_runs ? '1' : '0');
    const suffix = `?${q}`;
    const res = await fetch(`/api/projects/${projectId}/export${suffix}`);
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error((data as { error?: string }).error || `HTTP ${res.status}`);
    }
    const blob = await res.blob();
    const disposition = res.headers.get('Content-Disposition') || '';
    const match = /filename="([^"]+)"/.exec(disposition);
    return { blob, filename: match?.[1] || `project-${projectId}.zip` };
  },
  importProject: async (opts: {
    file: Blob;
    app_root: string;
    name?: string;
    create_app_root?: boolean;
    include_runs?: boolean;
    max_runs?: number;
  }) => {
    const q = new URLSearchParams();
    q.set('app_root', opts.app_root);
    if (opts.name) q.set('name', opts.name);
    if (opts.create_app_root) q.set('create_app_root', '1');
    // 默认不导入 runs
    if (opts.include_runs) q.set('include_runs', '1');
    if (opts.max_runs != null) q.set('max_runs', String(opts.max_runs));
    const res = await fetch(`/api/projects/import?${q}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/zip' },
      body: opts.file,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error((data as { error?: string }).error || `HTTP ${res.status}`);
    }
    return data as {
      project: ProjectBinding;
      tasks: TaskItem[];
      written: string[];
      file_count: number;
      task_count: number;
      run_count: number;
      include_runs: boolean;
      zip_bytes: number;
      max_zip_bytes: number;
      manifest: Record<string, unknown>;
    };
  },
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
  cloneTask: (projectId: string, taskId: string, body: { name_suffix?: string } = {}) =>
    rawFetch<{ task: TaskItem }>(`/api/projects/${projectId}/tasks/${taskId}/clone`, {
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
  getProjectHealth: (projectId: string) =>
    rawFetch<ProjectHealth>(`/api/projects/${projectId}/health`),
  fixProjectHealth: (projectId: string) =>
    rawFetch<ProjectHealth>(`/api/projects/${projectId}/health-fix`, {
      method: 'POST',
      body: JSON.stringify({}),
    }),
  getTaskBoard: (projectId?: string) => {
    const q = projectId ? `?project_id=${encodeURIComponent(projectId)}` : '';
    return rawFetch<TaskPriorityBoard>(`/api/board${q}`);
  },
  getProjectBoard: (projectId: string) =>
    rawFetch<TaskPriorityBoard>(`/api/projects/${projectId}/board`),
  getRuns: (params?: { project_id?: string; task_id?: string; status?: string }) => {
    const q = new URLSearchParams();
    if (params?.project_id) q.set('project_id', params.project_id);
    if (params?.task_id) q.set('task_id', params.task_id);
    if (params?.status) q.set('status', params.status);
    const suffix = q.toString() ? `?${q}` : '';
    return rawFetch<{ runs: WorkflowRun[] }>(`/api/runs${suffix}`);
  },
  getRun: (runId: string) => rawFetch<{ run: WorkflowRun }>(`/api/runs/${runId}`),
  startRun: (body: Record<string, unknown>) =>
    rawFetch<{ run: WorkflowRun }>('/api/runs', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  cancelRun: (runId: string) =>
    rawFetch<{ run: WorkflowRun }>(`/api/runs/${runId}/cancel`, {
      method: 'POST',
      body: JSON.stringify({}),
    }),
  retryRun: (
    runId: string,
    fresh = false,
    opts: { resume_from_node?: string; single_node?: boolean } = {},
  ) =>
    rawFetch<{ run: WorkflowRun }>(`/api/runs/${runId}/retry`, {
      method: 'POST',
      body: JSON.stringify({
        fresh,
        resume_from_node: opts.resume_from_node || '',
        single_node: Boolean(opts.single_node),
      }),
    }),
  previewArtifact: (runId: string, nodeId: string) =>
    rawFetch<{
      run_id: string;
      node_id: string;
      path: string;
      content: string;
      truncated: boolean;
      size: number;
    }>(`/api/runs/${runId}/artifacts/${encodeURIComponent(nodeId)}`),
  compareRuns: (left: string, right: string) =>
    rawFetch<{
      left: WorkflowRun;
      right: WorkflowRun;
      nodes: Array<{
        node_id: string;
        left_has: boolean;
        right_has: boolean;
        same_content: boolean | null;
        left_chars: number;
        right_chars: number;
      }>;
      summary: {
        left_completed: number;
        right_completed: number;
        nodes_same: number;
        nodes_diff: number;
        nodes_missing: number;
      };
      confidence: {
        left: { score: number | null; reached_0_8: boolean | null } | null;
        right: { score: number | null; reached_0_8: boolean | null } | null;
      };
    }>(`/api/runs/compare?left=${encodeURIComponent(left)}&right=${encodeURIComponent(right)}`),
  compareArtifact: (left: string, right: string, nodeId: string) =>
    rawFetch<{
      node_id: string;
      left: { run_id: string; path: string; content: string };
      right: { run_id: string; path: string; content: string };
      same: boolean;
      truncated: boolean;
    }>(
      `/api/runs/compare?left=${encodeURIComponent(left)}&right=${encodeURIComponent(right)}&node_id=${encodeURIComponent(nodeId)}`,
    ),
  openArtifact: (runId: string, nodeId: string) =>
    rawFetch<{ opened: string }>(`/api/runs/${runId}/open-artifact`, {
      method: 'POST',
      body: JSON.stringify({ node_id: nodeId }),
    }),
  exportRuleSet: async (ruleSetId: string) => {
    const res = await fetch(`/api/rule-sets/${ruleSetId}/export`);
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error((data as { error?: string }).error || `HTTP ${res.status}`);
    }
    const blob = await res.blob();
    const disposition = res.headers.get('Content-Disposition') || '';
    const match = /filename="([^"]+)"/.exec(disposition);
    return { blob, filename: match?.[1] || `ruleset-${ruleSetId}.zip` };
  },
  exportRun: async (runId: string) => {
    const res = await fetch(`/api/runs/${runId}/export`);
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error((data as { error?: string }).error || `HTTP ${res.status}`);
    }
    const blob = await res.blob();
    const disposition = res.headers.get('Content-Disposition') || '';
    const match = /filename="([^"]+)"/.exec(disposition);
    return { blob, filename: match?.[1] || `run-${runId.slice(0, 8)}.zip` };
  },
  importRuleSet: (body: {
    zip_base64: string;
    folder_path: string;
    name?: string;
    create_folder?: boolean;
  }) =>
    rawFetch<{ rule_set: RuleSetItem; written: string[]; file_count: number }>(
      '/api/rule-sets/import',
      {
        method: 'POST',
        body: JSON.stringify(body),
      },
    ),
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
