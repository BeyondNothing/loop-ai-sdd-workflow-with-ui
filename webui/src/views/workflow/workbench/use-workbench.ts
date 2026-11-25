import {
  computed,
  nextTick,
  onMounted,
  onUnmounted,
  reactive,
  ref,
  watch,
} from 'vue';

import { message, Modal } from 'ant-design-vue';

import {
  type ProjectBinding,
  type ProjectHealth,
  type RuleSetItem,
  type SystemInfo,
  type TaskInsights,
  type TaskItem,
  type TaskPriorityBoard,
  type WorkflowNodeDef,
  type WorkflowRun,
  workflowApi,
} from '#/api/workflow';

export type NodeStatus = 'queued' | 'running' | 'completed' | 'failed' | 'skipped';

export type LogFilterMode = 'all' | 'error' | 'node' | 'cancel' | 'eperm' | 'keyword';

export interface LogGroup {
  key: string;
  title: string;
  nodeId: string;
  lines: string[];
}

function prefsKey(projectId: string) {
  return `ai-loop:workbench:prefs:${projectId}`;
}

const LAST_PROJECT_KEY = 'ai-loop:workbench:last-project';

function readLastProjectId(): string {
  if (typeof localStorage === 'undefined') return '';
  return localStorage.getItem(LAST_PROJECT_KEY) || '';
}

function writeLastProjectId(projectId: string) {
  if (typeof localStorage === 'undefined' || !projectId) return;
  try {
    localStorage.setItem(LAST_PROJECT_KEY, projectId);
  } catch {
    // ignore quota
  }
}

function matchLogLine(line: string, mode: LogFilterMode, keyword: string): boolean {
  const lower = line.toLowerCase();
  if (mode === 'all') return true;
  if (mode === 'error') {
    return /error|fail|exception|traceback|失败|报错/i.test(line);
  }
  if (mode === 'node') {
    return /进入节点|节点完成|节点结束|离开节点/.test(line);
  }
  if (mode === 'cancel') {
    return /cancel|取消/i.test(line);
  }
  if (mode === 'eperm') {
    return /eperm|operation not permitted|uv_cwd|cannot change working directory|full disk access/i.test(
      line,
    );
  }
  if (mode === 'keyword') {
    const kw = keyword.trim().toLowerCase();
    if (!kw) return true;
    return lower.includes(kw);
  }
  return true;
}

function highlightLogLine(line: string): string {
  const escaped = line
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');
  return escaped.replace(
    /(EPERM|Operation not permitted|失败|error|ERROR|cancelled|取消|进入节点|节点完成)/gi,
    '<mark class="log-hl">$1</mark>',
  );
}

export function useWorkbench() {
  const nodes = ref<WorkflowNodeDef[]>([]);
  const projects = ref<ProjectBinding[]>([]);
  const tasks = ref<TaskItem[]>([]);
  const runs = ref<WorkflowRun[]>([]);

  const selectedProjectId = ref('');
  const selectedTaskId = ref('');
  const selectedRun = ref<WorkflowRun | null>(null);

  const form = reactive({
    taskName: '',
    prdPath: '',
    requirement: '',
  });
  const flags = reactive({ headless: false, skipClar: false, auto: false });

  const projectModalOpen = ref(false);
  const projectForm = reactive({
    name: '',
    app_root: '',
    docs_dir: 'docs',
    ai_rules_dir: 'ai-rules',
    create_app_root: false,
    bootstrap: true,
    rule_set_id: '' as string,
  });
  const editingProject = ref(false);

  const taskModalOpen = ref(false);
  const taskNameInput = ref('');
  const projectImportOpen = ref(false);
  const projectImportFile = ref<File | null>(null);
  const projectImportForm = reactive({
    name: '',
    app_root: '',
    create_app_root: true,
    include_runs: false,
    include_runs_export: false,
    file_name: '',
  });
  const MAX_PROJECT_IMPORT_MB = 50;
  const loading = ref(false);
  const systemInfo = ref<SystemInfo | null>(null);
  const defaultTool = ref('omp');
  const ruleSets = ref<RuleSetItem[]>([]);
  const ruleDirPickerOpen = ref(false);
  const taskInsights = ref<TaskInsights | null>(null);
  const taskQaStatus = ref<Record<string, string>>({});
  const historyTaskFilter = ref<string>('');
  const compareLeftId = ref('');
  const compareRightId = ref('');
  const compareResult = ref<Awaited<ReturnType<typeof workflowApi.compareRuns>> | null>(
    null,
  );
  const compareOpen = ref(false);
  const projectHealth = ref<ProjectHealth | null>(null);
  const taskBoard = ref<TaskPriorityBoard | null>(null);
  const healthLoading = ref(false);
  const boardLoading = ref(false);
  const logFilter = ref<LogFilterMode>('all');
  const logKeyword = ref('');
  const logActiveKeys = ref<string[]>([]);
  const notifyEnabled = ref(
    typeof localStorage !== 'undefined'
      ? localStorage.getItem('ai-loop:notify-terminal') !== '0'
      : true,
  );
  const lastNotifiedRunKey = ref('');
  const sidebarNodeId = ref('');
  const sidebarPreview = reactive({
    nodeId: '',
    path: '',
    content: '',
    truncated: false,
    isMarkdown: false,
    loading: false,
    error: '',
  });
  const artifactPreviewOpen = ref(false);
  const artifactPreview = reactive({
    nodeId: '',
    path: '',
    content: '',
    truncated: false,
    mode: 'single' as 'single' | 'diff',
    rightPath: '',
    rightContent: '',
    same: false,
    isMarkdown: false,
  });

  function looksLikeMarkdown(path: string): boolean {
    const lower = (path || '').toLowerCase();
    return (
      lower.endsWith('.md') ||
      lower.endsWith('.markdown') ||
      lower.endsWith('.mdx')
    );
  }
  const artifactNodeOptions = computed(() => {
    const outputs = selectedRun.value?.node_outputs || {};
    return Object.keys(outputs)
      .filter((id) => id !== 'original_requirement' && outputs[id])
      .map((id) => ({ label: id, value: id }));
  });

  let pollTimer: number | undefined;
  let eventSource: EventSource | null = null;
  const sseStatus = ref<'off' | 'connected' | 'reconnecting'>('off');
  const highlightedNodeId = ref('');

  const selectedProject = computed(() =>
    projects.value.find((p) => p.project_id === selectedProjectId.value),
  );

  const ruleDirOptions = computed(() =>
    ruleSets.value.map((item) => ({
      label: `${item.name} (${item.projects.length} 项)`,
      value: item.resolved_path,
      ai_rules_dir: item.resolved_path,
    })),
  );

  const projectRuns = computed(() => {
    let list = runs.value.filter((r) => r.project_id === selectedProjectId.value);
    if (historyTaskFilter.value) {
      list = list.filter(
        (r) =>
          r.task_id === historyTaskFilter.value ||
          r.requirement_name ===
            tasks.value.find((t) => t.task_id === historyTaskFilter.value)?.task_name,
      );
    }
    return list;
  });

  const historyTaskOptions = computed(() => [
    { label: '全部任务', value: '' },
    ...tasks.value.map((t) => ({ label: t.task_name, value: t.task_id })),
  ]);

  const canCancelSelected = computed(() =>
    ['queued', 'running', 'cancelling'].includes(selectedRun.value?.status || ''),
  );

  const canRetrySelected = computed(() =>
    ['completed', 'failed', 'cancelled', 'interrupted'].includes(
      selectedRun.value?.status || '',
    ),
  );

  function isServerInterruptedRun(run: { status?: string; error?: string } | null) {
    if (!run) return false;
    if (run.status === 'interrupted') return true;
    // 兼容旧数据：重启收尸曾标成 cancelled
    return (
      run.status === 'cancelled' &&
      /server restarted|orphaned|服务重启|运行中断/i.test(run.error || '')
    );
  }

  function statusColor(status: NodeStatus | string) {
    const map: Record<string, string> = {
      queued: 'default',
      running: 'processing',
      completed: 'success',
      failed: 'error',
      skipped: 'warning',
      cancelling: 'warning',
      cancelled: 'default',
      interrupted: 'warning',
    };
    return map[status] || 'default';
  }

  function statusLabel(run: { status?: string; error?: string } | null) {
    if (!run?.status) return '';
    if (isServerInterruptedRun(run)) return '中断（可续跑）';
    if (run.status === 'cancelled') return '已取消';
    if (run.status === 'failed') return '失败';
    if (run.status === 'completed') return '完成';
    if (run.status === 'running') return '运行中';
    if (run.status === 'queued') return '排队';
    if (run.status === 'cancelling') return '取消中';
    return run.status;
  }

  function deriveNodeStatuses(run: WorkflowRun | null) {
    const result = run?.result || {};
    const outputs =
      run?.node_outputs || (result.node_outputs as Record<string, string>) || {};
    const completed = new Set(
      run?.completed_nodes || (result.completed_nodes as string[]) || [],
    );
    const currentNode =
      run?.current_node || (result.current_node as string) || '';

    return nodes.value.map((node) => {
      let status: NodeStatus = 'queued';
      if (run?.status === 'completed') {
        status =
          outputs[node.id] || completed.has(node.id) ? 'completed' : 'skipped';
      } else if (
        run?.status === 'failed' ||
        run?.status === 'cancelled' ||
        run?.status === 'interrupted'
      ) {
        if (outputs[node.id] || completed.has(node.id)) status = 'completed';
        else if (currentNode === node.id) status = 'failed';
      } else if (run?.status === 'running') {
        if (outputs[node.id] || completed.has(node.id)) status = 'completed';
        else if (currentNode === node.id) status = 'running';
      }
      return {
        ...node,
        status,
        artifact: outputs[node.id] || '',
      };
    });
  }

  const nodeStatuses = computed(() => deriveNodeStatuses(selectedRun.value));

  const currentStepIndex = computed(() => {
    const list = nodeStatuses.value;
    const runningIdx = list.findIndex((n) => n.status === 'running');
    if (runningIdx >= 0) return runningIdx;
    const lastDone = [...list].reverse().findIndex((n) => n.status === 'completed');
    if (lastDone >= 0) return list.length - 1 - lastDone + 1;
    return 0;
  });

  const runLogLines = computed(() => {
    const run = selectedRun.value;
    if (!run) return [] as string[];
    return (run.logs || []).slice(-500);
  });

  const runLogs = computed(() => {
    const lines = runLogLines.value;
    if (!lines.length) return '(暂无日志)';
    return lines.join('\n');
  });

  const logGroups = computed(() => {
    const lines = runLogLines.value;
    if (!lines.length) return [] as LogGroup[];
    const groups: LogGroup[] = [];
    let current: LogGroup = {
      key: 'boot',
      title: '启动 / 其它',
      nodeId: '',
      lines: [],
    };
    groups.push(current);
    for (const line of lines) {
      const enter = /进入节点:\s*(\S+)/.exec(line);
      if (enter?.[1]) {
        current = {
          key: `${enter[1]}-${groups.length}`,
          title: enter[1],
          nodeId: enter[1],
          lines: [line],
        };
        groups.push(current);
      } else {
        current.lines.push(line);
      }
    }
    return groups
      .map((g) => ({
        ...g,
        lines: g.lines.filter((line) =>
          matchLogLine(line, logFilter.value, logKeyword.value),
        ),
      }))
      .filter((g) => g.lines.length > 0);
  });

  watch(
    logGroups,
    (groups) => {
      const valid = new Set(groups.map((g) => g.key));
      const kept = logActiveKeys.value.filter((k) => valid.has(k));
      const latest = groups.slice(-2).map((g) => g.key);
      logActiveKeys.value = [...new Set([...kept, ...latest])];
    },
    { immediate: true },
  );

  function loadProjectPrefs(projectId: string) {
    if (!projectId || typeof localStorage === 'undefined') return;
    try {
      const raw = localStorage.getItem(prefsKey(projectId));
      if (!raw) return;
      const data = JSON.parse(raw) as {
        headless?: boolean;
        skipClar?: boolean;
        auto?: boolean;
        tool?: string;
        lastTaskId?: string;
      };
      if (typeof data.headless === 'boolean') flags.headless = data.headless;
      if (typeof data.skipClar === 'boolean') flags.skipClar = data.skipClar;
      if (typeof data.auto === 'boolean') flags.auto = data.auto;
      if (data.tool) defaultTool.value = data.tool;
    } catch {
      // ignore bad prefs
    }
  }

  /** 该项目的偏好（含上次选中的任务）；不改变 flags */
  function readProjectPrefs(projectId: string): { lastTaskId?: string } {
    if (!projectId || typeof localStorage === 'undefined') return {};
    try {
      const raw = localStorage.getItem(prefsKey(projectId));
      if (!raw) return {};
      return JSON.parse(raw) as { lastTaskId?: string };
    } catch {
      return {};
    }
  }

  function pickRememberedTask(projectId: string): string {
    return String(readProjectPrefs(projectId).lastTaskId || '');
  }

  function rememberTask(projectId: string, taskId: string) {
    if (!projectId || !taskId || typeof localStorage === 'undefined') return;
    try {
      const current = readProjectPrefs(projectId);
      localStorage.setItem(
        prefsKey(projectId),
        JSON.stringify({ ...current, lastTaskId: taskId }),
      );
    } catch {
      // ignore quota
    }
  }

  function saveProjectPrefs() {
    if (!selectedProjectId.value || typeof localStorage === 'undefined') return;
    try {
      const current = readProjectPrefs(selectedProjectId.value);
      localStorage.setItem(
        prefsKey(selectedProjectId.value),
        JSON.stringify({
          ...current,
          headless: flags.headless,
          skipClar: flags.skipClar,
          auto: flags.auto,
          tool: defaultTool.value,
        }),
      );
    } catch {
      // ignore quota
    }
  }

  watch(
    () => [flags.headless, flags.skipClar, flags.auto, defaultTool.value],
    () => {
      saveProjectPrefs();
    },
  );

  async function loadNodes() {
    const data = await workflowApi.getNodes();
    nodes.value = data.nodes || [];
  }

  async function loadProjects() {
    const data = await workflowApi.getProjects();
    projects.value = data.projects || [];
    if (!selectedProjectId.value && projects.value.length) {
      // 再次进入时优先回到上次的项目
      const remembered = readLastProjectId();
      const hit = projects.value.find((p) => p.project_id === remembered);
      await selectProject((hit || projects.value[0]!).project_id);
    }
  }

  async function loadRuleSets() {
    try {
      const data = await workflowApi.getRuleSets();
      ruleSets.value = data.rule_sets || data.rule_dirs || [];
    } catch {
      ruleSets.value = [];
    }
  }

  async function loadTasks() {
    if (!selectedProjectId.value) {
      tasks.value = [];
      return;
    }
    const data = await workflowApi.getTasks(selectedProjectId.value);
    tasks.value = data.tasks || [];
  }

  /** 最近活跃的任务：优先有执行记录的，其次按 updated_at 倒序 */
  function pickRecentTask(list: TaskItem[]): TaskItem | null {
    if (!list.length) return null;
    const score = (t: TaskItem) => {
      const ran = t.last_run_id ? 1 : 0;
      const ts = Date.parse(t.updated_at || t.created_at || '') || 0;
      return [ran, ts] as const;
    };
    return [...list].sort((a, b) => {
      const [ra, ta] = score(a);
      const [rb, tb] = score(b);
      if (ra !== rb) return rb - ra;
      return tb - ta;
    })[0]!;
  }

  async function loadRuns() {
    const data = await workflowApi.getRuns(
      selectedProjectId.value
        ? { project_id: selectedProjectId.value }
        : undefined,
    );
    runs.value = data.runs || [];
    syncSelectedRun();
  }

  function applyRunPayload(payload: WorkflowRun) {
    if (!payload?.run_id) return;
    const prevStatus =
      runs.value.find((r) => r.run_id === payload.run_id)?.status ||
      (selectedRun.value?.run_id === payload.run_id
        ? selectedRun.value.status
        : '');
    const idx = runs.value.findIndex((r) => r.run_id === payload.run_id);
    if (idx >= 0) {
      const next = [...runs.value];
      next[idx] = { ...next[idx], ...payload };
      runs.value = next;
    } else if (
      !selectedProjectId.value ||
      payload.project_id === selectedProjectId.value
    ) {
      runs.value = [payload, ...runs.value];
    }
    if (selectedRun.value?.run_id === payload.run_id) {
      selectedRun.value = { ...selectedRun.value, ...payload };
    } else {
      syncSelectedRun();
    }
    const fromActive = ['queued', 'running', 'cancelling'].includes(prevStatus);
    const toTerminal = ['completed', 'failed', 'cancelled', 'interrupted'].includes(
      payload.status || '',
    );
    if (fromActive && toTerminal) {
      notifyRunTerminal(payload);
    }
  }

  function disconnectRunEvents() {
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
    sseStatus.value = 'off';
  }

  function connectRunEvents() {
    disconnectRunEvents();
    if (!selectedProjectId.value || typeof EventSource === 'undefined') return;
    const url = `/api/events?project_id=${encodeURIComponent(selectedProjectId.value)}`;
    eventSource = new EventSource(url);
    sseStatus.value = 'reconnecting';
    const onMessage = (ev: MessageEvent) => {
      sseStatus.value = 'connected';
      try {
        const data = JSON.parse(String(ev.data || '{}')) as {
          payload?: WorkflowRun;
        };
        if (data.payload) applyRunPayload(data.payload);
      } catch {
        // ignore malformed
      }
    };
    eventSource.addEventListener('snapshot', onMessage as EventListener);
    eventSource.addEventListener('update', onMessage as EventListener);
    eventSource.addEventListener('log', onMessage as EventListener);
    eventSource.onopen = () => {
      sseStatus.value = 'connected';
    };
    eventSource.onerror = () => {
      // 浏览器会自动重连；慢轮询兜底
      sseStatus.value = 'reconnecting';
    };
  }

  const isTccSensitiveAppRoot = computed(() => {
    const root = (projectForm.app_root || selectedProject.value?.app_root || '')
      .trim()
      .replace(/\\/g, '/');
    if (!root) return false;
    return /\/(Downloads|Desktop|Documents)(\/|$)/i.test(root);
  });

  function syncSelectedRun(preferLastRun = false) {
    // 轮询刷新：优先保留用户已点「查看」的同一条 run，只更新对象内容
    if (!preferLastRun && selectedRun.value?.run_id) {
      const current = runs.value.find((r) => r.run_id === selectedRun.value!.run_id);
      if (current) {
        selectedRun.value = current;
        return;
      }
    }

    const task = tasks.value.find((t) => t.task_id === selectedTaskId.value);
    if (task?.last_run_id) {
      const hit = runs.value.find((r) => r.run_id === task.last_run_id);
      if (hit) {
        selectedRun.value = hit;
        return;
      }
    }
    if (task) {
      const hit = runs.value.find(
        (r) =>
          r.project_id === selectedProjectId.value &&
          r.requirement_name === task.task_name,
      );
      selectedRun.value = hit || null;
    } else {
      selectedRun.value = null;
    }
  }

  function taskRunStatus(task: TaskItem) {
    const run = runs.value.find((r) => r.run_id === task.last_run_id);
    return run?.status || '';
  }

  function qaBadge(taskId: string) {
    return taskQaStatus.value[taskId] || '';
  }

  async function loadTaskInsights(taskId = selectedTaskId.value) {
    if (!selectedProjectId.value || !taskId) {
      taskInsights.value = null;
      return;
    }
    try {
      const data = await workflowApi.getTaskInsights(selectedProjectId.value, taskId);
      taskInsights.value = data;
      taskQaStatus.value = {
        ...taskQaStatus.value,
        [taskId]: data.qa_review?.status || '',
      };
    } catch {
      taskInsights.value = null;
    }
  }

  async function loadTaskQaBadges() {
    if (!selectedProjectId.value || !tasks.value.length) {
      taskQaStatus.value = {};
      return;
    }
    const projectId = selectedProjectId.value;
    const entries = await Promise.all(
      tasks.value.slice(0, 30).map(async (task) => {
        try {
          const data = await workflowApi.getTaskInsights(projectId, task.task_id);
          return [task.task_id, data.qa_review?.status || ''] as const;
        } catch {
          return [task.task_id, ''] as const;
        }
      }),
    );
    const next: Record<string, string> = {};
    for (const [id, status] of entries) next[id] = status;
    taskQaStatus.value = next;
  }

  async function approveQa(status = 'approved', userNote = '') {
    if (!selectedProjectId.value || !selectedTaskId.value) return;
    loading.value = true;
    try {
      const data = await workflowApi.approveTaskQa(
        selectedProjectId.value,
        selectedTaskId.value,
        { status, user_note: userNote },
      );
      taskInsights.value = data.insights;
      taskQaStatus.value = {
        ...taskQaStatus.value,
        [selectedTaskId.value]: data.insights.qa_review?.status || status,
      };
      message.success(status === 'approved' ? '已标记用例 QA 通过（异步，不阻塞主流程）' : '已重置为待审');
    } catch (e) {
      message.error(String(e));
    } finally {
      loading.value = false;
    }
  }

  async function selectProject(projectId: string) {
    selectedProjectId.value = projectId;
    writeLastProjectId(projectId);
    selectedTaskId.value = '';
    selectedRun.value = null;
    taskInsights.value = null;
    projectHealth.value = null;
    sidebarNodeId.value = '';
    sidebarPreview.nodeId = '';
    sidebarPreview.content = '';
    sidebarPreview.path = '';
    sidebarPreview.error = '';
    form.taskName = '';
    form.prdPath = '';
    form.requirement = '';
    loadProjectPrefs(projectId);
    await loadTasks();
    await loadRuns();
    await loadTaskQaBadges();
    void loadTaskBoard();
    connectRunEvents();

    // 记住上次的任务；否则默认选中最近活跃的任务
    const remembered = pickRememberedTask(projectId);
    const target =
      (remembered && tasks.value.find((t) => t.task_id === remembered)) ||
      pickRecentTask(tasks.value);
    if (target) await selectTask(target.task_id);
  }

  async function selectTask(taskId: string) {
    selectedTaskId.value = taskId;
    const task = tasks.value.find((t) => t.task_id === taskId);
    if (!task) return;
    rememberTask(selectedProjectId.value, taskId);
    form.taskName = task.task_name;
    form.prdPath = task.requirement_prd_path;
    form.requirement = task.requirement_text;
    syncSelectedRun(true);
    await loadTaskInsights(taskId);
  }

  async function viewRun(runId: string) {
    const hit = runs.value.find((r) => r.run_id === runId);
    if (!hit) {
      message.warning('找不到该执行记录');
      return false;
    }
    selectedRun.value = hit;

    // 联动左侧任务，但不覆盖刚选中的 run
    const matched =
      (hit.task_id && tasks.value.find((t) => t.task_id === hit.task_id)) ||
      tasks.value.find(
        (t) =>
          t.task_name === hit.requirement_name &&
          (!hit.project_id || selectedProjectId.value === hit.project_id),
      );

    if (matched) {
      selectedTaskId.value = matched.task_id;
      form.taskName = matched.task_name;
      form.prdPath = matched.requirement_prd_path;
      form.requirement = matched.requirement_text;
      await loadTaskInsights(matched.task_id);
    } else if (hit.requirement_name) {
      form.taskName = hit.requirement_name;
    }
    return true;
  }

  function selectRun(runId: string) {
    void viewRun(runId);
  }

  function openProjectModal(edit = false) {
    editingProject.value = edit;
    if (edit && selectedProject.value) {
      projectForm.name = selectedProject.value.name;
      projectForm.app_root = selectedProject.value.app_root;
      projectForm.docs_dir = selectedProject.value.docs_dir;
      projectForm.ai_rules_dir = selectedProject.value.ai_rules_dir;
      projectForm.create_app_root = false;
      projectForm.bootstrap = false;
      projectForm.rule_set_id = '';
    } else {
      projectForm.name = '';
      projectForm.app_root = '';
      projectForm.docs_dir = 'docs';
      projectForm.ai_rules_dir = 'ai-rules';
      projectForm.create_app_root = false;
      projectForm.bootstrap = true;
      projectForm.rule_set_id = '';
    }
    projectModalOpen.value = true;
  }

  function findRuleSetForForm() {
    const root = projectForm.app_root.trim();
    const rulesPath = projectForm.ai_rules_dir.trim();
    return ruleSets.value.find((item) => {
      if (item.resolved_path === rulesPath) return true;
      if (root && item.resolved_path.startsWith(root)) {
        const rel = item.resolved_path.slice(root.length).replace(/^[/\\]/, '');
        return rel === rulesPath;
      }
      return false;
    });
  }

  async function submitProject() {
    try {
      let projectId = selectedProjectId.value;
      if (editingProject.value && selectedProjectId.value) {
        await workflowApi.updateProject(selectedProjectId.value, {
          name: projectForm.name,
          app_root: projectForm.app_root,
          docs_dir: projectForm.docs_dir,
          ai_rules_dir: projectForm.ai_rules_dir,
        });
        const matchedRuleSet = findRuleSetForForm();
        if (matchedRuleSet && projectId) {
          await workflowApi.bindRuleSet(matchedRuleSet.rule_set_id, [projectId]);
        }
        message.success('项目已保存');
      } else {
        const matched = projectForm.rule_set_id
          ? ruleSets.value.find((r) => r.rule_set_id === projectForm.rule_set_id)
          : findRuleSetForForm();
        const created = await workflowApi.createProject({
          name: projectForm.name,
          app_root: projectForm.app_root,
          docs_dir: projectForm.docs_dir,
          ai_rules_dir: projectForm.ai_rules_dir,
          create_app_root: projectForm.create_app_root,
          bootstrap: projectForm.bootstrap,
          rule_set_id: matched?.rule_set_id || projectForm.rule_set_id || undefined,
        });
        projectId = created.project.project_id;
        selectedProjectId.value = created.project.project_id;
        const boot = created.bootstrap;
        if (projectForm.bootstrap && boot && boot.ok === false) {
          message.warning(
            `项目已创建，但初始化未完全成功：${boot.error || boot.summary || '见健康检查'}`,
          );
        } else if (projectForm.bootstrap) {
          message.success(
            `项目已创建并初始化${
              created.actions?.length ? `（${created.actions.length} 步）` : ''
            }`,
          );
        } else {
          message.success('项目已创建');
        }
      }
      projectModalOpen.value = false;
      await Promise.all([loadProjects(), loadRuleSets()]);
      if (projectId) await selectProject(projectId);
    } catch (e) {
      message.error(String(e));
    }
  }

  async function deleteProject() {
    if (!selectedProjectId.value) return;
    Modal.confirm({
      title: '确认删除项目？',
      content: '将删除绑定、任务、runs 记录，并清理 runtime 磁盘目录。',
      onOk: async () => {
        await workflowApi.deleteProject(selectedProjectId.value);
        selectedProjectId.value = '';
        await loadProjects();
        message.success('已删除（含 runtime 清理）');
      },
    });
  }

  async function exportSelectedProject() {
    if (!selectedProjectId.value) return message.warning('请先选择项目');
    loading.value = true;
    try {
      const { blob, filename } = await workflowApi.exportProject(
        selectedProjectId.value,
        { include_runs: projectImportForm.include_runs_export },
      );
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
      message.success(
        `已导出整包 ${filename}${
          projectImportForm.include_runs_export ? '（含 runs）' : '（不含 runs）'
        }`,
      );
    } catch (e) {
      message.error(String(e));
    } finally {
      loading.value = false;
    }
  }

  function openProjectImportModal() {
    projectImportForm.name = '';
    projectImportForm.app_root = '';
    projectImportForm.create_app_root = true;
    projectImportForm.include_runs = false;
    projectImportForm.file_name = '';
    projectImportFile.value = null;
    projectImportOpen.value = true;
  }

  async function onProjectImportFile(file: File) {
    const maxBytes = MAX_PROJECT_IMPORT_MB * 1024 * 1024;
    if (file.size > maxBytes) {
      message.error(`文件过大（>${MAX_PROJECT_IMPORT_MB}MB），请去掉 runs 后重新导出再导入`);
      projectImportFile.value = null;
      projectImportForm.file_name = '';
      return;
    }
    projectImportFile.value = file;
    projectImportForm.file_name = file.name;
    if (!projectImportForm.name) {
      projectImportForm.name = file.name
        .replace(/\.zip$/i, '')
        .replace(/\.project$/i, '');
    }
  }

  async function submitProjectImport() {
    if (!projectImportFile.value) {
      message.warning('请选择项目包 zip');
      return;
    }
    if (!projectImportForm.app_root.trim()) {
      message.warning('请填写目标 app_root');
      return;
    }
    loading.value = true;
    try {
      const data = await workflowApi.importProject({
        file: projectImportFile.value,
        app_root: projectImportForm.app_root.trim(),
        name: projectImportForm.name.trim() || undefined,
        create_app_root: projectImportForm.create_app_root,
        include_runs: projectImportForm.include_runs,
        max_runs: 20,
      });
      projectImportOpen.value = false;
      await loadProjects();
      if (data.project?.project_id) {
        await selectProject(data.project.project_id);
      }
      message.success(
        `已导入项目：任务 ${data.task_count} · runs ${data.run_count} · 文件 ${data.file_count}`,
      );
    } catch (e) {
      message.error(String(e));
    } finally {
      loading.value = false;
    }
  }

  async function submitTask() {
    const name = taskNameInput.value.trim();
    if (!name) return message.warning('请输入任务名称');
    await workflowApi.createTask(selectedProjectId.value, {
      task_name: name,
      requirement_prd_path: '',
      requirement_text: '',
    });
    taskModalOpen.value = false;
    taskNameInput.value = '';
    await loadTasks();
    const created = tasks.value.find((t) => t.task_name === name);
    if (created) selectTask(created.task_id);
  }

  async function deleteTask(taskId: string) {
    Modal.confirm({
      title: '确认删除任务？',
      onOk: async () => {
        await workflowApi.deleteTask(selectedProjectId.value, taskId);
        if (selectedTaskId.value === taskId) {
          selectedTaskId.value = '';
          selectedRun.value = null;
        }
        await loadTasks();
      },
    });
  }

  async function cloneTask(taskId: string) {
    if (!selectedProjectId.value) return;
    loading.value = true;
    try {
      const { task } = await workflowApi.cloneTask(selectedProjectId.value, taskId);
      await loadTasks();
      selectTask(task.task_id);
      message.success(`已克隆: ${task.task_name}`);
    } catch (e) {
      message.error(String(e));
    } finally {
      loading.value = false;
    }
  }

  async function startRun(opts: { resume_from_node?: string; single_node?: boolean } = {}) {
    if (!selectedProjectId.value || !selectedTaskId.value) {
      return message.warning('请先选择项目和任务');
    }
    if (!form.requirement.trim() && !form.prdPath.trim()) {
      return message.warning('请填写需求或 PRD 路径');
    }
    loading.value = true;
    try {
      await workflowApi.updateTask(selectedProjectId.value, selectedTaskId.value, {
        task_name: form.taskName,
        requirement_prd_path: form.prdPath,
        requirement_text: form.requirement,
      });
      const { run } = await workflowApi.startRun({
        project_id: selectedProjectId.value,
        task_id: selectedTaskId.value,
        requirement_name: form.taskName,
        requirement: form.requirement,
        requirement_prd_path: form.prdPath,
        tool: defaultTool.value,
        skip_clarification: flags.skipClar,
        auto: flags.auto,
        headless_all_nodes: flags.headless,
        fresh: false,
        skip_mcp_setup: false,
        resume_from_node: opts.resume_from_node || '',
        single_node: Boolean(opts.single_node),
      });
      selectedRun.value = run;
      const tip = opts.single_node
        ? `只跑节点 ${opts.resume_from_node}`
        : opts.resume_from_node
          ? `从 ${opts.resume_from_node} 续跑`
          : '任务已启动';
      message.success(`${tip}: ${run.run_id}`);
      saveProjectPrefs();
      await loadRuns();
      await loadTasks();
    } catch (e) {
      message.error(String(e));
    } finally {
      loading.value = false;
    }
  }

  async function resumeFromNode(nodeId: string) {
    Modal.confirm({
      title: `从「${nodeId}」续跑？`,
      content: '将从该节点起继续执行后续流水线（不删已有产物）。',
      okText: '从此续跑',
      onOk: () => startRun({ resume_from_node: nodeId, single_node: false }),
    });
  }

  async function runSingleNode(nodeId: string) {
    Modal.confirm({
      title: `只跑「${nodeId}」？`,
      content: '仅执行这一步，不继续后续节点。',
      okText: '只跑一步',
      onOk: () => startRun({ resume_from_node: nodeId, single_node: true }),
    });
  }

  async function openArtifact(nodeId: string) {
    if (!selectedRun.value) return;
    try {
      const data = await workflowApi.openArtifact(selectedRun.value.run_id, nodeId);
      message.success(`已打开: ${data.opened}`);
    } catch (e) {
      message.error(String(e));
    }
  }

  async function loadSidebarArtifact(nodeId: string): Promise<boolean> {
    if (!selectedRun.value || !nodeId) return false;
    sidebarNodeId.value = nodeId;
    sidebarPreview.loading = true;
    sidebarPreview.error = '';
    try {
      const data = await workflowApi.previewArtifact(selectedRun.value.run_id, nodeId);
      sidebarPreview.nodeId = data.node_id;
      sidebarPreview.path = data.path;
      sidebarPreview.content = data.content;
      sidebarPreview.truncated = data.truncated;
      sidebarPreview.isMarkdown = looksLikeMarkdown(data.path);
      return true;
    } catch (e) {
      sidebarPreview.nodeId = nodeId;
      sidebarPreview.path = '';
      sidebarPreview.content = '';
      sidebarPreview.error = String(e);
      return false;
    } finally {
      sidebarPreview.loading = false;
    }
  }

  async function previewArtifact(nodeId: string, opts: { modal?: boolean } = {}): Promise<boolean> {
    if (!selectedRun.value) return false;
    const openModal = opts.modal === true;
    loading.value = true;
    try {
      const data = await workflowApi.previewArtifact(selectedRun.value.run_id, nodeId);
      sidebarNodeId.value = data.node_id;
      sidebarPreview.nodeId = data.node_id;
      sidebarPreview.path = data.path;
      sidebarPreview.content = data.content;
      sidebarPreview.truncated = data.truncated;
      sidebarPreview.isMarkdown = looksLikeMarkdown(data.path);
      sidebarPreview.error = '';
      if (openModal) {
        artifactPreview.mode = 'single';
        artifactPreview.nodeId = data.node_id;
        artifactPreview.path = data.path;
        artifactPreview.content = data.content;
        artifactPreview.truncated = data.truncated;
        artifactPreview.rightPath = '';
        artifactPreview.rightContent = '';
        artifactPreview.same = false;
        artifactPreview.isMarkdown = looksLikeMarkdown(data.path);
        artifactPreviewOpen.value = true;
      }
      return true;
    } catch (e) {
      message.error(String(e));
      sidebarPreview.error = String(e);
      return false;
    } finally {
      loading.value = false;
    }
  }

  async function openTimelineNode(nodeId: string): Promise<'previewed' | 'focused'> {
    const ok = await loadSidebarArtifact(nodeId);
    if (ok) {
      highlightedNodeId.value = '';
      return 'previewed';
    }
    highlightedNodeId.value = nodeId;
    await nextTick();
    const el = document.querySelector(
      `[data-node-id="${CSS.escape(nodeId)}"]`,
    ) as HTMLElement | null;
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    message.info('尚无产物，已定位到节点表');
    window.setTimeout(() => {
      if (highlightedNodeId.value === nodeId) highlightedNodeId.value = '';
    }, 4000);
    return 'focused';
  }

  async function exportSelectedRun() {
    if (!selectedRun.value) return message.warning('请先选择一次执行');
    loading.value = true;
    try {
      const { blob, filename } = await workflowApi.exportRun(selectedRun.value.run_id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
      message.success(`已导出 ${filename}`);
    } catch (e) {
      message.error(String(e));
    } finally {
      loading.value = false;
    }
  }

  async function switchPreviewNode(nodeId: string) {
    if (!nodeId || artifactPreview.mode !== 'single') return;
    // 弹窗内切换必须写回 artifactPreview（默认只更新侧栏）
    await previewArtifact(nodeId, { modal: true });
  }

  async function openCompareDiff(nodeId: string) {
    if (!compareLeftId.value || !compareRightId.value) {
      message.warning('请先选择对比的 A/B 两次执行');
      return;
    }
    loading.value = true;
    try {
      const data = await workflowApi.compareArtifact(
        compareLeftId.value,
        compareRightId.value,
        nodeId,
      );
      artifactPreview.mode = 'diff';
      artifactPreview.nodeId = data.node_id;
      artifactPreview.path = data.left.path;
      artifactPreview.content = data.left.content;
      artifactPreview.rightPath = data.right.path;
      artifactPreview.rightContent = data.right.content;
      artifactPreview.same = data.same;
      artifactPreview.truncated = data.truncated;
      artifactPreview.isMarkdown =
        looksLikeMarkdown(data.left.path) || looksLikeMarkdown(data.right.path);
      artifactPreviewOpen.value = true;
      compareOpen.value = false;
    } catch (e) {
      message.error(String(e));
    } finally {
      loading.value = false;
    }
  }

  async function cancelSelectedRun() {
    if (!selectedRun.value) return;
    Modal.confirm({
      title: '取消当前运行？',
      content: '将在当前节点等待结束后停止（交互 CLI / Warp 等待会立即中断）。',
      okType: 'danger',
      okText: '取消运行',
      onOk: async () => {
        try {
          const { run } = await workflowApi.cancelRun(selectedRun.value!.run_id);
          selectedRun.value = run;
          message.success('已发送取消请求');
          await loadRuns();
        } catch (e) {
          message.error(String(e));
        }
      },
    });
  }

  async function retrySelectedRun(
    fresh = false,
    opts: { resume_from_node?: string; single_node?: boolean } = {},
  ) {
    if (!selectedRun.value) return;
    const explain = selectedRun.value.explain;
    const doRetry = async () => {
      loading.value = true;
      try {
        const { run } = await workflowApi.retryRun(selectedRun.value!.run_id, fresh, {
          resume_from_node: opts.resume_from_node || '',
          single_node: opts.single_node,
        });
        selectedRun.value = run;
        message.success(fresh ? `已全新重跑: ${run.run_id}` : `已续跑/重试: ${run.run_id}`);
        await loadRuns();
        await loadTasks();
      } catch (e) {
        message.error(String(e));
      } finally {
        loading.value = false;
      }
    };
    if (fresh) {
      Modal.confirm({
        title: '全新重跑？',
        content: '将清空本次任务相关产物后重新执行，不可撤销。',
        okType: 'danger',
        okText: '全新重跑',
        onOk: doRetry,
      });
      return;
    }
    const stuck = opts.resume_from_node || explain?.stuck_node || '';
    const summary = (explain?.log_summary || explain?.last_logs || []).slice(-6);
    Modal.confirm({
      title: stuck ? `重试（卡在 ${stuck}）？` : '续跑/重试？',
      content: [
        stuck ? `将尽量从节点 ${stuck} 继续。` : '将按文档状态续跑（不删产物）。',
        summary.length ? `\n最近日志：\n${summary.join('\n')}` : '',
      ]
        .filter(Boolean)
        .join('\n'),
      okText: '重试',
      width: 560,
      onOk: doRetry,
    });
  }

  async function copyManualCommand() {
    const cmd = selectedRun.value?.explain?.manual_command || '';
    if (!cmd) {
      message.warning('暂无 Warp 手动命令');
      return;
    }
    try {
      await navigator.clipboard.writeText(cmd);
      message.success('已复制 Warp 手动命令');
    } catch {
      message.info(cmd);
    }
  }

  async function checkProjectHealth() {
    if (!selectedProjectId.value) return message.warning('请先选择项目');
    healthLoading.value = true;
    try {
      projectHealth.value = await workflowApi.getProjectHealth(selectedProjectId.value);
      message.success(projectHealth.value.summary);
    } catch (e) {
      message.error(String(e));
    } finally {
      healthLoading.value = false;
    }
  }

  async function fixProjectHealth() {
    if (!selectedProjectId.value) return;
    healthLoading.value = true;
    try {
      projectHealth.value = await workflowApi.fixProjectHealth(selectedProjectId.value);
      const actions = projectHealth.value.actions || [];
      message.success(
        actions.length
          ? `已修复 ${actions.length} 步：${projectHealth.value.summary}`
          : projectHealth.value.summary,
      );
    } catch (e) {
      message.error(String(e));
    } finally {
      healthLoading.value = false;
    }
  }

  async function loadTaskBoard() {
    if (!selectedProjectId.value) {
      taskBoard.value = null;
      return;
    }
    boardLoading.value = true;
    try {
      taskBoard.value = await workflowApi.getProjectBoard(selectedProjectId.value);
    } catch (e) {
      message.error(String(e));
    } finally {
      boardLoading.value = false;
    }
  }

  function toggleCompareRun(runId: string) {
    if (compareLeftId.value === runId) {
      compareLeftId.value = '';
      return;
    }
    if (compareRightId.value === runId) {
      compareRightId.value = '';
      return;
    }
    if (!compareLeftId.value) {
      compareLeftId.value = runId;
      return;
    }
    if (!compareRightId.value) {
      compareRightId.value = runId;
      return;
    }
    // 已选满两个：替换右侧
    compareRightId.value = runId;
  }

  function compareSelectionLabel(runId: string) {
    if (compareLeftId.value === runId) return 'A';
    if (compareRightId.value === runId) return 'B';
    return '';
  }

  async function openCompare() {
    if (!compareLeftId.value || !compareRightId.value) {
      message.warning('请先勾选两次执行（A / B）');
      return;
    }
    loading.value = true;
    try {
      compareResult.value = await workflowApi.compareRuns(
        compareLeftId.value,
        compareRightId.value,
      );
      compareOpen.value = true;
    } catch (e) {
      message.error(String(e));
    } finally {
      loading.value = false;
    }
  }

  function findLastSuccessRun(
    taskId: string,
    excludeRunId = '',
  ): WorkflowRun | null {
    if (!taskId) return null;
    return (
      projectRuns.value.find(
        (r) =>
          r.task_id === taskId &&
          r.status === 'completed' &&
          r.run_id !== excludeRunId,
      ) || null
    );
  }

  async function compareWithLastSuccess(runId?: string) {
    const current =
      (runId && runs.value.find((r) => r.run_id === runId)) || selectedRun.value;
    if (!current) {
      message.warning('请先选择一次执行');
      return;
    }
    const taskId = current.task_id || '';
    if (!taskId) {
      message.warning('当前 run 没有关联任务，无法找上次成功');
      return;
    }
    const prev = findLastSuccessRun(taskId, current.run_id);
    if (!prev) {
      message.warning('同任务没有更早的成功 run 可对比');
      return;
    }
    compareLeftId.value = current.run_id;
    compareRightId.value = prev.run_id;
    historyTaskFilter.value = taskId;
    await openCompare();
  }

  const heartbeatLabel = computed(() => {
    const run = selectedRun.value;
    if (!run || !['running', 'cancelling'].includes(run.status)) return '';
    const ms = run.heartbeat_elapsed_ms;
    if (ms != null && ms >= 0) {
      const sec = Math.round(ms / 1000);
      const node = run.current_node ? ` · ${run.current_node}` : '';
      return `已运行 ${sec}s${node}`;
    }
    if (run.last_heartbeat_at) {
      return `心跳 ${run.last_heartbeat_at}`;
    }
    return run.current_node ? `节点 ${run.current_node}` : '';
  });

  function playNotifyBeep() {
    try {
      const Ctx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext?: typeof AudioContext })
          .webkitAudioContext;
      if (!Ctx) return;
      const ctx = new Ctx();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.value = 880;
      gain.gain.value = 0.04;
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.18);
      window.setTimeout(() => ctx.close(), 400);
    } catch {
      // ignore
    }
  }

  async function ensureNotifyPermission(): Promise<boolean> {
    if (typeof Notification === 'undefined') return false;
    if (Notification.permission === 'granted') return true;
    if (Notification.permission === 'denied') return false;
    const result = await Notification.requestPermission();
    return result === 'granted';
  }

  function notifyRunTerminal(run: WorkflowRun) {
    if (!notifyEnabled.value) return;
    const key = `${run.run_id}:${run.status}`;
    if (lastNotifiedRunKey.value === key) return;
    lastNotifiedRunKey.value = key;
    playNotifyBeep();
    const title =
      run.status === 'completed'
        ? '任务完成'
        : run.status === 'failed'
          ? '任务失败'
          : isServerInterruptedRun(run)
            ? '任务中断（可续跑）'
            : '任务已取消';
    const body = `${run.requirement_name || run.run_id.slice(0, 8)} · ${statusLabel(run)}`;
    void (async () => {
      const ok = await ensureNotifyPermission();
      if (!ok || typeof Notification === 'undefined') return;
      try {
        const n = new Notification(title, {
          body,
          tag: `ai-loop-run-${run.run_id}`,
        });
        window.setTimeout(() => n.close(), 8000);
      } catch {
        // ignore
      }
    })();
  }

  function setNotifyEnabled(on: boolean) {
    notifyEnabled.value = on;
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('ai-loop:notify-terminal', on ? '1' : '0');
    }
    if (on) void ensureNotifyPermission();
  }

  watch(
    () => selectedRun.value?.status,
    (status, prev) => {
      const run = selectedRun.value;
      if (!run || !status) return;
      const fromActive = ['queued', 'running', 'cancelling'].includes(prev || '');
      const toTerminal = ['completed', 'failed', 'cancelled', 'interrupted'].includes(
        status,
      );
      if (fromActive && toTerminal) {
        notifyRunTerminal(run);
      }
    },
  );

  function applyRuleDirToProject(resolvedPath: string) {
    const hit = ruleSets.value.find((d) => d.resolved_path === resolvedPath);
    if (!hit) return;
    const root = projectForm.app_root.trim();
    if (root && hit.resolved_path.startsWith(root)) {
      projectForm.ai_rules_dir = hit.resolved_path
        .slice(root.length)
        .replace(/^[/\\]/, '');
    } else {
      projectForm.ai_rules_dir = hit.resolved_path;
    }
  }

  function onRuleDirPicked(path: string) {
    projectForm.ai_rules_dir = path;
    ruleDirPickerOpen.value = false;
  }

  async function refreshAll() {
    await Promise.all([loadProjects(), loadTasks(), loadRuns(), loadRuleSets()]);
    await Promise.all([loadTaskQaBadges(), loadTaskInsights(), loadTaskBoard()]);
    if (selectedProjectId.value) {
      try {
        projectHealth.value = await workflowApi.getProjectHealth(selectedProjectId.value);
      } catch {
        // ignore
      }
    }
  }

  async function loadSystemInfo() {
    try {
      const [info, config] = await Promise.all([
        workflowApi.getSystemInfo(),
        workflowApi.getSystemConfig(),
      ]);
      systemInfo.value = info;
      defaultTool.value = config.default_tool || 'omp';
    } catch {
      systemInfo.value = null;
    }
  }

  const runTimeline = computed(() => selectedRun.value?.timeline || []);

  onMounted(async () => {
    await Promise.all([loadSystemInfo(), loadNodes(), loadProjects(), loadRuleSets()]);
    if (selectedProjectId.value) connectRunEvents();
    // SSE 为主；慢轮询兜底 + 刷新 insights
    pollTimer = window.setInterval(async () => {
      await loadRuns();
      if (selectedTaskId.value) await loadTaskInsights();
    }, 15000);
  });

  onUnmounted(() => {
    if (pollTimer) window.clearInterval(pollTimer);
    disconnectRunEvents();
  });

  return {
    approveQa,
    artifactNodeOptions,
    artifactPreview,
    artifactPreviewOpen,
    boardLoading,
    canCancelSelected,
    openCompareDiff,
    openTimelineNode,
    switchPreviewNode,
    canRetrySelected,
    cancelSelectedRun,
    checkProjectHealth,
    cloneTask,
    copyManualCommand,
    defaultTool,
    exportSelectedRun,
    fixProjectHealth,
    highlightLogLine,
    highlightedNodeId,
    isTccSensitiveAppRoot,
    sseStatus,
    compareLeftId,
    compareOpen,
    compareResult,
    compareRightId,
    compareSelectionLabel,
    compareWithLastSuccess,
    currentStepIndex,
    deleteProject,
    deleteTask,
    editingProject,
    flags,
    form,
    heartbeatLabel,
    healthLoading,
    notifyEnabled,
    setNotifyEnabled,
    historyTaskFilter,
    historyTaskOptions,
    loadSidebarArtifact,
    loading,
    loadTaskBoard,
    loadTaskInsights,
    logActiveKeys,
    logFilter,
    logGroups,
    logKeyword,
    nodeStatuses,
    openArtifact,
    openCompare,
    previewArtifact,
    applyRuleDirToProject,
    onRuleDirPicked,
    onProjectImportFile,
    openProjectImportModal,
    openProjectModal,
    projectForm,
    projectHealth,
    projectImportForm,
    projectImportOpen,
    projectModalOpen,
    projectRuns,
    exportSelectedProject,
    submitProjectImport,
    projects,
    qaBadge,
    refreshAll,
    resumeFromNode,
    retrySelectedRun,
    runSingleNode,
    runTimeline,
    ruleDirOptions,
    ruleDirPickerOpen,
    ruleSets,
    runLogs,
    selectedProject,
    selectedProjectId,
    selectedRun,
    selectedTaskId,
    selectProject,
    selectRun,
    selectTask,
    sidebarNodeId,
    sidebarPreview,
    toggleCompareRun,
    viewRun,
    startRun,
    statusColor,
    statusLabel,
    isServerInterruptedRun,
    systemInfo,
    submitProject,
    submitTask,
    taskBoard,
    taskInsights,
    taskModalOpen,
    taskNameInput,
    taskRunStatus,
    tasks,
  };
}
