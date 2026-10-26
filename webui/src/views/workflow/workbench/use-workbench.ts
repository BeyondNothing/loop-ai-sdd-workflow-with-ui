import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue';

import { message, Modal } from 'ant-design-vue';

import {
  type ProjectBinding,
  type RuleDirCatalogItem,
  type SystemInfo,
  type TaskItem,
  type WorkflowNodeDef,
  type WorkflowRun,
  workflowApi,
} from '#/api/workflow';

export type NodeStatus = 'queued' | 'running' | 'completed' | 'failed' | 'skipped';

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
  });
  const editingProject = ref(false);

  const taskModalOpen = ref(false);
  const taskNameInput = ref('');
  const loading = ref(false);
  const systemInfo = ref<SystemInfo | null>(null);
  const ruleDirs = ref<RuleDirCatalogItem[]>([]);
  const ruleDirPickerOpen = ref(false);

  let pollTimer: number | undefined;

  const selectedProject = computed(() =>
    projects.value.find((p) => p.project_id === selectedProjectId.value),
  );

  const ruleDirOptions = computed(() =>
    ruleDirs.value.map((d) => ({
      label: `${d.ai_rules_dir} (${d.projects.length} 项)`,
      value: d.resolved_path,
      ai_rules_dir: d.ai_rules_dir,
    })),
  );

  const projectRuns = computed(() =>
    runs.value.filter((r) => r.project_id === selectedProjectId.value),
  );

  function statusColor(status: NodeStatus | string) {
    const map: Record<string, string> = {
      queued: 'default',
      running: 'processing',
      completed: 'success',
      failed: 'error',
      skipped: 'warning',
    };
    return map[status] || 'default';
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
      } else if (run?.status === 'failed') {
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

  const runLogs = computed(() => {
    const run = selectedRun.value;
    if (!run) return '';
    return (run.logs || []).slice(-50).join('\n') || '(暂无日志)';
  });

  async function loadNodes() {
    const data = await workflowApi.getNodes();
    nodes.value = data.nodes || [];
  }

  async function loadProjects() {
    const data = await workflowApi.getProjects();
    projects.value = data.projects || [];
    if (!selectedProjectId.value && projects.value.length) {
      await selectProject(projects.value[0]!.project_id);
    }
  }

  async function loadRuleDirs() {
    try {
      const data = await workflowApi.getRuleDirs();
      ruleDirs.value = data.rule_dirs || [];
    } catch {
      ruleDirs.value = [];
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

  async function loadRuns() {
    const data = await workflowApi.getRuns();
    runs.value = data.runs || [];
    syncSelectedRun();
  }

  function syncSelectedRun() {
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

  async function selectProject(projectId: string) {
    selectedProjectId.value = projectId;
    selectedTaskId.value = '';
    selectedRun.value = null;
    form.taskName = '';
    form.prdPath = '';
    form.requirement = '';
    await loadTasks();
    await loadRuns();
  }

  function selectTask(taskId: string) {
    selectedTaskId.value = taskId;
    const task = tasks.value.find((t) => t.task_id === taskId);
    if (!task) return;
    form.taskName = task.task_name;
    form.prdPath = task.requirement_prd_path;
    form.requirement = task.requirement_text;
    syncSelectedRun();
  }

  function selectRun(runId: string) {
    const hit = runs.value.find((r) => r.run_id === runId);
    if (hit) selectedRun.value = hit;
  }

  function openProjectModal(edit = false) {
    editingProject.value = edit;
    if (edit && selectedProject.value) {
      projectForm.name = selectedProject.value.name;
      projectForm.app_root = selectedProject.value.app_root;
      projectForm.docs_dir = selectedProject.value.docs_dir;
      projectForm.ai_rules_dir = selectedProject.value.ai_rules_dir;
    } else {
      projectForm.name = '';
      projectForm.app_root = '';
      projectForm.docs_dir = 'docs';
      projectForm.ai_rules_dir = 'ai-rules';
    }
    projectModalOpen.value = true;
  }

  async function submitProject() {
    const payload = { ...projectForm };
    try {
      if (editingProject.value && selectedProjectId.value) {
        await workflowApi.updateProject(selectedProjectId.value, payload);
      } else {
        const { project } = await workflowApi.createProject(payload);
        selectedProjectId.value = project.project_id;
      }
      projectModalOpen.value = false;
      await Promise.all([loadProjects(), loadRuleDirs()]);
      message.success('项目已保存');
    } catch (e) {
      message.error(String(e));
    }
  }

  async function deleteProject() {
    if (!selectedProjectId.value) return;
    Modal.confirm({
      title: '确认删除项目？',
      content: '关联任务不会被自动清理。',
      onOk: async () => {
        await workflowApi.deleteProject(selectedProjectId.value);
        selectedProjectId.value = '';
        await loadProjects();
        message.success('已删除');
      },
    });
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

  async function startRun() {
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
        tool: 'omp',
        skip_clarification: flags.skipClar,
        auto: flags.auto,
        headless_all_nodes: flags.headless,
        fresh: false,
        skip_mcp_setup: false,
      });
      selectedRun.value = run;
      message.success(`任务已启动: ${run.run_id}`);
      await loadRuns();
      await loadTasks();
    } catch (e) {
      message.error(String(e));
    } finally {
      loading.value = false;
    }
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

  function applyRuleDirToProject(resolvedPath: string) {
    const hit = ruleDirs.value.find((d) => d.resolved_path === resolvedPath);
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
    await Promise.all([loadProjects(), loadTasks(), loadRuns(), loadRuleDirs()]);
  }

  async function loadSystemInfo() {
    try {
      systemInfo.value = await workflowApi.getSystemInfo();
    } catch {
      systemInfo.value = null;
    }
  }

  onMounted(async () => {
    await Promise.all([loadSystemInfo(), loadNodes(), loadProjects(), loadRuleDirs()]);
    pollTimer = window.setInterval(loadRuns, 3000);
  });

  onUnmounted(() => {
    if (pollTimer) window.clearInterval(pollTimer);
  });

  watch(selectedTaskId, () => syncSelectedRun());

  return {
    currentStepIndex,
    deleteProject,
    deleteTask,
    editingProject,
    flags,
    form,
    loading,
    nodeStatuses,
    openArtifact,
    applyRuleDirToProject,
    onRuleDirPicked,
    openProjectModal,
    projectForm,
    projectModalOpen,
    projectRuns,
    projects,
    refreshAll,
    ruleDirOptions,
    ruleDirPickerOpen,
    runLogs,
    selectedProject,
    selectedProjectId,
    selectedRun,
    selectedTaskId,
    selectProject,
    selectRun,
    selectTask,
    startRun,
    statusColor,
    systemInfo,
    submitProject,
    submitTask,
    taskModalOpen,
    taskNameInput,
    taskRunStatus,
    tasks,
  };
}
