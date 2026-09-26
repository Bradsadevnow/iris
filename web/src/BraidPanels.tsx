import { Activity, Brain, Heart, Layers3 } from "lucide-react";
import { AffectState, MemoryChannel, ScopedMemory, TimelineEvent } from "./api";

export type MemoryLens = "graph" | "explorer" | "timeline" | "affect";
export type ChannelFilter = "all" | MemoryChannel;

export const CHANNELS: { id: ChannelFilter; label: string; color: string }[] = [
  { id: "all", label: "All", color: "#88828d" },
  { id: "experience", label: "Experience", color: "#91a8c2" },
  { id: "cognitive_semantic", label: "Meaning", color: "#aa9be2" },
  { id: "emotional_semantic", label: "Emotional meaning", color: "#d99cae" },
];

const channelLabel = (channel: string) => CHANNELS.find((item) => item.id === channel)?.label ?? channel;
const channelColor = (channel: string) => CHANNELS.find((item) => item.id === channel)?.color ?? "#88828d";

export function LensTabs({ lens, onChange }: { lens: MemoryLens; onChange: (lens: MemoryLens) => void }) {
  return <div className="lens-tabs">{(["graph", "explorer", "timeline", "affect"] as const).map((item) =>
    <button className={lens === item ? "active" : ""} key={item} onClick={() => onChange(item)}>{item}</button>)}</div>;
}

export function ChannelTabs({ channel, onChange }: { channel: ChannelFilter; onChange: (channel: ChannelFilter) => void }) {
  return <div className="channel-tabs">{CHANNELS.map((item) => <button className={channel === item.id ? "active" : ""} key={item.id} onClick={() => onChange(item.id)}><i style={{ background: item.color }} />{item.label}</button>)}</div>;
}

export function Explorer({ entries, query }: { entries: ScopedMemory[]; query: string }) {
  const visible = entries.filter((item) => `${item.content} ${item.scope} ${item.channel}`.toLowerCase().includes(query.toLowerCase()));
  const groups = visible.reduce((map, item) => map.set(item.scope, [...(map.get(item.scope) ?? []), item]), new Map<string, ScopedMemory[]>());
  if (!visible.length) return <div className="braid-empty"><Layers3 size={24} /><h2>No scoped memories in this view</h2><p>Experience, cognitive meaning, and emotional meaning will remain distinct here.</p></div>;
  return <div className="memory-explorer">{[...groups].map(([scope, items]) => <section key={scope}><header><span>{scope}</span><b>{items.length}</b></header>{items.map((item) => <article key={item.id} style={{ "--channel": channelColor(item.channel) } as React.CSSProperties}><div className="memory-channel"><i />{channelLabel(item.channel)}</div><p>{item.content}</p><footer><span>{item.origin}</span><time>{new Date(item.created_at * 1000).toLocaleString()}</time></footer>{item.affect_delta ? <div className="affect-delta">{Object.entries(item.affect_delta).filter(([, value]) => value).map(([key, value]) => <span key={key}>{key} {value > 0 ? "+" : ""}{value}</span>)}</div> : null}</article>)}</section>)}</div>;
}

export function Timeline({ events }: { events: TimelineEvent[] }) {
  if (!events.length) return <div className="braid-empty"><Activity size={24} /><h2>No braid history yet</h2><p>Committed memory and Affect transitions will meet here without becoming the same state.</p></div>;
  return <div className="braid-timeline">{events.map((event) => <article key={event.id}><time>{new Date(event.created_at * 1000).toLocaleString()}</time><i style={{ background: event.kind === "affect" ? "#d99cae" : channelColor(event.kind) }} /><div><span>{event.kind === "affect" ? "Affect" : channelLabel(event.kind)} · {event.scope}</span><p>{event.content}</p>{event.delta ? <small>{Object.entries(event.delta).filter(([, value]) => value).map(([key, value]) => `${key} ${value > 0 ? "+" : ""}${value}`).join(" · ")}</small> : null}</div></article>)}</div>;
}

export function AffectLens({ affect, emotional }: { affect: AffectState; emotional: ScopedMemory[] }) {
  return <div className="affect-lens"><header><div className="affect-mark"><Heart size={20} /></div><div><span>Canonical Affect</span><h2>Mixed states are allowed.</h2><p>Eight independent values settle toward baseline with elapsed time. Emotional meaning remains in Memory.</p></div></header><div className="affect-layout"><section className="affect-vector"><h3>Current state</h3>{Object.entries(affect.values).map(([name, value]) => { const baseline = affect.baselines[name]; return <div className="affect-row" key={name}><div><span>{name}</span><b>{value.toFixed(1)}</b></div><div className="affect-track"><i className="baseline" style={{ left: `${baseline}%` }} /><i className="value" style={{ left: `${value}%` }} /></div><small>{affect.directions[name]} · baseline {baseline}</small></div>; })}</section><section className="emotional-memory"><h3><Brain size={13} /> Emotional meaning</h3>{emotional.length ? emotional.map((item) => <article key={item.id}><span>{item.scope}</span><p>{item.content}</p></article>) : <div className="quiet-card">No emotional-semantic memories have been admitted yet. The empty channel is real—not filled with invented feelings.</div>}</section></div></div>;
}
