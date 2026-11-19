<script lang="ts" setup>
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Alert,
  Badge,
  Button,
  Card,
  Col,
  Collapse,
  Dropdown,
  Empty,
  Form,
  Input,
  Menu,
  Modal,
  Progress,
  Row,
  Select,
  Space,
  Switch,
  Table,
  Tabs,
  Tag,
  Timeline,
  Tooltip,
} from 'ant-design-vue';

import { renderMarkdown } from '#/utils/markdown';

import PathPickerModal from './PathPickerModal.vue';
import { useWorkbench } from './use-workbench';

const activeTab = ref('config');
const prdPickerOpen = ref(false);
const projectRootPickerOpen = ref(false);
const importRootPickerOpen = ref(false);

/** 历史表格：仅 body 滚动，分页钉在底部（不进外层滚动条） */
const historyTableWrapRef = ref<HTMLElement | null>(null);
const historyScrollY = ref(280);
let historyResizeObserver: ResizeObserver | null = null;

function updateHistoryScrollY() {
  const el = historyTableWrapRef.value;
  if (!el) return;
  // 预留分页条高度；表头由 Table scroll.y 机制放在可滚区域外
  const paginationReserve = 56;
  historyScrollY.value = Math.max(120, Math.floor(el.clientHeight - paginationReserve));
}

function bindHistoryResizeObserver() {
  if (typeof ResizeObserver === 'undefined') return;
  historyResizeObserver?.disconnect();
  historyResizeObserver = new ResizeObserver(() => updateHistoryScrollY());
  if (historyTableWrapRef.value) {
    historyResizeObserver.observe(historyTableWrapRef.value);
    updateHistoryScrollY();
  }
}

watch(activeTab, async (key) => {
  if (key !== 'history') return;
  await nextTick();
  bindHistoryResizeObserver();
});

onMounted(() => {
  if (activeTab.value === 'history') {
    bindHistoryResizeObserver();
  }
});

onBeforeUnmount(() => {
  historyResizeObserver?.disconnect();
  historyResizeObserver = null;
});

const {
  approveQa,
  applyRuleDirToProject,
  artifactNodeOptions,
  artifactPreview,
  artifactPreviewOpen,
  boardLoading,
  canCancelSelected,
  canRetrySelected,
  cancelSelectedRun,
  checkProjectHealth,
  cloneTask,
  compareLeftId,
  compareOpen,
  compareResult,
  compareRightId,
  compareSelectionLabel,
  compareWithLastSuccess,
  copyManualCommand,
  deleteProject,
  openCompareDiff,
  editingProject,
  exportSelectedProject,
  exportSelectedRun,
  fixProjectHealth,
  flags,
  form,
  heartbeatLabel,
  healthLoading,
  highlightLogLine,
  notifyEnabled,
  setNotifyEnabled,
  historyTaskFilter,
  historyTaskOptions,
  loading,
  loadSidebarArtifact,
  loadTaskBoard,
  onProjectImportFile,
  openProjectImportModal,
  projectImportForm,
  projectImportOpen,
  submitProjectImport,
  logActiveKeys,
  logFilter,
  logGroups,
  logKeyword,
  nodeStatuses,
  onRuleDirPicked,
  openArtifact,
  openCompare,
  openProjectModal,
  previewArtifact,
  projectForm,
  projectHealth,
  projectModalOpen,
  projectRuns,
  projects,
  qaBadge,
  refreshAll,
  resumeFromNode,
  retrySelectedRun,
  runSingleNode,
  runTimeline,
  openTimelineNode,
  highlightedNodeId,
  isTccSensitiveAppRoot,
  sseStatus,
  switchPreviewNode,
  ruleDirOptions,
  ruleDirPickerOpen,
  ruleSets,
  runLogs,
  selectedProject,
  selectedProjectId,
  selectedRun,
  selectedTaskId,
  selectProject,
  selectTask,
  sidebarNodeId,
  sidebarPreview,
  startRun,
  toggleCompareRun,
  viewRun,
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
} = useWorkbench();

const logFilterOptions = [
  { label: '全部', value: 'all' },
  { label: '错误', value: 'error' },
  { label: '节点进出', value: 'node' },
  { label: '取消', value: 'cancel' },
  { label: 'EPERM', value: 'eperm' },
  { label: '关键字', value: 'keyword' },
];

const confidencePercent = computed(() => {
  const score = taskInsights.value?.release_confidence?.score;
  if (score == null || Number.isNaN(score)) return 0;
  return Math.round(Math.min(1, Math.max(0, score)) * 100);
});

const confidenceColor = computed(() => {
  const reached = taskInsights.value?.release_confidence?.reached_0_8;
  if (reached === true) return '#52c41a';
  if (reached === false) return '#faad14';
  return '#1677ff';
});

function qaTagColor(status: string) {
  if (status === 'approved') return 'success';
  if (status === 'pending') return 'warning';
  if (status === 'missing') return 'default';
  return 'default';
}

function qaTagText(status: string) {
  if (status === 'approved') return 'QA✓';
  if (status === 'pending') return 'QA待审';
  if (status === 'missing') return '无用例';
  return '';
}

const nodeColumns = [
  { title: '#', dataIndex: 'index', width: 44, align: 'center' as const },
  { title: '节点', dataIndex: 'name', width: 140, ellipsis: true },
  { title: '标识', dataIndex: 'id', ellipsis: true },
  { title: '状态', dataIndex: 'status', width: 96 },
  { title: '产物', dataIndex: 'artifact', ellipsis: true },
  { title: '', dataIndex: 'action', width: 280 },
];

const boardBucketMeta: Array<{
  key: 'stuck' | 'awaiting' | 'ready' | 'running' | 'other';
  title: string;
  color: string;
}> = [
  { key: 'stuck', title: '卡住', color: 'error' },
  { key: 'awaiting', title: '待确认', color: 'warning' },
  { key: 'ready', title: '可发布', color: 'success' },
  { key: 'running', title: '运行中', color: 'processing' },
  { key: 'other', title: '其他', color: 'default' },
];

const nodeTableData = computed(() =>
  nodeStatuses.value.map((node, index) => ({
    key: node.id,
    index: index + 1,
    name: node.name,
    id: node.id,
    status: node.status,
    artifact: node.artifact || '—',
    hasArtifact: !!node.artifact,
    nodeId: node.id,
  })),
);

const runHistoryColumns = [
  { title: '对比', dataIndex: 'compare', width: 64 },
  { title: 'Run ID', dataIndex: 'run_id', ellipsis: true, width: 120 },
  { title: '任务', dataIndex: 'requirement_name', ellipsis: true },
  { title: '状态', dataIndex: 'status', width: 96 },
  { title: 'Auto', dataIndex: 'auto', width: 64 },
  { title: '', dataIndex: 'action', width: 120 },
];

const compareColumns = [
  { title: '节点', dataIndex: 'node_id' },
  { title: 'A', dataIndex: 'left_has', width: 72 },
  { title: 'B', dataIndex: 'right_has', width: 72 },
  { title: '内容', dataIndex: 'same_content', width: 96 },
  { title: 'A 字数', dataIndex: 'left_chars', width: 88 },
  { title: 'B 字数', dataIndex: 'right_chars', width: 88 },
];

const completedCount = computed(
  () => nodeStatuses.value.filter((n) => n.status === 'completed').length,
);

const prdPickerInitial = computed(() => {
  if (form.prdPath) {
    const idx = form.prdPath.lastIndexOf('/');
    return idx > 0 ? form.prdPath.slice(0, idx) : form.prdPath;
  }
  const root = selectedProject.value?.app_root || '';
  const docs = selectedProject.value?.docs_dir || 'docs';
  return root ? `${root}/${docs}` : root;
});

function onPrdPicked(path: string) {
  const root = selectedProject.value?.app_root || '';
  form.prdPath =
    root && path.startsWith(root) ? path.slice(root.length).replace(/^\//, '') : path;
}

function onProjectRootPicked(path: string) {
  projectForm.app_root = path;
}

async function onViewRun(runId: string) {
  const ok = await viewRun(runId);
  if (ok) activeTab.value = 'logs';
}
</script>

<template>
  <Page auto-content-height content-class="p-0">
    <div class="flex h-full min-h-0">
      <!-- 左侧：项目 / 任务导航 -->
      <aside
        class="nav-panel flex w-[240px] shrink-0 flex-col border-r border-border bg-sidebar/50"
      >
        <!-- 项目 -->
        <div class="nav-section border-b border-border px-2 py-2">
          <div class="mb-1.5 flex items-center justify-between px-1">
            <span class="nav-section__title">
              <IconifyIcon icon="lucide:folder" class="mr-1 inline opacity-50" />
              项目
            </span>
            <Space :size="2">
              <Tooltip title="新建">
                <Button size="small" type="text" @click="openProjectModal(false)">
                  <IconifyIcon icon="lucide:plus" class="size-3.5" />
                </Button>
              </Tooltip>
              <Tooltip title="导入整包">
                <Button size="small" type="text" @click="openProjectImportModal">
                  <IconifyIcon icon="lucide:upload" class="size-3.5" />
                </Button>
              </Tooltip>
              <Tooltip
                :title="
                  projectImportForm.include_runs_export
                    ? '导出整包（含 runs）'
                    : '导出整包（不含 runs，体积更小）'
                "
              >
                <Button
                  :disabled="!selectedProjectId"
                  :loading="loading"
                  size="small"
                  type="text"
                  @click="exportSelectedProject"
                >
                  <IconifyIcon icon="lucide:download" class="size-3.5" />
                </Button>
              </Tooltip>
              <Tooltip title="导出时是否包含 runs">
                <Switch
                  v-model:checked="projectImportForm.include_runs_export"
                  :disabled="!selectedProjectId"
                  size="small"
                />
              </Tooltip>
              <Tooltip title="编辑">
                <Button
                  :disabled="!selectedProjectId"
                  size="small"
                  type="text"
                  @click="openProjectModal(true)"
                >
                  <IconifyIcon icon="lucide:pencil" class="size-3.5" />
                </Button>
              </Tooltip>
              <Tooltip title="删除">
                <Button
                  :disabled="!selectedProjectId"
                  danger
                  size="small"
                  type="text"
                  @click="deleteProject"
                >
                  <IconifyIcon icon="lucide:trash-2" class="size-3.5" />
                </Button>
              </Tooltip>
            </Space>
          </div>
          <div class="max-h-[140px] overflow-y-auto">
            <div
              v-for="p in projects"
              :key="p.project_id"
              :class="
                p.project_id === selectedProjectId
                  ? 'nav-item--active'
                  : 'hover:bg-muted/40'
              "
              class="nav-item cursor-pointer rounded px-2 py-1.5 transition-colors"
              @click="selectProject(p.project_id)"
            >
              <Tooltip :title="`${p.app_root}\n规则: ${p.ai_rules_dir}`" placement="right">
                <div class="truncate text-sm font-medium">{{ p.name }}</div>
                <div class="truncate text-[11px] opacity-40">{{ p.ai_rules_dir }}</div>
              </Tooltip>
            </div>
            <Empty
              v-if="!projects.length"
              :image-style="{ height: 32 }"
              class="my-2"
              description="暂无项目"
            />
          </div>
        </div>

        <!-- 任务 -->
        <div class="nav-section flex min-h-0 flex-1 flex-col px-2 py-2">
          <div class="mb-1.5 flex items-center justify-between px-1">
            <span class="nav-section__title">
              <IconifyIcon icon="lucide:list-todo" class="mr-1 inline opacity-50" />
              任务
            </span>
            <Space :size="2">
              <Tooltip title="新建">
                <Button
                  :disabled="!selectedProjectId"
                  size="small"
                  type="text"
                  @click="taskModalOpen = true"
                >
                  <IconifyIcon icon="lucide:plus" class="size-3.5" />
                </Button>
              </Tooltip>
              <Tooltip title="克隆当前任务">
                <Button
                  :disabled="!selectedTaskId"
                  :loading="loading"
                  size="small"
                  type="text"
                  @click="selectedTaskId && cloneTask(selectedTaskId)"
                >
                  <IconifyIcon icon="lucide:copy" class="size-3.5" />
                </Button>
              </Tooltip>
              <Tooltip title="刷新">
                <Button size="small" type="text" @click="refreshAll">
                  <IconifyIcon icon="lucide:refresh-cw" class="size-3.5" />
                </Button>
              </Tooltip>
            </Space>
          </div>
          <div class="min-h-0 flex-1 overflow-y-auto">
            <div
              v-for="t in tasks"
              :key="t.task_id"
              :class="
                t.task_id === selectedTaskId ? 'nav-item--active' : 'hover:bg-muted/40'
              "
              class="nav-item flex cursor-pointer items-center justify-between gap-1 rounded px-2 py-1.5 text-sm transition-colors"
              @click="selectTask(t.task_id)"
            >
              <span class="min-w-0 truncate">{{ t.task_name }}</span>
              <div class="flex shrink-0 items-center gap-1">
                <Tag
                  v-if="qaTagText(qaBadge(t.task_id))"
                  :color="qaTagColor(qaBadge(t.task_id))"
                  class="m-0 px-1 text-[10px] leading-4"
                >
                  {{ qaTagText(qaBadge(t.task_id)) }}
                </Tag>
                <Badge
                  v-if="taskRunStatus(t)"
                  :status="
                    taskRunStatus(t) === 'running'
                      ? 'processing'
                      : taskRunStatus(t) === 'completed'
                        ? 'success'
                        : taskRunStatus(t) === 'failed'
                          ? 'error'
                          : 'default'
                  "
                />
              </div>
            </div>
            <Empty
              v-if="!tasks.length"
              :description="selectedProjectId ? '暂无任务' : '先选项目'"
              :image-style="{ height: 32 }"
              class="my-2"
            />
          </div>
        </div>
      </aside>

      <!-- 右侧：状态栏 + Tab 内容（min-h-0 保证子级可滚，不被裁切） -->
      <div class="flex min-h-0 min-w-0 flex-1 flex-col">
        <header
          class="flex shrink-0 items-center gap-3 border-b border-border px-4 py-2"
        >
          <template v-if="selectedProject">
            <span class="text-sm font-medium">{{ selectedProject.name }}</span>
            <span v-if="form.taskName" class="text-sm opacity-50">
              / {{ form.taskName }}
            </span>
          </template>
          <span v-else class="text-sm opacity-40">请选择项目和任务</span>

          <Tag v-if="systemInfo" class="m-0 ml-2" color="blue">
            {{ systemInfo.os_name }}
          </Tag>

          <div v-if="selectedRun" class="ml-2 flex items-center gap-2 text-xs">
            <Tag
              :color="
                isServerInterruptedRun(selectedRun)
                  ? 'warning'
                  : statusColor(selectedRun.status)
              "
              class="m-0"
            >
              {{ statusLabel(selectedRun) }}
            </Tag>
            <span class="opacity-50">
              节点 {{ completedCount }}/{{ nodeStatuses.length }}
            </span>
            <span v-if="heartbeatLabel" class="opacity-55">
              {{ heartbeatLabel }}
            </span>
          </div>
          <Tag
            v-if="sseStatus === 'connected'"
            class="m-0 ml-2"
            color="success"
          >
            实时
          </Tag>
          <Tag
            v-else-if="sseStatus === 'reconnecting'"
            class="m-0 ml-2"
            color="warning"
          >
            实时中断·轮询兜底
          </Tag>

          <Space class="ml-auto" :size="4">
            <Tooltip title="中断当前运行（含交互等待）">
              <Button
                :disabled="!canCancelSelected"
                danger
                size="small"
                @click="cancelSelectedRun"
              >
                取消
              </Button>
            </Tooltip>
            <Tooltip title="按文档续跑（不删产物）">
              <Button
                :disabled="!canRetrySelected"
                :loading="loading"
                size="small"
                @click="retrySelectedRun(false)"
              >
                重试
              </Button>
            </Tooltip>
            <Tooltip title="清空产物后全新重跑">
              <Button
                :disabled="!canRetrySelected"
                :loading="loading"
                size="small"
                @click="retrySelectedRun(true)"
              >
                全新重跑
              </Button>
            </Tooltip>
            <Tooltip :title="notifyEnabled ? '终态通知已开' : '终态通知已关'">
              <Button size="small" @click="setNotifyEnabled(!notifyEnabled)">
                {{ notifyEnabled ? '通知开' : '通知关' }}
              </Button>
            </Tooltip>
            <Tooltip title="导出当前 Run（日志/时间线/产物）">
              <Button
                :disabled="!selectedRun"
                :loading="loading"
                size="small"
                @click="exportSelectedRun"
              >
                导出
              </Button>
            </Tooltip>
            <Tooltip title="项目健康检查">
              <Button
                :disabled="!selectedProjectId"
                :loading="healthLoading"
                size="small"
                @click="checkProjectHealth"
              >
                健康
              </Button>
            </Tooltip>
            <Dropdown>
              <Button size="small" type="text">
                <IconifyIcon icon="lucide:more-horizontal" />
              </Button>
              <template #overlay>
                <Menu>
                  <Menu.Item @click="refreshAll">刷新数据</Menu.Item>
                  <Menu.Item
                    :disabled="!selectedProjectId"
                    @click="fixProjectHealth"
                  >
                    一键修复项目
                  </Menu.Item>
                  <Menu.Item
                    :disabled="!selectedTaskId"
                    @click="selectedTaskId && cloneTask(selectedTaskId)"
                  >
                    克隆当前任务
                  </Menu.Item>
                </Menu>
              </template>
            </Dropdown>
          </Space>
        </header>

        <div class="flex min-h-0 flex-1 flex-col overflow-hidden px-4 pb-3 pt-2">
          <Alert
            v-if="selectedRun?.explain?.manual_command"
            class="mb-2 shrink-0"
            show-icon
            type="info"
          >
            <template #message>
              <div class="flex flex-wrap items-center gap-2">
                <span>Warp 手动命令（自动注入失败时复制执行）</span>
                <Button size="small" type="primary" @click="copyManualCommand">
                  复制命令
                </Button>
                <Button size="small" @click="activeTab = 'logs'">看日志</Button>
              </div>
            </template>
            <template #description>
              <code class="break-all text-[11px]">{{
                selectedRun.explain.manual_command
              }}</code>
            </template>
          </Alert>
          <Alert
            v-if="projectHealth && projectHealth.fixable_count > 0"
            class="mb-2 shrink-0"
            show-icon
            type="warning"
          >
            <template #message>
              <div class="flex flex-wrap items-center gap-2">
                <span>{{ projectHealth.summary }}</span>
                <Button
                  :loading="healthLoading"
                  size="small"
                  type="primary"
                  @click="fixProjectHealth"
                >
                  一键修复
                </Button>
              </div>
            </template>
            <template #description>
              <ul class="m-0 list-disc pl-4 text-xs opacity-80">
                <li
                  v-for="c in projectHealth.checks.filter((x) => !x.ok)"
                  :key="c.key"
                >
                  {{ c.message }}
                </li>
              </ul>
            </template>
          </Alert>
          <Alert
            v-if="
              selectedRun &&
              ['failed', 'cancelled', 'interrupted'].includes(selectedRun.status) &&
              selectedRun.explain
            "
            class="mb-2 shrink-0"
            :type="selectedRun.status === 'failed' ? 'error' : 'warning'"
            show-icon
          >
            <template #message>
              <div class="flex flex-wrap items-center gap-2">
                <span>
                  {{
                    selectedRun.status === 'failed'
                      ? '执行失败'
                      : isServerInterruptedRun(selectedRun)
                        ? '服务中断（非手动取消，可续跑）'
                        : '已取消'
                  }}
                  <template v-if="selectedRun.explain?.stuck_node">
                    · 卡在节点
                    <code>{{ selectedRun.explain.stuck_node }}</code>
                  </template>
                </span>
                <Button
                  v-if="selectedRun.explain?.can_retry"
                  size="small"
                  type="primary"
                  @click="retrySelectedRun(false)"
                >
                  {{ isServerInterruptedRun(selectedRun) ? '一键续跑' : '一键重试' }}
                </Button>
                <Button size="small" @click="activeTab = 'logs'">看日志</Button>
              </div>
            </template>
            <template #description>
              <div v-if="selectedRun.explain?.error" class="mb-1 text-xs">
                {{ selectedRun.explain.error }}
              </div>
              <div
                v-if="selectedRun.explain?.permission_hint"
                class="mb-1 text-xs text-amber-700 dark:text-amber-300"
              >
                {{ selectedRun.explain.permission_hint }}
              </div>
              <pre
                v-if="
                  (selectedRun.explain?.log_summary || selectedRun.explain?.last_logs)
                    ?.length
                "
                class="m-0 max-h-28 overflow-auto whitespace-pre-wrap font-mono text-[11px] opacity-80"
              >{{
                (
                  selectedRun.explain?.log_summary ||
                  selectedRun.explain?.last_logs ||
                  []
                ).join('\n')
              }}</pre>
            </template>
          </Alert>
          <Tabs
            v-model:active-key="activeTab"
            class="workbench-tabs min-h-0 flex-1 overflow-hidden"
            size="small"
          >
            <Tabs.TabPane key="config" tab="任务配置">
              <div v-if="selectedTaskId" class="config-panel">
                <Form layout="vertical" size="middle" class="config-form">
                  <!-- 基本信息 -->
                  <Card class="config-card" size="small" title="基本信息">
                    <Row :gutter="20">
                      <Col :lg="8" :md="10" :span="24">
                        <Form.Item label="任务名称" class="mb-0">
                          <Input
                            v-model:value="form.taskName"
                            placeholder="任务标识名"
                          />
                        </Form.Item>
                      </Col>
                      <Col :lg="16" :md="14" :span="24">
                        <Form.Item label="PRD 路径" class="mb-0">
                          <Input
                            v-model:value="form.prdPath"
                            placeholder="相对路径或绝对路径"
                          >
                            <template #suffix>
                              <Tooltip title="浏览选择文件">
                                <Button
                                  size="small"
                                  type="text"
                                  @click="prdPickerOpen = true"
                                >
                                  <IconifyIcon icon="lucide:folder-open" />
                                </Button>
                              </Tooltip>
                            </template>
                          </Input>
                        </Form.Item>
                      </Col>
                    </Row>
                  </Card>

                  <!-- 运行选项 -->
                  <Card class="config-card" size="small" title="运行选项">
                    <template #extra>
                      <span class="text-xs opacity-40">按项目自动记住</span>
                    </template>
                    <div class="option-grid">
                      <div
                        :class="{ 'option-card--on': flags.headless }"
                        class="option-card"
                        @click="flags.headless = !flags.headless"
                      >
                        <Switch v-model:checked="flags.headless" size="small" @click.stop />
                        <div>
                          <div class="option-card__title">无界面</div>
                          <div class="option-card__desc">Headless 模式运行节点</div>
                        </div>
                      </div>
                      <div
                        :class="{ 'option-card--on': flags.skipClar }"
                        class="option-card"
                        @click="flags.skipClar = !flags.skipClar"
                      >
                        <Switch v-model:checked="flags.skipClar" size="small" @click.stop />
                        <div>
                          <div class="option-card__title">跳过澄清</div>
                          <div class="option-card__desc">跳过需求澄清环节</div>
                        </div>
                      </div>
                      <div
                        :class="{ 'option-card--on': flags.auto }"
                        class="option-card"
                        @click="flags.auto = !flags.auto"
                      >
                        <Switch v-model:checked="flags.auto" size="small" @click.stop />
                        <div>
                          <div class="option-card__title">无人值守</div>
                          <div class="option-card__desc">
                            使用 *.auto.md，门禁与推荐强度达标后自动继续
                          </div>
                        </div>
                      </div>
                    </div>
                  </Card>

                  <!-- 需求文本 -->
                  <Card
                    class="config-card config-card--grow"
                    size="small"
                    title="需求文本"
                  >
                    <template #extra>
                      <span class="text-xs opacity-40">PRD 为空时使用</span>
                    </template>
                    <Input.TextArea
                      v-model:value="form.requirement"
                      class="requirement-textarea"
                      placeholder="在此粘贴需求摘要、用户故事或补充说明…"
                    />
                  </Card>
                </Form>

                <!-- 底栏操作 -->
                <div class="config-footer">
                  <span class="text-xs opacity-40">
                    {{ systemInfo?.os_name || '—' }} · 就绪
                  </span>
                  <Button :loading="loading" size="large" type="primary" @click="startRun">
                    <IconifyIcon class="mr-1.5" icon="lucide:play" />
                    执行任务
                  </Button>
                </div>
              </div>
              <Empty v-else description="请从左侧选择任务" />
            </Tabs.TabPane>

            <Tabs.TabPane key="pipeline" tab="流水线">
              <div
                class="pipeline-panel grid h-full min-h-0 gap-3 overflow-hidden lg:grid-cols-[minmax(0,1fr)_minmax(280px,36%)]"
              >
                <div class="flex min-h-0 min-w-0 flex-col gap-3 overflow-y-auto pr-1">
                <Card
                  v-if="selectedTaskId"
                  class="shrink-0"
                  size="small"
                  title="质量洞察"
                >
                  <div class="grid gap-4 md:grid-cols-[160px_1fr]">
                    <div class="flex flex-col items-center justify-center gap-1">
                      <Progress
                        :percent="confidencePercent"
                        :stroke-color="confidenceColor"
                        type="dashboard"
                        :width="108"
                      />
                      <div class="text-xs opacity-50">发布置信度</div>
                      <Tag
                        v-if="taskInsights?.release_confidence?.reached_0_8 != null"
                        :color="
                          taskInsights.release_confidence.reached_0_8 ? 'success' : 'warning'
                        "
                        class="m-0"
                      >
                        {{
                          taskInsights.release_confidence.reached_0_8
                            ? '已达 0.8'
                            : '未达 0.8'
                        }}
                      </Tag>
                      <span
                        v-else-if="!taskInsights?.release_confidence?.has_report"
                        class="text-xs opacity-40"
                      >
                        尚无 05-test-report
                      </span>
                    </div>
                    <div class="min-w-0 space-y-2">
                      <div class="flex flex-wrap items-center gap-2">
                        <span class="text-xs opacity-50">用例 QA（异步，不阻塞）</span>
                        <Tag
                          :color="qaTagColor(taskInsights?.qa_review?.status || '')"
                          class="m-0"
                        >
                          {{
                            qaTagText(taskInsights?.qa_review?.status || '') ||
                            '未检测'
                          }}
                        </Tag>
                        <Button
                          v-if="taskInsights?.qa_review?.status === 'pending'"
                          :loading="loading"
                          size="small"
                          type="primary"
                          @click="approveQa('approved')"
                        >
                          标记通过
                        </Button>
                        <Button
                          v-if="taskInsights?.qa_review?.status === 'approved'"
                          :loading="loading"
                          size="small"
                          @click="approveQa('pending')"
                        >
                          重置待审
                        </Button>
                      </div>
                      <div class="flex flex-wrap gap-2 text-xs">
                        <Tag class="m-0">
                          pass {{ taskInsights?.release_confidence?.result_rows?.pass || 0 }}
                        </Tag>
                        <Tag class="m-0">
                          fail {{ taskInsights?.release_confidence?.result_rows?.fail || 0 }}
                        </Tag>
                        <Tag class="m-0">
                          skip {{ taskInsights?.release_confidence?.result_rows?.skip || 0 }}
                        </Tag>
                        <Tag
                          v-if="taskInsights?.release_confidence?.test_passed != null"
                          :color="
                            taskInsights.release_confidence.test_passed
                              ? 'success'
                              : 'error'
                          "
                          class="m-0"
                        >
                          test_passed=
                          {{ taskInsights.release_confidence.test_passed ? 'true' : 'false' }}
                        </Tag>
                      </div>
                      <ul
                        v-if="taskInsights?.release_confidence?.highlights?.length"
                        class="m-0 list-disc pl-4 text-xs opacity-70"
                      >
                        <li
                          v-for="(line, idx) in taskInsights.release_confidence.highlights"
                          :key="idx"
                        >
                          {{ line }}
                        </li>
                      </ul>
                      <div v-else class="text-xs opacity-40">
                        解析自任务 docs 下的 02-test-cases / 05-test-report
                      </div>
                    </div>
                  </div>
                </Card>

                <Card
                  v-if="runTimeline.length"
                  size="small"
                  class="shrink-0"
                  title="运行时间线"
                >
                  <Timeline class="run-timeline px-1">
                    <Timeline.Item
                      v-for="(ev, idx) in runTimeline"
                      :key="`${ev.at}-${ev.node_id}-${ev.event}-${idx}`"
                      :color="
                        ev.event === 'enter'
                          ? 'blue'
                          : ev.event === 'resume'
                            ? 'orange'
                            : ev.success === false
                              ? 'red'
                              : 'green'
                      "
                    >
                      <div class="flex flex-wrap items-baseline gap-2 text-xs">
                        <span class="font-medium">{{ ev.node_id || '—' }}</span>
                        <Tag
                          :color="
                            ev.event === 'enter'
                              ? 'processing'
                              : ev.event === 'resume'
                                ? 'warning'
                                : 'default'
                          "
                          class="m-0 cursor-pointer"
                          title="预览产物；若无产物则定位到节点表"
                          @click="
                            async () => {
                              if (!ev.node_id) return;
                              activeTab = 'pipeline';
                              await openTimelineNode(ev.node_id);
                            }
                          "
                        >
                          {{
                            ev.event === 'enter'
                              ? '进入'
                              : ev.event === 'resume'
                                ? '续跑'
                                : '离开'
                          }}
                        </Tag>
                        <span
                          v-if="ev.duration_ms != null"
                          class="opacity-55"
                        >
                          {{ (ev.duration_ms / 1000).toFixed(1) }}s
                        </span>
                        <span class="opacity-40">{{ ev.at }}</span>
                      </div>
                    </Timeline.Item>
                  </Timeline>
                </Card>

                <Table
                  :columns="nodeColumns"
                  :custom-row="
                    (record) => ({
                      'data-node-id': record.nodeId,
                      class:
                        record.nodeId === highlightedNodeId ? 'node-row--hl' : undefined,
                    })
                  "
                  :data-source="nodeTableData"
                  :pagination="false"
                  class="min-h-0 shrink-0"
                  row-key="key"
                  size="small"
                >
                  <template #bodyCell="{ column, record }">
                    <template v-if="column.dataIndex === 'status'">
                      <Tag :color="statusColor(record.status)" class="m-0">
                        {{ record.status }}
                      </Tag>
                    </template>
                    <template v-else-if="column.dataIndex === 'action'">
                      <Space :size="0" wrap>
                        <Button
                          v-if="record.hasArtifact"
                          size="small"
                          type="link"
                          @click="loadSidebarArtifact(record.nodeId)"
                        >
                          侧栏
                        </Button>
                        <Button
                          v-if="record.hasArtifact"
                          size="small"
                          type="link"
                          @click="previewArtifact(record.nodeId, { modal: true })"
                        >
                          弹窗
                        </Button>
                        <Button
                          v-if="record.hasArtifact"
                          size="small"
                          type="link"
                          @click="openArtifact(record.nodeId)"
                        >
                          打开
                        </Button>
                        <Button
                          :disabled="!selectedTaskId || canCancelSelected"
                          size="small"
                          type="link"
                          @click="resumeFromNode(record.nodeId)"
                        >
                          从此续跑
                        </Button>
                        <Button
                          :disabled="!selectedTaskId || canCancelSelected"
                          size="small"
                          type="link"
                          @click="runSingleNode(record.nodeId)"
                        >
                          只跑一步
                        </Button>
                      </Space>
                    </template>
                  </template>
                  <template #emptyText>
                    <Empty description="执行工作流后显示节点状态" />
                  </template>
                </Table>
                </div>

                <Card
                  class="artifact-sidebar flex min-h-0 flex-col overflow-hidden"
                  size="small"
                >
                  <template #title>
                    <span>产物速览</span>
                    <Tag v-if="sidebarPreview.nodeId" class="ml-2 m-0" color="blue">
                      {{ sidebarPreview.nodeId }}
                    </Tag>
                  </template>
                  <template #extra>
                    <Space :size="4">
                      <Select
                        :disabled="!artifactNodeOptions.length"
                        :options="artifactNodeOptions"
                        :value="sidebarNodeId || undefined"
                        allow-clear
                        class="w-[140px]"
                        placeholder="选节点"
                        size="small"
                        @change="
                          (v) => v && loadSidebarArtifact(String(v))
                        "
                      />
                      <Button
                        :disabled="!sidebarPreview.content"
                        size="small"
                        type="link"
                        @click="
                          sidebarPreview.nodeId &&
                            previewArtifact(sidebarPreview.nodeId, { modal: true })
                        "
                      >
                        放大
                      </Button>
                    </Space>
                  </template>
                  <div class="flex min-h-0 flex-1 flex-col overflow-hidden">
                    <div
                      v-if="sidebarPreview.path"
                      class="mb-1 truncate text-[11px] opacity-45"
                      :title="sidebarPreview.path"
                    >
                      {{ sidebarPreview.path }}
                    </div>
                    <Tag
                      v-if="sidebarPreview.truncated"
                      class="mb-1 w-fit"
                      color="warning"
                    >
                      已截断
                    </Tag>
                    <div
                      v-if="sidebarPreview.loading"
                      class="py-8 text-center text-xs opacity-50"
                    >
                      加载中…
                    </div>
                    <div
                      v-else-if="sidebarPreview.error"
                      class="text-xs text-destructive"
                    >
                      {{ sidebarPreview.error }}
                    </div>
                    <div
                      v-else-if="sidebarPreview.content && sidebarPreview.isMarkdown"
                      class="artifact-md min-h-0 flex-1 overflow-auto text-sm"
                      v-html="renderMarkdown(sidebarPreview.content)"
                    ></div>
                    <pre
                      v-else-if="sidebarPreview.content"
                      class="m-0 min-h-0 flex-1 overflow-auto whitespace-pre-wrap font-mono text-[11px]"
                    >{{ sidebarPreview.content }}</pre>
                    <Empty
                      v-else
                      class="my-6"
                      description="点「侧栏」或时间线节点预览"
                      :image-style="{ height: 40 }"
                    />
                  </div>
                </Card>
              </div>
            </Tabs.TabPane>

            <Tabs.TabPane key="board" tab="优先级看板">
              <div class="flex h-full min-h-0 flex-col gap-3 overflow-y-auto pr-1">
                <div class="flex flex-wrap items-center gap-2">
                  <Button
                    :disabled="!selectedProjectId"
                    :loading="boardLoading"
                    size="small"
                    @click="loadTaskBoard"
                  >
                    刷新看板
                  </Button>
                  <span class="text-xs opacity-45">
                    卡住 / 待确认 / 可发布 / 运行中（当前项目）
                  </span>
                </div>
                <Empty
                  v-if="!taskBoard"
                  description="选择项目后刷新看板"
                />
                <div
                  v-else
                  class="grid gap-3 md:grid-cols-2 xl:grid-cols-3"
                >
                  <Card
                    v-for="bucket in boardBucketMeta"
                    :key="bucket.key"
                    size="small"
                    :title="`${bucket.title} (${taskBoard.counts[bucket.key] || 0})`"
                  >
                    <div
                      v-if="!(taskBoard.buckets[bucket.key] || []).length"
                      class="text-xs opacity-40"
                    >
                      暂无
                    </div>
                    <div
                      v-for="item in taskBoard.buckets[bucket.key] || []"
                      :key="item.task_id"
                      class="mb-2 cursor-pointer rounded border border-border/40 px-2 py-1.5 hover:bg-muted/30"
                      @click="selectTask(item.task_id)"
                    >
                      <div class="flex items-center justify-between gap-2">
                        <span class="truncate text-sm font-medium">{{
                          item.task_name
                        }}</span>
                        <Tag :color="statusColor(item.run_status || 'queued')" class="m-0">
                          {{ item.run_status || '—' }}
                        </Tag>
                      </div>
                      <div class="mt-1 truncate text-[11px] opacity-50">
                        <template v-if="item.stuck_node">
                          卡在 {{ item.stuck_node }} ·
                        </template>
                        QA {{ item.qa_status || '—' }}
                        <template v-if="item.confidence != null">
                          · 置信 {{ Number(item.confidence).toFixed(2) }}
                        </template>
                      </div>
                    </div>
                  </Card>
                </div>
              </div>
            </Tabs.TabPane>

            <Tabs.TabPane key="history" tab="执行历史">
              <div class="history-panel">
                <div class="mb-2 flex shrink-0 flex-wrap items-center gap-2">
                  <Select
                    v-model:value="historyTaskFilter"
                    :options="historyTaskOptions"
                    allow-clear
                    class="w-[220px]"
                    placeholder="按任务筛选"
                    size="small"
                  />
                  <Button
                    :disabled="!compareLeftId || !compareRightId"
                    :loading="loading"
                    size="small"
                    type="primary"
                    @click="openCompare"
                  >
                    对比 A/B
                  </Button>
                  <Button
                    :disabled="!selectedRun"
                    :loading="loading"
                    size="small"
                    @click="compareWithLastSuccess()"
                  >
                    对比上次成功
                  </Button>
                  <span class="text-xs opacity-45">
                    点「选」勾 A/B，或一键对比当前 vs 同任务上次成功
                  </span>
                </div>
                <div ref="historyTableWrapRef" class="history-table-wrap min-h-0 flex-1">
                  <Table
                    :columns="runHistoryColumns"
                    :data-source="projectRuns"
                    :pagination="{
                      pageSize: 12,
                      size: 'small',
                      showSizeChanger: false,
                      position: ['bottomRight'],
                    }"
                    :scroll="{ y: historyScrollY, x: 'max-content' }"
                    row-key="run_id"
                    size="small"
                  >
                    <template #bodyCell="{ column, record }">
                      <template v-if="column.dataIndex === 'compare'">
                        <Button
                          size="small"
                          :type="compareSelectionLabel(record.run_id) ? 'primary' : 'default'"
                          @click.stop="toggleCompareRun(record.run_id)"
                        >
                          {{ compareSelectionLabel(record.run_id) || '选' }}
                        </Button>
                      </template>
                      <template v-else-if="column.dataIndex === 'status'">
                        <Tag
                          :color="
                            isServerInterruptedRun(record)
                              ? 'warning'
                              : statusColor(record.status)
                          "
                          class="m-0"
                        >
                          {{ statusLabel(record) }}
                        </Tag>
                      </template>
                      <template v-else-if="column.dataIndex === 'auto'">
                        {{ record.auto ? '是' : '否' }}
                      </template>
                      <template v-else-if="column.dataIndex === 'action'">
                        <Space :size="0">
                          <Button
                            size="small"
                            type="link"
                            @click.stop="onViewRun(record.run_id)"
                          >
                            查看
                          </Button>
                          <Button
                            size="small"
                            type="link"
                            @click.stop="
                              async () => {
                                await onViewRun(record.run_id);
                                await exportSelectedRun();
                              }
                            "
                          >
                            导出
                          </Button>
                        </Space>
                      </template>
                    </template>
                    <template #emptyText>
                      <Empty description="暂无执行记录" />
                    </template>
                  </Table>
                </div>
              </div>
            </Tabs.TabPane>

            <Tabs.TabPane key="logs" tab="日志">
              <div class="flex h-full min-h-0 flex-col gap-2 pt-1">
                <div class="flex shrink-0 flex-wrap items-center gap-2">
                  <Select
                    v-model:value="logFilter"
                    :options="logFilterOptions"
                    class="w-[120px]"
                    size="small"
                  />
                  <Input
                    v-if="logFilter === 'keyword'"
                    v-model:value="logKeyword"
                    allow-clear
                    class="w-[200px]"
                    placeholder="关键字"
                    size="small"
                  />
                  <Button
                    size="small"
                    @click="logActiveKeys = logGroups.map((g) => g.key)"
                  >
                    全部展开
                  </Button>
                  <Button size="small" @click="logActiveKeys = []">全部折叠</Button>
                  <Button
                    :disabled="!selectedRun"
                    :loading="loading"
                    size="small"
                    @click="exportSelectedRun"
                  >
                    导出 Run
                  </Button>
                  <span class="text-xs opacity-40">
                    {{ logGroups.reduce((n, g) => n + g.lines.length, 0) }} 行 ·
                    {{ logGroups.length }} 组
                  </span>
                </div>
                <div
                  v-if="logGroups.length"
                  class="min-h-0 flex-1 overflow-auto rounded-md border border-border/50 bg-muted/10 px-2 py-1"
                >
                  <Collapse
                    v-model:active-key="logActiveKeys"
                    :bordered="false"
                    ghost
                    size="small"
                  >
                    <Collapse.Panel
                      v-for="group in logGroups"
                      :key="group.key"
                      :header="`${group.title}（${group.lines.length}）`"
                    >
                      <pre
                        class="log-panel m-0 max-h-[320px] overflow-auto whitespace-pre-wrap font-mono text-[11px] leading-relaxed"
                        v-html="
                          group.lines.map((line) => highlightLogLine(line)).join('\n')
                        "
                      ></pre>
                    </Collapse.Panel>
                  </Collapse>
                </div>
                <pre
                  v-else
                  class="min-h-[200px] flex-1 overflow-auto rounded-md border border-border/50 bg-muted/20 p-3 font-mono text-xs leading-relaxed"
                >{{ runLogs }}</pre>
                <pre
                  v-if="selectedRun?.error"
                  class="max-h-[160px] shrink-0 overflow-auto rounded-md border border-destructive/30 bg-destructive/10 p-3 font-mono text-xs text-destructive"
                >{{ selectedRun.error }}</pre>
              </div>
            </Tabs.TabPane>
          </Tabs>
        </div>
      </div>
    </div>

    <Modal
      v-model:open="projectModalOpen"
      :title="editingProject ? '编辑项目' : '新建项目向导'"
      ok-text="保存"
      width="560px"
      @ok="submitProject"
    >
      <Form layout="vertical">
        <Form.Item label="名称" required>
          <Input v-model:value="projectForm.name" placeholder="项目显示名" />
        </Form.Item>
        <Form.Item label="根目录 (app_root)" required>
          <Input.Group compact>
            <Input
              v-model:value="projectForm.app_root"
              placeholder="绝对路径"
              style="width: calc(100% - 72px)"
            />
            <Button @click="projectRootPickerOpen = true">
              <IconifyIcon icon="lucide:folder-open" />
            </Button>
          </Input.Group>
          <Alert
            v-if="isTccSensitiveAppRoot"
            class="mt-2"
            show-icon
            type="warning"
            message="该路径在 Downloads/Desktop/Documents 下"
            description="macOS 上 Warp/omp 可能报 EPERM。请按 README「Warp 权限（macOS）」授权，或改绑到 ~/IdeaProjects 等目录。"
          />
        </Form.Item>
        <Form.Item label="文档目录">
          <Input v-model:value="projectForm.docs_dir" />
        </Form.Item>
        <Form.Item label="规则目录绑定">
          <Select
            v-if="ruleDirOptions.length"
            allow-clear
            class="mb-2 w-full"
            placeholder="从已有规则目录选择"
            :options="ruleDirOptions"
            @change="(v) => v && applyRuleDirToProject(String(v))"
          />
          <Select
            v-if="!editingProject && ruleSets.length"
            v-model:value="projectForm.rule_set_id"
            allow-clear
            class="mb-2 w-full"
            placeholder="可选：绑定 RuleSet（写入节点规则）"
            :options="
              ruleSets.map((r) => ({
                label: `${r.name} (${r.projects.length} 项)`,
                value: r.rule_set_id,
              }))
            "
          />
          <Input
            v-model:value="projectForm.ai_rules_dir"
            placeholder="相对 app_root 或绝对路径"
          >
            <template #suffix>
              <Tooltip title="浏览选择规则目录">
                <Button size="small" type="text" @click="ruleDirPickerOpen = true">
                  <IconifyIcon icon="lucide:folder-open" />
                </Button>
              </Tooltip>
            </template>
          </Input>
        </Form.Item>
        <Form.Item v-if="!editingProject" label="向导选项">
          <div class="flex flex-col gap-2">
            <label class="flex items-center gap-2 text-sm">
              <Switch v-model:checked="projectForm.create_app_root" size="small" />
              目录不存在时自动创建
            </label>
            <label class="flex items-center gap-2 text-sm">
              <Switch v-model:checked="projectForm.bootstrap" size="small" />
              创建后自动初始化（配置 / Skill / MCP）
            </label>
          </div>
        </Form.Item>
      </Form>
    </Modal>

    <Modal
      v-model:open="taskModalOpen"
      ok-text="创建"
      title="新建任务"
      @ok="submitTask"
    >
      <Form layout="vertical">
        <Form.Item label="任务名称" required>
          <Input v-model:value="taskNameInput" placeholder="例如：用户登录优化" />
        </Form.Item>
      </Form>
    </Modal>

    <Modal
      v-model:open="projectImportOpen"
      :confirm-loading="loading"
      ok-text="导入"
      title="导入项目整包"
      width="560px"
      @ok="submitProjectImport"
    >
      <Form layout="vertical">
        <Form.Item label="项目包 (.project.zip)" required>
          <input
            accept=".zip,application/zip"
            type="file"
            @change="
              async (e) => {
                const input = e.target as HTMLInputElement;
                const file = input.files?.[0];
                if (file) await onProjectImportFile(file);
              }
            "
          />
          <div v-if="projectImportForm.file_name" class="mt-1 text-xs opacity-50">
            {{ projectImportForm.file_name }}
          </div>
        </Form.Item>
        <Form.Item label="项目名称">
          <Input v-model:value="projectImportForm.name" placeholder="默认用包内名称" />
        </Form.Item>
        <Form.Item label="目标根目录 (app_root)" required>
          <Input.Group compact>
            <Input
              v-model:value="projectImportForm.app_root"
              placeholder="绝对路径，配置会写入此目录"
              style="width: calc(100% - 72px)"
            />
            <Button @click="importRootPickerOpen = true">
              <IconifyIcon icon="lucide:folder-open" />
            </Button>
          </Input.Group>
        </Form.Item>
        <Form.Item label="选项">
          <div class="flex flex-col gap-2">
            <label class="flex items-center gap-2 text-sm">
              <Switch v-model:checked="projectImportForm.create_app_root" size="small" />
              目录不存在时自动创建
            </label>
            <label class="flex items-center gap-2 text-sm">
              <Switch v-model:checked="projectImportForm.include_runs" size="small" />
              导入历史 runs（默认关，省磁盘）
            </label>
          </div>
        </Form.Item>
        <Alert
          show-icon
          type="info"
          message="整包内容 · 上限 50MB"
          description="直传 zip（不再 base64）。含项目绑定、任务、配置、规则；runs 默认不导入。导入会新建 id，不覆盖现有绑定。"
        />
      </Form>
    </Modal>

    <PathPickerModal
      v-model:open="prdPickerOpen"
      :initial-path="prdPickerInitial"
      mode="file"
      title="选择 PRD 文件"
      @select="onPrdPicked"
    />
    <PathPickerModal
      v-model:open="projectRootPickerOpen"
      :initial-path="projectForm.app_root"
      mode="dir"
      title="选择项目根目录"
      @select="onProjectRootPicked"
    />
    <PathPickerModal
      v-model:open="importRootPickerOpen"
      :initial-path="projectImportForm.app_root"
      mode="dir"
      title="选择导入目标根目录"
      @select="
        (path) => {
          projectImportForm.app_root = path;
          importRootPickerOpen = false;
        }
      "
    />
    <PathPickerModal
      v-model:open="ruleDirPickerOpen"
      :initial-path="projectForm.ai_rules_dir || projectForm.app_root"
      mode="dir"
      title="选择规则目录"
      @select="onRuleDirPicked"
    />

    <Modal
      v-model:open="compareOpen"
      :footer="null"
      title="执行对比"
      width="920px"
    >
      <template v-if="compareResult">
        <div class="mb-3 flex flex-wrap gap-3 text-xs">
          <Tag class="m-0">
            A {{ compareResult.left.run_id.slice(0, 8) }} · {{ compareResult.left.status }}
          </Tag>
          <Tag class="m-0">
            B {{ compareResult.right.run_id.slice(0, 8) }} · {{ compareResult.right.status }}
          </Tag>
          <Tag class="m-0" color="success">
            相同 {{ compareResult.summary.nodes_same }}
          </Tag>
          <Tag class="m-0" color="warning">
            不同 {{ compareResult.summary.nodes_diff }}
          </Tag>
          <Tag class="m-0">
            置信度 A
            {{
              compareResult.confidence.left?.score != null
                ? compareResult.confidence.left.score
                : '—'
            }}
            /
            B
            {{
              compareResult.confidence.right?.score != null
                ? compareResult.confidence.right.score
                : '—'
            }}
          </Tag>
        </div>
        <Table
          :columns="compareColumns"
          :data-source="compareResult.nodes"
          :pagination="false"
          row-key="node_id"
          size="small"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.dataIndex === 'left_has' || column.dataIndex === 'right_has'">
              {{ record[column.dataIndex] ? '有' : '无' }}
            </template>
            <template v-else-if="column.dataIndex === 'same_content'">
              <Space :size="4">
                <Tag
                  v-if="record.same_content === true"
                  class="m-0"
                  color="success"
                >
                  相同
                </Tag>
                <Tag
                  v-else-if="record.same_content === false"
                  class="m-0"
                  color="warning"
                >
                  不同
                </Tag>
                <span v-else class="opacity-40">—</span>
                <Button
                  v-if="record.left_has || record.right_has"
                  size="small"
                  type="link"
                  @click="openCompareDiff(record.node_id)"
                >
                  Diff
                </Button>
              </Space>
            </template>
          </template>
        </Table>
      </template>
    </Modal>

    <Modal
      v-model:open="artifactPreviewOpen"
      :footer="null"
      :title="
        artifactPreview.mode === 'diff'
          ? `产物 Diff · ${artifactPreview.nodeId}`
          : `产物预览 · ${artifactPreview.nodeId}`
      "
      width="960px"
    >
      <div
        v-if="artifactPreview.mode === 'single' && artifactNodeOptions.length"
        class="mb-3 flex items-center gap-2"
      >
        <span class="text-xs opacity-50">节点</span>
        <Select
          :value="artifactPreview.nodeId"
          :options="artifactNodeOptions"
          class="min-w-[220px]"
          size="small"
          @change="(v) => switchPreviewNode(String(v))"
        />
      </div>
      <template v-if="artifactPreview.mode === 'diff'">
        <div class="mb-2 flex flex-wrap gap-2 text-xs">
          <Tag :color="artifactPreview.same ? 'success' : 'warning'" class="m-0">
            {{ artifactPreview.same ? '内容相同' : '内容不同' }}
          </Tag>
          <Tag v-if="artifactPreview.truncated" color="warning" class="m-0">已截断</Tag>
        </div>
        <div class="grid gap-3 md:grid-cols-2">
          <div>
            <div class="mb-1 truncate text-xs opacity-45">A · {{ artifactPreview.path }}</div>
            <div
              v-if="artifactPreview.isMarkdown"
              class="md-preview max-h-[58vh] overflow-auto rounded-md border border-border/50 bg-muted/20 p-3 text-sm"
              v-html="renderMarkdown(artifactPreview.content || '')"
            />
            <pre
              v-else
              class="max-h-[58vh] overflow-auto rounded-md border border-border/50 bg-muted/20 p-3 font-mono text-xs leading-relaxed whitespace-pre-wrap"
            >{{ artifactPreview.content || '（无）' }}</pre>
          </div>
          <div>
            <div class="mb-1 truncate text-xs opacity-45">
              B · {{ artifactPreview.rightPath }}
            </div>
            <div
              v-if="artifactPreview.isMarkdown"
              class="md-preview max-h-[58vh] overflow-auto rounded-md border border-border/50 bg-muted/20 p-3 text-sm"
              v-html="renderMarkdown(artifactPreview.rightContent || '')"
            />
            <pre
              v-else
              class="max-h-[58vh] overflow-auto rounded-md border border-border/50 bg-muted/20 p-3 font-mono text-xs leading-relaxed whitespace-pre-wrap"
            >{{ artifactPreview.rightContent || '（无）' }}</pre>
          </div>
        </div>
      </template>
      <template v-else>
        <div class="mb-2 truncate text-xs opacity-45">{{ artifactPreview.path }}</div>
        <Tag v-if="artifactPreview.truncated" color="warning" class="mb-2">已截断显示</Tag>
        <div
          v-if="artifactPreview.isMarkdown"
          class="md-preview max-h-[65vh] overflow-auto rounded-md border border-border/50 bg-muted/20 p-3 text-sm"
          v-html="renderMarkdown(artifactPreview.content || '')"
        />
        <pre
          v-else
          class="max-h-[65vh] overflow-auto rounded-md border border-border/50 bg-muted/20 p-3 font-mono text-xs leading-relaxed whitespace-pre-wrap"
        >{{ artifactPreview.content }}</pre>
      </template>
    </Modal>
  </Page>
</template>

<style scoped>
.nav-section__title {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  opacity: 0.5;
}

.nav-item--active {
  background: hsl(var(--primary) / 0.12);
  color: hsl(var(--primary));
}

.nav-panel {
  font-size: 13px;
}

/* 用 flex 填满剩余高度，避免 100vh 固定值在出现 Alert 时把底栏裁掉 */
.workbench-tabs {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.workbench-tabs :deep(.ant-tabs-nav) {
  flex-shrink: 0;
  margin-bottom: 8px;
}

.workbench-tabs :deep(.ant-tabs-content-holder) {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.workbench-tabs :deep(.ant-tabs-content) {
  height: 100%;
  overflow: hidden;
}

/* 安全网：任意 Tab 内容超高时可滚，避免再被裁切且无滚动条 */
.workbench-tabs :deep(.ant-tabs-tabpane) {
  height: 100%;
  min-height: 0;
  overflow: auto;
}

.workbench-tabs :deep(.ant-tabs-tabpane-hidden) {
  display: none;
}

.tab-scroll-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: auto;
  overscroll-behavior: contain;
  padding-right: 2px;
  padding-bottom: 8px;
}

/* 历史：工具栏顶、表体滚、分页钉底（不进外层滚动） */
.history-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  gap: 0;
  padding-bottom: 4px;
}

.history-table-wrap {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  overflow: hidden;
}

.history-table-wrap :deep(.ant-table-wrapper),
.history-table-wrap :deep(.ant-spin-nested-loading),
.history-table-wrap :deep(.ant-spin-container) {
  height: 100%;
}

.history-table-wrap :deep(.ant-spin-container) {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.history-table-wrap :deep(.ant-table) {
  flex: 1 1 auto;
  min-height: 0;
}

.history-table-wrap :deep(.ant-pagination) {
  flex-shrink: 0;
  margin: 8px 0 0 !important;
}

.pipeline-panel {
  overscroll-behavior: contain;
}

.artifact-sidebar {
  min-height: 0;
}

.artifact-sidebar :deep(.ant-card-body) {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.artifact-md :deep(h1),
.artifact-md :deep(h2),
.artifact-md :deep(h3) {
  margin: 0.5em 0 0.3em;
  font-weight: 600;
  line-height: 1.35;
}

.artifact-md :deep(p),
.artifact-md :deep(ul),
.artifact-md :deep(ol) {
  margin: 0.3em 0;
  line-height: 1.6;
}

.artifact-md :deep(code) {
  padding: 0.1em 0.3em;
  border-radius: 4px;
  background: hsl(var(--muted) / 0.55);
  font-size: 0.9em;
}

.artifact-md :deep(pre) {
  overflow: auto;
  padding: 0.6rem;
  border-radius: 6px;
  background: hsl(var(--muted) / 0.45);
}

.log-panel :deep(mark.log-hl) {
  padding: 0 2px;
  border-radius: 2px;
  background: hsl(45 90% 50% / 0.35);
  color: inherit;
}

/* ── 配置面板 ── */
.config-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  gap: 0;
}

.config-form {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
  gap: 12px;
  overflow-y: auto;
  padding-bottom: 8px;
}

.config-card {
  flex-shrink: 0;
  border-radius: 8px;
}

.config-card--grow {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
}

.config-card--grow :deep(.ant-card-body) {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
  padding-bottom: 12px;
}

.requirement-textarea {
  flex: 1;
  min-height: 0;
}

.requirement-textarea :deep(textarea) {
  height: 100% !important;
  min-height: 160px;
  resize: none;
  line-height: 1.6;
  font-size: 13px;
}

/* ── 运行选项卡片 ── */
.option-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

@media (max-width: 768px) {
  .option-grid {
    grid-template-columns: 1fr;
  }
}

.option-card {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid hsl(var(--border));
  border-radius: 8px;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
  user-select: none;
}

.option-card:hover {
  background: hsl(var(--muted) / 0.3);
}

.option-card--on {
  border-color: hsl(var(--primary) / 0.5);
  background: hsl(var(--primary) / 0.06);
}

.option-card__title {
  font-size: 13px;
  font-weight: 500;
  line-height: 1.3;
}

.option-card__desc {
  margin-top: 2px;
  font-size: 11px;
  opacity: 0.45;
  line-height: 1.3;
}

/* ── 底栏 ── */
.config-footer {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: space-between;
  padding: 12px 0 4px;
  border-top: 1px solid hsl(var(--border) / 0.6);
}

.run-timeline :deep(.ant-timeline-item-content) {
  min-height: auto;
}

:deep(.node-row--hl) > td {
  background: hsl(var(--primary) / 0.12) !important;
}

.md-preview :deep(h1),
.md-preview :deep(h2),
.md-preview :deep(h3) {
  margin: 0.6em 0 0.35em;
  font-weight: 600;
  line-height: 1.35;
}

.md-preview :deep(p),
.md-preview :deep(ul),
.md-preview :deep(ol) {
  margin: 0.35em 0;
  line-height: 1.65;
}

.md-preview :deep(code) {
  padding: 0.1em 0.35em;
  border-radius: 4px;
  background: hsl(var(--muted) / 0.55);
  font-size: 0.9em;
}

.md-preview :deep(pre) {
  overflow: auto;
  padding: 0.75rem;
  border-radius: 6px;
  background: hsl(var(--muted) / 0.45);
}

.md-preview :deep(pre code) {
  padding: 0;
  background: transparent;
}

.md-preview :deep(a) {
  color: hsl(var(--primary));
}
</style>
