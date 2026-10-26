<script lang="ts" setup>
import { computed, ref, watch } from 'vue';

import { Button, Select, Table, message } from 'ant-design-vue';

import { type WorkflowNodeDef, workflowApi } from '#/api/workflow';

const props = defineProps<{
  files: string[];
  nodeRules: Record<string, string[]>;
}>();

const emit = defineEmits<{ save: [rules: Record<string, string[]>] }>();

const nodes = ref<WorkflowNodeDef[]>([]);
const draft = ref<Record<string, string[]>>({});
const saving = ref(false);

const fileOptions = computed(() =>
  props.files.map((file) => ({ label: file, value: file })),
);

const tableData = computed(() =>
  nodes.value.map((node) => ({
    key: node.id,
    id: node.id,
    name: node.name,
    rules: draft.value[node.id] || [],
  })),
);

watch(
  () => props.nodeRules,
  (value) => {
    draft.value = Object.fromEntries(
      Object.entries(value || {}).map(([k, v]) => [k, [...v]]),
    );
  },
  { immediate: true, deep: true },
);

async function loadNodes() {
  const data = await workflowApi.getNodes();
  nodes.value = data.nodes || [];
}

function updateNodeRules(nodeId: string, values: string[]) {
  draft.value = { ...draft.value, [nodeId]: values };
}

async function handleSave() {
  saving.value = true;
  try {
    const cleaned: Record<string, string[]> = {};
    for (const [nodeId, rules] of Object.entries(draft.value)) {
      const filtered = rules.filter(Boolean);
      if (filtered.length) cleaned[nodeId] = filtered;
    }
    emit('save', cleaned);
  } catch (e) {
    message.error(String(e));
  } finally {
    saving.value = false;
  }
}

loadNodes();
</script>

<template>
  <div>
    <div class="mb-3 flex items-center justify-between">
      <span class="section-label">节点规则配置</span>
      <Button :loading="saving" size="small" type="primary" @click="handleSave">
        保存节点规则
      </Button>
    </div>
    <Table
      :columns="[
        { title: '流程节点', dataIndex: 'name', width: 180 },
        { title: '注入规则（可多选）', dataIndex: 'rules' },
      ]"
      :data-source="tableData"
      :pagination="false"
      bordered
      size="small"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.dataIndex === 'rules'">
          <Select
            :options="fileOptions"
            :value="record.rules"
            allow-clear
            class="w-full"
            mode="multiple"
            placeholder="选择 .md 规则文件"
            @change="(v) => updateNodeRules(record.id, (v as string[]) || [])"
          />
        </template>
      </template>
    </Table>
    <p v-if="!files.length" class="mt-2 text-xs opacity-45">
      当前目录无 .md 文件，请先添加规则文件或检查目录路径。
    </p>
  </div>
</template>

<style scoped>
.section-label {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  opacity: 0.45;
}
</style>
