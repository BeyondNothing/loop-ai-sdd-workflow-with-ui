export type NodeStatus = "queued" | "running" | "completed" | "failed" | "skipped";

export interface WorkflowNodeDef {
  id: string;
  name: string;
  output: string;
  tool: string;
  mode: string;
}

export interface Project {
  project_id: string;
  name: string;
  app_root: string;
  docs_dir: string;
  ai_rules_dir: string;
  node_rules: Record<string, string[]>;
  created_at: string;
  updated_at: string;
}

export interface Task {
  task_id: string;
  task_name: string;
  requirement_prd_path: string;
  requirement_text: string;
  last_run_id?: string;
  created_at: string;
  updated_at: string;
}

export interface WorkflowRun {
  run_id: string;
  project_id: string;
  task_id?: string;
  status: string;
  requirement: string;
  requirement_path: string;
  requirement_name: string;
  tool: string;
  skip_clarification: boolean;
  auto: boolean;
  fresh: boolean;
  headless_all_nodes: boolean;
  docs_dir: string;
  started_at: string;
  updated_at: string;
  ended_at: string;
  result?: Record<string, unknown> | null;
  error: string;
  logs: string[];
  current_node?: string;
  completed_nodes?: string[];
  node_outputs?: Record<string, string>;
}

export interface RunFlags {
  headless: boolean;
  skipClar: boolean;
  auto: boolean;
}
