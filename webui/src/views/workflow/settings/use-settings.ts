import { computed, onMounted, reactive, ref } from 'vue';

import { Modal, message } from 'ant-design-vue';

import {
  type AiToolOption,
  type ConfidenceNodeRules,
  type McpServerItem,
  type NodeRuntimeRow,
  type ProjectBinding,
  type SkillAgentItem,
  type SystemInfo,
  workflowApi,
} from '#/api/workflow';

export function useSettings() {
  const loading = ref(false);
  const saving = ref(false);
  const syncing = ref(false);
  const activeTab = ref('tool');
  const mcpModalOpen = ref(false);
  const confidencePath = ref('');
  const confidenceEnginePath = ref('');
  const confidenceNodes = ref<ConfidenceNodeRules[]>([]);
  const confidenceEngineNodes = ref<ConfidenceNodeRules[]>([]);
  const confidenceNodeId = ref('');
  const mcpEditingName = ref('');
  const mcpForm = reactive({
    name: '',
    enabled: true,
    command: '',
    wrapper: '',
    url: '',
    argsText: '',
    description: '',
  });

  const defaultTool = ref('omp');
  const tools = ref<AiToolOption[]>([]);
  const systemInfo = ref<SystemInfo | null>(null);

  const projects = ref<ProjectBinding[]>([]);
  const selectedProjectId = ref('');

  const nodeDefaults = reactive({ tool: 'omp', model: '', docs_dir: 'spec' });
  const nodeRows = ref<NodeRuntimeRow[]>([]);
  const nodeAppRoot = ref('');

  const mcpServers = ref<McpServerItem[]>([]);
  const mcpPath = ref('');

  const skillName = ref('start-workflow');
  const skillAgents = ref<SkillAgentItem[]>([]);
  const selectedSkillAgents = ref<string[]>([]);
  const probing = ref(false);
  const probeResult = ref<Awaited<
    ReturnType<typeof workflowApi.probeConnectivity>
  > | null>(null);

  const projectOptions = computed(() =>
    projects.value.map((p) => ({ label: `${p.name} (${p.project_id})`, value: p.project_id })),
  );

  const toolSelectOptions = computed(() =>
    tools.value.map((t) => ({ label: `${t.name} (${t.id})`, value: t.id })),
  );

  async function loadProjects() {
    const data = await workflowApi.getProjects();
    projects.value = data.projects || [];
    if (!selectedProjectId.value && projects.value.length) {
      selectedProjectId.value = projects.value[0]!.project_id;
    }
  }

  async function loadBase() {
    const [config, info] = await Promise.all([
      workflowApi.getSystemConfig(),
      workflowApi.getSystemInfo(),
    ]);
    defaultTool.value = config.default_tool || 'omp';
    tools.value = config.available_tools || [];
    systemInfo.value = info;
  }

  async function loadNodeSettings() {
    const data = await workflowApi.getNodeSettings(selectedProjectId.value || undefined);
    nodeAppRoot.value = data.app_root;
    nodeDefaults.tool = data.defaults?.tool || 'omp';
    nodeDefaults.model = data.defaults?.model || '';
    nodeDefaults.docs_dir = data.docs_dir || 'spec';
    nodeRows.value = (data.nodes || []).map((n) => ({ ...n }));
    if (data.available_tools?.length) {
      tools.value = data.available_tools;
    }
  }

  async function loadMcp() {
    const data = await workflowApi.getMcpSettings();
    mcpPath.value = data.path;
    mcpServers.value = (data.servers || []).map((s) => ({ ...s }));
  }

  async function loadSkills() {
    const data = await workflowApi.getSkillSettings(selectedProjectId.value || undefined);
    skillName.value = data.skill_name;
    skillAgents.value = data.agents || [];
    selectedSkillAgents.value = (data.agents || [])
      .filter((a) => a.installed)
      .map((a) => a.agent);
    if (!selectedSkillAgents.value.length) {
      selectedSkillAgents.value = (data.agents || []).map((a) => a.agent);
    }
  }

  async function loadConfidenceRules() {
    const data = await workflowApi.getConfidenceRules(
      selectedProjectId.value || undefined,
    );
    confidencePath.value = data.path || '';
    confidenceEnginePath.value = data.engine_path || '';
    confidenceEngineNodes.value = data.engine_nodes || [];
    // 编辑业务扩展；若业务为空则用引擎节点骨架便于添加扩展规则
    const business = (data.nodes || []).map((n) => ({
      ...n,
      high_confidence_rules: [...(n.high_confidence_rules || [])],
      low_confidence_rules: [...(n.low_confidence_rules || [])],
    }));
    if (business.length) {
      confidenceNodes.value = business;
    } else {
      confidenceNodes.value = (data.engine_nodes || []).map((n) => ({
        node_id: n.node_id,
        description: n.description || '',
        high_confidence_rules: [],
        low_confidence_rules: [],
      }));
    }
    if (
      !confidenceNodeId.value ||
      !confidenceNodes.value.some((n) => n.node_id === confidenceNodeId.value)
    ) {
      confidenceNodeId.value = confidenceNodes.value[0]?.node_id || '';
    }
  }

  const confidenceNodeOptions = computed(() =>
    confidenceNodes.value.map((n) => ({
      label: `${n.description || n.node_id} (${n.node_id})`,
      value: n.node_id,
    })),
  );

  const selectedConfidenceNode = computed(() =>
    confidenceNodes.value.find((n) => n.node_id === confidenceNodeId.value),
  );

  const engineRulesForSelected = computed(() =>
    confidenceEngineNodes.value.find((n) => n.node_id === confidenceNodeId.value),
  );

  function addConfidenceRule(kind: 'high' | 'low') {
    const node = selectedConfidenceNode.value;
    if (!node) return;
    const list =
      kind === 'high' ? node.high_confidence_rules : node.low_confidence_rules;
    list.push({ condition: '', reason: '' });
  }

  function removeConfidenceRule(kind: 'high' | 'low', index: number) {
    const node = selectedConfidenceNode.value;
    if (!node) return;
    const list =
      kind === 'high' ? node.high_confidence_rules : node.low_confidence_rules;
    list.splice(index, 1);
  }

  async function saveConfidenceRules() {
    saving.value = true;
    try {
      const data = await workflowApi.updateConfidenceRules({
        project_id: selectedProjectId.value || undefined,
        nodes: confidenceNodes.value.map((n) => ({
          node_id: n.node_id,
          description: n.description,
          high_confidence_rules: (n.high_confidence_rules || []).filter((r) =>
            r.condition.trim(),
          ),
          low_confidence_rules: (n.low_confidence_rules || []).filter((r) =>
            r.condition.trim(),
          ),
        })),
      });
      confidencePath.value = data.path;
      confidenceNodes.value = (data.nodes || []).map((n) => ({
        ...n,
        high_confidence_rules: [...(n.high_confidence_rules || [])],
        low_confidence_rules: [...(n.low_confidence_rules || [])],
      }));
      confidenceEngineNodes.value = data.engine_nodes || [];
      message.success('置信度扩展规则已写入业务 suggestion-confidence-rules.yaml');
    } catch (e) {
      message.error(String(e));
    } finally {
      saving.value = false;
    }
  }

  async function loadAll() {
    loading.value = true;
    try {
      await loadProjects();
      await loadBase();
      await Promise.all([
        loadNodeSettings(),
        loadMcp(),
        loadSkills(),
        loadConfidenceRules(),
      ]);
    } catch (e) {
      message.error(String(e));
    } finally {
      loading.value = false;
    }
  }

  async function onProjectChange() {
    loading.value = true;
    probeResult.value = null;
    try {
      await Promise.all([loadNodeSettings(), loadSkills(), loadConfidenceRules()]);
    } catch (e) {
      message.error(String(e));
    } finally {
      loading.value = false;
    }
  }

  async function saveDefaultTool() {
    saving.value = true;
    try {
      const config = await workflowApi.updateSystemConfig({
        default_tool: defaultTool.value,
      });
      defaultTool.value = config.default_tool;
      tools.value = config.available_tools || tools.value;
      message.success('默认工具已保存');
    } catch (e) {
      message.error(String(e));
    } finally {
      saving.value = false;
    }
  }

  async function saveNodeSettings() {
    saving.value = true;
    try {
      const data = await workflowApi.updateNodeSettings({
        project_id: selectedProjectId.value || undefined,
        docs_dir: nodeDefaults.docs_dir,
        defaults: { tool: nodeDefaults.tool, model: nodeDefaults.model },
        nodes: nodeRows.value.map((n) => ({
          id: n.id,
          tool: n.tool,
          model: n.model,
          recommendation_threshold: n.recommendation_threshold,
        })),
      });
      nodeRows.value = (data.nodes || []).map((n) => ({ ...n }));
      message.success('节点配置已写入业务 sdd-loop-workflow-config/workflow.yaml');
    } catch (e) {
      message.error(String(e));
    } finally {
      saving.value = false;
    }
  }

  async function saveMcp() {
    saving.value = true;
    try {
      const data = await workflowApi.updateMcpSettings(
        mcpServers.value.map((s) => ({ name: s.name, enabled: s.enabled })),
      );
      mcpServers.value = (data.servers || []).map((s) => ({ ...s }));
      message.success('MCP 开关已保存到 config/mcp/servers.json');
    } catch (e) {
      message.error(String(e));
    } finally {
      saving.value = false;
    }
  }

  function openMcpModal(server?: McpServerItem) {
    mcpEditingName.value = server?.name || '';
    mcpForm.name = server?.name || '';
    mcpForm.enabled = server?.enabled ?? true;
    mcpForm.command = server?.command || '';
    mcpForm.wrapper = server?.wrapper || '';
    mcpForm.url = server?.url || '';
    mcpForm.argsText = (server?.args || []).join(' ');
    mcpForm.description = server?.description || '';
    mcpModalOpen.value = true;
  }

  async function submitMcpModal() {
    const name = mcpForm.name.trim();
    if (!name) {
      message.warning('请填写服务器名称');
      return;
    }
    if (!mcpForm.command.trim() && !mcpForm.wrapper.trim() && !mcpForm.url.trim()) {
      message.warning('请至少填写 command / wrapper / url 之一');
      return;
    }
    saving.value = true;
    try {
      // 若改名：先写新条目再删旧条目
      const data = await workflowApi.upsertMcpServer({
        name,
        enabled: mcpForm.enabled,
        command: mcpForm.command.trim(),
        wrapper: mcpForm.wrapper.trim(),
        url: mcpForm.url.trim(),
        args: mcpForm.argsText
          .split(/\s+/)
          .map((s) => s.trim())
          .filter(Boolean),
        description: mcpForm.description.trim(),
      });
      if (mcpEditingName.value && mcpEditingName.value !== name) {
        await workflowApi.deleteMcpServer(mcpEditingName.value);
        const refreshed = await workflowApi.getMcpSettings();
        mcpServers.value = (refreshed.servers || []).map((s) => ({ ...s }));
      } else {
        mcpServers.value = (data.servers || []).map((s) => ({ ...s }));
      }
      mcpModalOpen.value = false;
      message.success(mcpEditingName.value ? 'MCP 服务器已更新' : 'MCP 服务器已新增');
    } catch (e) {
      message.error(String(e));
    } finally {
      saving.value = false;
    }
  }

  function deleteMcp(name: string) {
    Modal.confirm({
      title: `删除 MCP 服务器「${name}」？`,
      content: '将从 config/mcp/servers.json 移除该定义。',
      okType: 'danger',
      okText: '删除',
      onOk: async () => {
        const data = await workflowApi.deleteMcpServer(name);
        mcpServers.value = (data.servers || []).map((s) => ({ ...s }));
        message.success('已删除');
      },
    });
  }

  async function syncMcp() {
    syncing.value = true;
    try {
      await workflowApi.syncMcpSettings(selectedProjectId.value || undefined);
      message.success('已同步 MCP 到引擎与业务项目（.cursor/.omp/.mcp.json 等）');
    } catch (e) {
      message.error(String(e));
    } finally {
      syncing.value = false;
    }
  }

  async function installSkills() {
    syncing.value = true;
    try {
      const data = await workflowApi.installSkills(
        selectedProjectId.value || undefined,
        selectedSkillAgents.value,
      );
      skillAgents.value = data.skills?.agents || [];
      message.success(`已安装 skill 到 ${data.written?.length || 0} 个目录`);
    } catch (e) {
      message.error(String(e));
    } finally {
      syncing.value = false;
    }
  }

  async function initProject() {
    syncing.value = true;
    try {
      await workflowApi.initProjectSettings(selectedProjectId.value || undefined);
      await Promise.all([
        loadNodeSettings(),
        loadSkills(),
        loadMcp(),
        loadConfidenceRules(),
      ]);
      message.success('已初始化业务配置 + skill + MCP 同步');
    } catch (e) {
      message.error(String(e));
    } finally {
      syncing.value = false;
    }
  }

  async function probeConnectivity() {
    probing.value = true;
    try {
      probeResult.value = await workflowApi.probeConnectivity(
        selectedProjectId.value || undefined,
      );
      if (probeResult.value.ok) {
        message.success('连通探测通过');
      } else {
        message.warning(
          `探测未完全通过：MCP ${probeResult.value.mcp.summary} · Skill ${probeResult.value.skills.summary}`,
        );
      }
    } catch (e) {
      probeResult.value = null;
      message.error(String(e));
    } finally {
      probing.value = false;
    }
  }

  onMounted(loadAll);

  return {
    activeTab,
    addConfidenceRule,
    confidenceEnginePath,
    confidenceNodeId,
    confidenceNodeOptions,
    confidencePath,
    defaultTool,
    deleteMcp,
    engineRulesForSelected,
    initProject,
    installSkills,
    loading,
    mcpEditingName,
    mcpForm,
    mcpModalOpen,
    mcpPath,
    mcpServers,
    nodeAppRoot,
    nodeDefaults,
    nodeRows,
    onProjectChange,
    openMcpModal,
    probeConnectivity,
    probeResult,
    probing,
    projectOptions,
    projects,
    removeConfidenceRule,
    saveConfidenceRules,
    saveDefaultTool,
    saveMcp,
    saveNodeSettings,
    saving,
    selectedConfidenceNode,
    selectedProjectId,
    selectedSkillAgents,
    skillAgents,
    skillName,
    submitMcpModal,
    syncMcp,
    syncing,
    systemInfo,
    toolSelectOptions,
    tools,
  };
}
