<script lang="ts" setup>
import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Empty,
  List,
  Space,
  Tabs,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import RuleBindModal from '../workbench/RuleBindModal.vue';
import NodeRulesEditor from './NodeRulesEditor.vue';
import RuleSetCreateModal from './RuleSetCreateModal.vue';
import { useRuleDirs } from './use-rule-dirs';

const {
  bindModalOpen,
  confirmDelete,
  createModalOpen,
  files,
  loading,
  onBindSaved,
  openBindModal,
  openCreateModal,
  projects,
  refreshAll,
  ruleSets,
  saveNodeRules,
  selectRuleSet,
  selectedId,
  selectedRuleSet,
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
