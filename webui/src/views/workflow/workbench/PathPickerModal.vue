<script lang="ts" setup>
import { ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Breadcrumb, Button, Empty, List, Modal, Space, Spin } from 'ant-design-vue';

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
  const parts = currentPath.value.split('/').filter(Boolean);
  if (parts.length <= 1) return;
  parts.pop();
  loadDir(`/${parts.join('/')}`);
}

function selectPath(path: string) {
  emit('select', path);
  open.value = false;
}

watch(open, (v) => {
  if (v) openPicker();
});
</script>

<template>
  <Modal
    v-model:open="open"
    :title="title || (mode === 'dir' ? '选择文件夹' : '选择文件')"
    :width="560"
    :footer="null"
  >
    <Spin :spinning="loading">
      <div class="mb-2 flex flex-wrap gap-1">
        <Button
          v-for="r in roots"
          :key="r.path"
          size="small"
          type="text"
          @click="loadDir(r.path)"
        >
          {{ r.name }}
        </Button>
      </div>

      <Breadcrumb class="mb-2 text-xs">
        <Breadcrumb.Item>
          <a @click.prevent="goUp">
            <IconifyIcon icon="lucide:arrow-up" class="mr-1 inline" />
            上级
          </a>
        </Breadcrumb.Item>
        <Breadcrumb.Item>{{ currentPath }}</Breadcrumb.Item>
      </Breadcrumb>

      <div v-if="mode === 'dir'" class="mb-2">
        <Button size="small" type="primary" @click="selectPath(currentPath)">
          选择当前文件夹
        </Button>
      </div>

      <List :data-source="dirs" bordered class="mb-2" size="small">
        <template #renderItem="{ item }">
          <List.Item class="cursor-pointer hover:bg-muted/30" @click="loadDir(item.path)">
            <Space>
              <IconifyIcon icon="lucide:folder" class="opacity-60" />
              <span>{{ item.name }}</span>
            </Space>
          </List.Item>
        </template>
        <template #header>文件夹</template>
      </List>

      <List v-if="mode !== 'dir'" :data-source="files" bordered size="small">
        <template #renderItem="{ item }">
          <List.Item class="cursor-pointer hover:bg-muted/30" @click="selectPath(item.path)">
            <Space>
              <IconifyIcon icon="lucide:file-text" class="opacity-60" />
              <span>{{ item.name }}</span>
            </Space>
          </List.Item>
        </template>
        <template #header>文件</template>
        <template #empty>
          <Empty description="此目录无文件" />
        </template>
      </List>
    </Spin>
  </Modal>
</template>
