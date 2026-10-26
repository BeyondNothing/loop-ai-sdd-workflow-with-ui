import { useEffect, useState } from "react";
import { client } from "../../api/client";
import { useWorkflowStore } from "../../store/workflowStore";
import { RULE_NODE_OPTIONS } from "./TaskModal";

interface Props {
  onClose: () => void;
}

export function RulesModal({ onClose }: Props) {
  const selectedProjectId = useWorkflowStore((s) => s.selectedProjectId);

  const [rulesDir, setRulesDir] = useState("ai-rules");
  const [ruleFiles, setRuleFiles] = useState<string[]>([]);
  const [nodeRules, setNodeRules] = useState<Record<string, string[]>>({});
  const [message, setMessage] = useState("");

  useEffect(() => {
    const load = async () => {
      if (!selectedProjectId) return;
      const data = await client.getRules(selectedProjectId);
      setRulesDir(data.ai_rules_dir || "ai-rules");
      setNodeRules(data.node_rules || {});
      const scanned = await client.scanRuleFiles(selectedProjectId, data.ai_rules_dir || "ai-rules");
      setRuleFiles(scanned.files || []);
    };
    load();
  }, [selectedProjectId]);

  const scan = async () => {
    if (!selectedProjectId) return;
    const data = await client.scanRuleFiles(selectedProjectId, rulesDir.trim() || "ai-rules");
    setRuleFiles(data.files || []);
    setMessage(`已扫描 ${data.files.length} 个 .md 文件`);
  };

  const save = async () => {
    if (!selectedProjectId) return;
    const payload: Record<string, unknown> = {
      ai_rules_dir: rulesDir.trim() || "ai-rules",
      node_rules: {},
    };
    for (const node of RULE_NODE_OPTIONS) {
      const el = document.getElementById(`rule-${node.id}`) as HTMLSelectElement | null;
      payload.node_rules = {
        ...(payload.node_rules as Record<string, string[]>),
        [node.id]: Array.from(el?.selectedOptions || []).map((o) => o.value),
      };
    }
    await client.saveRules(selectedProjectId, payload);
    setMessage("规则已保存");
  };

  return (
    <div className="modal-mask" onClick={onClose}>
      <div className="modal" style={{ width: "min(560px, 96vw)" }} onClick={(e) => e.stopPropagation()}>
        <h3>规则配置</h3>
        <p className="panel-sub">项目级规则目录与节点规则文件映射</p>
        <div className="field">
          <label>规则目录</label>
          <input value={rulesDir} onChange={(e) => setRulesDir(e.target.value)} placeholder="ai-rules" />
        </div>
        <div className="actions">
          <button type="button" className="btn" onClick={scan}>
            扫描文件
          </button>
          <button type="button" className="btn btn-primary" onClick={save}>
            保存规则
          </button>
          <button type="button" className="btn" onClick={onClose}>
            关闭
          </button>
        </div>
        {message && <p className="msg">{message}</p>}
        <div style={{ display: "grid", gap: 10, marginTop: 12 }}>
          {RULE_NODE_OPTIONS.map((node) => (
            <div key={node.id} className="card" style={{ padding: 10 }}>
              <label htmlFor={`rule-${node.id}`}>
                {node.label} ({node.id})
              </label>
              <select
                id={`rule-${node.id}`}
                multiple
                size={5}
                defaultValue={nodeRules[node.id] || []}
                style={{ marginTop: 6 }}
              >
                {ruleFiles.map((f) => (
                  <option key={f} value={f}>
                    {f}
                  </option>
                ))}
              </select>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
