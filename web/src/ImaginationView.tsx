import { FormEvent, useEffect, useRef, useState } from "react";
import { Brain, CircleDot, Pause, Send, Sparkles, Square } from "lucide-react";
import { api, ImaginationRun, Message, WorldMemory } from "./api";
import ImaginationWorldGraph from "./ImaginationWorldGraph";

type LiveTurn = { content: string; reasoning: string; status: "thinking" | "responding" | "saving"; kind: "chat" | "autonomous" };

function ImaginationTranscript({ run, live }: { run: ImaginationRun | null; live: LiveTurn | null }) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [run?.conversation?.messages.length, live?.content]);
  const kinds = run?.turn_kinds ?? {};
  const visible = (run?.conversation?.messages ?? []).filter((message) => message.role === "assistant" || kinds[message.turn_id]?.kind === "chat");
  return <div className="imagination-transcript">
    {!visible.length && !live ? <div className="imagination-awaiting"><Sparkles size={24} /><h2>A world waiting to happen</h2><p>Talk with Halcyon about the world, or choose a number of turns and let her rip.</p></div> : visible.map((message: Message) => {
      const meta = kinds[message.turn_id];
      const isUser = message.role === "user";
      const label = isUser ? "You" : meta?.kind === "autonomous" ? `Autonomous turn ${meta.step ?? ""}` : "Halcyon";
      return <article key={message.id} className={isUser ? "world-user-message" : "world-assistant-message"}>
        <header><span>{label}</span>{!isUser && message.outcome ? <b className={message.outcome}><CircleDot size={9} />{message.outcome}</b> : null}</header>
        {!isUser && message.reasoning_content ? <details><summary><Brain size={12} />Thinking</summary><p>{message.reasoning_content}</p></details> : null}
        <p>{message.display_content}</p>
      </article>;
    })}
    {live ? <article className={`live ${live.kind}`}><header><span>{live.kind === "chat" ? "Halcyon" : "Imagining now"}</span><b><i />{live.status}</b></header>{live.reasoning ? <details open><summary><Brain size={12} />Thinking</summary><p>{live.reasoning}</p></details> : null}{live.content ? <p>{live.content}<i className="stream-caret" /></p> : null}</article> : null}
    <div ref={end} />
  </div>;
}

function patchFocus(patch: Record<string, any> | null): string | null {
  if (!patch) return null;
  const result = patch.result ?? {};
  return result.created ?? result.node_id ?? result.target ?? result.source ?? result.related?.target ?? result.occurred?.source ?? result.constrained?.target ?? null;
}

export default function ImaginationView() {
  const [run, setRun] = useState<ImaginationRun | null>(null);
  const runRef = useRef<ImaginationRun | null>(null);
  const [world, setWorld] = useState<WorldMemory | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [seed, setSeed] = useState("Grow a world that reflects continuity, wonder, and the strange consequences of memory.");
  const [turns, setTurns] = useState(5);
  const [draft, setDraft] = useState("");
  const [live, setLive] = useState<LiveTurn | null>(null);
  const [error, setError] = useState("");
  const stream = useRef<EventSource | null>(null);

  const updateRun = (next: ImaginationRun) => { runRef.current = next; setRun(next); };
  const refresh = async (runId?: string) => {
    const [nextWorld, nextRun] = await Promise.all([api.imaginationWorld(), runId ? api.imaginationRun(runId) : Promise.resolve(null)]);
    setWorld(nextWorld);
    if (nextRun) updateRun(nextRun);
  };
  const subscribe = (id: string, url = `/api/imagination/runs/${id}/stream`) => {
    stream.current?.close();
    const events = new EventSource(url);
    stream.current = events;
    events.addEventListener("imagination.autonomous.started", () => setLive({ content: "", reasoning: "", status: "thinking", kind: "autonomous" }));
    events.addEventListener("imagination.chat.started", () => setLive({ content: "", reasoning: "", status: "thinking", kind: "chat" }));
    events.addEventListener("imagination.assistant.reasoning.delta", (event) => { const data = JSON.parse((event as MessageEvent).data); setLive((current) => current ? { ...current, reasoning: current.reasoning + data.delta } : current); });
    events.addEventListener("imagination.assistant.delta", (event) => { const data = JSON.parse((event as MessageEvent).data); setLive((current) => current ? { ...current, content: current.content + data.delta, status: "responding" } : current); });
    events.addEventListener("imagination.assistant.completed", async () => { setLive((current) => current ? { ...current, status: "saving" } : current); await refresh(id); setLive(null); });
    events.addEventListener("imagination.step.completed", async (event) => { const data = JSON.parse((event as MessageEvent).data); await refresh(id); const focus = patchFocus(data.graph_patch); if (focus) setSelected(focus); setLive(null); });
    for (const name of ["imagination.run.completed", "imagination.run.paused", "imagination.run.cancelled", "imagination.run.failed"]) events.addEventListener(name, async () => { events.close(); setLive(null); await refresh(id); });
    events.onerror = () => { if (events.readyState !== EventSource.CLOSED) setError("The imagination stream disconnected."); };
  };
  useEffect(() => {
    Promise.all([api.imaginationWorld(), api.imaginationRuns()]).then(async ([nextWorld, runs]) => {
      setWorld(nextWorld);
      if (runs[0]) { const detail = await api.imaginationRun(runs[0].id); updateRun(detail); if (detail.status === "running" || detail.conversation?.active_turn) subscribe(detail.id); }
    }).catch(() => setError("Imagination is unavailable. Restart the Halcyon server."));
    return () => stream.current?.close();
  }, []);

  const ensureSession = async () => {
    if (runRef.current) return runRef.current;
    const created = await api.createImaginationRun(seed, 1, false);
    updateRun(created);
    return created;
  };
  const rip = async () => {
    try { setError(""); setLive(null); const current = await ensureSession(); const next = await api.startImagination(current.id, turns); updateRun(next); subscribe(current.id); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Imagination could not start."); }
  };
  const send = async (event: FormEvent) => {
    event.preventDefault();
    const content = draft.trim();
    if (!content) return;
    try { setError(""); const current = await ensureSession(); setDraft(""); const response = await api.imaginationMessage(current.id, content); await refresh(current.id); subscribe(current.id, response.stream_url); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Message could not be sent."); }
  };
  const pause = async () => { if (run) updateRun(await api.pauseImagination(run.id)); };
  const stop = async () => { if (run) updateRun(await api.stopImagination(run.id)); };
  const busy = run?.status === "running" || Boolean(run?.conversation?.active_turn) || Boolean(live);

  return <main className="imagination-page">
    <header className="imagination-toolbar"><div><span className="eyebrow">Living world workspace</span><h1>Imagination</h1></div><div className="imagination-intention"><input aria-label="World intention" value={seed} onChange={(event) => setSeed(event.target.value)} disabled={Boolean(run)} /></div><div className="imagination-actions">
      <label className="turn-counter"><span>Turns</span><input aria-label="Autonomous turn count" type="number" min="1" max="20" value={turns} onChange={(event) => setTurns(Math.max(1, Math.min(20, Number(event.target.value) || 1)))} disabled={busy} /></label>
      <button className="rip-button" onClick={() => void rip()} disabled={busy}><Sparkles size={13} />Rip</button>
      <button onClick={pause} disabled={run?.status !== "running"}><Pause size={13} />Pause</button>
      <button onClick={stop} disabled={run?.status !== "running"}><Square size={11} />Stop</button>
    </div></header>
    <div className="imagination-status"><span className={`run-state ${run?.status ?? "idle"}`}><i />{run?.status ?? "idle"}</span><span>{run ? `${run.completed_steps} autonomous turns complete` : "New world session"}</span><span>{world ? `state ${world.sequence} · ${Object.keys(world.nodes).length} nodes` : "loading world"}</span>{error ? <b>{error}</b> : null}</div>
    <div className="imagination-split"><section className="imagination-chat"><ImaginationTranscript run={run} live={live} /><form className="world-composer" onSubmit={send}><textarea aria-label="Talk to Halcyon about the world" placeholder="Talk to Halcyon about this world…" rows={2} value={draft} onChange={(event) => setDraft(event.target.value)} disabled={busy} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} /><button aria-label="Send world message" disabled={busy || !draft.trim()}><Send size={14} /></button></form></section><section className="imagination-world"><div className="world-pane-label"><span>Canonical world</span><b>Live graph</b></div>{world ? <ImaginationWorldGraph memory={world} selected={selected} onSelect={setSelected} /> : <div className="memory-loading">Loading world…</div>}</section></div>
  </main>;
}
