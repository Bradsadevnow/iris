import { useEffect, useMemo, useState } from "react";
import { Activity, Brain, Check, ChevronDown, CircleDot, Database, Fingerprint, Network, Plug, Search, ShieldCheck, Wrench, X } from "lucide-react";
import { api, Capability, PromptProjection, SelfClaim, SystemProjection, ToolReceipt } from "./api";

type Lens = "identity" | "system" | "capabilities" | "attention" | "receipts";
const titles: Record<Lens, string> = { identity: "Identity", system: "Composition", capabilities: "Capabilities", attention: "Attention history", receipts: "Tool receipts" };

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

function Attention({ items }: { items: PromptProjection[] }) {
  const [open, setOpen] = useState<string | null>(items[0]?.id ?? null);
  if (!items.length) return <div className="self-empty"><Network size={26} /><h2>No projections yet</h2><p>Send a message to capture what Halcyon focused on for that turn.</p></div>;
  return <div className="attention-lens"><header><span>Turn-specific attention</span><h2>Projection history</h2><p>What reached the model, why it was selected, and what stayed outside the prompt budget.</p></header>
    <div className="attention-list">{items.map((item) => {
      const isOpen = open === item.id;
      const counts = item.selected_nodes.reduce<Record<string, number>>((map, node) => { map[node.owner] = (map[node.owner] ?? 0) + 1; return map; }, {});
      return <article key={item.id} className={isOpen ? "open" : ""}><button onClick={() => setOpen(isOpen ? null : item.id)} aria-expanded={isOpen}>
        <div><strong>{item.request.message}</strong><small>{new Date(item.created_at * 1000).toLocaleString()} · state {item.state_sequence}</small></div>
        <span>{item.selected_nodes.length} nodes · {item.estimated_tokens.toLocaleString()} tokens</span><ChevronDown size={15} className={isOpen ? "rotated" : ""} />
      </button>{isOpen ? <div className="attention-detail">
        <div className="attention-counts">{Object.entries(counts).map(([owner, count]) => <span key={owner}>{owner.replaceAll("_", " ")}<b>{count}</b></span>)}</div>
        <h3>Selected nodes</h3>{item.selected_nodes.map((node) => <div className="attention-node" key={node.id}><div><strong>{node.label}</strong><span>{node.owner} · {node.status}</span></div><p>{node.content}</p><small>{node.reason}</small></div>)}
        <footer><code>{item.id}</code><span>{item.excluded_nodes.length} excluded · {item.expansion_handles.length} expansion handles</span></footer>
      </div> : null}</article>;
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
  const [projections, setProjections] = useState<PromptProjection[]>([]);
  const [error, setError] = useState("");
  const refresh = () => Promise.all([api.systemProjection(), api.toolReceipts(), api.promptProjections(null, 30)])
    .then(([next, nextReceipts, nextProjections]) => { setProjection(next); setReceipts(nextReceipts); setProjections(nextProjections); });
  useEffect(() => { refresh().catch(() => setError("System projection unavailable. Restart the Halcyon server.")); }, []);
  const run = async (tool: Capability) => { await api.executeTool(tool.id); await refresh(); setLens("receipts"); };
  return <main className="self-page"><header className="self-toolbar"><div><span className="eyebrow">System identity</span><h1>Self</h1></div><nav>{(Object.keys(titles) as Lens[]).map((item) => <button className={lens === item ? "active" : ""} onClick={() => setLens(item)} key={item}>{titles[item]}</button>)}</nav><span className="projection-label"><i /> projection</span></header><section className="self-content">{error ? <div className="self-empty"><Brain size={26} /><h2>Self unavailable</h2><p>{error}</p></div> : !projection ? <div className="self-empty">Composing Halcyon…</div> : lens === "identity" ? <Identity claims={projection.self.claims} /> : lens === "system" ? <System projection={projection} /> : lens === "capabilities" ? <Capabilities items={projection.capabilities.items} onRun={run} /> : lens === "attention" ? <Attention items={projections} /> : <Receipts items={receipts} />}</section></main>;
}
