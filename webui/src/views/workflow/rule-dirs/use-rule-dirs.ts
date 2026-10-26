import { computed, onMounted, ref } from 'vue';

import { Modal, message } from 'ant-design-vue';

import {
  type ProjectBinding,
  type RuleSetItem,
  workflowApi,
} from '#/api/workflow';

export function useRuleDirs() {
  const ruleSets = ref<RuleSetItem[]>([]);
  const projects = ref<ProjectBinding[]>([]);
  const loading = ref(false);
  const selectedId = ref('');
  const bindModalOpen = ref(false);
  const createModalOpen = ref(false);
  const files = ref<string[]>([]);

  const selectedRuleSet = computed(
    () => ruleSets.value.find((item) => item.rule_set_id === selectedId.value) || null,
  );

  async function loadProjects() {
    const data = await workflowApi.getProjects();
    projects.value = data.projects || [];
  }

  async function loadRuleSets() {
    const data = await workflowApi.getRuleSets();
    ruleSets.value = data.rule_sets || data.rule_dirs || [];
    if (!selectedId.value && ruleSets.value.length) {
      selectedId.value = ruleSets.value[0]!.rule_set_id;
    } else if (
      selectedId.value &&
      !ruleSets.value.some((item) => item.rule_set_id === selectedId.value)
    ) {
      selectedId.value = ruleSets.value[0]?.rule_set_id || '';
    }
  }

  async function loadFiles(path: string) {
    try {
      const data = await workflowApi.getRuleFiles(path);
      files.value = data.files || [];
    } catch {
      files.value = [];
    }
  }

  async function refreshAll() {
    loading.value = true;
    try {
      await Promise.all([loadProjects(), loadRuleSets()]);
      const current = selectedRuleSet.value;
      if (current?.resolved_path) {
        await loadFiles(current.resolved_path);
      } else {
        files.value = [];
      }
    } catch (e) {
      message.error(String(e));
    } finally {
      loading.value = false;
    }
  }

  function selectRuleSet(ruleSetId: string) {
    selectedId.value = ruleSetId;
    const hit = ruleSets.value.find((item) => item.rule_set_id === ruleSetId);
    if (hit?.resolved_path) loadFiles(hit.resolved_path);
  }

  function openBindModal() {
    bindModalOpen.value = true;
  }

  function openCreateModal() {
    createModalOpen.value = true;
  }

  async function onBindSaved() {
    await refreshAll();
  }

  async function saveNodeRules(nodeRules: Record<string, string[]>) {
    if (!selectedRuleSet.value) return;
    loading.value = true;
    try {
      await workflowApi.updateRuleSet(selectedRuleSet.value.rule_set_id, { node_rules: nodeRules });
      message.success('节点规则已保存，已同步到绑定项目');
      await refreshAll();
    } catch (e) {
      message.error(String(e));
    } finally {
      loading.value = false;
    }
  }

  function confirmDelete() {
    if (!selectedRuleSet.value) return;
    Modal.confirm({
      title: '删除规则目录配置？',
      content: '仅删除配置记录，不会删除磁盘上的 MD 文件；已绑定项目不会被自动解绑。',
      okType: 'danger',
      okText: '删除',
      onOk: async () => {
        await workflowApi.deleteRuleSet(selectedRuleSet.value!.rule_set_id);
        message.success('已删除');
        selectedId.value = '';
        await refreshAll();
      },
    });
  }

  onMounted(async () => {
    await refreshAll();
  });

  return {
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
  };
}
