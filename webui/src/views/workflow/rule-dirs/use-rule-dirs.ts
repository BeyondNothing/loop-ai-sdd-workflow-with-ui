import { computed, onMounted, ref } from 'vue';

import { message } from 'ant-design-vue';

import {
  type ProjectBinding,
  type RuleDirCatalogItem,
  workflowApi,
} from '#/api/workflow';

export function useRuleDirs() {
  const ruleDirs = ref<RuleDirCatalogItem[]>([]);
  const projects = ref<ProjectBinding[]>([]);
  const loading = ref(false);
  const selectedPath = ref('');
  const bindModalOpen = ref(false);
  const files = ref<string[]>([]);

  const selectedDir = computed(
    () => ruleDirs.value.find((d) => d.resolved_path === selectedPath.value) || null,
  );

  async function loadProjects() {
    const data = await workflowApi.getProjects();
    projects.value = data.projects || [];
  }

  async function loadRuleDirs() {
    const data = await workflowApi.getRuleDirs();
    ruleDirs.value = data.rule_dirs || [];
    if (!selectedPath.value && ruleDirs.value.length) {
      selectedPath.value = ruleDirs.value[0]!.resolved_path;
    } else if (
      selectedPath.value &&
      !ruleDirs.value.some((d) => d.resolved_path === selectedPath.value)
    ) {
      selectedPath.value = ruleDirs.value[0]?.resolved_path || '';
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
      await Promise.all([loadProjects(), loadRuleDirs()]);
      if (selectedPath.value) {
        await loadFiles(selectedPath.value);
      }
    } catch (e) {
      message.error(String(e));
    } finally {
      loading.value = false;
    }
  }

  function selectDir(path: string) {
    selectedPath.value = path;
    loadFiles(path);
  }

  function openBindModal() {
    bindModalOpen.value = true;
  }

  async function onBindSaved() {
    await refreshAll();
  }

  onMounted(async () => {
    await refreshAll();
  });

  return {
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
  };
}
