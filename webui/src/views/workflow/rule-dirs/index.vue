<script lang="ts" setup>
import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Empty,
  List,
  Space,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import RuleBindModal from '../workbench/RuleBindModal.vue';
import { useRuleDirs } from './use-rule-dirs';

const {
  bindModalOpen,
  files,
  loading,
  onBindSaved,
  openBindModal,
  projects,
  refreshAll,
  ruleDirs,
  selectDir,
  selectedDir,
  selectedPath,
} = useRuleDirs();
</script>

<template>
  <Page auto-content-height content-class="p-0">
    <div class="flex h-full min-h-0">
      <!-- 规则目录列表 -->
      <aside
        class="flex w-[240px] shrink-0 flex-col border-r border-border bg-sidebar/50"
      >
        <div class="border-b border-border px-3 py-2.5">
          <div class="flex items-center justify-between">
            <span class="panel-title">
              <IconifyIcon icon="lucide:book-open" class="mr-1 inline opacity-50" />
              规则目录
            </span>
            <Tooltip title="刷新">
              <Button :loading="loading" size="small" type="text" @click="refreshAll">
                <IconifyIcon icon="lucide:refresh-cw" class="size-3.5" />
              </Button>
            </Tooltip>
          </div>
        </div>
        <div class="min-h-0 flex-1 overflow-y-auto px-2 py-2">
          <div
            v-for="dir in ruleDirs"
            :key="dir.resolved_path"
            :class="
              dir.resolved_path === selectedPath
                ? 'nav-item--active'
                : 'hover:bg-muted/40'
            "
            class="nav-item mb-0.5 flex cursor-pointer items-center justify-between gap-1 rounded px-2 py-2 transition-colors"
            @click="selectDir(dir.resolved_path)"
          >
            <div class="min-w-0 flex-1">
              <div class="truncate text-sm font-medium">{{ dir.ai_rules_dir }}</div>
              <div class="truncate text-[11px] opacity-40">
                {{ dir.file_count }} 文件
              </div>
            </div>
            <Tag
              class="m-0 shrink-0 text-[10px]"
              :color="dir.projects.length ? 'blue' : 'default'"
            >
              {{ dir.projects.length }}
            </Tag>
          </div>
          <Empty
            v-if="!ruleDirs.length"
            :image-style="{ height: 40 }"
            class="my-4"
            description="暂无规则目录"
          />
        </div>
      </aside>

      <!-- 详情区 -->
      <div class="flex min-w-0 flex-1 flex-col">
        <template v-if="selectedDir">
          <header
            class="flex shrink-0 items-center gap-3 border-b border-border px-4 py-3"
          >
            <IconifyIcon icon="lucide:book-open" class="size-4 opacity-50" />
            <div class="min-w-0 flex-1">
              <div class="text-sm font-medium">{{ selectedDir.ai_rules_dir }}</div>
              <div class="truncate text-xs opacity-40">
                {{ selectedDir.resolved_path }}
              </div>
            </div>
            <Space>
              <Tag :color="selectedDir.exists ? 'success' : 'warning'" class="m-0">
                {{ selectedDir.exists ? '目录存在' : '目录不存在' }}
              </Tag>
              <Button type="primary" @click="openBindModal">
                <IconifyIcon class="mr-1" icon="lucide:link" />
                管理项目绑定
              </Button>
            </Space>
          </header>

          <div class="min-h-0 flex-1 overflow-y-auto p-4">
            <section class="mb-6">
              <div class="section-label">已绑定项目</div>
              <div v-if="selectedDir.projects.length" class="flex flex-wrap gap-2">
                <Tag
                  v-for="p in selectedDir.projects"
                  :key="p.project_id"
                  class="m-0"
                  color="blue"
                >
                  {{ p.name }}
                </Tag>
              </div>
              <Empty
                v-else
                :image-style="{ height: 32 }"
                description="尚未绑定任何项目"
              />
            </section>

            <section>
              <div class="section-label">规则文件</div>
              <List
                v-if="files.length"
                :data-source="files"
                bordered
                class="max-h-[420px] overflow-y-auto"
                size="small"
              >
                <template #renderItem="{ item }">
                  <List.Item class="py-1.5 text-sm">{{ item }}</List.Item>
                </template>
              </List>
              <Empty
                v-else
                :image-style="{ height: 40 }"
                description="目录中无 .md 规则文件"
              />
            </section>
          </div>
        </template>
        <Empty
          v-else
          class="m-auto"
          description="请选择左侧规则目录，或在项目中配置 ai-rules 目录"
        />
      </div>
    </div>

    <RuleBindModal
      v-model:open="bindModalOpen"
      :projects="projects"
      :rule-dir="selectedDir"
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

.section-label {
  margin-bottom: 8px;
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  opacity: 0.45;
}

.nav-item--active {
  background: hsl(var(--primary) / 12%);
  color: hsl(var(--primary));
}
</style>
