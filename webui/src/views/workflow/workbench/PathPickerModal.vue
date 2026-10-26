<script lang="ts" setup>
import { computed, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Button, Empty, Modal, Space, Spin, Tag, Tooltip } from 'ant-design-vue';

import { workflowApi } from '#/api/workflow';

const open = defineModel<boolean>('open', { default: false });
const props = defineProps<{
  fileExt?: string;
  initialPath?: string;
  mode?: 'file' | 'dir';
  title?: string;
}>();

const emit = defineEmits<{ select: [path: string] }>();

const loading = ref(false);
const currentPath = ref('');
const dirs = ref<Array<{ name: string; path: string }>>([]);
const files = ref<Array<{ name: string; path: string }>>([]);
const roots = ref<Array<{ name: string; path: string }>>([]);
const activeRoot = ref('');

const pathSegments = computed(() => {
  const path = currentPath.value;
  if (!path) return [];
  const parts = path.split('/').filter(Boolean);
  const segments: Array<{ name: string; path: string }> = [];
  let acc = path.startsWith('/') ? '' : '';
  for (const part of parts) {
    acc = acc ? `${acc}/${part}` : `/${part}`;
    segments.push({ name: part, path: acc });
  }
  return segments;
});

const itemCount = computed(() => dirs.value.length + (props.mode === 'dir' ? 0 : files.value.length));

async function loadDir(path: string) {
  loading.value = true;
  try {
    const data = await workflowApi.listDir(
      path,
      props.mode !== 'dir',
      props.fileExt || '',
    );
    currentPath.value = data.path;
    dirs.value = data.dirs;
    files.value = data.files;
    const hit = roots.value.find((r) => data.path.startsWith(r.path));
    activeRoot.value = hit?.path || '';
  } finally {
    loading.value = false;
  }
}

async function openPicker() {
  const rootsData = await workflowApi.getFsRoots();
  roots.value = rootsData.roots;
  const start = props.initialPath?.trim() || roots.value[0]?.path || '';
  await loadDir(start);
}

function goUp() {
  const path = currentPath.value;
  const parent = path.replace(/[/\\][^/\\]+$/, '') || '/';
  if (parent !== path) loadDir(parent);
}

function selectPath(path: string) {
  emit('select', path);
  open.value = false;
}

function closeModal() {
  open.value = false;
}

watch(open, (v) => {
  if (v) openPicker();
});
</script>

<template>
  <Modal
    v-model:open="open"
    :body-style="{ padding: 0, overflow: 'hidden' }"
    :footer="null"
    :title="title || (mode === 'dir' ? '选择文件夹' : '选择文件')"
    :width="620"
    centered
    destroy-on-close
    wrap-class-name="path-picker-modal-wrap"
  >
    <div class="picker">
      <!-- 快捷根目录 -->
      <div class="picker__toolbar">
        <span class="picker__label">快捷入口</span>
        <div class="picker__roots">
          <button
            v-for="r in roots"
            :key="r.path"
            :class="{ 'picker__root--active': activeRoot === r.path }"
            class="picker__root"
            type="button"
            @click="loadDir(r.path)"
          >
            <IconifyIcon
              :icon="
                r.name === 'Home'
                  ? 'lucide:home'
                  : r.name === 'Root'
                    ? 'lucide:hard-drive'
                    : 'lucide:folder-root'
              "
              class="size-3.5 shrink-0 opacity-60"
            />
            {{ r.name }}
          </button>
        </div>
      </div>

      <!-- 路径导航 -->
      <div class="picker__nav">
        <Tooltip title="上级目录">
          <Button :disabled="!pathSegments.length" size="small" @click="goUp">
            <IconifyIcon icon="lucide:arrow-up" />
          </Button>
        </Tooltip>
        <div class="picker__breadcrumb">
          <button
            v-for="seg in pathSegments"
            :key="seg.path"
            class="picker__crumb"
            type="button"
            @click="loadDir(seg.path)"
          >
            {{ seg.name }}
          </button>
          <span v-if="!pathSegments.length" class="picker__crumb picker__crumb--muted">
            /
          </span>
        </div>
        <Tag class="m-0 shrink-0" color="blue">{{ itemCount }} 项</Tag>
      </div>

      <!-- 可滚动列表区（不撑开浏览器） -->
      <Spin :spinning="loading">
        <div class="picker__scroll">
          <template v-if="dirs.length">
            <div class="picker__section-title">
              <IconifyIcon icon="lucide:folder" class="size-3.5 opacity-50" />
              文件夹
              <span class="opacity-40">({{ dirs.length }})</span>
            </div>
            <button
              v-for="item in dirs"
              :key="item.path"
              class="picker__row"
              type="button"
              @click="loadDir(item.path)"
            >
              <IconifyIcon icon="lucide:folder" class="picker__row-icon" />
              <span class="picker__row-name">{{ item.name }}</span>
              <IconifyIcon class="picker__row-arrow opacity-30" icon="lucide:chevron-right" />
            </button>
          </template>

          <template v-if="mode !== 'dir'">
            <div v-if="files.length" class="picker__section-title picker__section-title--files">
              <IconifyIcon icon="lucide:file-text" class="size-3.5 opacity-50" />
              文件
              <span class="opacity-40">({{ files.length }})</span>
            </div>
            <button
              v-for="item in files"
              :key="item.path"
              class="picker__row picker__row--file"
              type="button"
              @click="selectPath(item.path)"
            >
              <IconifyIcon icon="lucide:file-text" class="picker__row-icon" />
              <span class="picker__row-name">{{ item.name }}</span>
            </button>
          </template>

          <Empty
            v-if="!dirs.length && (mode === 'dir' || !files.length)"
            :image-style="{ height: 48 }"
            class="my-6"
            description="此目录为空"
          />
        </div>
      </Spin>

      <!-- 底栏 -->
      <div class="picker__footer">
        <Tooltip :title="currentPath">
          <span class="picker__current-path">{{ currentPath || '—' }}</span>
        </Tooltip>
        <Space>
          <Button @click="closeModal">取消</Button>
          <Button
            v-if="mode === 'dir'"
            type="primary"
            @click="selectPath(currentPath)"
          >
            <IconifyIcon class="mr-1" icon="lucide:check" />
            选择此目录
          </Button>
        </Space>
      </div>
    </div>
  </Modal>
</template>

<style scoped>
.picker {
  display: flex;
  flex-direction: column;
  max-height: min(520px, calc(100vh - 160px));
}

.picker__toolbar {
  flex-shrink: 0;
  padding: 12px 16px 8px;
  border-bottom: 1px solid hsl(var(--border) / 50%);
}

.picker__label {
  display: block;
  margin-bottom: 8px;
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  opacity: 0.4;
}

.picker__roots {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.picker__root {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  font-size: 12px;
  color: inherit;
  cursor: pointer;
  background: hsl(var(--muted) / 30%);
  border: 1px solid hsl(var(--border) / 60%);
  border-radius: 6px;
  transition: all 0.15s;
}

.picker__root:hover {
  background: hsl(var(--muted) / 50%);
}

.picker__root--active {
  color: hsl(var(--primary));
  background: hsl(var(--primary) / 10%);
  border-color: hsl(var(--primary) / 40%);
}

.picker__nav {
  display: flex;
  flex-shrink: 0;
  gap: 8px;
  align-items: center;
  padding: 8px 16px;
  border-bottom: 1px solid hsl(var(--border) / 50%);
}

.picker__breadcrumb {
  display: flex;
  flex: 1;
  gap: 2px;
  align-items: center;
  min-width: 0;
  overflow: hidden;
}

.picker__crumb {
  flex-shrink: 0;
  max-width: 120px;
  padding: 2px 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 12px;
  color: hsl(var(--primary));
  white-space: nowrap;
  cursor: pointer;
  background: transparent;
  border: none;
  border-radius: 4px;
}

.picker__crumb:hover {
  background: hsl(var(--muted) / 40%);
}

.picker__crumb:not(:last-child)::after {
  margin-left: 4px;
  color: hsl(var(--foreground) / 30%);
  content: '/';
}

.picker__crumb--muted {
  color: hsl(var(--foreground) / 45%);
}

.picker__scroll {
  flex: 1;
  min-height: 200px;
  max-height: 320px;
  padding: 4px 8px 8px;
  overflow-x: hidden;
  overflow-y: auto;
}

.picker__section-title {
  display: flex;
  gap: 6px;
  align-items: center;
  padding: 8px 8px 4px;
  font-size: 11px;
  font-weight: 500;
  opacity: 0.5;
}

.picker__section-title--files {
  padding-top: 12px;
  margin-top: 4px;
  border-top: 1px dashed hsl(var(--border) / 50%);
}

.picker__row {
  display: flex;
  gap: 10px;
  align-items: center;
  width: 100%;
  padding: 8px 10px;
  font-size: 13px;
  text-align: left;
  cursor: pointer;
  background: transparent;
  border: none;
  border-radius: 6px;
  transition: background 0.12s;
}

.picker__row:hover {
  background: hsl(var(--muted) / 40%);
}

.picker__row-icon {
  flex-shrink: 0;
  width: 16px;
  height: 16px;
  opacity: 0.55;
}

.picker__row-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.picker__row-arrow {
  flex-shrink: 0;
  width: 14px;
  height: 14px;
}

.picker__row--file .picker__row-icon {
  opacity: 0.45;
}

.picker__footer {
  display: flex;
  flex-shrink: 0;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  border-top: 1px solid hsl(var(--border) / 50%);
}

.picker__current-path {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  font-family: ui-monospace, monospace;
  font-size: 11px;
  white-space: nowrap;
  opacity: 0.45;
}
</style>

<style>
/* 防止 Modal 撑开页面滚动 */
.path-picker-modal-wrap .ant-modal {
  max-width: calc(100vw - 32px);
}

.path-picker-modal-wrap .ant-modal-content {
  overflow: hidden;
}
</style>
