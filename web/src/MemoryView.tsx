import { useEffect, useMemo, useRef, useState } from "react";
import Graph from "graphology";
import forceAtlas2 from "graphology-layout-forceatlas2";
import Sigma from "sigma";
import { ArrowDownLeft, ArrowUpRight, CircleDot, Database, Focus, Maximize2, Minus, Network, Plus, Search, Sparkles, X } from "lucide-react";
import { api, ActiveContext, AffectState, MemoryNode, ScopedMemory, TimelineEvent, WorldMemory } from "./api";
import { AffectLens, ChannelFilter, ChannelTabs, Explorer, LensTabs, MemoryLens, Timeline } from "./BraidPanels";

const TYPE_COLORS: Record<string, string> = {
  Person: "#c3b5ff", Principle: "#a7d7c5", Belief: "#a7d7c5", DerivedPattern: "#d5a6c2",
  Project: "#8db7e8", CreativeProject: "#8db7e8", Experiment: "#d8ad72", Organization: "#d69a87",
  Capability: "#a9c97f", Preference: "#a9a5bf", Goal: "#e0c277", Interest: "#cc9fc9",
  Resource: "#85c5cd", Place: "#b8a58b", Role: "#b0a5d6", reference: "#807c86",
  Experience: "#91a8c2", CognitiveSemantic: "#aa9be2", EmotionalSemantic: "#d99cae", Scope: "#716d79",
};
const colorFor = (type: string) => {
  if (TYPE_COLORS[type]) return TYPE_COLORS[type];
  const palette = Object.values(TYPE_COLORS);
  let hash = 0;
  for (let i = 0; i < type.length; i += 1) hash = ((hash << 5) - hash + type.charCodeAt(i)) | 0;
  return palette[Math.abs(hash) % palette.length];
};
const formatType = (type: string) => type.replace(/([a-z])([A-Z])/g, "$1 $2");

const initialPosition = (name: string, index: number, count: number) => {
  let hash = 2166136261;
  for (let i = 0; i < name.length; i += 1) hash = Math.imul(hash ^ name.charCodeAt(i), 16777619);
  const angle = (index / Math.max(count, 1)) * Math.PI * 2 + ((hash >>> 0) % 100) / 100;
  const radius = 4 + ((hash >>> 8) % 100) / 35;
  return { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius };
};

function buildGraph(memory: WorldMemory): Graph {
  const graph = new Graph({ multi: true, type: "directed" });
  const names = new Set(Object.keys(memory.nodes));
  for (const edge of memory.edges) { names.add(edge.source); names.add(edge.target); }
  for (const item of memory.constraints) names.add(item.target);
  const ordered = [...names].sort();
  ordered.forEach((name, index) => {
    const node = memory.nodes[name] ?? { label: name, type: "reference" };
    const position = initialPosition(name, index, ordered.length);
    const isIdentity = node.type === "Person" && Boolean(node.properties?.primary_identity);
    graph.addNode(name, { label: node.label, memoryType: node.type, primaryIdentity: isIdentity, color: colorFor(node.type), size: isIdentity ? 18 : 7, forceLabel: isIdentity, ...position });
  });
  memory.edges.forEach((edge) => {
    if (!graph.hasEdge(edge.id)) graph.addDirectedEdgeWithKey(edge.id, edge.source, edge.target, { label: edge.relation, color: "#4c4a50", size: 1 });
  });
  if (graph.order > 1 && graph.size > 0) {
    forceAtlas2.assign(graph, { iterations: Math.min(160, 40 + graph.order * 2), settings: { gravity: 1.1, scalingRatio: 7, slowDown: 4 } });
  }
  graph.forEachNode((node) => {
    const identity = Boolean(graph.getNodeAttribute(node, "primaryIdentity"));
    graph.setNodeAttribute(node, "size", identity ? 19 : Math.min(14, 5.5 + Math.sqrt(graph.degree(node)) * 1.8));
  });
  return graph;
}

function braidProjection(world: WorldMemory, entries: ScopedMemory[], channel: ChannelFilter): WorldMemory {
  const nodes = { ...world.nodes };
  const edges = [...world.edges];
  const visible = channel === "all" ? entries : entries.filter((item) => item.channel === channel);
  const defaultTarget = Object.values(nodes).find((node) => node.properties?.primary_identity)?.id
    ?? Object.values(nodes).find((node) => node.type === "Person")?.id
    ?? (nodes["project:iris"] ? "project:iris" : Object.keys(nodes)[0]);
  const scopeIds = new Set(visible.map((item) => `scope:${item.scope}`));
  for (const scopeNode of scopeIds) {
    const label = scopeNode.slice(6);
    nodes[scopeNode] = { id: scopeNode, label, type: "Scope", visibility: "standard", properties: { scope: label }, sources: [] };
    const target = label === "world:halcyon" && nodes["project:iris"] ? "project:iris" : defaultTarget;
    if (nodes[target]) edges.push({ id: `projection:${scopeNode}:${target}`, source: scopeNode, relation: "active context", target, assertion: "projection", status: "active", sources: [] });
  }
  for (const item of visible) {
    const type = item.channel === "experience" ? "Experience" : item.channel === "cognitive_semantic" ? "CognitiveSemantic" : "EmotionalSemantic";
    nodes[item.id] = { id: item.id, label: item.content.length > 58 ? `${item.content.slice(0, 55)}…` : item.content, type, visibility: "standard", properties: { scope: item.scope, channel: item.channel, content: item.content }, sources: [] };
    edges.push({ id: `projection:${item.id}:scope`, source: item.id, relation: "belongs to", target: `scope:${item.scope}`, assertion: "projection", status: "active", sources: [] });
    for (const source of item.derived_from) if (nodes[source]) edges.push({ id: `projection:${item.id}:${source}`, source: item.id, relation: "derived from", target: source, assertion: "projection", status: "active", sources: [] });
  }
  return { ...world, nodes, edges };
}

function NodeInspector({ node, onClose, onSelect }: { node: MemoryNode; onClose: () => void; onSelect: (name: string) => void }) {
  const relationships = [...node.outgoing.map((edge) => ({ direction: "out", edge })), ...node.incoming.map((edge) => ({ direction: "in", edge }))];
  const accent = colorFor(node.type);
  return <aside className="node-inspector" aria-label={`${node.name} details`} style={{ "--node-accent": accent } as React.CSSProperties}>
    <header><div className="node-inspector-orb" style={{ background: accent }}><Sparkles size={17} /></div><div className="node-heading"><span className="node-type">{formatType(node.type)}</span><h2>{node.name}</h2><div className="node-summary"><span>{relationships.length} connections</span><span>{node.sources.length} {node.sources.length === 1 ? "source" : "sources"}</span></div></div><button aria-label="Close node details" onClick={onClose}><X size={17} /></button></header>
    {node.aliases.length > 0 ? <section><h3>Known as</h3><p>{node.aliases.join(", ")}</p></section> : null}
    <section><h3>Relationships <span>{relationships.length}</span></h3>
      <div className="relationship-list">{relationships.length === 0 ? <p className="quiet">No relationships yet.</p> : relationships.map(({ direction, edge }, index) => {
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
    {node.source_details.length > 0 ? <section><h3>Sources</h3>{node.source_details.map((source) => <div className="source-detail" key={source.title}><strong>{source.title}</strong><span>{source.kind?.replaceAll("_", " ")}{source.captured_at ? ` · ${source.captured_at}` : ""}</span></div>)}</section> : null}
    <section><h3>Provenance</h3>{node.provenance ? <div className="provenance"><CircleDot size={14} /><div><strong>Created in turn {String(node.provenance.ordinal)}</strong><span>State {String(node.provenance.state_sequence_after)}</span></div></div> : <p className="quiet">Provenance unavailable.</p>}</section>
  </aside>;
}

export function WorldGraph({ memory, selected, onSelect }: { memory: WorldMemory; selected: string | null; onSelect: (name: string | null) => void }) {
  const container = useRef<HTMLDivElement>(null);
  const renderer = useRef<Sigma | null>(null);
  const selectedRef = useRef<string | null>(selected);
  const graph = useMemo(() => buildGraph(memory), [memory]);
  useEffect(() => {
    if (!container.current || graph.order === 0) return;
    const sigma = new Sigma(graph, container.current, {
      allowInvalidContainer: true,
      renderEdgeLabels: false,
      labelColor: { color: "#d9d5df" },
      labelFont: "DM Sans",
      labelSize: 12,
      labelDensity: .7,
      labelGridCellSize: 140,
      labelRenderedSizeThreshold: 9,
      defaultEdgeColor: "#35333a",
      defaultNodeColor: "#9484db",
      stagePadding: 50,
      nodeReducer: (node, data) => {
        const active = selectedRef.current;
        if (!active) return data;
        if (node === active) return { ...data, highlighted: true, zIndex: 2, size: data.size * 1.28, color: "#d4caff" };
        if (graph.areNeighbors(node, active)) return { ...data, zIndex: 1, size: data.size * 1.08 };
        return { ...data, color: "#302e35", label: "", zIndex: 0 };
      },
      edgeReducer: (edge, data) => {
        const active = selectedRef.current;
        if (!active) return data;
        const [source, target] = graph.extremities(edge);
        return source === active || target === active ? { ...data, color: "#8074aa", size: 1.8, zIndex: 1 } : { ...data, color: "#28272a", hidden: false, zIndex: 0 };
      },
    });
    sigma.on("clickNode", ({ node }) => onSelect(node));
    sigma.on("clickStage", () => onSelect(null));
    renderer.current = sigma;
    return () => { sigma.kill(); renderer.current = null; };
  }, [graph, onSelect]);
  useEffect(() => {
    selectedRef.current = selected;
    renderer.current?.refresh();
    if (!selected || !renderer.current || !graph.hasNode(selected)) return;
    const display = renderer.current.getNodeDisplayData(selected);
    if (display) renderer.current.getCamera().animate({ x: display.x, y: display.y, ratio: .45 }, { duration: 350 });
  }, [selected, graph]);
  const zoom = (factor: number) => renderer.current?.getCamera().animatedZoom({ duration: 220, factor });
  const reset = () => renderer.current?.getCamera().animatedReset({ duration: 320 });
  if (graph.order === 0) return <div className="graph-empty"><div><Network size={28} /><h2>No world yet</h2><p>As Halcyon imagines and remembers relationships, they will appear here.</p></div></div>;
  const types = [...new Set(Object.values(memory.nodes).map((node) => node.type))].slice(0, 6);
  return <div className="graph-stage"><div className="graph-atmosphere" /><div className="sigma-container" ref={container} />
    <div className="graph-intro"><span>Living memory</span><p>Select anything to trace what it means and where it came from.</p></div>
    <div className="graph-controls" aria-label="Graph controls"><button onClick={() => zoom(1.4)} aria-label="Zoom in"><Plus size={15} /></button><button onClick={() => zoom(.72)} aria-label="Zoom out"><Minus size={15} /></button><button onClick={reset} aria-label="Fit graph"><Maximize2 size={14} /></button>{selected ? <button onClick={() => onSelect(null)} aria-label="Clear focus"><Focus size={14} /></button> : null}</div>
    <div className="graph-key">{types.map((type) => <span key={type}><i style={{ background: colorFor(type) }} />{formatType(type)}</span>)}</div>
    <div className="graph-legend"><span><b>{graph.order}</b> memories</span><span><b>{graph.size}</b> connections</span><span className="graph-state"><i />state {memory.sequence}</span></div>
  </div>;
}

export default function MemoryView() {
  const [lens, setLens] = useState<MemoryLens>("graph");
  const [channel, setChannel] = useState<ChannelFilter>("all");
  const [world, setWorld] = useState<WorldMemory | null>(null);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [node, setNode] = useState<MemoryNode | null>(null);
  const [error, setError] = useState("");
  const [entries, setEntries] = useState<ScopedMemory[]>([]);
  const [affect, setAffect] = useState<AffectState | null>(null);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [activeContext, setActiveContext] = useState<ActiveContext | null>(null);
  useEffect(() => {
    Promise.all([api.world(), api.memoryEntries(), api.affect(), api.timeline()])
      .then(([nextWorld, nextEntries, nextAffect, nextTimeline]) => { setWorld(nextWorld); setEntries(nextEntries.entries); setActiveContext(nextEntries.context); setAffect(nextAffect); setTimeline(nextTimeline); })
      .catch(() => setError("Memory API unavailable. Restart the Halcyon server to load the current state."));
  }, []);
  useEffect(() => {
    if (!selected || selected.startsWith("mem_") || selected.startsWith("scope:")) { setNode(null); return; }
    api.memoryNode(selected).then(setNode).catch(() => setNode(null));
  }, [selected]);
  const results = useMemo(() => {
    if (!world || !query.trim()) return [];
    return Object.values(world.nodes).filter((node) => `${node.label} ${node.type}`.toLowerCase().includes(query.toLowerCase())).slice(0, 8);
  }, [world, query]);
  const projectedWorld = useMemo(() => world ? braidProjection(world, entries, channel) : null, [world, entries, channel]);
  return <main className="memory-page">
    <header className="memory-toolbar"><div><span className="eyebrow">Affect · Memory · Language</span><h1>Memory <small>{world ? Object.keys(world.nodes).length + entries.length : ""}</small></h1></div>
      <div className="memory-search"><Search size={15} /><input aria-label="Search memory" placeholder="Search memory" value={query} onChange={(event) => setQuery(event.target.value)} />
        {query && <button aria-label="Clear search" onClick={() => setQuery("")}><X size={14} /></button>}
        {results.length > 0 ? <div className="search-results">{results.map((node) => <button key={node.id} onClick={() => { setSelected(node.id); setQuery(""); }}><i style={{ background: colorFor(node.type) }} /><span>{node.label}</span><small>{node.type}</small></button>)}</div> : null}
      </div>
      <span className="memory-sequence"><i /> live state {world?.sequence ?? "…"}</span>
    </header>
    <div className="memory-subnav"><LensTabs lens={lens} onChange={setLens} />{lens !== "affect" ? <ChannelTabs channel={channel} onChange={setChannel} /> : null}<div className="scope-pills"><span>global</span>{activeContext?.skills.map((item) => <span key={item}>{item}</span>)}{activeContext?.world ? <span>{activeContext.world}</span> : null}{activeContext?.task ? <span>{activeContext.task}</span> : null}</div></div>
    <section className="memory-content">{error ? <div className="memory-error"><Database size={26} /><h2>Memory unavailable</h2><p>{error}</p></div> : world ? lens === "graph" && projectedWorld ? <WorldGraph memory={projectedWorld} selected={selected} onSelect={setSelected} /> : lens === "explorer" ? <Explorer entries={channel === "all" ? entries : entries.filter((item) => item.channel === channel)} query={query} /> : lens === "timeline" ? <Timeline events={channel === "all" ? timeline : timeline.filter((item) => item.kind === channel)} /> : affect ? <AffectLens affect={affect} emotional={entries.filter((item) => item.channel === "emotional_semantic")} /> : <div className="memory-loading">Loading Affect…</div> : <div className="memory-loading">Loading world…</div>}
      {node ? <NodeInspector node={node} onClose={() => setSelected(null)} onSelect={setSelected} /> : null}
    </section>
  </main>;
}
