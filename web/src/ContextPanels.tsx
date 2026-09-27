import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity, AlertTriangle, Brain, Check, ChevronDown, ChevronRight,
  Database, FileCheck2, Fingerprint, Network, Plus, Sparkles, X,
} from "lucide-react";
import {
  api, ContextManifest, ExpressionReceipt, PromptProjection, PromptProjectionNode,
  RoleSummary, ScopedMemory, SystemProjection, TurnContext,
} from "./api";

const formatTokens = (value: number) => value >= 1000 ? `${(value / 1000).toFixed(1)}k` : `${value}`;
const ownerLabel = (owner: string) => owner.replaceAll("_", " ");

function OwnerBadge({ owner, children }: { owner: string; children?: React.ReactNode }) {
  return <span className={`owner-badge owner-${owner}`}>{children ?? ownerLabel(owner)}</span>;
}

function Stage({ index, title, owner, summary, children }: {
  index: number; title: string; owner: string; summary: string; children?: React.ReactNode;
}) {
  return <details className={`context-stage stage-${owner}`} open={index < 3}>
    <summary><span className="stage-index">{index}</span><div><strong>{title}</strong><small>{summary}</small></div><OwnerBadge owner={owner} /><ChevronDown size={14} /></summary>
    {children ? <div className="stage-detail">{children}</div> : null}
  </details>;
}

function IdList({ ids, empty = "None supplied" }: { ids: string[]; empty?: string }) {
  if (!ids.length) return <p className="context-empty-inline">{empty}</p>;
  return <div className="context-id-list">{ids.map((id) => <code key={id}>{id}</code>)}</div>;
}

function NodeList({ nodes }: { nodes: PromptProjectionNode[] }) {
  if (!nodes.length) return <p className="context-empty-inline">No records reached this stage.</p>;
  return <div className="context-node-list">{nodes.map((node) => <details key={node.id}>
    <summary><div><strong>{node.label}</strong><small>{node.reason}</small></div><OwnerBadge owner={node.owner}>{node.status}</OwnerBadge></summary>
    <p>{node.content}</p><footer><code>{node.id}</code><span>{node.estimated_tokens} tokens</span></footer>
  </details>)}</div>;
}

function MemoryBuckets({ manifest, supplied }: { manifest: ContextManifest; supplied: ScopedMemory[] }) {
  const records = new Map(supplied.map((item) => [item.id, item]));
  const buckets = [
    ["Eligible", manifest.memory.eligible, "Records allowed by scope and channel."],
    ["Supplied", manifest.memory.supplied, "Records included in the grounded request."],
    ["Tool retrieved", manifest.memory.tool_retrieved, "Records returned by an executed tool."],
    ["Omitted", manifest.memory.omitted, "Eligible records left outside this prompt."],
  ] as const;
  return <div className="memory-buckets">{buckets.map(([label, ids, description]) => <details key={label} open={label === "Supplied"}>
    <summary><div><strong>{label}</strong><small>{description}</small></div><b>{ids.length}</b></summary>
    <div>{ids.length ? ids.map((id) => {
      const record = records.get(id);
      return <article key={id}><code>{id}</code>{record ? <><p>{record.content}</p><small>{record.channel} · {record.scope} · {record.origin}</small></> : null}</article>;
    }) : <p className="context-empty-inline">No records</p>}</div>
  </details>)}</div>;
}

function AffectTrajectory({ receipt, manifest }: { receipt?: ExpressionReceipt; manifest: ContextManifest }) {
  const trajectory = receipt?.profile.affect_trajectory;
  const before = trajectory?.before ?? manifest.affect_snapshot.values;
  const after = trajectory?.after;
  const delta = trajectory?.delta ?? {};
  const meaningful = Object.entries(delta).filter(([, value]) => Math.abs(value) >= .01);
  return <div className="affect-trajectory">
    <div className="trajectory-head"><span>Before</span><ChevronRight size={13} /><span>Proposed</span><ChevronRight size={13} /><span>Committed at finalization</span></div>
    <p>{after ? `${meaningful.length} dimensions moved within the validated boundary.` : "No completed Affect proposal was captured."}</p>
    <div className="affect-mini-grid">{Object.keys(before).map((key) => <div key={key}><span>{key}</span><b>{before[key]?.toFixed(1)}</b><i>{delta[key] ? `${delta[key] > 0 ? "+" : ""}${delta[key].toFixed(1)}` : "—"}</i><strong>{after?.[key]?.toFixed(1) ?? "—"}</strong></div>)}</div>
  </div>;
}

function ExpressionPanel({ receipt }: { receipt?: ExpressionReceipt }) {
  if (!receipt) return <p className="context-empty-inline">Expression evidence is recorded after a turn completes.</p>;
  const checks = Object.entries(receipt.fidelity.checks ?? {});
  return <div className="expression-evidence">
    <div className={`expression-status ${receipt.fallback ? "fallback" : "passed"}`}>
      {receipt.fallback ? <AlertTriangle size={16} /> : <Check size={16} />}
      <div><strong>{receipt.fallback ? "Grounded response shown" : "Expression fidelity passed"}</strong><span>{receipt.fallback ? "The expression output crossed a fidelity boundary." : "The final rendering preserved the grounded answer."}</span></div>
    </div>
    <div className="fidelity-grid">{checks.map(([name, passed]) => <div key={name}><span className={passed ? "pass" : "fail"}>{passed ? <Check size={11} /> : <X size={11} />}</span>{name.replaceAll("_", " ")}</div>)}</div>
    <details><summary>Grounded visible draft</summary><p>{receipt.grounded_visible}</p></details>
    <details><summary>Expressed output</summary><p>{receipt.expressed_content}</p></details>
    <details><summary>Expression profile</summary><pre>{JSON.stringify(receipt.profile, null, 2)}</pre></details>
  </div>;
}

type InspectorTab = "overview" | "knowledge" | "memory" | "affect" | "expression" | "raw";

export function ContextInspector({ turnId }: { turnId: string }) {
  const [data, setData] = useState<TurnContext | null>(null);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<InspectorTab>("overview");
  useEffect(() => { setData(null); setError(""); api.context(turnId).then(setData).catch(() => setError("Turn context is unavailable.")); }, [turnId]);
  const projection = data?.prompt_projection;
  const manifest = data?.context_manifest;
  const selected = useMemo(() => projection?.selected_nodes ?? [], [projection]);
  if (error) return <div className="context-loading"><AlertTriangle size={20} /><p>{error}</p></div>;
  if (!data || !manifest) return <div className="context-loading"><span className="self-drawer-pulse" /><p>Loading turn evidence…</p></div>;
  const roleText = manifest.roles.map((role) => `${role.id} (${role.source})`).join(", ") || "No task stance";
  const knowledgeNodes = selected.filter((node) => node.owner === "known_world" || node.owner === "imagination");
  return <>
    <div className="drawer-meta">Captured for this turn · state {data.state_sequence} · {data.model_id}</div>
    <div className="context-tabs" role="tablist" aria-label="Turn context sections">{(["overview", "knowledge", "memory", "affect", "expression", "raw"] as InspectorTab[]).map((item) => <button role="tab" aria-selected={tab === item} key={item} className={tab === item ? "active" : ""} onClick={() => setTab(item)}>{item}</button>)}</div>
    {tab === "overview" ? <div className="context-overview">
      <div className="context-summary-grid"><div><span>Selected</span><strong>{selected.length}</strong></div><div><span>Excluded</span><strong>{projection?.excluded_nodes.length ?? 0}</strong></div><div><span>Budget</span><strong>{formatTokens(manifest.budgets.prompt_tokens)}</strong></div><div><span>Bound tools</span><strong>{manifest.tools.bound.length}</strong></div></div>
      <div className="context-pipeline">
        <Stage index={1} title="Canonical Self" owner="self" summary={`${manifest.identity_kernel.length} kernel · ${manifest.activated_self_claims.length} activated`}><IdList ids={[...manifest.identity_kernel, ...manifest.activated_self_claims]} /></Stage>
        <Stage index={2} title="Task context" owner="context" summary={[manifest.task_context.world, manifest.task_context.task, ...manifest.task_context.skills].filter(Boolean).join(" · ") || "global"}><pre>{JSON.stringify(manifest.task_context, null, 2)}</pre></Stage>
        <Stage index={3} title="Reasoning stance" owner="role" summary={roleText}><IdList ids={manifest.roles.map((role) => `${role.id} · ${role.source}`)} /></Stage>
        <Stage index={4} title="Selected knowledge" owner="known_world" summary={`${manifest.knowledge.known_world.length} known · ${manifest.knowledge.imagination.length} imagined`}><NodeList nodes={knowledgeNodes} /></Stage>
        <Stage index={5} title="Memory" owner="memory" summary={`${manifest.memory.supplied.length} of ${manifest.memory.eligible.length} eligible supplied`}><MemoryBuckets manifest={manifest} supplied={data.retrieved_memory} /></Stage>
        <Stage index={6} title="Tools" owner="capabilities" summary={`${manifest.tools.bound.length} bound · ${manifest.tools.registered.length} registered`}><h4>Bound to this request</h4><IdList ids={manifest.tools.bound} empty="No tools were bound." /><h4>Registered only</h4><IdList ids={manifest.tools.registered} /></Stage>
        <Stage index={7} title="Affect transition" owner="affect" summary="Validated before expression; committed only at finalization"><AffectTrajectory receipt={data.expression_receipt} manifest={manifest} /></Stage>
        <Stage index={8} title="Expression" owner="expression" summary={data.expression_receipt?.fallback ? "Grounded fallback used" : "Final rendering stage"}><ExpressionPanel receipt={data.expression_receipt} /></Stage>
      </div>
    </div> : null}
    {tab === "knowledge" ? <div className="context-panel"><header><Brain size={17} /><div><strong>Knowledge supplied</strong><span>Known World and Imagination remain separate owners.</span></div></header><NodeList nodes={knowledgeNodes} /><h3>Expansion handles</h3>{manifest.expansion_handles.length ? <div className="projection-handles">{manifest.expansion_handles.map((handle) => <div key={handle.node_id}><Network size={12} /><span><strong>{handle.node_id}</strong><small>{handle.unexpanded_count} beyond focus · {handle.available_edges.join(", ")}</small></span></div>)}</div> : <p className="context-empty-inline">No traversal handles exposed.</p>}</div> : null}
    {tab === "memory" ? <div className="context-panel"><header><Database size={17} /><div><strong>Memory stages</strong><span>Eligibility is not the same as model visibility.</span></div></header><MemoryBuckets manifest={manifest} supplied={data.retrieved_memory} /></div> : null}
    {tab === "affect" ? <div className="context-panel"><header><Activity size={17} /><div><strong>Affect boundary</strong><span>The proposal is tone input until finalization commits it.</span></div></header><AffectTrajectory receipt={data.expression_receipt} manifest={manifest} /></div> : null}
    {tab === "expression" ? <div className="context-panel"><header><Sparkles size={17} /><div><strong>Expression receipt</strong><span>Presentation is last and has no control authority.</span></div></header><ExpressionPanel receipt={data.expression_receipt} /></div> : null}
    {tab === "raw" ? <div className="context-raw"><details open><summary>Context manifest</summary><pre>{JSON.stringify(manifest, null, 2)}</pre></details><details><summary>Projection receipt</summary><pre>{JSON.stringify(projection ?? {}, null, 2)}</pre></details><details><summary>Expression receipt</summary><pre>{JSON.stringify(data.expression_receipt ?? {}, null, 2)}</pre></details><details><summary>Instructions</summary><pre>{data.instructions_text}</pre></details></div> : null}
  </>;
}

type ActiveTab = "now" | "last" | "evidence";

export function ActiveProjectionPanel({ conversationId, onOpenFull, onOpenTurn }: {
  conversationId: string | null; onOpenFull: () => void; onOpenTurn: (turnId: string) => void;
}) {
  const [projection, setProjection] = useState<SystemProjection | null>(null);
  const [lastProjection, setLastProjection] = useState<PromptProjection | null>(null);
  const [roles, setRoles] = useState<RoleSummary[]>([]);
  const [tab, setTab] = useState<ActiveTab>("now");
  const [error, setError] = useState("");
  const [busyRole, setBusyRole] = useState<string | null>(null);
  const load = useCallback(() => Promise.all([api.systemProjection(), api.promptProjections(conversationId, 1), api.availableRoles()])
    .then(([system, history, nextRoles]) => { setProjection(system); setLastProjection(history[0] ?? null); setRoles(nextRoles); setError(""); })
    .catch(() => setError("The active context is unavailable.")), [conversationId]);
  useEffect(() => { void load(); }, [load]);
  const toggleRole = async (roleId: string) => {
    if (!projection) return;
    setBusyRole(roleId);
    const active = projection.context.roles;
    const rolesNext = active.includes(roleId) ? active.filter((id) => id !== roleId) : [...active, roleId];
    try { await api.setActiveContext({ world: projection.context.world, task: projection.context.task, skills: projection.context.skills, roles: rolesNext }); await load(); }
    finally { setBusyRole(null); }
  };
  if (error) return <div className="self-drawer-empty"><AlertTriangle size={22} /><p>{error}</p></div>;
  if (!projection) return <div className="self-drawer-empty"><span className="self-drawer-pulse" /><p>Composing active context…</p></div>;
  const roleNames = new Map(roles.map((role) => [role.id, role.name]));
  const projectedRoles = lastProjection?.strategy.selected_roles ?? [];
  const configuredChanged = [...projection.context.roles].sort().join("|") !== [...projectedRoles.filter((id) => lastProjection?.strategy.role_sources[id] === "explicit")].sort().join("|");
  const ownerCounts = lastProjection?.selected_nodes.reduce<Record<string, number>>((counts, node) => { counts[node.owner] = (counts[node.owner] ?? 0) + 1; return counts; }, {}) ?? {};
  return <>
    <div className="active-switcher" role="tablist">{(["now", "last", "evidence"] as ActiveTab[]).map((item) => <button role="tab" aria-selected={tab === item} className={tab === item ? "active" : ""} key={item} onClick={() => setTab(item)}>{item === "last" ? "Last turn" : item}</button>)}</div>
    <div className="self-drawer-intro"><div className="self-drawer-mark"><Fingerprint size={19} /></div><div><span><i /> Halcyon · canonical Self</span><p>Identity remains stable; this panel shows the context composed around it.</p></div></div>
    {tab === "now" ? <>
      {configuredChanged ? <p className="projection-pending">Configuration changed · applies to the next turn</p> : null}
      <section className="self-drawer-section"><h3>Active stance <b>{projection.context.roles.length} explicit</b></h3><p className="self-drawer-hint">Roles steer attention for the next turn. They are never identity or authority.</p><div className="self-drawer-roles">{roles.map((role) => { const active = projection.context.roles.includes(role.id); return <button key={role.id} className={`role-chip ${active ? "active" : ""}`} disabled={busyRole === role.id} title={role.tagline} onClick={() => void toggleRole(role.id)}><span>{role.name}</span>{active ? <X size={11} /> : <Plus size={11} />}</button>; })}</div></section>
      <section className="self-drawer-section"><h3>Retrieval scopes <b>configured now</b></h3><div className="self-drawer-scopes">{["global", ...projection.context.skills, projection.context.world, projection.context.task].filter(Boolean).map((scope) => <span key={scope}>{scope}</span>)}</div></section>
      <section className="self-drawer-section"><h3>Current Affect <b>canonical</b></h3><div className="self-drawer-affect">{Object.entries(projection.affect.values).map(([name, value]) => <div key={name}><span>{name}</span><b>{value.toFixed(0)}</b><div><i style={{ width: `${value}%` }} /></div></div>)}</div></section>
      <section className="self-drawer-section"><h3>Tool boundary <b>{projection.capabilities.available} registered</b></h3><p className="self-drawer-hint">Registered tools are not bound to a request until the turn manifest says so.</p></section>
    </> : null}
    {tab === "last" ? <>{!lastProjection ? <p className="context-empty-inline">Send a message to capture the first turn-specific projection.</p> : <>
      <section className="self-drawer-section"><h3>Reasoning stance <b>captured</b></h3><div className="projected-role-line">{projectedRoles.map((roleId) => <b key={roleId}>{roleNames.get(roleId) ?? roleId}<i>{lastProjection.strategy.role_sources[roleId]}</i></b>)}</div></section>
      <section className="self-drawer-section"><h3>Owners in focus <b>state {lastProjection.state_sequence}</b></h3><div className="projection-owner-grid">{Object.entries(ownerCounts).map(([owner, count]) => <div key={owner}><span>{ownerLabel(owner)}</span><b>{count}</b></div>)}</div><NodeList nodes={lastProjection.selected_nodes.filter((node) => node.owner !== "self").slice(0, 8)} /></section>
    </>}</> : null}
    {tab === "evidence" ? <>{lastProjection ? <section className="self-drawer-section projection-receipt"><h3>Projection receipt</h3><code>{lastProjection.id}</code><p>{new Date(lastProjection.created_at * 1000).toLocaleString()} · {lastProjection.selected_nodes.length} selected · {lastProjection.excluded_nodes.length} excluded</p>{lastProjection.turn_id ? <button className="evidence-button" onClick={() => onOpenTurn(lastProjection.turn_id!)}><FileCheck2 size={13} />Open complete turn evidence<ChevronRight size={13} /></button> : null}</section> : <p className="context-empty-inline">No completed turn evidence yet.</p>}<section className="self-drawer-section"><h3>Boundary state <b>read only</b></h3><div className="version-chips">{Object.entries(projection.versions).map(([owner, version]) => <span key={owner}>{owner}<b>v{version}</b></span>)}</div></section></> : null}
    <button className="open-full-self" onClick={onOpenFull}><span><Fingerprint size={15} />Open canonical Self</span><ChevronRight size={16} /></button>
  </>;
}
