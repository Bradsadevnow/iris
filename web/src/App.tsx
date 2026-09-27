import { FormEvent, KeyboardEvent, lazy, Suspense, useEffect, useRef, useState } from "react";
import {
  Activity, Brain, Check, ChevronDown, ChevronRight, CircleDot,
  Database, FileCheck2, MessageSquare, Network, PanelLeftClose, PanelLeftOpen,
  Plus, Send, Settings, ShieldCheck, Sparkles, Square, UserRound, X,
} from "lucide-react";
import { api, Conversation, ConversationDetail, Message, StreamEvent, TokenUsage } from "./api";
import { ActiveProjectionPanel, ContextInspector } from "./ContextPanels";

const MemoryView = lazy(() => import("./MemoryView"));
const SelfSystemView = lazy(() => import("./SelfSystemView"));
const ImaginationView = lazy(() => import("./ImaginationView"));

type View = "chat" | "imagination" | "memory" | "self" | "proposals" | "gate-decisions" | "receipts" | "boundary" | "settings";
type DraftAssistant = {
  turnId: string;
  content: string;
  reasoning: string;
  status: "thinking" | "responding" | "saving" | "failed";
  outcome?: string;
  usage?: Record<string, number | string | null>;
};

const formatTokens = (value: number) => value >= 1000 ? `${(value / 1000).toFixed(1)}k` : `${value}`;
const relativeTime = (timestamp: number) => {
  const seconds = Math.max(0, Math.floor(Date.now() / 1000 - timestamp));
  if (seconds < 60) return "now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
  return `${Math.floor(seconds / 86400)}d`;
};

function IconButton({ label, onClick, children, className = "" }: {
  label: string; onClick?: () => void; children: React.ReactNode; className?: string;
}) {
  return <button type="button" className={`icon-button ${className}`} aria-label={label} title={label} onClick={onClick}>{children}</button>;
}

function Sidebar({ collapsed, setCollapsed, conversations, selectedId, onSelect, onNew, view, setView }: {
  collapsed: boolean;
  setCollapsed: (value: boolean) => void;
  conversations: Conversation[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  view: View;
  setView: (view: View) => void;
}) {
  const governance: { id: View; label: string; icon: React.ReactNode }[] = [
    { id: "proposals", label: "Proposals", icon: <Sparkles size={17} /> },
    { id: "gate-decisions", label: "Gate decisions", icon: <ShieldCheck size={17} /> },
    { id: "receipts", label: "Receipts", icon: <FileCheck2 size={17} /> },
    { id: "boundary", label: "Boundary", icon: <Database size={17} /> },
  ];
  return (
    <aside className={`sidebar ${collapsed ? "collapsed" : ""}`}>
      <div className="sidebar-head">
        {!collapsed && <div className="wordmark"><span className="iris-mark" />halcyon</div>}
        <IconButton label={collapsed ? "Expand sidebar" : "Collapse sidebar"} onClick={() => setCollapsed(!collapsed)}>
          {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
        </IconButton>
      </div>
      <button className="new-chat" aria-label="New chat" title={collapsed ? "New chat" : undefined} onClick={onNew}><Plus size={17} />{!collapsed && <span>New chat</span>}</button>
      <nav className="conversation-nav" aria-label="Conversations">
        {!collapsed && <div className="nav-label">Conversations</div>}
        {conversations.map((conversation) => (
          <button key={conversation.id} className={`conversation-link ${view === "chat" && selectedId === conversation.id ? "active" : ""}`}
            onClick={() => onSelect(conversation.id)} title={conversation.title}>
            <MessageSquare size={16} />
            {!collapsed && <><span>{conversation.title}</span><time>{relativeTime(conversation.updated_at)}</time></>}
          </button>
        ))}
      </nav>
      <nav className="governance-nav" aria-label="Governance">
        <button className={`nav-link ${view === "imagination" ? "active" : ""}`} onClick={() => setView("imagination")}><Sparkles size={17} />{!collapsed && <span>Imagination</span>}</button>
        <button className={`nav-link ${view === "memory" ? "active" : ""}`} onClick={() => setView("memory")}><Network size={17} />{!collapsed && <span>Memory</span>}</button>
        <button className={`nav-link ${view === "self" ? "active" : ""}`} onClick={() => setView("self")}><UserRound size={17} />{!collapsed && <span>Self</span>}</button>
        {!collapsed && <div className="nav-label">Governance</div>}
        {governance.map((item) => (
          <button key={item.id} className={`nav-link ${view === item.id ? "active" : ""}`} onClick={() => setView(item.id)}>
            {item.icon}{!collapsed && <span>{item.label}</span>}
          </button>
        ))}
      </nav>
      <button className={`settings-link ${view === "settings" ? "active" : ""}`} aria-label="Settings" title={collapsed ? "Settings" : undefined} onClick={() => setView("settings")}><Settings size={17} />{!collapsed && <span>Settings</span>}</button>
    </aside>
  );
}

function Thinking({ content, active, turnId, onContext }: {
  content?: string | null; active?: boolean; turnId: string; onContext: (turnId: string) => void;
}) {
  const [open, setOpen] = useState(Boolean(active));
  if (!active && !content) return null;
  return (
    <div className={`thinking ${active ? "active" : ""}`}>
      <button className="thinking-toggle" onClick={() => setOpen(!open)} aria-expanded={open}>
        <Brain size={15} /><span>{active ? "Thinking…" : "Thinking"}</span>
        <ChevronDown size={14} className={open ? "rotated" : ""} />
      </button>
      {open && <div className="thinking-body">
        {content ? <div className="thinking-content">{content}</div> : <div className="thinking-placeholder">Waiting for the model…</div>}
        <button className="context-link" onClick={() => onContext(turnId)}>Context used <ChevronRight size={13} /></button>
      </div>}
    </div>
  );
}

function Outcome({ outcome, onOpen }: { outcome?: string | null; onOpen: () => void }) {
  if (!outcome || outcome === "none") return null;
  const labels: Record<string, string> = { committed: "Remembered", denied: "Not remembered", noop: "No change", execution_failed: "Could not save" };
  return <button className={`outcome ${outcome}`} onClick={onOpen}>
    {outcome === "committed" ? <Check size={13} /> : <CircleDot size={13} />}{labels[outcome] ?? outcome}
  </button>;
}

function Transcript({ detail, draft, onContext, onReceipt }: {
  detail: ConversationDetail | null;
  draft: DraftAssistant | null;
  onContext: (turnId: string) => void;
  onReceipt: (turnId: string) => void;
}) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [detail?.messages.length, draft?.content]);
  if (!detail?.messages.length && !draft) {
    return <div className="empty-state"><div className="empty-orb"><span /></div><h1>Talk to Halcyon</h1><p>She remembers through a boundary you can inspect.</p></div>;
  }
  return <div className="transcript">
    {detail?.messages.map((message) => (
      <article className={`message ${message.role}`} key={message.id}>
        <div className="message-meta">{message.role === "user" ? "You" : "Halcyon"}</div>
        {message.role === "assistant" && <Thinking content={message.reasoning_content} turnId={message.turn_id} onContext={onContext} />}
        <div className="message-content">{message.display_content}</div>
        {message.role === "assistant" && <div className="message-foot">
          <Outcome outcome={message.outcome} onOpen={() => onReceipt(message.turn_id)} />
          {message.total_tokens ? <span className="message-tokens">{message.total_tokens.toLocaleString()} tokens · {message.token_count_source}</span> : null}
        </div>}
      </article>
    ))}
    {draft && <article className="message assistant live">
      <div className="message-meta">Halcyon</div>
      <Thinking content={draft.reasoning} active={draft.status === "thinking"} turnId={draft.turnId} onContext={onContext} />
      {draft.content && <div className="message-content">{draft.content}<span className="stream-caret" /></div>}
      <div className="stream-status"><Activity size={13} />{draft.status === "saving" ? "Saving" : draft.status === "failed" ? "Connection failed" : draft.content ? "Responding" : "Thinking"}</div>
    </article>}
    <div ref={endRef} />
  </div>;
}

function TokenCounter({ usage, open, setOpen }: { usage: TokenUsage | null; open: boolean; setOpen: (value: boolean) => void }) {
  const wrapRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const dismissOutside = (event: PointerEvent) => {
      if (!wrapRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const dismissEscape = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", dismissOutside);
    document.addEventListener("keydown", dismissEscape);
    return () => {
      document.removeEventListener("pointerdown", dismissOutside);
      document.removeEventListener("keydown", dismissEscape);
    };
  }, [open, setOpen]);
  if (!usage) return <span className="token-counter muted">counting…</span>;
  const ratio = usage.total / usage.context_limit;
  return <div className="token-wrap" ref={wrapRef}>
    <button className={`token-counter ${ratio >= .95 ? "critical" : ratio >= .8 ? "warning" : ""}`} onClick={() => setOpen(!open)}>
      {!usage.exact && "~"}{formatTokens(usage.total)} / {formatTokens(usage.context_limit)}
    </button>
    {open && <div className="token-popover">
      <div><span>Instructions</span><strong>{formatTokens(usage.instructions)}</strong></div>
      <div><span>Knowledge</span><strong>{formatTokens(usage.knowledge)}</strong></div>
      <div><span>Conversation</span><strong>{formatTokens(usage.conversation)}</strong></div>
      <div><span>Draft</span><strong>{formatTokens(usage.draft)}</strong></div>
      <div className="token-total"><span>Total</span><strong>{formatTokens(usage.total)}</strong></div>
      <small>{usage.exact ? "Model tokenizer" : "Estimated count"}</small>
    </div>}
  </div>;
}

function Composer({ conversationId, busy, onSend, onStop }: {
  conversationId: string | null; busy: boolean; onSend: (text: string) => Promise<void>; onStop: () => void;
}) {
  const [text, setText] = useState("");
  const [usage, setUsage] = useState<TokenUsage | null>(null);
  const [tokensOpen, setTokensOpen] = useState(false);
  useEffect(() => {
    const timer = window.setTimeout(() => api.tokens(conversationId, text).then(setUsage).catch(() => setUsage(null)), 250);
    return () => window.clearTimeout(timer);
  }, [conversationId, text]);
  const submit = async (event?: FormEvent) => {
    event?.preventDefault();
    const value = text.trim();
    if (!value || busy || (usage && usage.total > usage.context_limit)) return;
    setText("");
    await onSend(value).catch(() => setText(value));
  };
  const keyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void submit(); }
  };
  return <div className="composer-shell"><form className="composer" onSubmit={submit}>
    <textarea value={text} onChange={(event) => setText(event.target.value)} onKeyDown={keyDown}
      placeholder="Message Halcyon…" rows={1} aria-label="Message Halcyon" disabled={busy} />
    <div className="composer-bottom">
      <TokenCounter usage={usage} open={tokensOpen} setOpen={setTokensOpen} />
      {busy ? <IconButton label="Stop generating" className="send-button stop" onClick={onStop}><Square size={14} fill="currentColor" /></IconButton>
        : <IconButton label="Send message" className="send-button" onClick={() => void submit()}><Send size={16} /></IconButton>}
    </div>
  </form><div className="composer-note">Halcyon can make mistakes. Inspect memory changes when they matter.</div></div>;
}

function Drawer({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return <aside className="drawer" aria-label={title}><header><h2>{title}</h2><IconButton label="Close" onClick={onClose}><X size={18} /></IconButton></header><div className="drawer-body">{children}</div></aside>;
}

function ReceiptDrawer({ turnId, onClose }: { turnId: string; onClose: () => void }) {
  const [items, setItems] = useState<Record<string, any>[]>([]);
  useEffect(() => { api.governance("receipts").then(setItems); }, []);
  const receipt = items.find((item) => item.turn_id === turnId);
  const checks = receipt ? JSON.parse(receipt.decision_basis_json) as string[][] : [];
  return <Drawer title="Gate receipt" onClose={onClose}>
    {!receipt ? <p className="muted">Loading receipt…</p> : <>
      <div className={`decision-hero ${receipt.outcome}`}><ShieldCheck size={18} /><div><strong>{receipt.outcome.replaceAll("_", " ")}</strong><span>{receipt.decision}</span></div></div>
      <div className="check-list">{checks.map((check, index) => <div className="check-row" key={`${check[0]}-${index}`}><span className={`check-state ${check[1].toLowerCase()}`}>{check[1]}</span><div><strong>{check[0]}</strong><p>{check[2]}</p></div></div>)}</div>
      <details><summary>Technical details</summary><pre className="context-content">{receipt.rationale}</pre></details>
    </>}
  </Drawer>;
}

function Governance({ view }: { view: Exclude<View, "chat"> }) {
  const [items, setItems] = useState<Record<string, any>[]>([]);
  const [boundary, setBoundary] = useState<Record<string, any> | null>(null);
  useEffect(() => {
    if (view === "boundary") api.boundary().then(setBoundary);
    else api.governance(view).then(setItems);
  }, [view]);
  const title = view === "gate-decisions" ? "Gate decisions" : view[0].toUpperCase() + view.slice(1);
  if (view === "boundary") return <main className="governance-page"><div className="page-head"><span className="eyebrow">Governance</span><h1>Boundary</h1><p>What this Halcyon instance actually enforces.</p></div><pre className="boundary-code">{boundary ? JSON.stringify(boundary, null, 2) : "Loading…"}</pre></main>;
  return <main className="governance-page"><div className="page-head"><span className="eyebrow">Governance</span><h1>{title}</h1><p>{view === "proposals" ? "What Halcyon asked the gate to change." : view === "receipts" ? "Immutable evidence for every adjudicated turn." : "How proposals moved through admission, execution, and persistence."}</p></div>
    <div className="governance-list">{items.length === 0 ? <div className="list-empty">Nothing here yet. Talk to Halcyon and proposed changes will appear here.</div> : items.map((item) => <div className="governance-row" key={item.id}>
      <div className="row-icon">{view === "proposals" ? <Sparkles size={16} /> : view === "receipts" ? <FileCheck2 size={16} /> : <ShieldCheck size={16} />}</div>
      <div className="row-main"><strong>{view === "proposals" ? `${item.verb ?? "Malformed proposal"}` : view === "receipts" ? item.outcome : `${item.admission} · ${item.execution}`}</strong><span>{view === "proposals" ? item.what_path ?? item.raw_line : view === "receipts" ? item.decision : `Persistence: ${item.persistence}`}</span></div>
      <div className="row-side"><span>Turn {item.ordinal}</span><time>{relativeTime(item.created_at)}</time></div>
    </div>)}</div>
  </main>;
}

function SettingsPage() {
  const [health, setHealth] = useState<{ status: string; model: string; model_api: string; state_sequence: number } | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => { api.health().then(setHealth).catch(() => setFailed(true)); }, []);
  return <main className="governance-page"><div className="page-head"><span className="eyebrow">Halcyon</span><h1>Settings</h1><p>Current server connection and model configuration.</p></div>
    <div className="settings-grid">
      <div className="setting-row"><span>Server</span><strong className={failed ? "bad" : "good"}>{failed ? "Disconnected" : health ? "Connected" : "Checking…"}</strong></div>
      <div className="setting-row"><span>Model</span><strong>{health?.model ?? "—"}</strong></div>
      <div className="setting-row"><span>API protocol</span><strong>{health?.model_api ?? "—"}</strong></div>
      <div className="setting-row"><span>State sequence</span><strong>{health?.state_sequence ?? "—"}</strong></div>
    </div>
    <p className="settings-note">Connection values are configured through server environment variables. Secrets are never returned to this interface.</p>
  </main>;
}

export default function App() {
  const [collapsed, setCollapsed] = useState(false);
  const [view, setView] = useState<View>("chat");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ConversationDetail | null>(null);
  const [draft, setDraft] = useState<DraftAssistant | null>(null);
  const [drawer, setDrawer] = useState<{ type: "context" | "receipt"; turnId: string } | { type: "self" } | null>(null);

  const refreshList = () => api.conversations().then(setConversations);
  const loadConversation = (id: string) => { setConversationId(id); setView("chat"); api.conversation(id).then(setDetail); };
  useEffect(() => { void refreshList(); }, []);

  const send = async (content: string) => {
    const optimisticUser: Message = { id: `local-${Date.now()}`, turn_id: "pending", role: "user", raw_content: content, display_content: content, turn_status: "generating", created_at: Date.now() / 1000 };
    setDetail((current) => ({ ...(current ?? { id: "new", title: "New conversation", created_at: Date.now() / 1000, updated_at: Date.now() / 1000, turn_count: 0, messages: [] }), messages: [...(current?.messages ?? []), optimisticUser] }));
    const created = await api.createTurn(conversationId, content);
    setConversationId(created.conversation_id);
    setDraft({ turnId: created.turn_id, content: "", reasoning: "", status: "thinking" });
    const stream = new EventSource(created.stream_url);
    stream.addEventListener("assistant.reasoning.delta", (event) => {
      const data = JSON.parse((event as MessageEvent).data) as StreamEvent;
      setDraft((current) => current && ({ ...current, reasoning: current.reasoning + (data.delta ?? "") }));
    });
    stream.addEventListener("assistant.delta", (event) => {
      const data = JSON.parse((event as MessageEvent).data) as StreamEvent;
      setDraft((current) => current && ({ ...current, content: current.content + (data.delta ?? ""), status: "responding" }));
    });
    stream.addEventListener("assistant.finalizing", () => setDraft((current) => current && ({ ...current, status: "saving" })));
    stream.addEventListener("assistant.completed", async (event) => {
      const completed = JSON.parse((event as MessageEvent).data) as StreamEvent & { affect_transition?: { after?: Record<string, number> } };
      stream.close(); setDraft(null); await refreshList(); setDetail(await api.conversation(created.conversation_id));
    });
    stream.addEventListener("turn.failed", () => { stream.close(); setDraft((current) => current && ({ ...current, status: "failed" })); });
    stream.addEventListener("turn.cancelled", async () => { stream.close(); setDraft(null); setDetail(await api.conversation(created.conversation_id)); });
  };

  const stop = async () => { if (draft) await api.cancelTurn(draft.turnId); };
  const selectView = (next: View) => { setView(next); setDrawer(null); };

  return <div className="app-shell">
    <Sidebar collapsed={collapsed} setCollapsed={setCollapsed} conversations={conversations} selectedId={conversationId}
      onSelect={loadConversation} onNew={() => { setConversationId(null); setDetail(null); setView("chat"); }} view={view} setView={selectView} />
    <section className="workspace">
      {view === "chat" ? <>
        <header className="chat-header"><div><span className="status-dot" />Halcyon</div><div className="chat-state"><button className="self-popout-button" onClick={() => setDrawer({ type: "self" })}><Network size={14} /><span>Active</span><ChevronRight size={13} /></button></div></header>
        <div className="chat-scroll"><Transcript detail={detail} draft={draft} onContext={(turnId) => setDrawer({ type: "context", turnId })} onReceipt={(turnId) => setDrawer({ type: "receipt", turnId })} /></div>
        <Composer conversationId={conversationId} busy={Boolean(draft)} onSend={send} onStop={stop} />
      </> : view === "imagination" ? <Suspense fallback={<div className="memory-loading">Opening imagination…</div>}><ImaginationView /></Suspense> : view === "memory" ? <Suspense fallback={<div className="memory-loading">Loading memory…</div>}><MemoryView /></Suspense> : view === "self" ? <Suspense fallback={<div className="memory-loading">Composing Self…</div>}><SelfSystemView /></Suspense> : view === "settings" ? <SettingsPage /> : <Governance view={view} />}
    </section>
    {drawer?.type === "context" && <Drawer title="Turn context" onClose={() => setDrawer(null)}><ContextInspector turnId={drawer.turnId} /></Drawer>}
    {drawer?.type === "receipt" && <ReceiptDrawer turnId={drawer.turnId} onClose={() => setDrawer(null)} />}
    {drawer?.type === "self" && <Drawer title="Active context" onClose={() => setDrawer(null)}><ActiveProjectionPanel conversationId={conversationId}
      onOpenTurn={(turnId) => setDrawer({ type: "context", turnId })} onOpenFull={() => { setDrawer(null); setView("self"); }} /></Drawer>}
  </div>;
}
