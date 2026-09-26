export type Conversation = {
  id: string;
  title: string;
  created_at: number;
  updated_at: number;
  turn_count: number;
};

export type Message = {
  id: string;
  turn_id: string;
  role: "user" | "assistant";
  raw_content: string;
  display_content: string;
  reasoning_content?: string | null;
  reasoning_kind?: "summary" | "analysis" | null;
  turn_status: string;
  outcome?: string | null;
  input_tokens?: number | null;
  reasoning_tokens?: number | null;
  output_tokens?: number | null;
  total_tokens?: number | null;
  token_count_source?: string | null;
  created_at: number;
};

export type ConversationDetail = Conversation & {
  messages: Message[];
  active_turn?: { id: string } | null;
};

export type TokenUsage = {
  instructions: number;
  knowledge: number;
  conversation: number;
  draft: number;
  total: number;
  context_limit: number;
  source: string;
  exact: boolean;
};

export type StreamEvent = {
  turn_id: string;
  sequence: number;
  timestamp: number;
  delta?: string;
  reasoning_kind?: "summary" | "analysis";
  display_content?: string;
  reasoning_content?: string | null;
  outcome?: string;
  message_id?: string;
  receipt_id?: string;
  proposal_id?: string | null;
  gate_decision_id?: string;
  usage?: Record<string, number | string | null>;
  error_code?: string;
};

export type WorldMemory = {
  sequence: number;
  schema_version: number;
  sources: Record<string, { kind: string; title: string; captured_at: string }>;
  nodes: Record<string, { id: string; label: string; type: string; visibility: string; properties: Record<string, unknown>; sources: string[] }>;
  edges: { id: string; source: string; source_label?: string; relation: string; target: string; target_label?: string; assertion: string; confidence?: number | null; status: string; properties?: Record<string, unknown>; sources: string[] }[];
  constraints: { id: string; target: string; rule: string; value: string; sources: string[] }[];
};

export type SelfMemory = {
  sequence: number;
  name: string;
  memory: Record<string, string>;
};

export type MemoryNode = {
  id: string;
  name: string;
  type: string;
  properties: Record<string, unknown>;
  sources: string[];
  source_details: { kind?: string; title: string; captured_at?: string }[];
  aliases: string[];
  incoming: WorldMemory["edges"];
  outgoing: WorldMemory["edges"];
  constraints: WorldMemory["constraints"];
  sequence: number;
  provenance?: Record<string, unknown> | null;
};

export type MemoryChannel = "experience" | "cognitive_semantic" | "emotional_semantic";
export type ScopedMemory = {
  id: string; scope: string; scope_type: string; scope_id?: string | null;
  channel: MemoryChannel; content: string; origin: string; source_event_id?: string | null;
  derived_from: string[]; affect_before?: Record<string, number> | null;
  affect_after?: Record<string, number> | null; affect_delta?: Record<string, number> | null;
  created_at: number;
};
export type ActiveContext = { global: true; world: string | null; task: string | null; skills: string[] };
export type AffectState = {
  values: Record<string, number>; baselines: Record<string, number>; directions: Record<string, string>;
  history: { id: string; source_event_id: string; transition_kind: string; before: Record<string, number>; delta: Record<string, number>; after: Record<string, number>; created_at: number }[];
};
export type TimelineEvent = { id: string; kind: MemoryChannel | "affect"; content: string; scope: string; created_at: number; delta?: Record<string, number> };
export type SelfClaim = { id: string; kind: string; subject: string; predicate: string; value: string; status: string; source: string; created_at: number; self_version: number };
export type Capability = { id: string; source: string; effect_class: string; description: string; schema: Record<string, unknown>; scope: Record<string, unknown>; limits: Record<string, unknown>; available: boolean; boundary_version: string };
export type SystemProjection = {
  projection: true; versions: Record<string, number>;
  self: { claims: SelfClaim[]; claim_count: number; version: number };
  memory: { channels: Record<string, number>; reachable_entries: number; world_nodes: number; world_edges: number; version: number };
  affect: AffectState & { version: number };
  context: ActiveContext & { version: number };
  capabilities: { items: Capability[]; available: number; version: number };
  governance: { boundaries: Record<string, string>; version: number };
};
export type ToolReceipt = { id: string; tool_id: string; source: string; effect_class: string; raw_args: Record<string, unknown>; normalized_args?: Record<string, unknown>; context: ActiveContext; capability_version: number; decision: string; checks: string[][]; execution_status: string; result?: unknown; error?: string; created_at: number };
export type ImaginationRun = {
  id: string; conversation_id: string; seed: string; max_steps: number; completed_steps: number;
  status: "running" | "paused" | "cancelled" | "complete" | "failed";
  active_turn_id?: string | null; created_at: number; updated_at: number;
  conversation?: ConversationDetail;
  turn_kinds?: Record<string, { kind: "chat" | "autonomous"; step: number | null }>;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail));
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string; model: string; model_api: string; state_sequence: number }>("/api/health"),
  conversations: () => request<Conversation[]>("/api/conversations"),
  conversation: (id: string) => request<ConversationDetail>(`/api/conversations/${id}`),
  createTurn: (conversationId: string | null, content: string) =>
    request<{ turn_id: string; conversation_id: string; stream_url: string }>(
      `/api/conversations/${conversationId ?? "new"}/turns`,
      { method: "POST", body: JSON.stringify({ content }) },
    ),
  cancelTurn: (turnId: string) =>
    request(`/api/turns/${turnId}/cancel`, { method: "POST" }),
  tokens: (conversationId: string | null, draft: string) =>
    request<TokenUsage>("/api/tokens/count", {
      method: "POST",
      body: JSON.stringify({ conversation_id: conversationId, draft }),
    }),
  context: (turnId: string) => request<Record<string, unknown>>(`/api/turns/${turnId}/context`),
  governance: (kind: string) => request<Record<string, unknown>[]>(`/api/governance/${kind}`),
  boundary: () => request<Record<string, unknown>>("/api/boundary/attestation"),
  world: () => request<WorldMemory>("/api/memory/world"),
  selfMemory: () => request<SelfMemory>("/api/memory/self"),
  memoryNode: (name: string) => request<MemoryNode>(`/api/memory/nodes/${encodeURIComponent(name)}`),
  memoryEntries: (channel = "all") => request<{ context: ActiveContext; entries: ScopedMemory[] }>(`/api/memory/entries?channel=${channel}`),
  affect: () => request<AffectState>("/api/affect"),
  timeline: () => request<TimelineEvent[]>("/api/memory/timeline"),
  activeContext: () => request<ActiveContext>("/api/context/active"),
  setActiveContext: (context: Omit<ActiveContext, "global">) => request<ActiveContext>("/api/context/active", { method: "PUT", body: JSON.stringify(context) }),
  systemProjection: () => request<SystemProjection>("/api/system/projection"),
  selfClaims: () => request<{ version: number; claims: SelfClaim[] }>("/api/self/claims"),
  capabilities: () => request<{ version: number; items: Capability[] }>("/api/capabilities"),
  toolReceipts: () => request<ToolReceipt[]>("/api/tools/receipts"),
  executeTool: (tool_id: string, args: Record<string, unknown> = {}) => request<{ observation: unknown; receipt_id: string; remembered: false }>("/api/tools/execute", { method: "POST", body: JSON.stringify({ tool_id, arguments: args }) }),
  imaginationRuns: () => request<ImaginationRun[]>("/api/imagination/runs"),
  imaginationRun: (id: string) => request<ImaginationRun>(`/api/imagination/runs/${id}`),
  createImaginationRun: (seed: string, max_steps: number, auto_start = true) => request<ImaginationRun & { stream_url: string }>("/api/imagination/runs", { method: "POST", body: JSON.stringify({ seed, max_steps, auto_start }) }),
  startImagination: (id: string, turns: number) => request<ImaginationRun>(`/api/imagination/runs/${id}/start`, { method: "POST", body: JSON.stringify({ turns }) }),
  imaginationMessage: (id: string, content: string) => request<{ turn_id: string; run_id: string; stream_url: string }>(`/api/imagination/runs/${id}/messages`, { method: "POST", body: JSON.stringify({ content }) }),
  pauseImagination: (id: string) => request<ImaginationRun>(`/api/imagination/runs/${id}/pause`, { method: "POST" }),
  resumeImagination: (id: string) => request<ImaginationRun>(`/api/imagination/runs/${id}/resume`, { method: "POST" }),
  stopImagination: (id: string) => request<ImaginationRun>(`/api/imagination/runs/${id}/stop`, { method: "POST" }),
};
