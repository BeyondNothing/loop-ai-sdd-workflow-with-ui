<script lang="ts" setup>
import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Card,
  Checkbox,
  Descriptions,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Radio,
  Select,
  Space,
  Switch,
  Table,
  Tabs,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import { useSettings } from './use-settings';

const {
  activeTab,
  addConfidenceRule,
  confidenceEnginePath,
  confidenceNodeId,
  confidenceNodeOptions,
  confidencePath,
  defaultTool,
  deleteMcp,
  engineRulesForSelected,
  initProject,
  installSkills,
  loading,
  mcpEditingName,
  mcpForm,
  mcpModalOpen,
  mcpPath,
  mcpServers,
  nodeAppRoot,
  nodeDefaults,
  nodeRows,
  onProjectChange,
  openMcpModal,
  probeConnectivity,
  probeResult,
  probing,
  projectOptions,
  removeConfidenceRule,
  saveConfidenceRules,
  saveDefaultTool,
  saveMcp,
  saveNodeSettings,
  saving,
  selectedConfidenceNode,
  selectedProjectId,
  selectedSkillAgents,
  skillAgents,
  skillName,
  submitMcpModal,
  syncMcp,
  syncing,
  systemInfo,
  toolSelectOptions,
  tools,
} = useSettings();

const nodeColumns = [
  { title: '节点', dataIndex: 'name', width: 160 },
  { title: '模式', dataIndex: 'mode', width: 100 },
  { title: '工具', dataIndex: 'tool', width: 160 },
  { title: 'Model（可选）', dataIndex: 'model' },
  { title: '推荐阈值', dataIndex: 'recommendation_threshold', width: 140 },
];
</script>

<template>
  <Page auto-content-height content-class="p-4">
    <div class="mx-auto max-w-5xl space-y-4">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 class="text-lg font-medium">系统设置</h2>
          <p class="text-sm opacity-50">
            默认工具、节点、置信度规则、MCP 与 Skill 均可配置；节点/Skill/置信度作用于当前业务项目。
          </p>
        </div>
        <Space wrap>
          <Select
            v-model:value="selectedProjectId"
            :options="projectOptions"
            allow-clear
            class="w-[280px]"
            placeholder="选择业务项目"
            @change="onProjectChange"
          />
          <Button :loading="probing" @click="probeConnectivity">
            <IconifyIcon class="mr-1" icon="lucide:radar" />
            连通探测
          </Button>
          <Button :loading="syncing" @click="initProject">
            <IconifyIcon class="mr-1" icon="lucide:folder-cog" />
            一键初始化
          </Button>
        </Space>
      </div>

      <Card
        v-if="probeResult"
        :loading="probing"
        size="small"
        title="连通探测结果"
      >
        <div class="mb-3 flex flex-wrap items-center gap-2 text-sm">
          <Tag :color="probeResult.ok ? 'success' : 'warning'">
            {{ probeResult.ok ? '全部就绪' : '存在异常' }}
          </Tag>
          <span class="opacity-60">MCP {{ probeResult.mcp.summary }}</span>
          <span class="opacity-60">·</span>
          <span class="opacity-60">Skill {{ probeResult.skills.summary }}</span>
        </div>
        <div class="grid gap-3 md:grid-cols-2">
          <div>
            <div class="mb-2 text-sm font-medium">MCP 服务器</div>
            <div class="space-y-1">
              <div
                v-for="server in probeResult.mcp.servers"
                :key="server.name"
                class="flex items-center justify-between rounded border border-border/50 px-2 py-1 text-xs"
              >
                <span>{{ server.name }}</span>
                <Tag
                  :color="server.ok ? 'success' : 'error'"
                  class="m-0"
                >
                  {{ server.message || (server.ok ? '就绪' : '异常') }}
                </Tag>
              </div>
            </div>
            <div class="mt-2 space-y-1">
              <div
                v-for="item in probeResult.mcp.agent_sync"
                :key="item.path"
                class="truncate text-[11px] opacity-55"
              >
                <Tag :color="item.ok ? 'success' : 'default'" class="m-0 mr-1">
                  {{ item.ok ? 'OK' : '缺' }}
                </Tag>
                {{ item.path }}
              </div>
            </div>
          </div>
          <div>
            <div class="mb-2 text-sm font-medium">Skill</div>
            <div class="space-y-1">
              <div
                v-for="agent in probeResult.skills.agents"
                :key="agent.agent"
                class="flex items-center justify-between rounded border border-border/50 px-2 py-1 text-xs"
              >
                <span>
                  {{ agent.agent }}
                  <span v-if="agent.stale_hint" class="ml-1 opacity-45">
                    (与模板大小不同)
                  </span>
                </span>
                <Tag :color="agent.ok ? 'success' : 'warning'" class="m-0">
                  {{ agent.message }}
                </Tag>
              </div>
            </div>
          </div>
        </div>
      </Card>

      <Card :loading="loading" size="small" title="运行环境">
        <Descriptions v-if="systemInfo" :column="3" size="small">
          <Descriptions.Item label="操作系统">
            {{ systemInfo.os_name }}
          </Descriptions.Item>
          <Descriptions.Item label="平台">
            {{ systemInfo.platform }}
          </Descriptions.Item>
          <Descriptions.Item label="业务根">
            <span class="break-all text-xs">{{ nodeAppRoot || '—' }}</span>
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Card :loading="loading" size="small">
        <Tabs v-model:active-key="activeTab" size="small">
          <Tabs.TabPane key="tool" tab="默认工具">
            <Form layout="vertical">
              <Form.Item label="操作台启动任务时的默认 AI 工具">
                <Radio.Group v-model:value="defaultTool" class="tool-radio-group">
                  <Space direction="vertical" class="w-full">
                    <Radio
                      v-for="tool in tools"
                      :key="tool.id"
                      :value="tool.id"
                      class="tool-radio"
                    >
                      <div class="flex items-center gap-2">
                        <span class="font-medium">{{ tool.name }}</span>
                        <Tag class="m-0 text-[10px]">{{ tool.id }}</Tag>
                      </div>
                      <div class="text-xs opacity-45">{{ tool.description }}</div>
                    </Radio>
                  </Space>
                </Radio.Group>
              </Form.Item>
              <div class="flex justify-end">
                <Button :loading="saving" type="primary" @click="saveDefaultTool">
                  保存默认工具
                </Button>
              </div>
            </Form>
          </Tabs.TabPane>

          <Tabs.TabPane key="nodes" tab="节点配置">
            <p class="mb-3 text-xs opacity-50">
              写入业务项目
              <code>sdd-loop-workflow-config/workflow.yaml</code>
              ；节点 tool 优先于 defaults。
            </p>
            <Form class="mb-3" layout="inline">
              <Form.Item label="默认工具">
                <Select
                  v-model:value="nodeDefaults.tool"
                  :options="toolSelectOptions"
                  class="w-[180px]"
                />
              </Form.Item>
              <Form.Item label="默认 model">
                <Input
                  v-model:value="nodeDefaults.model"
                  class="w-[180px]"
                  placeholder="留空=CLI 默认"
                />
              </Form.Item>
              <Form.Item label="docs_dir">
                <Input v-model:value="nodeDefaults.docs_dir" class="w-[120px]" />
              </Form.Item>
            </Form>
            <Table
              :columns="nodeColumns"
              :data-source="nodeRows"
              :pagination="false"
              bordered
              row-key="id"
              size="small"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.dataIndex === 'tool'">
                  <Select
                    v-model:value="record.tool"
                    :options="toolSelectOptions"
                    class="w-full"
                    size="small"
                  />
                </template>
                <template v-else-if="column.dataIndex === 'model'">
                  <Input
                    v-model:value="record.model"
                    placeholder="可选，如 sonnet"
                    size="small"
                  />
                </template>
                <template v-else-if="column.dataIndex === 'recommendation_threshold'">
                  <InputNumber
                    v-model:value="record.recommendation_threshold"
                    :max="1"
                    :min="0"
                    :step="0.05"
                    class="w-full"
                    size="small"
                  />
                </template>
                <template v-else-if="column.dataIndex === 'mode'">
                  <Tag class="m-0">{{ record.mode }}</Tag>
                </template>
              </template>
            </Table>
            <div class="mt-3 flex justify-end">
              <Button :loading="saving" type="primary" @click="saveNodeSettings">
                保存节点配置
              </Button>
            </div>
          </Tabs.TabPane>

          <Tabs.TabPane key="confidence" tab="置信度规则">
            <p class="mb-3 text-xs opacity-50">
              编辑业务扩展规则（叠加引擎基线）。写入
              <code>{{ confidencePath || 'sdd-loop-workflow-config/suggestion-confidence-rules.yaml' }}</code>
              ；引擎基线只读：
              <code>{{ confidenceEnginePath || 'config/suggestion-confidence-rules.yaml' }}</code>
            </p>
            <div class="mb-3 flex flex-wrap items-center gap-2">
              <Select
                v-model:value="confidenceNodeId"
                :options="confidenceNodeOptions"
                class="w-[320px]"
                placeholder="选择节点"
              />
              <Input
                v-if="selectedConfidenceNode"
                v-model:value="selectedConfidenceNode.description"
                class="w-[240px]"
                placeholder="节点描述"
              />
            </div>
            <Empty
              v-if="!selectedConfidenceNode"
              description="请选择业务项目与节点"
            />
            <template v-else>
              <Card
                v-if="engineRulesForSelected"
                class="mb-3"
                size="small"
                title="引擎基线（只读）"
              >
                <div class="grid gap-3 md:grid-cols-2">
                  <div>
                    <div class="mb-1 text-xs opacity-50">高把握</div>
                    <ul class="m-0 list-disc pl-4 text-xs opacity-70">
                      <li
                        v-for="(r, i) in engineRulesForSelected.high_confidence_rules"
                        :key="`eh-${i}`"
                      >
                        {{ r.condition }}
                      </li>
                    </ul>
                  </div>
                  <div>
                    <div class="mb-1 text-xs opacity-50">低把握</div>
                    <ul class="m-0 list-disc pl-4 text-xs opacity-70">
                      <li
                        v-for="(r, i) in engineRulesForSelected.low_confidence_rules"
                        :key="`el-${i}`"
                      >
                        {{ r.condition }}
                      </li>
                    </ul>
                  </div>
                </div>
              </Card>

              <div class="mb-2 flex items-center justify-between">
                <span class="text-sm font-medium">项目扩展 · 高把握</span>
                <Button size="small" type="dashed" @click="addConfidenceRule('high')">
                  添加
                </Button>
              </div>
              <div class="mb-4 space-y-2">
                <div
                  v-for="(rule, idx) in selectedConfidenceNode.high_confidence_rules"
                  :key="`h-${idx}`"
                  class="grid gap-2 rounded border border-border/50 p-2 md:grid-cols-[1fr_1fr_auto]"
                >
                  <Input v-model:value="rule.condition" placeholder="condition" size="small" />
                  <Input v-model:value="rule.reason" placeholder="reason" size="small" />
                  <Button
                    danger
                    size="small"
                    type="text"
                    @click="removeConfidenceRule('high', idx)"
                  >
                    删
                  </Button>
                </div>
                <Empty
                  v-if="!selectedConfidenceNode.high_confidence_rules.length"
                  :image-style="{ height: 36 }"
                  description="暂无扩展高把握规则"
                />
              </div>

              <div class="mb-2 flex items-center justify-between">
                <span class="text-sm font-medium">项目扩展 · 低把握</span>
                <Button size="small" type="dashed" @click="addConfidenceRule('low')">
                  添加
                </Button>
              </div>
              <div class="mb-3 space-y-2">
                <div
                  v-for="(rule, idx) in selectedConfidenceNode.low_confidence_rules"
                  :key="`l-${idx}`"
                  class="grid gap-2 rounded border border-border/50 p-2 md:grid-cols-[1fr_1fr_auto]"
                >
                  <Input v-model:value="rule.condition" placeholder="condition" size="small" />
                  <Input v-model:value="rule.reason" placeholder="reason" size="small" />
                  <Button
                    danger
                    size="small"
                    type="text"
                    @click="removeConfidenceRule('low', idx)"
                  >
                    删
                  </Button>
                </div>
                <Empty
                  v-if="!selectedConfidenceNode.low_confidence_rules.length"
                  :image-style="{ height: 36 }"
                  description="暂无扩展低把握规则"
                />
              </div>

              <div class="flex justify-end">
                <Button :loading="saving" type="primary" @click="saveConfidenceRules">
                  保存置信度规则
                </Button>
              </div>
            </template>
          </Tabs.TabPane>

          <Tabs.TabPane key="mcp" tab="MCP">
            <div class="mb-3 flex items-start justify-between gap-2">
              <p class="m-0 text-xs opacity-50">
                真源：
                <code>{{ mcpPath || 'config/mcp/servers.json' }}</code>
                。可增删改自定义服务器；保存开关后点「同步到项目」。
              </p>
              <Button size="small" type="dashed" @click="openMcpModal()">
                <IconifyIcon class="mr-1" icon="lucide:plus" />
                新增
              </Button>
            </div>
            <div v-if="mcpServers.length" class="space-y-2">
              <div
                v-for="server in mcpServers"
                :key="server.name"
                class="flex items-center justify-between gap-3 rounded-md border border-border/60 px-3 py-2"
              >
                <div class="min-w-0 flex-1">
                  <div class="flex items-center gap-2">
                    <span class="font-medium">{{ server.name }}</span>
                    <Tag class="m-0 text-[10px]">
                      {{ server.wrapper || server.command || server.url || 'custom' }}
                    </Tag>
                  </div>
                  <div class="truncate text-xs opacity-45">
                    {{ server.description || (server.args || []).join(' ') || '—' }}
                  </div>
                </div>
                <Space :size="4">
                  <Switch v-model:checked="server.enabled" />
                  <Tooltip title="编辑">
                    <Button size="small" type="text" @click="openMcpModal(server)">
                      <IconifyIcon icon="lucide:pencil" class="size-3.5" />
                    </Button>
                  </Tooltip>
                  <Tooltip title="删除">
                    <Button danger size="small" type="text" @click="deleteMcp(server.name)">
                      <IconifyIcon icon="lucide:trash-2" class="size-3.5" />
                    </Button>
                  </Tooltip>
                </Space>
              </div>
            </div>
            <Empty v-else description="暂无 MCP 服务器定义" />
            <div class="mt-3 flex justify-end gap-2">
              <Button :loading="saving" @click="saveMcp">保存开关</Button>
              <Button :loading="syncing" type="primary" @click="syncMcp">
                同步到项目
              </Button>
            </div>
          </Tabs.TabPane>

          <Tabs.TabPane key="skills" tab="Skill">
            <p class="mb-3 text-xs opacity-50">
              安装引擎模板
              <code>skills/{{ skillName }}/SKILL.md</code>
              到业务项目各 Agent 目录。
            </p>
            <Checkbox.Group v-model:value="selectedSkillAgents" class="mb-3 w-full">
              <div class="space-y-2">
                <div
                  v-for="agent in skillAgents"
                  :key="agent.agent"
                  class="flex items-center justify-between rounded-md border border-border/60 px-3 py-2"
                >
                  <Checkbox :value="agent.agent">
                    <span class="font-medium">{{ agent.agent }}</span>
                    <Tag class="ml-2 m-0 text-[10px]">{{ agent.relative_dir }}</Tag>
                  </Checkbox>
                  <Tag :color="agent.installed ? 'success' : 'default'" class="m-0">
                    {{ agent.installed ? '已安装' : '未安装' }}
                  </Tag>
                </div>
              </div>
            </Checkbox.Group>
            <div class="flex justify-end">
              <Button :loading="syncing" type="primary" @click="installSkills">
                安装 / 更新 Skill
              </Button>
            </div>
          </Tabs.TabPane>
        </Tabs>
      </Card>
    </div>

    <Modal
      v-model:open="mcpModalOpen"
      :confirm-loading="saving"
      :title="mcpEditingName ? '编辑 MCP 服务器' : '新增 MCP 服务器'"
      ok-text="保存"
      @ok="submitMcpModal"
    >
      <Form layout="vertical">
        <Form.Item label="名称" required>
          <Input
            v-model:value="mcpForm.name"
            :disabled="!!mcpEditingName"
            placeholder="例如 filesystem"
          />
        </Form.Item>
        <Form.Item label="启用">
          <Switch v-model:checked="mcpForm.enabled" />
        </Form.Item>
        <Form.Item label="command">
          <Input v-model:value="mcpForm.command" placeholder="可执行命令，如 npx" />
        </Form.Item>
        <Form.Item label="wrapper">
          <Input
            v-model:value="mcpForm.wrapper"
            placeholder="相对引擎根的脚本，如 scripts/playwright-mcp.sh"
          />
        </Form.Item>
        <Form.Item label="url">
          <Input v-model:value="mcpForm.url" placeholder="远程 MCP URL（与 command/wrapper 二选一）" />
        </Form.Item>
        <Form.Item label="args（空格分隔）">
          <Input v-model:value="mcpForm.argsText" placeholder="--browser chrome" />
        </Form.Item>
        <Form.Item label="描述">
          <Input v-model:value="mcpForm.description" placeholder="可选说明" />
        </Form.Item>
      </Form>
    </Modal>
  </Page>
</template>

<style scoped>
.tool-radio-group :deep(.ant-radio-wrapper) {
  align-items: flex-start;
  width: 100%;
  padding: 10px 12px;
  border: 1px solid hsl(var(--border) / 60%);
  border-radius: 8px;
}

.tool-radio-group :deep(.ant-radio-wrapper-checked) {
  border-color: hsl(var(--primary) / 50%);
  background: hsl(var(--primary) / 8%);
}
</style>
