<script lang="ts" setup>
import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Empty,
  Form,
  Input,
  List,
  Modal,
  Space,
  Tabs,
  Tag,
  Tooltip,
  Upload,
} from 'ant-design-vue';

import RuleBindModal from '../workbench/RuleBindModal.vue';
import PathPickerModal from '../workbench/PathPickerModal.vue';
import NodeRulesEditor from './NodeRulesEditor.vue';
import RuleSetCreateModal from './RuleSetCreateModal.vue';
import { useRuleDirs } from './use-rule-dirs';
import { ref } from 'vue';

const importFolderPickerOpen = ref(false);

const {
  bindModalOpen,
  confirmDelete,
  createModalOpen,
  exportRuleSet,
  files,
  importFileName,
  importFolder,
  importModalOpen,
  importName,
  loading,
  onBindSaved,
  onImportFileChange,
  onSystemMdInput,
  openBindModal,
  openCreateModal,
  openImportModal,
  projects,
  refreshAll,
  ruleSets,
  saveNodeRules,
  saveSystemMd,
  savingSystemMd,
  selectRuleSet,
  selectedId,
  selectedRuleSet,
  submitImport,
  systemMd,
  systemMdDirty,
  systemMdExists,
  systemMdPath,
} = useRuleDirs();
</script>

<template>
  <Page auto-content-height content-class="p-0">
    <div class="flex h-full min-h-0">
      <aside
        class="flex w-[240px] shrink-0 flex-col border-r border-border bg-sidebar/50"
      >
        <div class="border-b border-border px-3 py-2.5">
          <div class="flex items-center justify-between">
            <span class="panel-title">
              <IconifyIcon icon="lucide:book-open" class="mr-1 inline opacity-50" />
              规则目录
            </span>
            <Space :size="2">
              <Tooltip title="导入 zip">
                <Button size="small" type="text" @click="openImportModal">
                  <IconifyIcon icon="lucide:upload" class="size-3.5" />
                </Button>
              </Tooltip>
              <Tooltip title="新建">
                <Button size="small" type="text" @click="openCreateModal">
                  <IconifyIcon icon="lucide:plus" class="size-3.5" />
                </Button>
              </Tooltip>
              <Tooltip title="刷新">
                <Button :loading="loading" size="small" type="text" @click="refreshAll">
                  <IconifyIcon icon="lucide:refresh-cw" class="size-3.5" />
                </Button>
              </Tooltip>
            </Space>
          </div>
        </div>
        <div class="min-h-0 flex-1 overflow-y-auto px-2 py-2">
          <div
            v-for="item in ruleSets"
            :key="item.rule_set_id"
            :class="
              item.rule_set_id === selectedId
                ? 'nav-item--active'
                : 'hover:bg-muted/40'
            "
            class="nav-item mb-0.5 flex cursor-pointer items-center justify-between gap-1 rounded px-2 py-2 transition-colors"
            @click="selectRuleSet(item.rule_set_id)"
          >
            <div class="min-w-0 flex-1">
              <div class="truncate text-sm font-medium">{{ item.name }}</div>
              <div class="truncate text-[11px] opacity-40">
                {{ item.file_count }} 文件 · {{ item.resolved_path }}
              </div>
            </div>
            <Tag
              class="m-0 shrink-0 text-[10px]"
              :color="item.projects.length ? 'blue' : 'default'"
            >
              {{ item.projects.length }}
            </Tag>
          </div>
          <Empty
            v-if="!ruleSets.length"
            :image-style="{ height: 40 }"
            class="my-4"
            description="暂无规则目录，点击 + 新建"
          />
        </div>
      </aside>

      <div class="flex min-w-0 flex-1 flex-col">
        <template v-if="selectedRuleSet">
          <header
            class="flex shrink-0 items-center gap-3 border-b border-border px-4 py-3"
          >
            <IconifyIcon icon="lucide:book-open" class="size-4 opacity-50" />
            <div class="min-w-0 flex-1">
              <div class="text-sm font-medium">{{ selectedRuleSet.name }}</div>
              <div class="truncate text-xs opacity-40">
                {{ selectedRuleSet.resolved_path }}
              </div>
            </div>
            <Space>
              <Tag :color="selectedRuleSet.exists ? 'success' : 'warning'" class="m-0">
                {{ selectedRuleSet.exists ? '目录存在' : '目录不存在' }}
              </Tag>
              <Button :loading="loading" @click="exportRuleSet">
                <IconifyIcon class="mr-1" icon="lucide:download" />
                导出
              </Button>
              <Button @click="openBindModal">
                <IconifyIcon class="mr-1" icon="lucide:link" />
                项目绑定
              </Button>
              <Button danger type="text" @click="confirmDelete">
                <IconifyIcon icon="lucide:trash-2" />
              </Button>
            </Space>
          </header>

          <div class="min-h-0 flex-1 overflow-y-auto p-4">
            <Tabs default-active-key="nodes" size="small">
              <Tabs.TabPane key="nodes" tab="节点规则">
                <NodeRulesEditor
                  :files="files"
                  :node-rules="selectedRuleSet.node_rules || {}"
                  @save="saveNodeRules"
                />
              </Tabs.TabPane>
              <Tabs.TabPane key="system" tab="system.md">
                <div class="mb-2 flex items-center justify-between gap-2">
                  <div class="min-w-0 truncate text-xs opacity-45">
                    {{ systemMdPath || 'system.md' }}
                    <Tag
                      class="ml-2 m-0 text-[10px]"
                      :color="systemMdExists ? 'success' : 'default'"
                    >
                      {{ systemMdExists ? '已存在' : '未创建' }}
                    </Tag>
                    <Tag v-if="systemMdDirty" class="ml-1 m-0 text-[10px]" color="warning">
                      未保存
                    </Tag>
                  </div>
                  <Button
                    :loading="savingSystemMd"
                    size="small"
                    type="primary"
                    @click="saveSystemMd"
                  >
                    保存
                  </Button>
                </div>
                <Input.TextArea
                  :value="systemMd"
                  :auto-size="{ minRows: 16, maxRows: 28 }"
                  class="font-mono text-xs"
                  placeholder="编写全局 system 规则（Markdown）…"
                  @update:value="onSystemMdInput"
                />
              </Tabs.TabPane>
              <Tabs.TabPane key="projects" tab="绑定项目">
                <div v-if="selectedRuleSet.projects.length" class="flex flex-wrap gap-2">
                  <Tag
                    v-for="p in selectedRuleSet.projects"
                    :key="p.project_id"
                    class="m-0"
                    color="blue"
                  >
                    {{ p.name }}
                  </Tag>
                </div>
                <Empty v-else description="尚未绑定项目" />
              </Tabs.TabPane>
              <Tabs.TabPane key="files" tab="规则文件">
                <List
                  v-if="files.length"
                  :data-source="files"
                  bordered
                  class="max-h-[480px] overflow-y-auto"
                  size="small"
                >
                  <template #renderItem="{ item }">
                    <List.Item class="py-1.5 text-sm">{{ item }}</List.Item>
                  </template>
                </List>
                <Empty v-else description="目录中无 .md 规则文件" />
              </Tabs.TabPane>
            </Tabs>
          </div>
        </template>
        <Empty
          v-else
          class="m-auto"
          description="请选择或新建规则目录"
        />
      </div>
    </div>

    <RuleSetCreateModal v-model:open="createModalOpen" @created="refreshAll" />
    <RuleBindModal
      v-model:open="bindModalOpen"
      :projects="projects"
      :rule-dir="selectedRuleSet"
      @saved="onBindSaved"
    />

    <Modal
      v-model:open="importModalOpen"
      :confirm-loading="loading"
      ok-text="导入"
      title="导入 RuleSet zip"
      @ok="submitImport"
    >
      <Form layout="vertical">
        <Form.Item label="zip 文件" required>
          <Upload
            :before-upload="
              (file) => {
                onImportFileChange(file as File);
                return false;
              }
            "
            :max-count="1"
            accept=".zip"
            :show-upload-list="false"
          >
            <Button>
              <IconifyIcon class="mr-1" icon="lucide:file-archive" />
              选择 zip
            </Button>
          </Upload>
          <div class="mt-1 text-xs opacity-45">{{ importFileName || '未选择' }}</div>
        </Form.Item>
        <Form.Item label="显示名称">
          <Input v-model:value="importName" placeholder="可选，默认用 zip 名" />
        </Form.Item>
        <Form.Item label="解压到目录" required>
          <Input.Group compact>
            <Input
              v-model:value="importFolder"
              placeholder="绝对路径"
              style="width: calc(100% - 72px)"
            />
            <Button @click="importFolderPickerOpen = true">浏览</Button>
          </Input.Group>
        </Form.Item>
      </Form>
    </Modal>
    <PathPickerModal
      v-model:open="importFolderPickerOpen"
      :initial-path="importFolder"
      mode="dir"
      title="选择导入目标目录"
      @select="(p) => (importFolder = p)"
    />
  </Page>
</template>

<style scoped>
.panel-title {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  opacity: 0.5;
}

.nav-item--active {
  background: hsl(var(--primary) / 12%);
  color: hsl(var(--primary));
}
</style>
