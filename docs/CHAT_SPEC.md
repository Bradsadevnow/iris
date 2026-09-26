# Iris Chat — Feature Specification

Status: Draft v0.1  
Parent specification: [Iris Server UI](./UI_SPEC.md)  
Delivery target: First usable vertical slice  

## 1. Feature definition

Chat is the primary Iris experience. It provides a familiar conversation surface while preserving the distinction between:

- What the user said.
- What Iris said.
- What Iris proposed changing.
- What the gate admitted or denied.
- What was durably committed to memory.

The user talks naturally. Protocol syntax and governance mechanics remain behind the interface unless the user deliberately inspects them.

## 2. First-release scope

The first release includes:

- Create and list conversations.
- Open an existing conversation.
- Send a user message.
- Stream an Iris response.
- Stream and expand a model-provided reasoning artifact when available.
- Stop an active generation.
- Adjudicate the finalized model response through the existing gate.
- Atomically persist the resulting turn and any admitted memory mutation.
- Show one quiet outcome annotation beneath the Iris response.
- Inspect the receipt associated with a turn.
- Recover cleanly after server or browser interruption.

The first release does not include:

- Editing or deleting messages.
- Regenerating a response.
- Conversation branching.
- File attachments.
- Web search or other model tools.
- Multi-user access.
- Cross-device synchronization.
- Full historical-state replay UI.

The storage model must leave room for retries, branches, and replay without implementing those interfaces now.

## 3. User experience

### 3.1 Conversation list

The expanded sidebar shows:

- New chat.
- Conversations ordered by most recent activity.
- Human-readable title.
- Relative recency.

Conversation titles are initially derived deterministically from the first user message. Model-generated titles are deferred.

Creating a new chat immediately opens an empty conversation. An empty conversation may remain client-only until its first message is sent, avoiding durable blank records.

### 3.2 Empty conversation

The main region shows Iris's name, one short invitation, and the composer. There are no feature cards, prompt suggestions, governance explanations, or onboarding carousel.

### 3.3 Transcript

The transcript uses a centered reading column. Messages appear in chronological order.

User messages:

- Are visually distinct without oversized chat bubbles.
- Preserve whitespace and line breaks.
- Expose their timestamp on hover or keyboard focus.

Iris messages:

- Render readable Markdown with sanitized output.
- Stream in place.
- Show an expandable Thinking disclosure when a distinct model-provided reasoning artifact exists.
- Preserve the exact raw model output separately for evidence.
- Hide a valid standalone `NOMINATE` protocol line from the normal transcript.
- Do not hide malformed protocol-like prose because the UI must not reinterpret the kernel grammar.

The server, not the browser, supplies both `display_content` and `raw_content`. The frontend does not independently parse nominations.

### 3.4 Thinking disclosure

Thinking is a compact disclosure associated with an Iris message. It is collapsed by default after the final answer completes and may be expanded by click or keyboard.

During generation it may show:

- A quiet “Thinking…” state before content exists.
- Streamed reasoning summary or analysis when the endpoint returns it through a distinct field or channel.
- Elapsed time after completion.

The disclosure must follow these truth rules:

- It contains only reasoning content explicitly returned by the configured model endpoint.
- It identifies whether the content is a display-oriented reasoning summary or endpoint-exposed model analysis.
- It never claims to reveal hidden reasoning that the endpoint did not provide.
- It never generates a post-hoc explanation and presents it as the original thought process.
- If no reasoning artifact exists, the completed message has no Thinking disclosure.

An expanded Thinking disclosure offers **Context used**, which opens a read-only inspector with three tabs:

1. **Instructions** — exact system/developer-style instructions supplied to the model for that turn, including the rendered boundary vocabulary.
2. **Knowledge** — the exact self and world projection supplied to the model, labeled with its canonical state sequence.
3. **Conversation** — the exact preceding messages included in the request.

This inspector demonstrates prompt versus persistent knowledge. It does not display secrets, authorization headers, endpoint credentials, or server-only configuration. It reflects captured turn context even if current memory or prompts have since changed.

### 3.5 Composer

The composer supports:

- Multiline plain text.
- Enter to send.
- Shift+Enter for a newline.
- A send button with an accessible label.
- A stop button during active generation.
- Draft preservation while navigating within the application.
- A compact token counter showing projected context usage.

The send action is unavailable when:

- The input is empty after trimming.
- A turn is already active in that conversation.
- The server is disconnected.
- Iris is in historical replay mode.

The first release allows one active generation per conversation and one canonical memory commit at a time per Iris instance.

#### Token counter

The composer shows a quiet counter in the form `12.4k / 32k` representing projected input-context tokens against the configured model context limit. The projection includes:

- Instructions.
- Canonical knowledge supplied to the model.
- Included conversation messages.
- The current unsent draft.

Hovering, focusing, or selecting the counter opens a compact breakdown by those four categories. The counter is not a progress dashboard and uses warning color only when action is required:

- Normal below 80%.
- Warning at or above 80%.
- Critical at or above 95%.
- Sending is disabled if the projected request exceeds the server-enforced context limit.

The server is authoritative for tokenization. While the user types, the client may debounce requests and temporarily show an explicitly approximate value prefixed with `~`. It must not claim character counts are exact token counts.

During generation, the compact display switches to output usage, such as `842 tokens`, and updates from provider usage events when available. After completion, turn details show:

- Input tokens.
- Reasoning tokens, when reported separately.
- Output tokens.
- Total tokens.
- Context limit.
- Count source: `provider`, `server tokenizer`, or `estimate`.

Cost is omitted unless a later pricing feature has authoritative model pricing. The UI never invents a dollar estimate for a local or unknown model.

### 3.6 Streaming states

An active turn progresses through these user-visible states:

1. **Sending** — the user message is being durably recorded.
2. **Thinking** — the model request has started but no content has arrived.
3. **Responding** — content is streaming.
4. **Saving** — the complete response is being adjudicated and committed.
5. **Complete** — the final turn and outcome are durable.

Only the current state is shown, using quiet text or a small activity indicator. The interface does not show the gate's internal stages unless receipt details are open.

### 3.7 Turn outcomes

After completion, the Iris message may show one compact annotation:

- **Remembered** — a mutation changed canonical memory and was committed.
- **Not remembered** — a nomination was denied.
- **Could not save** — adjudication or durable commit failed.

No annotation is shown for ordinary no-nomination turns. An admitted no-op is available in message details but does not clutter the transcript.

Selecting an annotation opens a receipt drawer. The drawer shows the exact original output, claim, checks, result, and durable outcome.

### 3.8 Stop behavior

Selecting Stop requests cancellation of model generation.

- Already received text remains visible as an interrupted draft.
- Interrupted assistant text is stored for diagnostic continuity but is not adjudicated.
- No nomination from a partial response is evaluated.
- The turn is finalized as `cancelled`.
- The user may immediately send another message after cancellation is durably recorded.

If the upstream model cannot be cancelled, the server discards later chunks and never adjudicates the abandoned response.

## 4. Behavioral rules

### 4.1 Exactly one active turn

The server rejects a second turn request for a conversation that already has a turn in `generating` or `finalizing` state. The response uses HTTP `409 Conflict` and returns the active turn ID.

### 4.2 User message durability

The server must durably record the user message before contacting the language model. If that write fails, no model request is made and the composer retains the draft.

### 4.3 Adjudication timing

The gate adjudicates only a finalized, non-cancelled assistant response. Streaming chunks have no authority and cannot change memory.

### 4.4 Context construction

The server builds model context from:

- The compiled system prompt.
- Current canonical self and world projections.
- A bounded sequence of completed conversation messages.

Cancelled assistant drafts, failed generations without assistant output, receipt details, and UI annotations are excluded from model context.

The first release may retain the current 20-message context window. The chosen messages and canonical state sequence are recorded on the turn so later inspection can establish what context version was used.

The exact inspectable request context is captured before the model call. Prompt text, knowledge text, and conversation messages are stored as separate fields or structured records so the UI does not reconstruct them later from changed state.

### 4.5 Display content

After generation completes, the server applies the kernel's literal nomination grammar to identify the one valid standalone nomination line. It derives display content by removing only that exact matched line. Raw content remains immutable.

The display transformation never affects adjudication or the receipt rationale.

## 5. Atomic persistence

Atomicity is a release requirement, not deferred replay work.

### 5.1 Authority

SQLite in WAL mode is the authoritative durable store from the first chat release. JSON and JSONL files become export or compatibility projections and are not used to determine whether a turn or memory mutation committed.

### 5.2 Transaction boundaries

The server uses short database transactions. It must never hold a transaction open while waiting for the language model or streaming content.

#### Transaction A — begin turn

Atomically:

- Create the conversation if this is its first message.
- Insert the user message.
- Insert the turn with status `generating`.
- Advance the conversation's activity timestamp.

Only after Transaction A commits may the server call the model.

#### Streaming — no canonical mutation

Assistant chunks are sent to the client as transient SSE events. They may be buffered for crash diagnostics, but partial chunks are not canonical conversation messages and never enter model context or the gate.

Reasoning chunks are also transient during streaming. A finalized reasoning artifact is stored with the assistant message only when the model endpoint returned it through a distinct reasoning field or channel. Reasoning content has no authority, is never adjudicated, and is never written into canonical memory as a side effect of display.

#### Transaction B — complete non-mutating turn

For a finalized response with no committed memory change, atomically:

- Insert the finalized assistant message, including raw and display content.
- Insert the receipt or explicit no-nomination outcome.
- Set the turn's terminal status and outcome.
- Advance the conversation's activity timestamp.

#### Transaction C — complete mutating turn

For an admitted state-changing response, atomically:

- Verify the canonical state version read for trial execution is still current.
- Write the canonical world or self mutation.
- Insert the finalized assistant message.
- Insert the receipt and normalized mutation record.
- Set the turn to `complete` with outcome `committed`.
- Increment the canonical state sequence.
- Advance the conversation's activity timestamp.

If any statement fails, the entire transaction rolls back. The UI must never receive a committed outcome unless Transaction C commits.

#### Transaction D — fail or cancel turn

Atomically:

- Store available diagnostic metadata and optional interrupted assistant text.
- Set the turn to `failed` or `cancelled`.
- Record a safe user-facing error code.
- Advance the conversation's activity timestamp.

### 5.3 Optimistic state check

Trial execution occurs outside the write transaction against a state snapshot with `state_sequence = N`. Transaction C performs a compare-and-swap check requiring the authoritative sequence still to equal `N`.

If it changed, the server reloads current state and repeats adjudication/trial execution before attempting the commit again. The first release serializes canonical commits, so retries should be exceptional, but the check prevents stale-state writes.

### 5.4 Projection files

After a successful state-changing transaction, the server may refresh `world.json`, `self.json`, and JSONL exports using atomic file replacement. Projection failure does not roll back the already committed database transaction.

Projection files contain the database state sequence. On startup, stale or missing projections are regenerated from SQLite.

### 5.5 Crash recovery

On startup, the server finds turns left in non-terminal states:

- `generating` becomes `interrupted` because the original model stream cannot be trusted to resume.
- `finalizing` is inspected. If no completion transaction committed, it becomes `interrupted`.
- No interrupted response is adjudicated automatically.
- Canonical memory requires no repair because mutation and completion shared one transaction.

The UI offers to resend the user's message as a new turn. It does not silently retry.

## 6. Minimal data model

The names below describe semantics; migrations may refine column details.

### `conversations`

- `id`
- `title`
- `created_at`
- `updated_at`
- `archived_at`, nullable

### `turns`

- `id`
- `conversation_id`
- `ordinal`
- `status`: `generating | finalizing | complete | failed | cancelled | interrupted`
- `outcome`: `none | noop | denied | committed | execution_failed | persistence_failed`, nullable until terminal
- `context_state_sequence`
- `created_at`
- `completed_at`, nullable
- `error_code`, nullable
- Captured request-context reference.
- `input_tokens`, nullable
- `reasoning_tokens`, nullable
- `output_tokens`, nullable
- `total_tokens`, nullable
- `token_count_source`: `provider | server_tokenizer | estimate`, nullable
- `context_limit`, nullable

`(conversation_id, ordinal)` is unique.

### `messages`

- `id`
- `turn_id`
- `conversation_id`
- `role`: `user | assistant`
- `raw_content`
- `display_content`
- `reasoning_content`, nullable
- `reasoning_kind`: `summary | analysis`, nullable
- `status`: `final | interrupted`
- `created_at`

There is exactly one final user message per turn and at most one final assistant message per turn.

### `turn_contexts`

- `turn_id`, primary key
- `instructions_text`
- `knowledge_text`
- `conversation_json`
- `state_sequence`
- `model_id`
- `created_at`

Turn context is immutable after Transaction A and contains only material actually sent to the model. Sensitive transport configuration is excluded.

### `proposals`

- `id`
- `turn_id`, unique when a single valid nomination exists
- `raw_line`
- `what_path`, nullable when malformed
- `verb`, nullable when malformed
- `raw_args`, nullable
- `normalized_args_json`, nullable
- `parse_status`: `valid | malformed | multiple`
- `created_at`

Proposals record model intent; they never imply admission or mutation.

### `gate_decisions`

- `id`
- `turn_id`, unique
- `proposal_id`, nullable for no-nomination turns
- `admission`: `none | denied | admitted`
- `execution`: `not_run | noop | applied | failed`
- `persistence`: `not_required | committed | failed`
- `terminal_stage`
- `checks_json`
- `created_at`

The transcript annotation and Governance views derive outcome from these explicit dimensions rather than overloading one decision value.

### `receipts`

- `id`
- `turn_id`, unique
- `decision`
- `outcome`
- `claim_json`, nullable
- `rationale`
- `decision_basis_json`
- `result_json`, nullable
- `boundary_hash`
- `created_at`

### `canonical_state`

- Singleton row identifier.
- `sequence`
- `world_json`
- `self_json`
- `updated_at`

Keeping both graphs in one versioned row is acceptable at the current 5,000-element limit and makes the initial transactional guarantee straightforward. Normalized graph tables may be introduced later without changing the API.

### `mutations`

- `id`
- `turn_id`, unique
- `state_sequence_before`
- `state_sequence_after`
- `verb`
- `what_path`
- `args_json`
- `result_json`
- `patch_json`
- `created_at`

The patch enables future replay. The first release must record it but does not need to expose full replay controls.

## 7. Server API

### `GET /api/conversations`

Returns conversation summaries ordered by `updated_at DESC`.

### `POST /api/conversations`

Optional in the first release because a conversation can be created with its first turn. If used, it creates an explicit durable empty conversation.

### `GET /api/conversations/{conversation_id}`

Returns conversation metadata, completed messages, terminal turn outcomes, and any active turn.

Interrupted assistant drafts are omitted from the standard transcript and available through turn details.

### `POST /api/tokens/count`

Returns the projected request token usage for the active conversation and supplied draft:

```json
{
  "instructions": 940,
  "knowledge": 2810,
  "conversation": 3200,
  "draft": 84,
  "total": 7034,
  "context_limit": 32768,
  "source": "server_tokenizer",
  "exact": true
}
```

The endpoint is read-only, debounced by the client, and may cache counts for unchanged instructions, knowledge sequence, and conversation prefix.

### `POST /api/conversations/{conversation_id}/turns`

Request:

```json
{
  "content": "Tell me what you remember about Riverhold.",
  "client_request_id": "client-generated-uuid"
}
```

`client_request_id` is unique per conversation and makes submission idempotent. Repeating the request returns the already-created turn rather than duplicating the user message.

Response begins an SSE stream, or returns a turn resource followed through a dedicated stream endpoint. The implementation must expose these semantic events:

- `turn.created`
- `assistant.started`
- `assistant.reasoning.delta`
- `assistant.delta`
- `assistant.usage`
- `assistant.finalizing`
- `assistant.completed`
- `turn.failed`
- `turn.cancelled`

`assistant.completed` contains finalized display content, available finalized reasoning metadata, proposal summary, gate-decision summary, receipt summary, outcome, and committed state sequence. It is sent only after the completion transaction commits.

### `POST /api/turns/{turn_id}/cancel`

Requests generation cancellation. It is idempotent. Cancelling a terminal turn returns its existing terminal state.

### `GET /api/turns/{turn_id}`

Returns exact turn status, messages, outcome, receipt summary, and safe error information.

### `GET /api/receipts/{receipt_id}`

Returns full receipt detail, including raw rationale and ordered checks.

## 8. SSE behavior

- Chat streaming uses Server-Sent Events with `Content-Type: text/event-stream` and UTF-8 payloads.
- The response begins immediately after Transaction A commits; the server does not wait for the first model token.
- Every event contains `turn_id` and an increasing in-stream event number.
- Heartbeats keep intermediaries from closing quiet model requests.
- Client disconnect does not cancel generation automatically.
- Reconnection fetches `GET /api/turns/{turn_id}` first.
- If generation is still active, the client reconnects to the stream when supported; otherwise it polls the turn resource.
- The finalized response always comes from durable turn state, never solely from an ephemeral terminal stream chunk.
- Markdown is rendered incrementally but sanitized after every update.
- Reasoning deltas render only inside the Thinking disclosure and never enter the answer body.

### 8.1 Stream endpoint

Turn creation returns `202 Accepted` with the durable turn resource and a stream URL:

```json
{
  "turn_id": "turn_...",
  "status": "generating",
  "stream_url": "/api/turns/turn_.../stream"
}
```

`GET /api/turns/{turn_id}/stream` opens the SSE connection. Separating creation from streaming makes the idempotent POST safe to retry and gives browser reconnection a stable GET endpoint.

The stream endpoint accepts the standard `Last-Event-ID` header. The server retains a bounded per-turn buffer until the turn reaches a terminal state, allowing recent missed events to be replayed. If the requested cursor is no longer buffered, the server sends `stream.resync_required`; the client reloads the durable turn resource and replaces its transient rendering state.

### 8.2 Event envelope

Every SSE message has an `id`, an `event` name, and a JSON `data` object:

```text
id: 7
event: assistant.delta
data: {"turn_id":"turn_...","sequence":7,"delta":"Riverhold"}
```

All event data includes:

- `turn_id`
- `sequence`, monotonically increasing within the stream
- `timestamp`

Terminal events additionally include the authoritative turn status.

### 8.3 Event semantics

#### `turn.created`

Confirms that Transaction A committed. Contains the durable user message and turn resource.

#### `assistant.started`

Confirms that the upstream model request began. It contains model identity metadata safe for display, but no credentials or endpoint secrets.

#### `assistant.reasoning.delta`

Contains an append-only reasoning delta from a distinct model reasoning channel. It includes `reasoning_kind: summary | analysis`. The client appends it only to the Thinking disclosure.

#### `assistant.delta`

Contains an append-only answer-text delta. The client appends it to the visible Iris response.

#### `assistant.usage`

Contains the latest cumulative token usage reported by the provider or server tokenizer. Fields may include input, reasoning, output, total, context limit, and count source. Missing fields remain unknown rather than being displayed as zero.

Providers that report usage only at completion do not emit speculative usage events unless the server can count with the configured model's tokenizer. The terminal usage stored on the turn supersedes all transient counters.

#### `assistant.finalizing`

Signals that the upstream response ended and atomic adjudication/finalization has begun. The client keeps the streamed answer visible and shows the quiet Saving state.

#### `assistant.completed`

Emitted only after Transaction B or C commits. It contains:

- Final durable message ID.
- Final `display_content`.
- Final reasoning metadata and content when available.
- Final token usage and count source.
- Turn outcome.
- Proposal summary.
- Gate-decision summary.
- Receipt summary.
- Authoritative canonical state sequence.

The client replaces its accumulated transient buffers with this durable payload, preventing token loss, duplication, or disagreement with server-side nomination removal.

#### `turn.failed`

Emitted only after Transaction D commits. It contains a safe error code, retryability, and the terminal turn resource. Transient assistant content may remain visible as interrupted output but is not presented as a completed Iris message.

#### `turn.cancelled`

Emitted only after cancellation is durable. It contains the terminal turn resource. No partial nomination is adjudicated.

#### `stream.resync_required`

Instructs the client to fetch `GET /api/turns/{turn_id}` because its cursor predates the retained stream buffer.

#### `stream.heartbeat`

Carries no conversational content. It exists only to maintain the connection and is ignored by the transcript.

### 8.4 Buffering and rendering

- The server forwards deltas in arrival order.
- Very small upstream fragments may be coalesced for up to 25 ms to avoid excessive browser rendering without making the response feel delayed.
- Reasoning and answer buffers are independent and preserve ordering within their own channels.
- The browser schedules visual updates at most once per animation frame.
- Autoscroll follows the stream only while the user is already near the transcript bottom. Scrolling upward disables follow mode until the user returns to the bottom.
- The caret/activity indicator appears only on the active output region and disappears on every terminal event.
- Incremental Markdown rendering must tolerate incomplete constructs such as code fences, links, and tables.

### 8.5 Stream authority

Streaming is presentational until finalization commits:

- Deltas are not canonical messages.
- Deltas do not enter conversation context.
- Deltas cannot reach the gate.
- Deltas cannot modify world or self state.
- Only `assistant.completed` represents a durable assistant message.
- A browser displaying all answer tokens may still show Saving until the atomic completion transaction succeeds.

This rule allows immediate interaction without weakening the transactional guarantee.

## 9. Error model

Stable server error codes include:

- `model_unavailable`
- `model_timeout`
- `generation_cancelled`
- `boundary_invalid`
- `adjudication_failed`
- `state_conflict`
- `persistence_failed`
- `conversation_busy`
- `server_interrupted`

User-facing language is concise and does not expose stack traces, raw database errors, environment variables, or model endpoint credentials.

Detailed local diagnostics include correlation ID, conversation ID, turn ID, and error code, but omit message bodies by default.

## 10. Visual specification

### Chat surface

- Graphite application canvas.
- Sidebar slightly distinct from the main canvas without a heavy border.
- Transcript messages use spacing and alignment rather than nested cards.
- Iris content uses warm off-white text.
- User content may use a subtle elevated surface.
- Composer is an elevated dark surface with a restrained focus ring.
- Maximum transcript width is 760 px.

### Outcome annotation

- One line beneath the Iris response.
- Small icon plus short label.
- Neutral by default.
- Denial or failure color appears only after the annotation is focused, expanded, or requires action.
- No receipt ID in the normal transcript.

### Thinking disclosure

- Appears immediately above the associated final answer.
- Uses a quiet disclosure row, not a bordered card.
- Collapsed by default after completion.
- Shows elapsed thinking time when known.
- Expanded content uses readable prose styling and clearly labels summary versus analysis.
- “Context used” opens an inspector with Instructions, Knowledge, and Conversation tabs.
- The inspector labels the captured state sequence and model ID.

### Token counter

- Appears quietly inside or immediately beneath the composer, aligned away from the primary Send action.
- Uses tabular numerals to prevent visual jitter.
- Shows context usage before sending and output usage during generation.
- Opens a small accessible usage breakdown on activation.
- Uses semantic warning color only near the configured limit.
- Remains readable without competing with the message draft.

### Receipt drawer

- Opens from the right without replacing chat.
- Begins with plain-language outcome.
- Shows gate checks as a vertical ordered list.
- Raw protocol and JSON are collapsed under “Technical details.”
- Closing returns focus to the originating annotation.

### Governance navigation

The Governance area contains:

- **Proposals** — what Iris asked the gate to change.
- **Gate Decisions** — how each proposal moved through the deterministic checks and durable commit.
- **Receipts** — the immutable evidence record.
- **Boundary** — what the active kernel instance enforces.

Each item links to its originating turn. Committed proposals also link to the resulting memory entity.

## 11. Accessibility

- New streamed content is announced politely without reading every token.
- Streamed Thinking content is not announced token by token; expansion is user-controlled.
- Completion and failure are announced once.
- Stop, Send, sidebar controls, message details, and receipt close controls have visible labels or accessible names.
- Keyboard focus never jumps merely because a stream chunk arrived.
- Outcome annotations are buttons, not clickable text spans.
- Markdown links are distinguishable without color alone.
- Code blocks are horizontally contained and keyboard reachable.

## 12. Acceptance criteria

### Happy path

- Sending a message durably creates exactly one user message before the model request begins.
- Iris text streams into one assistant message region.
- The final assistant message survives a browser refresh.
- A committed memory mutation and completed turn appear together or neither appears.
- The successful terminal SSE event is emitted only after the database commit.
- Raw and display content can be inspected and differ only by the exact hidden nomination line.
- When the endpoint supplies reasoning, the finalized artifact remains expandable after refresh and is labeled by kind.
- Context used shows the immutable instructions, knowledge, and conversation actually sent for the turn.
- Final token usage survives refresh and records whether counts were authoritative or estimated.

### Atomicity

- Injecting a failure at every statement in the mutation completion transaction never leaves partial canonical memory, a partial receipt, or a falsely completed turn.
- Killing the server during model generation leaves canonical memory unchanged.
- Killing the server during finalization results in either the complete committed turn or an interrupted turn with no mutation—never a half-commit.
- Two concurrent state-changing turns cannot commit from the same state sequence.
- Stale JSON projections are regenerated without altering authoritative database state.

### Idempotency and concurrency

- Repeating a turn request with the same `client_request_id` does not duplicate messages or model requests.
- A second active turn in the same conversation returns `409` and the first turn's ID.
- Cancellation is idempotent and partial text is never adjudicated.

### Failure states

- Model unavailability leaves a durable user message and a retryable failed turn.
- Database failure before Transaction A makes no model request.
- Database failure during completion never produces a “Remembered” annotation.
- Reopening an interrupted conversation clearly distinguishes the unfinished turn.

### Usability

- A first-time user can chat without seeing `NOMINATE`, receipt IDs, or invariant terminology.
- Receipt evidence remains reachable in one action from a denied or committed response.
- Thinking is expandable without displacing or obscuring the final answer.
- Prompt instructions and persistent knowledge are visibly separate in Context used.
- Proposals and Gate Decisions are independently browseable under Governance.
- The composer token counter includes instructions, knowledge, conversation, and draft usage.
- Over-limit requests are prevented with a clear explanation of which context categories consume the budget.
- The transcript remains readable between 720 px and large desktop widths.
- All chat functions are operable with a keyboard and screen reader.

## 13. Implementation order

1. Introduce SQLite schema, WAL mode, migrations, and transaction helpers.
2. Move canonical world/self authority into the versioned database row.
3. Adapt `Memory` and `Gate` integration so trial state is committed through one server-owned transaction.
4. Implement conversation, turn, message, receipt, and mutation repositories.
5. Add FastAPI turn creation, SSE streaming, cancellation, and recovery.
6. Build the dark application shell and transcript.
7. Add compact outcomes and receipt drawer.
8. Add fault-injection tests for every atomicity acceptance criterion.
9. Add graph, richer event history, snapshots, and replay incrementally under the parent UI specification.

## 14. Guardrail

No UI success state may be derived from model output or in-memory execution alone. “Complete” and “Remembered” mean the authoritative SQLite transaction committed.
