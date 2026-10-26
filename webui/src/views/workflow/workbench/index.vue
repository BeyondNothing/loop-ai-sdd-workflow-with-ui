<script lang="ts" setup>
import { computed, ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Badge,
  Button,
  Card,
  Col,
  Dropdown,
  Empty,
  Form,
  Input,
  Menu,
  Modal,
  Row,
  Select,
  Switch,
  Table,
  Tabs,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import PathPickerModal from './PathPickerModal.vue';
import { useWorkbench } from './use-workbench';

const activeTab = ref('config');
const prdPickerOpen = ref(false);
const projectRootPickerOpen = ref(false);

const {
  applyRuleDirToProject,
  deleteProject,
  editingProject,
  flags,
  form,
  loading,
  nodeStatuses,
  onRuleDirPicked,
  openArtifact,
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
} = useWorkbench();

const nodeColumns = [
  { title: '#', dataIndex: 'index', width: 44, align: 'center' as const },
  { title: '节点', dataIndex: 'name', width: 140, ellipsis: true },
  { title: '标识', dataIndex: 'id', ellipsis: true },
  { title: '状态', dataIndex: 'status', width: 96 },
  { title: '产物', dataIndex: 'artifact', ellipsis: true },
  { title: '', dataIndex: 'action', width: 64 },
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
  { title: 'Run ID', dataIndex: 'run_id', ellipsis: true, width: 120 },
  { title: '任务', dataIndex: 'requirement_name', ellipsis: true },
  { title: '状态', dataIndex: 'status', width: 96 },
  { title: 'Auto', dataIndex: 'auto', width: 64 },
  { title: '', dataIndex: 'action', width: 64 },
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
              <span class="truncate">{{ t.task_name }}</span>
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
            <Empty
              v-if="!tasks.length"
              :description="selectedProjectId ? '暂无任务' : '先选项目'"
              :image-style="{ height: 32 }"
              class="my-2"
            />
          </div>
        </div>
      </aside>

      <!-- 右侧：状态栏 + Tab 内容 -->
      <div class="flex min-w-0 flex-1 flex-col">
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
            <Tag :color="statusColor(selectedRun.status)" class="m-0">
              {{ selectedRun.status }}
            </Tag>
            <span class="opacity-50">
              节点 {{ completedCount }}/{{ nodeStatuses.length }}
            </span>
          </div>

          <Dropdown class="ml-auto">
            <Button size="small" type="text">
              <IconifyIcon icon="lucide:more-horizontal" />
            </Button>
            <template #overlay>
              <Menu>
                <Menu.Item @click="refreshAll">刷新数据</Menu.Item>
              </Menu>
            </template>
          </Dropdown>
        </header>

        <div class="min-h-0 flex-1 overflow-hidden px-4 pb-3 pt-2">
          <Tabs v-model:active-key="activeTab" class="workbench-tabs h-full" size="small">
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
                          <div class="option-card__desc">门禁通过后自动继续</div>
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
              <Table
                :columns="nodeColumns"
                :data-source="nodeTableData"
                :pagination="false"
                :scroll="{ y: 'calc(100vh - 200px)' }"
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
                    <Button
                      v-if="record.hasArtifact"
                      size="small"
                      type="link"
                      @click="openArtifact(record.nodeId)"
                    >
                      打开
                    </Button>
                  </template>
                </template>
                <template #emptyText>
                  <Empty description="执行工作流后显示节点状态" />
                </template>
              </Table>
            </Tabs.TabPane>

            <Tabs.TabPane key="history" tab="执行历史">
              <Table
                :columns="runHistoryColumns"
                :data-source="projectRuns"
                :pagination="{ pageSize: 12, size: 'small', showSizeChanger: false }"
                :scroll="{ y: 'calc(100vh - 200px)' }"
                row-key="run_id"
                size="small"
              >
                <template #bodyCell="{ column, record }">
                  <template v-if="column.dataIndex === 'status'">
                    <Tag :color="statusColor(record.status)" class="m-0">
                      {{ record.status }}
                    </Tag>
                  </template>
                  <template v-else-if="column.dataIndex === 'auto'">
                    {{ record.auto ? '是' : '否' }}
                  </template>
                  <template v-else-if="column.dataIndex === 'action'">
                    <Button size="small" type="link" @click="selectRun(record.run_id)">
                      查看
                    </Button>
                  </template>
                </template>
                <template #emptyText>
                  <Empty description="暂无执行记录" />
                </template>
              </Table>
            </Tabs.TabPane>

            <Tabs.TabPane key="logs" tab="日志">
              <div class="flex h-full min-h-0 flex-col gap-2 pt-1">
                <pre
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
      :title="editingProject ? '编辑项目' : '新建项目'"
      ok-text="保存"
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
      v-model:open="ruleDirPickerOpen"
      :initial-path="projectForm.ai_rules_dir || projectForm.app_root"
      mode="dir"
      title="选择规则目录"
      @select="onRuleDirPicked"
    />
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

.workbench-tabs :deep(.ant-tabs-content) {
  height: calc(100vh - 180px);
  overflow: hidden;
}

.workbench-tabs :deep(.ant-tabs-tabpane) {
  height: 100%;
}

/* ── 配置面板 ── */
.config-panel {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 200px);
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
</style>
