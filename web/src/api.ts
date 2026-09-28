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
  origin?: {
    turn_id: string; conversation_id?: string | null; ordinal?: number | null; state_sequence: number;
    reflection: string; mutation: { verb: string; what: string; arguments: Record<string, unknown>; result?: unknown };
    receipt: { id?: string | null; decision?: string | null; outcome?: string | null }; created_at: number;
  } | null;
  admission?: {
    id: string; blueprint_id: string; blueprint_revision: number; candidate_id: string;
    candidate_hash: string; state_sequence_before: number; state_sequence_after: number;
    entity_mapping: Record<string, string>; genealogy: Record<string, unknown>;
    receipt: Record<string, unknown>; created_at: number;
  } | null;
  lore?: {
    entity_id: string; title: string; markdown: string; version: number;
    created_turn_id: string | null; updated_turn_id: string | null;
    created_source_kind: string; created_source_id: string; updated_source_kind: string; updated_source_id: string;
    created_at: number; updated_at: number;
    revisions: { id: string; entity_id: string; version: number; operation: string;
      turn_id: string | null; source_kind: string; source_id: string; created_at: number }[];
  } | null;
};

export type MemoryChannel = "experience" | "cognitive_semantic" | "emotional_semantic";
export type ScopedMemory = {
  id: string; scope: string; scope_type: string; scope_id?: string | null;
  channel: MemoryChannel; content: string; origin: string; source_event_id?: string | null;
  derived_from: string[]; affect_before?: Record<string, number> | null;
  affect_after?: Record<string, number> | null; affect_delta?: Record<string, number> | null;
  created_at: number;
};
export type ActiveContext = { global: true; world: string | null; task: string | null; skills: string[]; roles: string[] };
export type RoleSummary = { id: string; name: string; version: number; tagline: string; path: string };
export type RolePackDetail = {
  id: string; name: string; version: number; tagline?: string; lineage?: string;
  claims: { id: string; kind: string; subject: string; predicate: string; value: string; source?: string }[];
  capabilities: { id: string; effect_class: string; description: string }[];
};
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
  stance?: CompiledStance;
  capabilities: { items: Capability[]; available: number; version: number };
  governance: { boundaries: Record<string, string>; version: number };
};
export type PromptProjectionNode = {
  id: string; owner: string; kind: string; label: string; content: string;
  status: string; confidence?: number | null; visibility: string; scope: string;
  source_ids: string[]; created_at?: number | null; metadata: Record<string, unknown>;
  score: number; reason: string; estimated_tokens: number;
};
export type PromptProjection = {
  id: string; turn_id?: string | null; subject_id: string; state_sequence: number;
  domain_versions: Record<string, number>;
  request: { message: string; active_context: ActiveContext; limits: { prompt_tokens: number; max_nodes: number; max_depth: number } };
  strategy: { explicit_roles: string[]; selected_roles: string[]; role_sources: Record<string, "explicit" | "inferred">; query_terms: string[]; role_terms: string[]; preferred_edges: string[]; compiled_stance?: CompiledStance };
  selected_nodes: PromptProjectionNode[];
  selected_edges: { source: string; relation: string; target: string; owner: string }[];
  expansion_handles: { node_id: string; available_edges: string[]; unexpanded_count: number }[];
  excluded_nodes: { node_id: string; reason: string }[];
  rendered_context: string; estimated_tokens: number; created_at: number;
};
export type StanceContribution = { value: string; contributed_by: string[] };
export type CompiledStance = {
  profiles: { id: string; name: string; source: "explicit" | "inferred"; attention: string[]; principles: string[]; methods: { id: string; description: string }[]; expression: string[]; preferred_edges: string[] }[];
  attention: StanceContribution[]; principles: StanceContribution[]; methods: StanceContribution[];
  expression: StanceContribution[]; preferred_edges: StanceContribution[];
  tensions: { profiles: string[]; between: string; requirement: string }[];
  precedence: string[];
};
export type ContextManifest = {
  identity_kernel: string[];
  activated_self_claims: string[];
  task_context: ActiveContext;
  roles: { id: string; source: "explicit" | "inferred" }[];
  compiled_stance?: CompiledStance;
  conversation: { messages_supplied: number; prior_messages: number };
  memory: { eligible: string[]; supplied: string[]; omitted: string[]; tool_retrieved: string[] };
  knowledge: { known_world: string[]; imagination: string[] };
  tools: { registered: string[]; bound: string[] };
  affect_snapshot: { values: Record<string, number>; baselines: Record<string, number>; directions: Record<string, string> };
  expansion_handles: PromptProjection["expansion_handles"];
  budgets: { prompt_tokens: number; max_nodes: number; max_depth: number };
  versions: Record<string, number>;
};
export type ExpressionReceipt = {
  profile: { voice?: string; role_voices?: string[]; affect?: Record<string, number>; affect_trajectory?: { before?: Record<string, number>; after?: Record<string, number>; delta?: Record<string, number>; committed?: boolean } };
  grounded_visible: string;
  expressed_content: string;
  fidelity: { passed?: boolean; checks?: Record<string, boolean>; grounded_numbers?: string[]; grounded_identifiers?: string[]; required_boundaries?: string[] };
  fallback: boolean;
  created_at: number;
};
export type TurnContext = {
  turn_id: string; state_sequence: number; model_id: string; instructions_text: string;
  conversation: { role: string; content: string }[];
  retrieved_memory: ScopedMemory[];
  affect: AffectState;
  active_context: ActiveContext;
  system_projection: SystemProjection;
  context_manifest: ContextManifest;
  expression_receipt?: ExpressionReceipt;
  prompt_projection?: PromptProjection | null;
};
export type ToolReceipt = { id: string; tool_id: string; source: string; effect_class: string; raw_args: Record<string, unknown>; normalized_args?: Record<string, unknown>; context: ActiveContext; capability_version: number; decision: string; checks: string[][]; execution_status: string; result?: unknown; error?: string; created_at: number };
export type ImaginationRun = {
  id: string; conversation_id: string; seed: string; max_steps: number; completed_steps: number;
  status: "running" | "paused" | "cancelled" | "complete" | "failed";
  active_turn_id?: string | null; created_at: number; updated_at: number;
  conversation?: ConversationDetail;
  turn_kinds?: Record<string, { kind: "chat" | "autonomous"; step: number | null }>;
};
export type IdeaLens = { id: string; label: string; domains: string[]; lanes?: string[]; legacy_ids?: string[] };
export type ImaginationPack = {
  id: string; slug: string; name: string; version: number; status: string;
  source_count: number; resource_count: number; lens_count: number; lenses: IdeaLens[];
  primitive_count?: number; edge_count?: number;
};
export type IdeaNode = {
  id: string; kind: string; lane?: string | null; lanes?: string[]; domains: string[]; label: string;
  classification?: { subject: string; role: string; clusters: string[]; granularity: string; selectable: boolean; treatment: string };
  content: Record<string, unknown>; inclusion_reason: string; estimated_tokens: number;
};
export type IdeaProjection = {
  pack: string; pack_version: number; lens: IdeaLens | null; query: string; selected: string[];
  nodes: IdeaNode[]; edges: { id: string; source: string; relation: string; target: string }[];
  estimated_tokens: number; match_count: number; excluded_count: number; rendered_context: string;
};
export type IdeaRelationship = { id: string; relation: string; source: string; target: string; source_label: string; target_label: string; evidence?: string };
export type DraftIngredient = {
  primitive: string; origin: "user_selected" | "halcyon_suggested" | "derived" | "world_pressure";
  locked?: boolean; accepted_by_user?: boolean;
};
export type ImaginationCandidate = {
  id: string; content_hash: string;
  entities: { id: string; type: string; label: string; properties?: Record<string, unknown> }[];
  edges: { id?: string; source: string; relation: string; target: string; properties?: Record<string, unknown> }[];
  lore: Record<string, string>; genealogy: Record<string, unknown>;
};
export type ImaginationDraft = {
  id: string; title: string; artifact_type: string; status: "draft" | "candidate" | "admitted" | "rejected";
  pack_id: string; pack_version: number; lens_id: string | null; initiating_pressure_id: string | null;
  revision: number; ingredients: DraftIngredient[]; tensions: { between: string[]; resolution?: string; reason?: string }[];
  rejected_suggestions: DraftIngredient[]; open_questions: string[];
  draft_entities: ImaginationCandidate["entities"]; draft_edges: ImaginationCandidate["edges"];
  candidate?: ImaginationCandidate; admission?: Record<string, unknown>;
  created_at: number; updated_at: number;
};
export type CharacterSnapshot = {
  title: string; blueprint_id: string; revision: number; pack_id: string; pack_version: number;
  traits: { id: string; label: string; group: string; locked: boolean }[];
};
export type LooseThread = {
  id: string; subject_entity_id: string; kind: string; status: "open" | "exploring" | "resolved" | "retained";
  reason: string; hint: unknown; possible_resolutions: string[]; source_admission_id: string;
  source_primitive_id?: string | null; exploration_blueprint_id?: string | null; created_at: number; updated_at: number;
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
  appendCharacterSnapshot: (conversationId: string | null, snapshot: CharacterSnapshot) =>
    request<Message & { conversation_id: string }>(`/api/conversations/${conversationId ?? "new"}/character-snapshots`, {
      method: "POST", body: JSON.stringify(snapshot),
    }),
  cancelTurn: (turnId: string) =>
    request(`/api/turns/${turnId}/cancel`, { method: "POST" }),
  tokens: (conversationId: string | null, draft: string) =>
    request<TokenUsage>("/api/tokens/count", {
      method: "POST",
      body: JSON.stringify({ conversation_id: conversationId, draft }),
    }),
  context: (turnId: string) => request<TurnContext>(`/api/turns/${turnId}/context`),
  governance: (kind: string) => request<Record<string, unknown>[]>(`/api/governance/${kind}`),
  boundary: () => request<Record<string, unknown>>("/api/boundary/attestation"),
  world: () => request<WorldMemory>("/api/world"),
  imaginationWorld: () => request<WorldMemory>("/api/imagination/world"),
  selfMemory: () => request<SelfMemory>("/api/memory/self"),
  memoryNode: (name: string) => request<MemoryNode>(`/api/memory/nodes/${encodeURIComponent(name)}`),
  imaginationNode: (name: string) => request<MemoryNode>(`/api/imagination/nodes/${encodeURIComponent(name)}`),
  memoryEntries: (channel = "all") => request<{ context: ActiveContext; entries: ScopedMemory[] }>(`/api/memory/entries?channel=${channel}`),
  affect: () => request<AffectState>("/api/affect"),
  timeline: () => request<TimelineEvent[]>("/api/memory/timeline"),
  activeContext: () => request<ActiveContext>("/api/context/active"),
  setActiveContext: (context: Omit<ActiveContext, "global">) => request<ActiveContext>("/api/context/active", { method: "PUT", body: JSON.stringify(context) }),
  availableRoles: () => request<RoleSummary[]>("/api/system/roles"),
  roleDetail: (id: string) => request<RolePackDetail>(`/api/system/roles/${encodeURIComponent(id)}`),
  systemProjection: () => request<SystemProjection>("/api/system/projection"),
  promptProjections: (conversationId?: string | null, limit = 50) => request<PromptProjection[]>(`/api/projections?limit=${limit}${conversationId ? `&conversation_id=${encodeURIComponent(conversationId)}` : ""}`),
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
  imaginationPacks: () => request<ImaginationPack[]>("/api/imagination/packs"),
  imaginationDoctrine: (pack = "villain", lens?: string | null, q = "", selected: string[] = [], limit = 120, tokenBudget = 4000) => {
    const params = new URLSearchParams({ pack, q, selected: selected.join(","), limit: String(limit), token_budget: String(tokenBudget) });
    if (lens) params.set("lens", lens);
    return request<IdeaProjection>(`/api/imagination/doctrine?${params}`);
  },
  imaginationDoctrineNode: (id: string, pack = "villain") => request<IdeaNode & { relationships: IdeaRelationship[] }>(`/api/imagination/doctrine/nodes/${encodeURIComponent(id)}?pack=${encodeURIComponent(pack)}`),
  imaginationBlueprints: () => request<ImaginationDraft[]>("/api/imagination/blueprints"),
  createImaginationBlueprint: (body: { title: string; artifact_type: string; pack?: string; lens_id?: string | null; initiating_pressure_id?: string | null; ingredients?: DraftIngredient[]; open_questions?: string[] }) => request<ImaginationDraft>("/api/imagination/blueprints", { method: "POST", body: JSON.stringify(body) }),
  updateImaginationBlueprint: (id: string, expected_revision: number, patch: Partial<ImaginationDraft>, reason = "updated draft") => request<ImaginationDraft>(`/api/imagination/blueprints/${id}`, { method: "PATCH", body: JSON.stringify({ expected_revision, patch, actor: "user", reason }) }),
  composeImaginationBlueprint: (id: string, expected_revision: number) => request<ImaginationDraft>(`/api/imagination/blueprints/${id}/compose`, { method: "POST", body: JSON.stringify({ expected_revision }) }),
  admitImaginationBlueprint: (id: string, expected_revision: number, candidate_hash: string) => request<Record<string, unknown>>(`/api/imagination/blueprints/${id}/admit`, { method: "POST", body: JSON.stringify({ expected_revision, candidate_hash }) }),
  imaginationPressures: () => request<LooseThread[]>("/api/imagination/pressures"),
  exploreImaginationPressure: (id: string, title: string, artifact_type: string, lens_id?: string | null) => request<ImaginationDraft>(`/api/imagination/pressures/${id}/explore`, { method: "POST", body: JSON.stringify({ title, artifact_type, lens_id }) }),
};
