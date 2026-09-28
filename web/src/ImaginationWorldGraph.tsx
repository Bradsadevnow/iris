import { useEffect, useMemo, useState } from "react";
import Graph from "graphology";
import { ArrowDownLeft, ArrowUpRight, BookOpen, CircleDot, GitCommitHorizontal, Network, Sparkles, X } from "lucide-react";
import { api, MemoryNode, WorldMemory } from "./api";
import { GraphCanvas, formatType, initialPosition, layoutGraph } from "./GraphCanvas";

// The Imagined World graph is a distinct domain from Memory: fictional entities, relations,
// events, and constraints Halcyon and the user build together, not autobiographical experience.
// See "Important graph distinction" in the README.

const WORLD_TYPE_COLORS: Record<string, string> = {
  person: "#c3b5ff", place: "#b8a58b", organization: "#d69a87",
  object: "#85c5cd", event: "#d8ad72", concept: "#a7d7c5", reference: "#807c86",
};
const colorFor = (type: string) => {
  const key = type.toLowerCase();
  if (WORLD_TYPE_COLORS[key]) return WORLD_TYPE_COLORS[key];
  const palette = Object.values(WORLD_TYPE_COLORS);
  let hash = 0;
  for (let i = 0; i < type.length; i += 1) hash = ((hash << 5) - hash + type.charCodeAt(i)) | 0;
  return palette[Math.abs(hash) % palette.length];
};

function buildWorldGraph(memory: WorldMemory): Graph {
  const graph = new Graph({ multi: true, type: "directed" });
  const names = new Set(Object.keys(memory.nodes));
  for (const edge of memory.edges) { names.add(edge.source); names.add(edge.target); }
  for (const item of memory.constraints) names.add(item.target);
  const ordered = [...names].sort();
  ordered.forEach((name, index) => {
    const node = memory.nodes[name] ?? { label: name, type: "reference" };
    const position = initialPosition(name, index, ordered.length);
    graph.addNode(name, { label: node.label, entityType: node.type, color: colorFor(node.type), size: 7, ...position });
  });
  memory.edges.forEach((edge) => {
    if (!graph.hasEdge(edge.id)) graph.addDirectedEdgeWithKey(edge.id, edge.source, edge.target, { label: edge.relation, color: "#4c4a50", size: 1 });
  });
  layoutGraph(graph);
  return graph;
}

function LoreMarkdown({ content }: { content: string }) {
  return <div className="lore-markdown">{content.split("\n").map((line, index) => {
    const key = `${index}-${line.slice(0, 12)}`;
    if (line.startsWith("### ")) return <h4 key={key}>{line.slice(4)}</h4>;
    if (line.startsWith("## ")) return <h3 key={key}>{line.slice(3)}</h3>;
    if (line.startsWith("# ")) return <h2 key={key}>{line.slice(2)}</h2>;
    if (line.startsWith("- ")) return <div className="lore-list-item" key={key}><i />{line.slice(2)}</div>;
    if (!line.trim()) return <span className="lore-break" key={key} />;
    return <p key={key}>{line}</p>;
  })}</div>;
}

function WorldEntityInspector({ node, onClose, onSelect }: { node: MemoryNode; onClose: () => void; onSelect: (name: string) => void }) {
  const [tab, setTab] = useState<"lore" | "graph" | "history">("lore");
  const relations = [...node.outgoing.map((edge) => ({ direction: "out", edge })), ...node.incoming.map((edge) => ({ direction: "in", edge }))];
  const accent = colorFor(node.type);
  return <aside className="node-inspector" aria-label={`${node.name} details`} style={{ "--node-accent": accent } as React.CSSProperties}>
    <header><div className="node-inspector-orb" style={{ background: accent }}><Sparkles size={17} /></div><div className="node-heading"><span className="node-type">{formatType(node.type)}</span><h2>{node.name}</h2><div className="node-summary"><span>{relations.length} relations</span><span>{node.sources.length} {node.sources.length === 1 ? "source" : "sources"}</span></div></div><button aria-label="Close entity details" onClick={onClose}><X size={17} /></button></header>
    <nav className="entity-dossier-tabs" aria-label="Entity dossier">{(["lore", "graph", "history"] as const).map((item) => <button key={item} className={tab === item ? "active" : ""} aria-pressed={tab === item} onClick={() => setTab(item)}>{item === "lore" ? <BookOpen size={12} /> : item === "history" ? <GitCommitHorizontal size={12} /> : <Network size={12} />}{item}</button>)}</nav>
    {tab === "lore" ? <div className="entity-lore">{node.lore ? <><div className="lore-meta"><span>Story so far</span><b>v{node.lore.version}</b></div><LoreMarkdown content={node.lore.markdown} /></> : <div className="lore-empty"><BookOpen size={20} /><h3>No story written yet</h3><p>As this part of the world grows, its story can live here in Markdown.</p>{node.origin?.reflection ? <div className="origin-fragment"><span>An early thought</span><p>{node.origin.reflection}</p><small>This helped begin the idea; it is not part of the story yet.</small></div> : null}</div>}</div> : null}
    {tab === "graph" ? <>{node.aliases.length > 0 ? <section><h3>Known as</h3><p>{node.aliases.join(", ")}</p></section> : null}
    <section><h3>Relations <span>{relations.length}</span></h3>
      <div className="relationship-list">{relations.length === 0 ? <p className="quiet">No relations yet.</p> : relations.map(({ direction, edge }, index) => {
        const peer = direction === "out" ? edge.target : edge.source;
        const peerLabel = direction === "out" ? edge.target_label ?? peer : edge.source_label ?? peer;
        return <button key={`${edge.id}-${index}`} onClick={() => onSelect(peer)}>
          {direction === "out" ? <ArrowUpRight size={14} /> : <ArrowDownLeft size={14} />}
          <span><strong>{edge.relation.replaceAll("_", " ")}{edge.status === "disputed" ? <b>disputed</b> : null}</strong>{peerLabel}{edge.properties && Object.keys(edge.properties).length > 0 ? <em>{Object.entries(edge.properties).filter(([key]) => key !== "conflict_group").map(([key, value]) => `${key.replaceAll("_", " ")}: ${String(value)}`).join(" · ")}</em> : null}</span>
        </button>;
      })}</div>
    </section>
    {Object.keys(node.properties).length > 0 ? <section><h3>Properties</h3>{Object.entries(node.properties).map(([key, value]) => <div className="constraint" key={key}><strong>{key.replaceAll("_", " ")}</strong><span>{String(value)}</span></div>)}</section> : null}
    {node.constraints.length > 0 ? <section><h3>Constraints</h3>{node.constraints.map((rule) => <div className="constraint" key={rule.id}><strong>{rule.rule}</strong><span>{rule.value}</span></div>)}</section> : null}
    {node.source_details.length > 0 ? <section><h3>Sources</h3>{node.source_details.map((source) => <div className="source-detail" key={source.title}><strong>{source.title}</strong><span>{source.kind?.replaceAll("_", " ")}{source.captured_at ? ` · ${source.captured_at}` : ""}</span></div>)}</section> : null}</> : null}
    {tab === "history" ? <div className="entity-history"><section><h3>Origin</h3>{node.admission ? <><div className="provenance"><CircleDot size={14} /><div><strong>Added from a draft</strong><span>World moment {node.admission.state_sequence_after} · draft version {node.admission.blueprint_revision}</span></div></div><details><summary>How we got here</summary><pre>{JSON.stringify(node.admission.genealogy, null, 2)}</pre></details><details><summary>What was added</summary><pre>{JSON.stringify(node.admission.receipt, null, 2)}</pre></details></> : node.origin ? <><div className="provenance"><CircleDot size={14} /><div><strong>Created in turn {node.origin.ordinal}</strong><span>World moment {node.origin.state_sequence} · {node.origin.receipt.outcome ?? node.origin.receipt.decision}</span></div></div><blockquote>{node.origin.reflection}</blockquote><details><summary>What changed</summary><pre>{JSON.stringify(node.origin.mutation, null, 2)}</pre></details></> : <p className="quiet">Its beginning is still a mystery.</p>}</section><section><h3>Lore history <span>{node.lore?.revisions.length ?? 0}</span></h3>{node.lore?.revisions.length ? node.lore.revisions.map((revision) => <div className="lore-revision" key={revision.id}><b>v{revision.version}</b><span>{revision.operation} · {revision.source_kind} {revision.source_id.slice(-6)}</span><time>{new Date(revision.created_at * 1000).toLocaleString()}</time></div>) : <p className="quiet">No lore changes yet.</p>}</section></div> : null}
  </aside>;
}

export default function ImaginationWorldGraph({ memory, selected, onSelect }: { memory: WorldMemory; selected: string | null; onSelect: (name: string | null) => void }) {
  const [node, setNode] = useState<MemoryNode | null>(null);
  useEffect(() => {
    if (!selected) { setNode(null); return; }
    api.imaginationNode(selected).then(setNode).catch(() => setNode(null));
  }, [selected]);
  const graph = useMemo(() => buildWorldGraph(memory), [memory]);
  if (graph.order === 0) return <div className="graph-empty"><div><Network size={28} /><h2>Your world is wide open</h2><p>Add a creation when you find something worth keeping.</p></div></div>;
  const types = [...new Set(Object.values(memory.nodes).map((entity) => entity.type))].slice(0, 6);
  return <div className="graph-stage"><div className="graph-atmosphere" />
    <GraphCanvas graph={graph} selected={selected} onSelect={onSelect} />
    <div className="graph-intro"><span>Your World</span><p>Choose something to see its story, connections, and history.</p></div>
    <div className="graph-key">{types.map((type) => <span key={type}><i style={{ background: colorFor(type) }} />{formatType(type)}</span>)}</div>
    <div className="graph-legend"><span><b>{graph.order}</b> entities</span><span><b>{graph.size}</b> relations</span><span className="graph-state"><i />state {memory.sequence}</span></div>
    {node ? <WorldEntityInspector key={node.id} node={node} onClose={() => onSelect(null)} onSelect={onSelect} /> : null}
  </div>;
}
