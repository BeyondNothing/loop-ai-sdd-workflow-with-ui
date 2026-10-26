import { create } from "zustand";
import { client } from "../api/client";
import type { Project, RunFlags, Task, WorkflowNodeDef, WorkflowRun } from "../types";

interface WorkflowStore {
  projects: Project[];
  tasksByProject: Record<string, Task[]>;
  runs: WorkflowRun[];
  nodeDefinitions: WorkflowNodeDef[];

  selectedProjectId: string;
  selectedTaskId: string;
  selectedRunId: string;
  selectedRun: WorkflowRun | null;

  leftCollapsed: boolean;
  flags: RunFlags;
  message: string;

  loadInitial: () => Promise<void>;
  loadProjects: () => Promise<void>;
  loadTasks: (projectId: string) => Promise<void>;
  loadRuns: () => Promise<void>;
  loadRunDetail: (runId: string) => Promise<void>;
  loadNodeDefinitions: () => Promise<void>;

  selectProject: (projectId: string) => Promise<void>;
  selectTask: (taskId: string) => void;
  toggleLeftCollapsed: () => void;
  toggleFlag: (key: keyof RunFlags) => void;
  setMessage: (msg: string) => void;

  createProject: (payload: Record<string, string>) => Promise<void>;
  updateProject: (projectId: string, payload: Record<string, string>) => Promise<void>;
  deleteProject: (projectId: string) => Promise<void>;

  createTask: (projectId: string, name: string) => Promise<void>;
  updateTask: (
    projectId: string,
    taskId: string,
    payload: Record<string, string>,
  ) => Promise<void>;
  deleteTask: (projectId: string, taskId: string) => Promise<void>;

  startRun: (payload: {
    taskName: string;
    requirement: string;
    requirementPrdPath: string;
  }) => Promise<void>;
  openArtifact: (nodeId: string) => Promise<void>;
}

export const useWorkflowStore = create<WorkflowStore>((set, get) => ({
  projects: [],
  tasksByProject: {},
  runs: [],
  nodeDefinitions: [],

  selectedProjectId: "",
  selectedTaskId: "",
  selectedRunId: "",
  selectedRun: null,

  leftCollapsed: false,
  flags: { headless: true, skipClar: true, auto: false },
  message: "",

  setMessage: (message) => set({ message }),

  toggleLeftCollapsed: () => set((s) => ({ leftCollapsed: !s.leftCollapsed })),

  toggleFlag: (key) =>
    set((s) => ({
      flags: { ...s.flags, [key]: !s.flags[key] },
    })),

  loadNodeDefinitions: async () => {
    const data = await client.getWorkflowNodes();
    set({ nodeDefinitions: data.nodes || [] });
  },

  loadProjects: async () => {
    const data = await client.getProjects();
    let selectedProjectId = get().selectedProjectId;
    if (!selectedProjectId && data.projects.length) {
      selectedProjectId = data.projects[0].project_id;
    }
    if (
      selectedProjectId &&
      !data.projects.some((p) => p.project_id === selectedProjectId)
    ) {
      selectedProjectId = data.projects[0]?.project_id || "";
    }
    set({ projects: data.projects, selectedProjectId });
    if (selectedProjectId) {
      await get().loadTasks(selectedProjectId);
    }
  },

  loadTasks: async (projectId) => {
    const data = await client.getTasks(projectId);
    set((s) => ({
      tasksByProject: { ...s.tasksByProject, [projectId]: data.tasks || [] },
    }));
  },

  loadRuns: async () => {
    const data = await client.getRuns();
    set({ runs: data.runs || [] });

    const { selectedProjectId, selectedTaskId, selectedRunId, tasksByProject } = get();
    const tasks = tasksByProject[selectedProjectId] || [];
    const task = tasks.find((t) => t.task_id === selectedTaskId);

    if (selectedRunId) {
      const hit = (data.runs || []).find((r) => r.run_id === selectedRunId);
      if (hit) {
        set({ selectedRun: hit, selectedRunId: hit.run_id });
        return;
      }
    }

    if (task?.last_run_id) {
      const hit = (data.runs || []).find((r) => r.run_id === task.last_run_id);
      if (hit) {
        set({ selectedRun: hit, selectedRunId: hit.run_id });
        return;
      }
    }

    set({ selectedRun: null, selectedRunId: "" });
  },

  loadRunDetail: async (runId) => {
    const data = await client.getRun(runId);
    set({ selectedRun: data.run, selectedRunId: runId });
  },

  loadInitial: async () => {
    await get().loadNodeDefinitions();
    await get().loadProjects();
    await get().loadRuns();
  },

  selectProject: async (projectId) => {
    set({
      selectedProjectId: projectId,
      selectedTaskId: "",
      selectedRunId: "",
      selectedRun: null,
    });
    await get().loadTasks(projectId);
    await get().loadRuns();
  },

  selectTask: (taskId) => {
    const { selectedProjectId, tasksByProject, runs } = get();
    const task = (tasksByProject[selectedProjectId] || []).find((t) => t.task_id === taskId);
    if (!task) return;

    let selectedRun: WorkflowRun | null = null;
    let selectedRunId = "";

    if (task.last_run_id) {
      selectedRun = runs.find((r) => r.run_id === task.last_run_id) || null;
      selectedRunId = selectedRun?.run_id || "";
    }
    if (!selectedRun) {
      selectedRun =
        runs.find(
          (r) =>
            r.project_id === selectedProjectId &&
            (r.requirement_name || "") === (task.task_name || ""),
        ) || null;
      selectedRunId = selectedRun?.run_id || "";
    }

    set({ selectedTaskId: taskId, selectedRun, selectedRunId });
  },

  createProject: async (payload) => {
    const data = await client.createProject(payload);
    set({ selectedProjectId: data.project.project_id });
    await get().loadProjects();
  },

  updateProject: async (projectId, payload) => {
    await client.updateProject(projectId, payload);
    set({ selectedProjectId: projectId });
    await get().loadProjects();
  },

  deleteProject: async (projectId) => {
    await client.deleteProject(projectId);
    set({
      selectedProjectId: "",
      selectedTaskId: "",
      selectedRunId: "",
      selectedRun: null,
    });
    await get().loadProjects();
    await get().loadRuns();
  },

  createTask: async (projectId, name) => {
    await client.createTask(projectId, {
      task_name: name,
      requirement_prd_path: "",
      requirement_text: "",
    });
    await get().loadTasks(projectId);
    const tasks = get().tasksByProject[projectId] || [];
    const created = tasks[0];
    if (created) {
      get().selectTask(created.task_id);
    }
  },

  updateTask: async (projectId, taskId, payload) => {
    await client.updateTask(projectId, taskId, payload);
    await get().loadTasks(projectId);
  },

  deleteTask: async (projectId, taskId) => {
    await client.deleteTask(projectId, taskId);
    if (get().selectedTaskId === taskId) {
      set({ selectedTaskId: "", selectedRunId: "", selectedRun: null });
    }
    await get().loadTasks(projectId);
  },

  startRun: async ({ taskName, requirement, requirementPrdPath }) => {
    const { selectedProjectId, selectedTaskId, flags } = get();
    if (!selectedProjectId) throw new Error("请先在左侧选择项目");
    if (!selectedTaskId) throw new Error("请先在中间列新建并选择任务");
    if (!requirement && !requirementPrdPath) {
      throw new Error("请填写需求文本或 PRD 路径");
    }

    if (taskName) {
      await get().updateTask(selectedProjectId, selectedTaskId, {
        task_name: taskName,
        requirement_prd_path: requirementPrdPath,
        requirement_text: requirement,
      });
    }

    const data = await client.startRun({
      project_id: selectedProjectId,
      task_id: selectedTaskId,
      requirement_name: taskName,
      requirement,
      requirement_prd_path: requirementPrdPath,
      tool: "omp",
      skip_clarification: flags.skipClar,
      auto: flags.auto,
      headless_all_nodes: flags.headless,
      fresh: false,
      skip_mcp_setup: false,
    });

    set({
      selectedRunId: data.run.run_id,
      selectedRun: data.run,
      message: `已启动任务: ${data.run.run_id}`,
    });
    await get().loadRuns();
    await get().loadTasks(selectedProjectId);
  },

  openArtifact: async (nodeId) => {
    const { selectedRunId } = get();
    if (!selectedRunId) return;
    const data = await client.openArtifact(selectedRunId, nodeId);
    set({ message: `已打开目录: ${data.opened}` });
  },
}));
