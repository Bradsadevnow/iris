import { useEffect, useMemo, useState } from "react";
import { Activity, Brain, Check, ChevronDown, CircleDot, Database, Fingerprint, Plug, Search, ShieldCheck, Sparkles, Wrench, X } from "lucide-react";
import { api, Capability, RolePackDetail, RoleSummary, SelfClaim, SystemProjection, ToolReceipt } from "./api";

type Lens = "identity" | "system" | "capabilities" | "roles" | "receipts";
const titles: Record<Lens, string> = { identity: "Identity", system: "System", capabilities: "Capabilities", roles: "Roles", receipts: "Tool receipts" };

function Identity({ claims }: { claims: SelfClaim[] }) {
  const groups = useMemo(() => claims.reduce((map, claim) => map.set(claim.kind, [...(map.get(claim.kind) ?? []), claim]), new Map<string, SelfClaim[]>()), [claims]);
  const name = claims.find((claim) => claim.id === "self:identity:name")?.value ?? "Halcyon";
  return <div className="identity-lens"><header className="identity-hero"><div className="identity-mark"><Fingerprint size={26} /></div><div><span>Canonical Self</span><h2>{name}</h2><p>Durable identity claims only. Memory, Affect, active work, and permissions remain with their owners.</p></div></header>{[...groups].map(([kind, items]) => <section key={kind}><h3>{kind.replaceAll("_", " ")}<span>{items.length}</span></h3>{items.map((claim) => <article key={claim.id}><CircleDot size={13} /><div><p><strong>{claim.subject}</strong> {claim.predicate} <strong>{claim.value}</strong></p><footer>{claim.status} · {claim.source} · Self v{claim.self_version}</footer></div></article>)}</section>)}</div>;
}

const ownerMeta = {
  self: [Fingerprint, "Durable identity"], memory: [Database, "Experience and meaning"], affect: [Activity, "Continuous internal state"],
  context: [Search, "Active retrieval scopes"], capabilities: [Wrench, "Reachable tools"], governance: [ShieldCheck, "Boundary evidence"],
} as const;

function System({ projection }: { projection: SystemProjection }) {
  const cards = [
    ["self", `${projection.self.claim_count} claims`],
    ["memory", `${projection.memory.world_nodes} entities · ${projection.memory.reachable_entries} scoped`],
    ["affect", `${Object.values(projection.affect.values).filter((value) => value !== 50).length} dimensions away from baseline`],
    ["context", [projection.context.world, projection.context.task, ...projection.context.skills].filter(Boolean).join(" · ") || "global"],
    ["capabilities", `${projection.capabilities.available} available`],
    ["governance", `${Object.keys(projection.governance.boundaries).length} boundaries`],
  ] as const;
  return <div className="system-lens"><header><span>Read-only projection</span><h2>Halcyon, composed now</h2><p>Each card is projected from an independently owned canonical system.</p></header><div className="owner-grid">{cards.map(([owner, summary]) => { const [Icon, subtitle] = ownerMeta[owner]; return <article key={owner}><div className={`owner-icon ${owner}`}><Icon size={18} /></div><div><span>{subtitle}</span><h3>{owner}</h3><p>{summary}</p></div><b>v{projection.versions[owner] ?? 0}</b></article>; })}</div><section className="version-vector"><h3>Version vector</h3><code>{Object.entries(projection.versions).map(([key, value]) => `${key}:${value}`).join("  ")}</code></section></div>;
}

function Capabilities({ items, onRun }: { items: Capability[]; onRun: (tool: Capability) => void }) {
  return <div className="capability-lens"><header><span>Capability boundary</span><h2>What Halcyon can attempt</h2><p>Discovery describes a tool. Local policy decides whether it is reachable.</p></header>{items.map((tool) => <article key={tool.id}><div className="capability-source">{tool.source.startsWith("mcp:") ? <Plug size={15} /> : <Wrench size={15} />}<span>{tool.source}</span></div><div className="capability-main"><div><h3>{tool.id}</h3><span className={`effect ${tool.effect_class}`}>{tool.effect_class}</span></div><p>{tool.description}</p><footer><span>{tool.boundary_version}</span><span>{Object.keys(tool.schema).length} arguments</span></footer></div><button disabled={!tool.available || tool.id === "memory.search"} onClick={() => onRun(tool)}>{tool.available ? "Run" : "Disconnected"}</button></article>)}</div>;
}

function Roles({ roles, active, onToggle, busy }: { roles: RoleSummary[]; active: string[]; onToggle: (id: string) => void; busy: string | null }) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const [detail, setDetail] = useState<Record<string, RolePackDetail>>({});
  const toggleExpand = async (id: string) => {
    if (expanded === id) { setExpanded(null); return; }
    setExpanded(id);
    if (!detail[id]) { const full = await api.roleDetail(id); setDetail((current) => ({ ...current, [id]: full })); }
  };
  if (!roles.length) return <div className="self-empty"><Sparkles size={26} /><h2>No role packs found</h2><p>Add one under seeds/identity_packs/ and it will appear here.</p></div>;
  return <div className="roles-lens">
    <header><span>Role overlays</span><h2>Wear a hat for the task at hand</h2><p>Halcyon's own Self stays canonical — an equipped role informs her without replacing her. Toggle any number on or off.</p></header>
    <div className="roles-grid">{roles.map((pack) => {
      const equipped = active.includes(pack.id);
      const isOpen = expanded === pack.id;
      const full = detail[pack.id];
      return <article key={pack.id} className={equipped ? "equipped" : ""}>
        <header><h3>{pack.name}</h3><button className={`equip-toggle ${equipped ? "on" : ""}`} disabled={busy === pack.id} onClick={() => onToggle(pack.id)}>{equipped ? "Equipped" : "Equip"}</button></header>
        <p className="role-tagline">{pack.tagline}</p>
        <button className="role-expand" onClick={() => void toggleExpand(pack.id)}>{isOpen ? "Hide details" : "Show claims & methods"}<ChevronDown size={13} className={isOpen ? "rotated" : ""} /></button>
        {isOpen ? <div className="role-detail">{!full ? <p className="muted">Loading…</p> : <>
          <ul className="role-claims">{full.claims.map((claim) => <li key={claim.id}><span className="role-claim-kind">{claim.kind}</span>{claim.value}</li>)}</ul>
          {full.capabilities.length ? <p className="role-methods"><strong>Known methods:</strong> {full.capabilities.map((cap) => cap.id.split(".").slice(1).join(".")).join(", ")}</p> : null}
        </>}</div> : null}
      </article>;
    })}</div>
  </div>;
}

function Receipts({ items }: { items: ToolReceipt[] }) {
  const [open, setOpen] = useState<string | null>(null);
  if (!items.length) return <div className="self-empty"><ShieldCheck size={26} /><h2>No tool attempts yet</h2><p>Admitted, denied, successful, and failed calls will leave evidence here.</p></div>;
  return <div className="tool-receipts">{items.map((item) => <article key={item.id}><button onClick={() => setOpen(open === item.id ? null : item.id)}><span className={`receipt-decision ${item.decision.toLowerCase()}`}>{item.decision === "ACCEPT" ? <Check size={13} /> : <X size={13} />}</span><div><strong>{item.tool_id}</strong><small>{item.source} · {item.execution_status}</small></div><time>{new Date(item.created_at * 1000).toLocaleString()}</time><ChevronDown size={14} className={open === item.id ? "rotated" : ""} /></button>{open === item.id ? <div className="tool-receipt-detail"><h4>Boundary checks</h4>{item.checks.map((check, index) => <div className="tool-check" key={index}><b>{check[1]}</b><span>{check[0]} · {check[2]}</span></div>)}<h4>Arguments</h4><pre>{JSON.stringify(item.raw_args, null, 2)}</pre>{item.result ? <><h4>Observation</h4><pre>{JSON.stringify(item.result, null, 2)}</pre></> : null}</div> : null}</article>)}</div>;
}

export default function SelfSystemView() {
  const [lens, setLens] = useState<Lens>("identity");
  const [projection, setProjection] = useState<SystemProjection | null>(null);
  const [receipts, setReceipts] = useState<ToolReceipt[]>([]);
  const [roles, setRoles] = useState<RoleSummary[]>([]);
  const [busyRole, setBusyRole] = useState<string | null>(null);
  const [error, setError] = useState("");
  const refresh = () => Promise.all([api.systemProjection(), api.toolReceipts(), api.availableRoles()])
    .then(([next, nextReceipts, nextRoles]) => { setProjection(next); setReceipts(nextReceipts); setRoles(nextRoles); });
  useEffect(() => { refresh().catch(() => setError("System projection unavailable. Restart the Halcyon server.")); }, []);
  const run = async (tool: Capability) => { await api.executeTool(tool.id); await refresh(); setLens("receipts"); };
  const toggleRole = async (roleId: string) => {
    if (!projection) return;
    const active = projection.context.roles;
    const next = active.includes(roleId) ? active.filter((id) => id !== roleId) : [...active, roleId];
    setBusyRole(roleId);
    try { await api.setActiveContext({ world: projection.context.world, task: projection.context.task, skills: projection.context.skills, roles: next }); await refresh(); }
    finally { setBusyRole(null); }
  };
  return <main className="self-page"><header className="self-toolbar"><div><span className="eyebrow">System identity</span><h1>Self</h1></div><nav>{(Object.keys(titles) as Lens[]).map((item) => <button className={lens === item ? "active" : ""} onClick={() => setLens(item)} key={item}>{titles[item]}</button>)}</nav><span className="projection-label"><i /> projection</span></header><section className="self-content">{error ? <div className="self-empty"><Brain size={26} /><h2>Self unavailable</h2><p>{error}</p></div> : !projection ? <div className="self-empty">Composing Halcyon…</div> : lens === "identity" ? <Identity claims={projection.self.claims} /> : lens === "system" ? <System projection={projection} /> : lens === "capabilities" ? <Capabilities items={projection.capabilities.items} onRun={run} /> : lens === "roles" ? <Roles roles={roles} active={projection.context.roles} onToggle={toggleRole} busy={busyRole} /> : <Receipts items={receipts} />}</section></main>;
}
