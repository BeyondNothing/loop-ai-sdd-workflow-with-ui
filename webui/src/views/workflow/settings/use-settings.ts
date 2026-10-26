import { onMounted, ref } from 'vue';

import { message } from 'ant-design-vue';

import { type AiToolOption, type SystemInfo, workflowApi } from '#/api/workflow';

export function useSettings() {
  const loading = ref(false);
  const saving = ref(false);
  const defaultTool = ref('omp');
  const tools = ref<AiToolOption[]>([]);
  const systemInfo = ref<SystemInfo | null>(null);

  async function load() {
    loading.value = true;
    try {
      const [config, info] = await Promise.all([
        workflowApi.getSystemConfig(),
        workflowApi.getSystemInfo(),
      ]);
      defaultTool.value = config.default_tool || 'omp';
      tools.value = config.available_tools || [];
      systemInfo.value = info;
    } catch (e) {
      message.error(String(e));
    } finally {
      loading.value = false;
    }
  }

  async function save() {
    saving.value = true;
    try {
      const config = await workflowApi.updateSystemConfig({
        default_tool: defaultTool.value,
      });
      defaultTool.value = config.default_tool;
      tools.value = config.available_tools || tools.value;
      message.success('系统配置已保存');
    } catch (e) {
      message.error(String(e));
    } finally {
      saving.value = false;
    }
  }

  onMounted(load);

  return {
    defaultTool,
    loading,
    save,
    saving,
    systemInfo,
    tools,
  };
}
