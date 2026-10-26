<script lang="ts" setup>
import { computed, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Checkbox, Empty, List, Modal, Tag, message } from 'ant-design-vue';

import { type ProjectBinding, type RuleDirCatalogItem, workflowApi } from '#/api/workflow';

const open = defineModel<boolean>('open', { default: false });

const props = defineProps<{
  ruleDir: RuleDirCatalogItem | null;
  projects: ProjectBinding[];
}>();

const emit = defineEmits<{ saved: [] }>();

const saving = ref(false);
const checkedIds = ref<string[]>([]);
const files = ref<string[]>([]);

const boundCount = computed(() => checkedIds.value.length);

watch(open, async (visible) => {
  if (!visible || !props.ruleDir) return;
  checkedIds.value = props.ruleDir.projects.map((p) => p.project_id);
  try {
    const data = await workflowApi.getRuleFiles(props.ruleDir.resolved_path);
    files.value = data.files || [];
  } catch {
    files.value = props.ruleDir.files || [];
  }
});

async function handleOk() {
  if (!props.ruleDir) return;
  saving.value = true;
  try {
    await workflowApi.bindRuleDir(props.ruleDir.resolved_path, checkedIds.value);
    message.success('规则目录绑定已更新');
    open.value = false;
    emit('saved');
  } catch (e) {
    message.error(String(e));
  } finally {
    saving.value = false;
  }
}

function toggleProject(projectId: string, checked: boolean) {
  if (checked) {
    if (!checkedIds.value.includes(projectId)) {
      checkedIds.value = [...checkedIds.value, projectId];
    }
  } else {
    checkedIds.value = checkedIds.value.filter((id) => id !== projectId);
  }
}
</script>

<template>
  <Modal
    v-model:open="open"
    :confirm-loading="saving"
    :title="ruleDir ? '规则目录绑定' : '规则目录'"
    ok-text="保存绑定"
    width="640"
    @ok="handleOk"
  >
    <template v-if="ruleDir">
      <div class="mb-3 rounded-md border border-border/60 bg-muted/20 px-3 py-2">
        <div class="mb-1 flex items-center gap-2 text-sm font-medium">
          <IconifyIcon icon="lucide:book-open" class="opacity-60" />
          {{ ruleDir.ai_rules_dir }}
        </div>
        <div class="break-all text-xs opacity-50">{{ ruleDir.resolved_path }}</div>
        <div class="mt-2 flex gap-2">
          <Tag class="m-0">{{ ruleDir.file_count }} 个规则文件</Tag>
          <Tag class="m-0" :color="boundCount ? 'blue' : 'default'">
            已绑定 {{ boundCount }} 个项目
          </Tag>
        </div>
      </div>

      <div class="mb-4">
        <div class="mb-2 text-xs font-medium uppercase tracking-wide opacity-50">
          绑定项目
        </div>
        <div v-if="projects.length" class="max-h-[200px] space-y-1 overflow-y-auto">
          <div
            v-for="p in projects"
            :key="p.project_id"
            class="flex items-center gap-2 rounded px-2 py-1.5 hover:bg-muted/30"
          >
            <Checkbox
              :checked="checkedIds.includes(p.project_id)"
              @change="(e) => toggleProject(p.project_id, e.target.checked)"
            />
            <span class="flex-1 truncate text-sm">{{ p.name }}</span>
            <span class="truncate text-xs opacity-40">{{ p.ai_rules_dir }}</span>
          </div>
        </div>
        <Empty v-else description="暂无项目可绑定" />
      </div>

      <div>
        <div class="mb-2 text-xs font-medium uppercase tracking-wide opacity-50">
          规则文件
        </div>
        <List
          v-if="files.length"
          :data-source="files"
          bordered
          class="max-h-[160px] overflow-y-auto"
          size="small"
        >
          <template #renderItem="{ item }">
            <List.Item class="py-1 text-xs">{{ item }}</List.Item>
          </template>
        </List>
        <Empty v-else :image-style="{ height: 32 }" description="目录中无 .md 规则文件" />
      </div>
    </template>
  </Modal>
</template>
