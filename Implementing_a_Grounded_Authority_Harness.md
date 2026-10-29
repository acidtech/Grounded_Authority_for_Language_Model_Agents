# Implementing a Grounded Authority Harness

Disclosure: Patent applications are pending. Non-commercial and research use is permitted under the license (see LICENSE.md); any commercial use requires a separately negotiated license (see COMMERCIAL-LICENSE.md).

License: Copyright (c) 2026 Nathan Scherdin. This document is licensed under CC BY-NC-ND 4.0 (https://creativecommons.org/licenses/by-nc-nd/4.0/), with an additional permission for non-commercial translations; see LICENSE.md. Any commercial use requires a separately negotiated license; see COMMERCIAL-LICENSE.md.

## Scope

This guide is for developers who want to add a grounded authority gate to an existing agent harness or command-line agent tool. It works in four stages, each usable on its own, and then adds the layers that sit above the gate.

- **No code ships with this guide.** Every listing is pseudocode. Nothing here is a reference implementation.
- **The paper is normative.** The source of every requirement is Grounded_Authority_for_Language_Model_Agents_C32.md, called "the paper" below. Where this guide and the paper differ, the paper governs.
- **Harness-generic.** The guide assumes only an OpenAI-compatible chat-completion interface with tool calls, a harness that receives those calls and dispatches them, and trusted state the worker cannot write. It does not target any particular harness product.

## Conventions

- **Section references** use the paper's own headings, for example "Section 3.3 The gate" or "Appendix B.2 Opening the gate".
- **Paper identifiers are unchanged.** Function, record and field names taken from Appendix A (Minimal CHR protocol) and Appendix B (Reference harness protocol) are used exactly as the paper writes them. As in Appendix A, every function runs under `serialized_frame_state(frame)`, and a failed `require` returns a denial and changes no state.
- **Guide-level helpers start with `g_`.** Any identifier beginning `g_` is a guide-level helper: the paper does not specify it, and an implementation may realize it differently. The table "Guide-level helpers" at the end lists every one. Any statement marked **Guide-level choice** is a design choice this guide makes where the paper leaves the matter open.
- **Tool names.** Four worker-callable tool names come from the paper's text rather than from Appendices A and B as functions: `status` (Section 3.3), `read_authority` (Appendix B.1 function name), `open_gate` (Appendices A and B.2) and `read_memory` (defined in the first sentence of Appendix B.2). Their bindings to protocol functions are guide-level and are listed in the helpers table.
- **Wire fields.** The OpenAI-compatible fields `messages`, `tools`, `tool_choice`, `tool_calls`, `choices`, `message`, `role`, `content`, `tool_call_id`, `function`, `name`, `arguments`, `parameters` and `id` belong to the chat-completion interface, not to the gate protocol.
- **Tests** are cited as the Appendix C subsection plus the exact text of the Fixture cell, for example C.1 "Valid witness at `open_gate`". Appendix C does not number its rows.
- **Status labels** follow Section 5.1 What ran: **Deployed** means the paper reports the component in use; **Specified addition** means the paper specifies it but does not report it in use.
- **Guarantees** follow Appendix E. What each mechanism establishes. Each stage repeats the rows that apply to it.

## Stage table

| Stage | C32 sections implemented | Appendix C tests to pass | Exit criterion |
| --- | --- | --- | --- |
| 1. Shared context-provenance validator and minimal warning profile | Section 3.0 The shared context-provenance validator; Section 2.3 Identifiers | 2 C.1 rows test the warning profile itself and pass at Stage 1. Three further C.1 rows exercise the shared retrieval check; they pass in their authority form at Stage 2. All five are listed in Stage 1. | A witness placed in a chunk validates while that chunk is present in current context. A citation of an absent, removed or unassociated chunk returns a warning to the same model and blocks nothing. |
| 2. Authority gate with `plan_auth` and the bound witness | Section 2.3 Identifiers; Section 2.4 Context epochs; Section 3.2 The four invariants; Section 3.3 The gate; Appendix A. Minimal CHR protocol; B.1 Epoch and authority changes; B.2 Opening the gate | 26 C.1 rows and 1 C.2 row, listed in Stage 2 | Every Stage 2 row passes with resurfacing disabled, and no consequential tool can reach dispatch except through `consequential_batch`. |
| 3. Resurfacing | Section 3.4 Resurfacing; B.2 Opening the gate (resurfacing lines) | 3 C.1 rows, listed in Stage 3 | Every successful opening returns the exact authority and selected evidence as prefilled tool-result content under the unchanged witness; Stage 2 rows still pass. |
| 4. Action-specific claims, claim-before-payload order and the generation receipt | Section 3.5 Claims; B.3 The action turn | 11 C.2 rows, listed in Stage 4 | Every consequential batch dispatches only through `act_tool_turn` with an authority claim, covering evidence claims and a receipt from the trusted generation adapter; Stage 2 and 3 rows still pass. |
| Above the gate (after Stage 4) | Sections 3.7, 3.8, 3.9, 3.10; B.4 End of turn; B.5 Structured authorities; Section 6. What the gate leaves to management | 16 rows (6 C.2 rows and all 3 C.3 rows assigned only here; 4 C.1 and 3 C.2 rows shared with a stage), listed in that section | Each layer adopted passes its rows; the gate's own rows still pass. |

Every Fixture row of Appendix C.1, C.2 and C.3 is assigned in the "Fixture assignment index" near the end. No row is out of guide scope.

## The tool-call loop

Everything below hangs off one loop. The harness owns the message list, sends it with a tools list to an OpenAI-compatible chat-completion endpoint, receives the model's `tool_calls`, dispatches them, and appends each result as a `tool` message. Consequential tools never run directly: they go through the gate. The message list is append-only, and any other change to it is a context modification that starts a new epoch (Section 2.4 Context epochs).

```text
# --- Guide-level loop around an OpenAI-compatible chat-completion endpoint ---

g_run_session(frame, first_user_message):
    start_new_epoch(frame)                    # B.1: a session start is a new epoch;
                                              # bootstrap_status delivers authority and witness
    g_append(frame, {role: "user", content: first_user_message})
    loop:
        turn = g_new_turn(frame)
        response = g_chat_completion(messages = frame.g_context,
                                     tools    = g_tool_definitions(frame))
        message = response.choices[0].message
        g_append(frame, message)              # assistant turn, including any tool_calls
        if message.tool_calls is empty:
            end_of_turn(frame, turn, g_gate_used(turn))     # B.4; see "Above the gate"
            if g_session_finished(frame): return
            g_append(frame, {role: "user", content: g_next_user_message()})
            continue
        results = g_harness_dispatch(frame, turn, message.tool_calls)
        for call in message.tool_calls:       # one tool message per call, in call order
            g_append(frame, {role: "tool", tool_call_id: call.id,
                             content: results[call.id]})
        end_of_turn(frame, turn, g_gate_used(turn))         # B.4

# --- Append-only context ---

g_append(frame, message):
    frame.g_context.append(message)           # never rewrites, removes or reorders a message
    on_context_change(frame, g_context_change(kind = "append_only_turn"))
                                              # B.1 returns at once: growth preserves the epoch

g_modify_context(frame, operation):           # the ONLY route that may rewrite, prune,
                                              # summarize, compact or remove cached context
    g_apply(frame.g_context, operation)
    on_context_change(frame, g_context_change(kind = operation.kind))
                                              # B.1: records the change, starts a new epoch,
                                              # clears witness and pending gate, bootstraps

g_on_host_context_event(frame, event):        # a host that edits history reports it here
    on_context_change(frame, g_context_change(kind = event.kind))

# --- Harness dispatch ---

g_harness_dispatch(frame, turn, tool_calls):
    calls = [g_parse_call(c) for c in tool_calls]       # name and arguments exactly as generated
    under serialized_frame_state(frame):                # Section 3.10: one call or batch at a time
        if g_stage < 4:
            return g_stage2_tool_turn(frame, turn, calls)          # Stage 2
        return act_tool_turn(frame, turn, calls,                   # Stage 4, B.3
                             g_claims_from_adapter(turn).authority_claim,
                             g_claims_from_adapter(turn).evidence_claims,
                             g_claims_from_adapter(turn).evidence_map,
                             g_receipt_from_adapter(turn))

# dispatch(free) in Appendices A and B runs each nonconsequential call like this:
g_execute_free_call(frame, call):
    match call.name:
        "status":         return bootstrap_status(frame)          # B.1
        "read_authority": return read_authority(frame)            # B.1
        "open_gate":      return open_gate(frame, call.arguments.witness,
                                           call.arguments.evidence_ids)   # B.2
        "read_memory":    return g_read_memory(frame, call.arguments.id)  # governed record read (B.2)
        otherwise:        return g_run_research_tool(call)        # nonconsequential tier, Section 3.7
```

**Guide-level choice: the tools list.** `g_tool_definitions(frame)` returns, in OpenAI-compatible form, the four governed tools and the deployment's research and action tools:

```text
tools = [
  {type: "function", function: {name: "status",
      description: "Deliver the active authority and its witness for this epoch.",
      parameters: {}}},
  {type: "function", function: {name: "read_authority",
      description: "Governed reread of the active authority.",
      parameters: {}}},
  {type: "function", function: {name: "open_gate",
      description: "Open the gate for the next consequential action or batch.",
      parameters: {witness: string,                 # the wit: value, or "authority_unavailable"
                   evidence_ids: list of string}}}, # admitted rec: IDs this action will rely on
  {type: "function", function: {name: "read_memory",
      description: "Governed read of a stored record; admits it to this epoch under its harness-assigned role.",
      parameters: {id: string}}},
  ... research tools (nonconsequential) ...,
  ... action tools (consequential under the effect policy) ...
]
```

Four properties of the loop carry the paper's requirements:

1. **The witness argument is model-generated.** `g_parse_call` passes `open_gate`'s `witness` exactly as the model generated it. The harness never fills it, defaults it or copies it in from the sidecar: "A harness-filled field or automatic echo is not model testimony" (Section 3.0).
2. **Consequential tools route through the gate.** `g_harness_dispatch` never executes a call by tool name. It hands the whole turn to the Stage 2 wrapper or to `act_tool_turn`, which classify each call by `derive_actual_effect` and dispatch consequential effects only behind a current gate (Section 3.2, Invariant 4).
3. **Append-only context.** `g_append` is the only routine that adds to `frame.g_context`, and it only appends. Ordinary new turns, tool messages and resurfaced authority are growth and leave the epoch valid.
4. **Epoch invalidation on modification.** Every rewrite, removal, pruning, summary, micro-compaction or host compaction of existing cached context goes through `g_modify_context` or `g_on_host_context_event` and so through `on_context_change`. "Any modification of existing cached context invalidates the authority admission, its witness and any pending gate" (Section 2.4). If the host can edit history without telling the harness, the deployment is the limited variant of Appendix F.3 and cannot claim strict admission validity.

**Guide-level choice: where bootstrap delivery lands.** `bootstrap_status` runs at the start of every epoch, before the model has asked for anything. Deliver its result as a harness-authored message appended with `g_append` (a `system` or `user` role message, whichever the host treats as harness input), and treat delivery as confirmed (`confirmed_delivery` in Appendix A) only once that message is in the list that the next `g_chat_completion` call will send. When the worker calls `status` or `read_authority` itself, the result is the `tool` message for that call.

## Stage 1: Shared context-provenance validator and minimal warning profile

**Purpose.** Build the one retrieval test that the authority gate later specializes. The harness places an unguessable witness inside a context chunk, records the association in protected state, and checks a model-generated citation against that chunk's presence in current context. On failure it warns the same model. In the paper's words, "Authority provenance is therefore a specialization of context provenance" (Section 3.0). Building this first gives Stage 2 a tested witness generator, placement routine and context tracker.

**C32 sections implemented.** Section 3.0 The shared context-provenance validator (its four steps and the "General provenance warning" profile); Section 2.3 Identifiers (witness form, and the rule that the witness is included within the delivered chunk).

**Status: Specified addition.** Section 5.1 What ran lists "Minimal provenance-warning feedback" as "Specified in Section 3.0; not yet in use; evaluation in Experiment 16".

### Data structures

```text
# Guide-level protected state, one set per frame, kept in the sidecar the worker cannot write
frame.g_provenance      {witness: chunk_id}   # association recorded at placement (Section 3.0 step 1)
frame.g_present_chunks  {chunk_id}            # chunks present in the current context
frame.epoch                                   # Appendix A field; Stage 1 already keys state by epoch

# Witness value: "wit:" followed by at least 64 random bits (Section 2.3; Appendix D).
# Durable record IDs are written "rec:..." and are never witnesses.
```

### Pseudocode

```text
g_place_witness(frame, chunk):                # Section 3.0 step 1
    nonce = fresh_unguessable_nonce()         # Appendix A: at least 64 random bits; never a record ID
    frame.g_provenance[nonce] = chunk.id
    g_append(frame, g_chunk_message(chunk.text, nonce))   # the witness travels INSIDE the chunk
    frame.g_present_chunks.add(chunk.id)
    return nonce                              # held in protected state; no other route to the worker

g_check_citation(frame, cited_witness):       # Section 3.0 steps 2 and 3
    # cited_witness is exactly what the model generated; the harness never fills it in.
    chunk_id = frame.g_provenance.get(cited_witness)
    if chunk_id is None:
        return g_warn(frame, cited_witness, "cited context is not validated: unknown witness")
    if chunk_id not in frame.g_present_chunks:
        return g_warn(frame, cited_witness, "cited context is not validated as present")
    return g_VALIDATED

g_warn(frame, cited_witness, text):           # Section 3.0 step 4: the minimal warning
    g_record_warning(frame, cited_witness, text)          # audit record
    return g_WARNING(text)                    # returned to the same model as tool-result content;
                                              # the call itself still runs: blocking is not required

g_clear_provenance(frame):
    frame.g_provenance = {}
    frame.g_present_chunks = {}

# Stage 1 context tracking. Until Stage 2 exists, on_context_change can take this reduced form.
# Stage 2 replaces it with the full B.1 on_context_change and start_new_epoch.
on_context_change(frame, change):             # B.1 name and shape
    if change.kind == "append_only_turn":
        return                                # growth keeps every present chunk present
    record_context_change(frame, change)      # B.1
    frame.epoch = fresh_epoch()               # Appendix A
    g_clear_provenance(frame)

# Stage 1 addition to g_harness_dispatch: check every citation the model generated.
g_check_turn_citations(frame, calls, results):
    for call in calls:
        for w in call.arguments.g_cites:      # optional list of witnesses on any tool call
            outcome = g_check_citation(frame, w)
            if outcome is a g_WARNING:
                results[call.id] = results[call.id] + outcome
```

**Guide-level choice: how the model cites.** The paper requires that "the model generates the witness when citing that chunk" but does not fix the syntax. This guide adds an optional `g_cites` argument (a list of witness strings) to every tool. An implementation may instead scan assistant text for `wit:` spans; either way the value must be generated by the model, never filled in by the harness.

**Guide-level choice: clearing on modification.** The paper requires that "The validator must track actual context changes" and that "A witness copied into an earlier model response does not keep a removed source chunk admitted." Clearing every association on any non-append change is the simplest way to meet that, and it matches the authority profile's rule in Section 2.4. A warning-only deployment could instead drop only the associations of chunks actually removed; that finer tracking is not specified by the paper.

### Appendix C tests

Two C.1 rows test the general warning profile itself. They pass at Stage 1:

| Test | Where Stage 1 decides it |
| --- | --- |
| C.1 "General-provenance citation matches a chunk present in current context" | `g_check_citation` finds the witness in `g_provenance` and its chunk in `g_present_chunks`, and returns `g_VALIDATED`; no warning is added |
| C.1 "General-provenance citation does not match any chunk present in current context" | `g_check_citation` returns a `g_WARNING`, which `g_check_turn_citations` appends to that call's tool result; the call itself still runs |

Three further C.1 rows, below, test the retrieval check Stage 1 builds. At Stage 1, run their warning-profile analogue on an ordinary chunk (**Guide-level choice**: the analogue expects a warning where the row expects a denial). The rows themselves must pass in their authority form at Stage 2.

| Test | Warning-profile analogue at Stage 1 |
| --- | --- |
| C.1 "Witness equals a durable record ID" | Citing a `rec:` ID returns the unknown-witness warning; `fresh_unguessable_nonce` never yields a record ID |
| C.1 "Witness copied into a note, same epoch" | Citing a witness copied into an earlier note validates while the chunk is present; success does not show which copy caused the generation (Section 3.0) |
| C.1 "Targeted removal or micro-compaction after authority read" | After removal or compaction, citing the witness warns, even though a copy of it survives in an earlier response |

### What it guarantees and does not guarantee (Appendix E)

- **Context-provenance witness check.** Establishes that the model-generated witness matches a target chunk actually present in current context; a failure identifies an invalid citation under that association. Does not establish semantic support, comprehension, causal use of that chunk, or detection of uncited confabulation.
- **Provenance-warning feedback.** Establishes that a failed context-citation check is reported back to the model. Does not establish correction, better subsequent reasoning or prevention of an action.

## Stage 2: Authority gate with `plan_auth` and the bound witness

**Purpose.** Bind every consequential action to the genuine reference. On a governed read of active `plan_auth`, the harness issues a witness bound to authority version, worker frame and context epoch and delivers it inside the authority's chunk. At each consequential boundary the worker must generate that witness at `open_gate`, and the harness dispatches consequential effects only behind a current, one-batch gate. This stage is CHR: "Appendix A implements the four invariants with nothing else" (Section 3.2). Deployed alone it is the "Gate only" variant of Appendix F.2.

**C32 sections implemented.** Section 2.3 Identifiers; Section 2.4 Context epochs; Section 3.2 The four invariants; Section 3.3 The gate; Appendix A. Minimal CHR protocol; B.1 Epoch and authority changes; B.2 Opening the gate (without its resurfacing lines, which Stage 3 adds).

**Status: Deployed, with specified additions.** Section 5.1 What ran reports "Witness gate, one gate per consequential batch, parallel-batch rule" and "Task-level sub-authorities with one read per task" as "In use". Within this stage, the `authority_unavailable` witness value and the failed-opening cap are **Specified additions** ("Specified (Section 3.3); not yet in use"). Section 5.1 lists the "`status()` bootstrap with a separately minted session witness" as "Specified (Sections 2.4 and 3.3; Appendix B.1); not yet in use", so it is a **Specified addition**. Section 5.1 lists "Strict invalidation on every modification of cached context" as "Specified (Section 2.4; Appendix A `on_cached_context_modified`); not yet in use"; Section 2.4 describes the historical fallback, an input-token-drop heuristic, as "a limited implementation option, not fulfillment of the strict invalidation rule". Build the strict rule.

### Data structures

```text
active plan_auth                       # Section 2.1; written and activated only by the trusted path
    id, version, exact_text            # the fields Appendix A reads as active_plan_auth.*

Frame sidecar, one per frame           # Section 3.10; Appendix A; B.1
    id
    epoch
    session_witness                    # "wit:..." or None
    witness_binding                    # (active_plan_auth.id, active_plan_auth.version, frame.id, frame.epoch) or None
    open_gate                          # Gate or None
    failed_openings                    # B.1
    admitted {record_id: role}         # B.1: epoch admissions, for example "evidence"
    active_area_basis {area_id: record_id}   # B.1: used by structured edits (Stage 4; Section 6.3)

Gate                                   # Appendix A; B.2 adds evidence
    opening_id, authority_id, version, frame_id, epoch, evidence, opened_at, expires

config
    gate_lifetime                      # Appendix A
    max_failed_openings                # B.2
    max_intervening_turns              # Appendix A: config.max_intervening_turns, read by within_opening_interval_policy
```

The sidecar, the approval path and the gate code sit outside every worker-controlled write route, including the shell sandboxes; "the running gate never executes from a tree the agent can edit" (Section 3.2).

### Pseudocode

Implement every function of Appendix A and B.1 exactly as the paper gives it: `activate_plan_auth`, `on_authority_change` (B.1 form), `clear_witness`, `read_active_authority`, `read_authority`, `on_context_change`, `start_new_epoch`, `consequential_batch` and `gate_is_current`. In a frame that runs B.1, Appendix A's `on_cached_context_modified` and `new_worker_epoch` are realized by `on_context_change` and `start_new_epoch` (**Guide-level choice**: use the B.1 pair, which also resets `failed_openings`, `admitted` and `active_area_basis`). The listing shows only what this guide wires together or adds.

```text
start_new_epoch(frame):                       # B.1, plus one guide-level line
    frame.epoch = fresh_epoch()
    clear_witness(frame)                      # session_witness, witness_binding, open_gate
    frame.failed_openings = 0
    frame.admitted = {}
    frame.active_area_basis = {}
    g_clear_provenance(frame)                 # guide-level: Stage 1 associations end with the epoch
    bootstrap_status(frame)

bootstrap_status(frame):                      # B.1: read_authority() plus task state and warnings
    result = read_authority(frame)            # B.1, which calls read_active_authority (Appendix A)
    if result is DELIVERY_UNCONFIRMED:
        return result                         # no witness set, no admission recorded
    return g_status_message(result, g_task_state(frame), g_pending_warnings(frame))

open_gate(frame, witness=None, evidence_ids=[]):     # B.2 without its resurfacing lines (Stage 3)
    require active_plan_auth_is_approved_current_and_live()
    if frame.failed_openings >= config.max_failed_openings:
        return DENIED("too many failed openings; call read_authority()")
    if witness == "authority_unavailable":
        return DENIED("no authority held; call read_authority()")   # not a fabrication
    binding = (active_plan_auth.id, active_plan_auth.version, frame.id, frame.epoch)
    valid = (witness is not None
             and witness == frame.session_witness
             and frame.witness_binding == binding)
    if not valid:
        frame.failed_openings += 1
        return DENIED("invalid authority reference; call read_authority()")
    ids = dedupe(evidence_ids)
    for e in ids:
        if frame.admitted.get(e) != "evidence":
            return DENIED("evidence not admitted in this epoch; call read_memory(ID)", e)
    frame.open_gate = Gate(opening_id=new_gate_id(),
                           authority_id=active_plan_auth.id,
                           version=active_plan_auth.version,
                           frame_id=frame.id, epoch=frame.epoch, evidence=set(ids),
                           opened_at=position(frame),
                           expires=now_plus(config.gate_lifetime))
    return OPEN                               # witness unchanged; replaces any pending gate

g_stage2_tool_turn(frame, turn, calls):       # guide-level; Stage 4 replaces it with act_tool_turn
    effects = [derive_actual_effect(c) for c in calls]     # by actual effect, not tool name
    gated   = [e for e in effects if effect_policy.requires_gate(e)]
    free    = [e for e in effects if e not in gated]
    if not gated:
        return dispatch(free)
    if any(is_open_gate_call(c) for c in calls):
        return DENIED(gated, "open the gate first, then act") + dispatch(free)
    return consequential_batch(frame, gated) + dispatch(free)   # Appendix A: consumes the gate

g_read_memory(frame, record_id):              # the governed read behind the read_memory tool
    record = g_store_get(record_id)
    if record is None:
        return DENIED("no such record", record_id)
    frame.admitted[record_id] = g_harness_assigned_role(record)   # B.2; Section 2.2: the harness assigns roles
    return g_record_message(record)           # never touches active_plan_auth, the witness or the gate
```

**Guide-level choice: `confirmed_delivery`.** Appendix A requires confirmed delivery before a witness is set. In the tool-call loop, `confirmed_delivery(frame, payload)` appends the payload itself, as the `tool` message for the current call or as the bootstrap message, and returns false if that append fails or the host truncates the payload. The loop then does not append that call's result a second time.

**The delivered chunk.** The authority's delivered chunk contains `active_plan_auth.exact_text` and the witness together, for example the approved text followed by a line `Authority witness: wit:2a9e4c71d0b3f685`. Keeping the witness only in the sidecar "would not test the model's ability to retrieve it from context" (Section 2.3). The worker supplies the witness, and only the witness, at `open_gate`; the check compares that one value against `frame.session_witness` and `frame.witness_binding`.

**Denials.** Each denial names the failed check and the recovery call, reports that the denied operation caused no protected effect and never reveals a valid witness (Section 3.3, "Failure handling").

### Appendix C tests

| Test | Where Stage 2 decides it |
| --- | --- |
| C.1 "New epoch; active `plan_auth` read" | `start_new_epoch` then `bootstrap_status`; `read_active_authority` mints and binds a fresh witness and clears `open_gate` |
| C.1 "Read again in the same epoch" | `read_active_authority` reuses `frame.session_witness` while the binding matches |
| C.1 "Epoch change, then `status()` (*regression*)" | `start_new_epoch` calls `clear_witness` before the bootstrap read |
| C.1 "Plan revision, then `read_authority()` (*regression*)" | `activate_plan_auth` and `on_authority_change` call `clear_witness` |
| C.1 "Witness equals a durable record ID" | The nonce is never a record ID, so the equality test fails |
| C.1 "Valid witness at `open_gate`" | `open_gate` sets one Gate; the witness is neither rotated nor consumed |
| C.1 "Same witness for the next batch in the same epoch" | The same session witness opens a new gate |
| C.1 "Witness copied into a note, same epoch" | Valid: the check is equality with the bound witness in this epoch |
| C.1 "Witness copied to another frame or epoch" | `frame.witness_binding != binding`, or no witness in the other frame |
| C.1 "Never-issued or wrong-authority witness" | Equality fails; the denial text reveals no value |
| C.1 "`authority_unavailable`" | The B.2 branch returns before `failed_openings` is incremented |
| C.1 "Failed openings reach the cap" | `max_failed_openings`; only `read_authority` resets the count |
| C.1 "`read_authority()` with unconfirmed delivery" | `read_active_authority` returns `DELIVERY_UNCONFIRMED` before setting state |
| C.1 "Correct authority text supplied in place of the required witness" | Only the witness value is compared; any other content in that argument is denied |
| C.1 "Witness supplied without confirmed admission for this frame and epoch" | `frame.session_witness` is None or bound elsewhere |
| C.1 "New opening while an unused gate is pending" | `open_gate` overwrites `frame.open_gate` |
| C.1 "No gate, an expired gate, or a second batch under one opening" | `consequential_batch` consumes the gate and checks `gate_is_current` |
| C.1 "`open_gate` and a consequential operation in one turn" | `g_stage2_tool_turn` denies the gated operations via `is_open_gate_call` (also Section 3.8, above the gate) |
| C.1 "Exact authority delivered, but worker cannot supply the required proof" | Delivery sets no gate; only a valid `open_gate` does; recovery is `read_authority` |
| C.1 "Targeted removal or micro-compaction after authority read" | `on_context_change` with a non-append kind starts a new epoch |
| C.1 "Context modification after gate opening" | `start_new_epoch` clears the pending gate, then bootstraps |
| C.1 "Authority revoked or expired after opening, without a version increment" | `gate_is_current` repeats `active_plan_auth_is_approved_current_and_live` at dispatch |
| C.1 "Valid gate; action violates the plan" | The gate passes; the correctness finding belongs to Section 6 (above the gate) |
| C.1 "Historical `plan_auth` read through memory search" | `g_read_memory` never touches active authority, witness or gate |
| C.1 "Self-hosted agent edits gate source" | Section 3.2: the gate never runs from a tree the agent can edit (see Section 3.10, above the gate) |
| C.1 "Harness directory accessed through the shell" | Section 3.2: the sidecar is outside every worker write route (see Section 3.7, above the gate) |
| C.2 "Evidence ID not admitted in this epoch" | The B.2 evidence loop denies the whole opening |

### What it guarantees and does not guarantee (Appendix E)

- **Witness gate.** Establishes that at this opening the worker reproduced the witness issued with active `plan_auth`, bound to the valid frame, epoch and version. Does not establish recall of every authority clause, comprehension, attention or correct execution.
- **Governed authority read.** Establishes that the exact active authority was made available in the admitted context. Does not establish that the worker can currently retrieve the required proof or use the authority correctly.
- **The gate under complete mediation.** Establishes that no reconstruction, invented, revoked or foreign-epoch authority reference is bound to a consequential action as the governing authority. Does not establish correct actions, discovery of every mistake, or containment of effects.
- **Failed-opening cap.** Interrupts blind-retry loops. Does not bound lifetime guessing (Appendix D).
- **`status()`.** Establishes delivery of the current authority with this epoch's witness. Does not establish that the worker read every clause carefully.

## Stage 3: Resurfacing

**Purpose.** Renew presentation of the exact approved authority at the moment it matters. A successful opening returns the exact authority and the selected evidence, under the unchanged witness, as the content of the `open_gate` tool message. The text is "prefilled input/tool-result content, not text the worker generates token by token" (Section 3.4), so the worker pays for it in input tokens only. Stage 3 also fixes the timing policy between opening and action.

**C32 sections implemented.** Section 3.4 Resurfacing (including "Timing policy" and "Policy and cost"); B.2 Opening the gate (the resurfacing lines omitted at Stage 2).

**Status: Deployed.** Section 5.1 What ran reports "Resurfacing at gate opening" as "In use", and describes the deployed two-step harness: "`open_gate` validates the witness and returns the approved authority as prefilled tool-result text".

### Data structures

```text
resurfacing payload                    # B.2
    (active_plan_auth.exact_text, frame.session_witness, exact_records(ids))

Gate.opened_at                         # Appendix A: position(frame) when the opening result was delivered
config.gate_lifetime                   # Appendix A
config.max_intervening_turns           # 0 = the next action turn only; N = up to N research turns
```

### Pseudocode

```text
open_gate(frame, witness=None, evidence_ids=[]):     # B.2 complete = Stage 2 form + the lines marked NEW
    require active_plan_auth_is_approved_current_and_live()
    if frame.failed_openings >= config.max_failed_openings:
        return DENIED("too many failed openings; call read_authority()")
    if witness == "authority_unavailable":
        return DENIED("no authority held; call read_authority()")
    binding = (active_plan_auth.id, active_plan_auth.version, frame.id, frame.epoch)
    valid = (witness is not None
             and witness == frame.session_witness
             and frame.witness_binding == binding)
    if not valid:
        frame.failed_openings += 1
        return DENIED("invalid authority reference; call read_authority()")
    ids = dedupe(evidence_ids)
    for e in ids:
        if frame.admitted.get(e) != "evidence":
            return DENIED("evidence not admitted in this epoch; call read_memory(ID)", e)
    # NEW. Resurfacing: exact authority under the SAME witness, plus the selected evidence.
    payload = (active_plan_auth.exact_text, frame.session_witness, exact_records(ids))
    if not confirmed_delivery(frame, payload):          # appended as this call's tool message
        return DENIED("resurfacing not delivered; no gate opened")
    frame.open_gate = Gate(opening_id=new_gate_id(),
                           authority_id=active_plan_auth.id,
                           version=active_plan_auth.version,
                           frame_id=frame.id, epoch=frame.epoch, evidence=set(ids),
                           opened_at=position(frame),
                           expires=now_plus(config.gate_lifetime))
    return OPEN                               # witness unchanged; replaces any pending gate

within_opening_interval_policy(frame, gate):  # named in Appendix A; this counting rule is guide-level
    n = g_completed_nonconsequential_turns_since(frame, gate.opened_at)
    return n <= config.max_intervening_turns
    # Appendix A notes: the opening turn and the action turn are not intervening turns.
    # Exceeding the limit requires another opening; it does not prohibit research.
```

Three rules from Section 3.4 apply to the interval:

1. **Append-only research keeps the gate.** Research turns append to context, so the admission stays valid within the gate lifetime and turn allowance.
2. **Modification still invalidates.** If cached context is modified during the interval, `on_context_change` starts a new epoch, clears the witness and pending gate and bootstraps; resurfacing "does not repair an invalid witness retroactively".
3. **New evidence needs a new opening.** Evidence read during the interval and relied on by the action is not in `gate.evidence`. Under Stage 4, `act_tool_turn` denies the operation ("evidence not cited at opening"); the worker opens again with the new evidence ID.

**Host limits.** On a host that can change cached context without a reliable event, enabling resurfacing gives renewed delivery but not strict admission validity. That is the limited "Hosted history with heuristic detection" variant of Appendix F.3, and its detection limits must be stated.

### Appendix C tests

| Test | Where Stage 3 decides it |
| --- | --- |
| C.1 "Resurfacing delivery fails at opening" | `confirmed_delivery` fails, so no Gate is set and `frame.session_witness` is untouched |
| C.1 "Research turn between opening and action, policy permits it" | `within_opening_interval_policy` with `config.max_intervening_turns` at or above the count; append-only growth leaves the epoch valid |
| C.1 "Research turn with zero-intervening-turn policy" | The research runs; `gate_is_current` then fails on the interval check, so a later action needs another opening |

All Stage 2 rows must still pass with resurfacing enabled.

### What it guarantees and does not guarantee (Appendix E)

- **Resurfacing.** Establishes that the exact approved authority is delivered at opening and remains available under the context-validity rule, and that the interval before action is configurable. Does not establish recall, attention, comprehension, retroactive repair of an invalid admission, or lower mistake rates.

## Stage 4: Action-specific claims, claim-before-payload order and the generation receipt

**Purpose.** Make the worker state, before it generates an action, why the active authority permits that specific action and what each piece of relied-on evidence contributes. A trusted generation adapter completes and freezes the claim fields before it enables the dependent action-payload fields, and supplies a protected receipt that binds the observed order to this gate opening and to the exact emitted claims and payloads. Dispatch runs through `act_tool_turn` (B.3), which replaces the Stage 2 wrapper.

**C32 sections implemented.** Section 3.5 Claims (including "Generation order and release" and "What the harness checks"); B.3 The action turn.

**Status: Deployed in part; the ordering contract is a Specified addition.** Section 5.1 What ran reports "Action claims and plan-level evidence obligations" as "In use". It lists "Enforced claim-before-payload generation and protected ordering receipt" as "Specified (Section 3.5; Appendix B.3); enforcement not established by the historical audit or current deployment record". Without the receipt check this stage is the "Deployed two-step gate, resurfacing and contemporaneous claims" variant of Appendix F.2. "An adapter that cannot enforce and attest this sequence must not report compliance with the strict reference contract" (B.3).

### Data structures

```text
authority_claim                        # testimony: why the active authority permits this action (Section 3.5)
evidence_claims                        # one claim per evidence ID an operation relies on
evidence_map {op.id: [evidence_id]}    # B.3: the evidence each operation names; must be within gate.evidence
generation_receipt                     # B.3: supplied by the trusted adapter, never by the worker
    g_frame_id, g_epoch, g_version, g_opening_id    # bind to frame, epoch, authority version, gate.opening_id
    g_claims_digest                    # exact emitted authority_claim and evidence_claims
    g_payload_digest                   # exact emitted action payloads (the tool_calls)
    g_evidence_digest                  # exact evidence_map
    g_claims_completed_at              # adapter-observed time the claim fields were frozen
    g_payload_started_at               # adapter-observed time payload generation was enabled
    g_adapter_mac                      # attestation; the key exists only inside the trusted adapter
```

The adapter, its key and its receipts belong to the protected surface: "The strict reference harness additionally protects its generation adapter and ordering receipts" (Section 3.10).

### Pseudocode

**Guide-level choice: two generations.** Section 3.5 allows "constrained serialization in one generation or separate claim and payload generations". On an OpenAI-compatible endpoint the portable form is two generations: the first offers only a claims tool and forces it with `tool_choice`; the second runs with the frozen claims already in context and the action tools enabled.

```text
g_generation_adapter(frame, turn):            # trusted; replaces g_chat_completion in the loop at Stage 4
    gate = frame.open_gate
    if gate is None:
        return g_ordinary_generation(frame)   # no consequential batch can dispatch without a gate
    # Generation 1: claims only. No action tool is offered.
    r1 = g_chat_completion(messages    = frame.g_context,
                           tools       = [g_claims_tool],
                           tool_choice = {type: "function", function: {name: "g_submit_claims"}})
    claims = g_parse_claims(r1)               # authority_claim, evidence_claims, or g_no_action
    if claims is g_no_action:
        return g_ordinary_generation(frame, tools = g_nonconsequential_tools(frame))
    claims_completed_at = g_adapter_clock()
    g_freeze(claims)                          # claim fields are now immutable
    g_append(frame, r1.choices[0].message)
    g_append(frame, {role: "tool", tool_call_id: r1.choices[0].message.tool_calls[0].id,
                     content: "claims recorded"})
    # Generation 2: dependent payload, with the frozen claims in context.
    payload_started_at = g_adapter_clock()
    r2 = g_chat_completion(messages = frame.g_context, tools = g_tool_definitions(frame))
    calls = r2.choices[0].message.tool_calls
    evidence_map = {c.id: c.arguments.g_evidence_ids for c in calls}   # evidence each call relies on
    receipt = g_sign_receipt(frame.id, frame.epoch, gate.version, gate.opening_id,
                             g_digest(claims.authority_claim, claims.evidence_claims),
                             g_digest(calls), g_digest(evidence_map),
                             claims_completed_at, payload_started_at)
    g_freeze(calls, evidence_map)             # frozen through dispatch (B.3)
    return (r2, claims, evidence_map, receipt)

claims_precede_payload(generation_receipt, frame, gate,
                       calls, authority_claim, evidence_claims, evidence_map):   # named in B.3
    r = generation_receipt
    if r is None or not g_receipt_mac_valid(r):
        return False                          # missing, asserted or fabricated receipt
    if (r.g_frame_id, r.g_epoch, r.g_version, r.g_opening_id) != \
       (frame.id, frame.epoch, gate.version, gate.opening_id):
        return False                          # receipt from another opening, frame or epoch
    if r.g_claims_digest != g_digest(authority_claim, evidence_claims):
        return False                          # claim changed after the receipt
    if r.g_payload_digest != g_digest(calls) or r.g_evidence_digest != g_digest(evidence_map):
        return False                          # payload or evidence binding changed or substituted
    return r.g_claims_completed_at < r.g_payload_started_at     # claims completed first
```

Dispatch then calls `act_tool_turn(frame, turn, calls, authority_claim, evidence_claims, evidence_map, generation_receipt)` exactly as B.3 gives it. In order, `act_tool_turn` classifies every call by `derive_actual_effect`; lets nonconsequential calls through; denies gated calls in the same turn as `open_gate`; consumes the gate; checks `gate_is_current`; requires `authority_claim`; checks `claims_precede_payload`; and then, per unit from `group_edits_sharing_a_basis`, checks that every bound evidence ID was cited at opening, is still admitted and is covered by a claim (`covered_by_claim`), that `derived_floor(op)` and `plan_obligations_checkable_before(op)` are satisfied, that the unit does not depend on another effect in the batch, and that `blocking_scope_permission_and_review_checks(unit)` pass. Only then does it persist the intent (`persist_intent_once` with `proof_record`), dispatch under `dispatch_with_atomic_version_check` against `versions_from_cited_observations`, persist the outcome and, after a structured edit, call `resurface_full_read_areas`.

**What the harness checks, and what it does not.** "Presence, generation order, binding to the pending gate and unchanged emitted claims and payloads, and coverage" (Section 3.5). It never validates a claim's truth: "A claim can be mistaken, ritualized or false; its content is for reviewers and auditors." The claim states the worker's interpretation of the authority for this action; the only proof value the worker reproduces anywhere in the protocol is the bound witness at `open_gate`.

### Appendix C tests

| Test | Where Stage 4 decides it |
| --- | --- |
| C.2 "Valid gate; no authority claim" | `act_tool_turn` consumes the gate before the `authority_claim` check |
| C.2 "Claims completed before payload through the trusted generation adapter" | `claims_precede_payload` returns true; the per-unit checks still run |
| C.2 "Action payload generated first, with a claim appended afterward" | `g_claims_completed_at < g_payload_started_at` fails |
| C.2 "Claims listed first, but no protected generation receipt" | `r is None` |
| C.2 "Worker supplies an asserted or fabricated ordering receipt" | `g_receipt_mac_valid` fails; the worker never holds the adapter key |
| C.2 "Claim, action payload or evidence binding changed after receipt" | A digest mismatch |
| C.2 "Receipt from another gate opening, even with the same valid witness" | `g_opening_id != gate.opening_id` |
| C.2 "Cited evidence ID with no covering claim" | `covered_by_claim` fails for that operation only |
| C.2 "Structured edit without a covering read" | `derived_floor(op)` is unmet (see Section 6.2 above the gate) |
| C.2 "Structured edit whose basis is stale at commit" | `dispatch_with_atomic_version_check` against the derived expected version (see Section 6.3 above the gate) |
| C.2 "External mutation without principal permission" | `blocking_scope_permission_and_review_checks` (see Section 3.7 above the gate) |

All Stage 2 and Stage 3 rows must still pass with `act_tool_turn` in place of `g_stage2_tool_turn`.

### What it guarantees and does not guarantee (Appendix E)

- **Claims under the strict reference generation contract.** Establishes that the worker completed an action-specific interpretation before dependent payload generation, and that a protected receipt binds the order and emitted proposal to the gate. Does not establish the claim's truth, private reasoning order or correctness of eventual effects; the historical audit does not establish this generation contract.
- **Evidence identity check.** Establishes that a cited evidence ID is real, admitted in this epoch and of the right role. Does not establish that it supports the claim or suffices for the action.
- **Evidence floors.** Establishes that the harness required what it could derive from the operation and that the plan could only raise it. Does not establish that the floor was sufficient, or that a shell call had the evidence it should have, until post-commit verification runs.

## Above the gate

These layers assess or constrain work done under the authority the gate binds. "None enlarges CHR's authority guarantee or promotes worker testimony to permission" (Section 6.1 The layers). Each can be adopted on its own once Stage 2 holds; each states its own status.

### Effect policy (Section 3.7 Effect policy)

| Tier | Operations | Treatment |
| --- | --- | --- |
| Research | Read, search, list, fetch; a research shell | Nonconsequential. The shell runs in a sandbox with the filesystem read-only and the harness directory unbound. |
| Project mutation | File edit, create, delete; a mutation shell | Consequential; gate required. The shell has project write access and the harness directory unbound. Every write path is gated identically. |
| External mutation | Deploys, pushes to shared remotes, external messages, system settings | Consequential, plus principal permission per action |

```text
derive_actual_effect(call):                   # named in B.3; this body is guide-level
    return g_classify_by_effect(call)         # by actual effect and enforced isolation, never by tool name

effect_policy.requires_gate(effect):          # named in B.3; this body is guide-level
    return g_tier(effect) in {"project_mutation", "external_mutation"}
           or g_plan_added_class(effect)      # approved plans may add classes; the worker cannot exempt its own

# Inside blocking_scope_permission_and_review_checks(unit) (B.3):
#   g_tier(effect) == "external_mutation" requires g_principal_permission(unit), else DENIED pending permission
```

The harness directory (memory store, approved plans, sidecar) is bound by neither sandbox and is reached only through governed tools; any other access prompts the principal and is logged. A deployer who does not trust a worker's disposition tightens the bounds, never the gate: network isolation for both shells, protected paths bound read-only, shell effects staged and validated before application, review before more action classes. Section 3.7 records that the reference MVP does not isolate the network from the mutation shell; deployments with network, secret-exfiltration or irreversible exposure need an effect policy that mediates those paths before the CHR guarantee applies to them.

- **Status: Deployed.** Section 5.1 reports both shell sandboxes, the principal prompt on harness-directory access and principal permission for mutation outside the project as "In use".
- **Tests.** C.1 "Harness directory accessed through the shell"; C.2 "External mutation without principal permission".
- **Appendix E.** "Effect classification" establishes that operations in the configured consequential set are checked, not that the set is right. The "`bash_research` sandbox" row establishes that research commands cannot write governed resources or reach the harness directory, and nothing about network effects not separately isolated. The "`bash_mutate` after the gate" row establishes that authority was proven before the command ran and the harness directory was unreachable, not that the command served the task or caused no external effect.
- **Variants.** Appendix F.6 Write paths.

### Parallel batches (Section 3.8 Parallel batches)

One successful opening covers the next consequential action, which may be one call or a parallel batch generated in one turn. Every rule in the Section 3.8 table is already enforced by `act_tool_turn` (Stage 4):

| Section 3.8 rule | Where `act_tool_turn` enforces it |
| --- | --- |
| One gate per batch; batch-wide denial | `frame.open_gate = None` before any check; `gate_is_current` fails for every gated operation without a valid gate |
| Evidence from the opening | `bound <= gate.evidence` per operation |
| Per-operation denial | Issues are collected per unit; unrelated valid units still dispatch |
| Opening first | `is_open_gate_call` denies gated operations in the opening turn |
| Intervening turns; interval exceeded | `within_opening_interval_policy` inside `gate_is_current` (Stage 3) |
| Context changes | `on_context_change` clears the pending gate (Stage 2) |
| Dependencies | `depends_on_effect_in_same_batch` |

- **Status: Deployed.** Section 5.1 reports the "parallel-batch rule" as "In use".
- **Tests.** C.1 "`open_gate` and a consequential operation in one turn" (also Stage 2).

### Approval and change requests (Section 3.9 Approval and change requests)

Approval is "the one sanctioned route by which agent-authored text can become authority". The principal states what they want; the agent asks questions and writes a full restatement with explicit bounds; the principal requests changes until satisfied and approves through the trusted channel, citing the record IDs of the restatement and of the approval message; the harness binds the approved text and applicable approved rules into one immutable `plan_auth` version and activates it. Only an event arriving through the principal's channel approves.

```text
# Activation is Appendix A's activate_plan_auth(approved_text, principal_approval); it clears every
# governed frame's witness. The change-request path below is guide-level apart from its signature.

request_plan_change(version, blocker, evidence, recommendation):   # signature from Section 3.9
    require version == active_plan_auth.version
    proposal = g_store_append("change_request", version, blocker, evidence, recommendation)   # testimony only
    g_present_to_principal(g_clause_diff(active_plan_auth, proposal),
                           g_scope_delta(active_plan_auth, proposal),     # where grants are declared
                           g_motivating_source_types(evidence),           # an external email reads as one
                           recommendation)
    return proposal                           # the worker never edits its authority

g_on_principal_decision(proposal, decision):  # arrives only through the principal's channel
    if g_approved(decision):
        activate_plan_auth(g_proposed_text(proposal), decision)   # new version; prior witnesses invalid
    # denied: nothing changes and the old version governs
```

- **Status: Deployed.** Section 5.1 reports "Plan approval bound to restatement and approval-message IDs" as "In use". Showing the cumulative diff against the root version is an open design item (Section 8.5).
- **Tests.** C.2 "Change request approved"; C.2 "Change request denied".
- **Appendix E.** Approval bound to restatement and approval-message IDs establishes that the principal approved exactly that text, not that its premises are true or that it was read with care. The change-request diff and scope delta establish that the principal saw which clauses and declared scope would change, not that the change was judged well.
- **Variants.** Appendix F.4 Approval.

### Implementation requirements (Section 3.10 Implementation requirements)

| Requirement | Where this guide meets it |
| --- | --- |
| One sidecar per frame | Stage 2 data structures |
| Serialized transitions | `serialized_frame_state` and the per-frame queue below |
| Complete mediation | The tool-call loop never dispatches by tool name; every consequential path ends in `consequential_batch` or `act_tool_turn` |
| Protected surface | The authority record, active binding, witness unguessability and binding, complete mediation, and at Stage 4 the adapter and receipts |
| Context validity | `g_append`, `g_modify_context` and `on_context_change` (the tool-call loop) |
| Claim generation order | Stage 4 |
| Gate timing policy | Stage 3; log the opening-to-action distance |
| Turn commits | End of turn, below |
| Concurrent workers | Separate worktrees, or changes attributed to the effect frame before post-commit verification |
| Self-hosting | The gating instance never runs from the tree it gates; gate code reaches it only through a principal-approved release |

```text
g_frame_queue(frame):                         # Section 3.10: one queue per sidecar
    for event in frame.g_queue:               # tool turns, authority changes and context events, in order
        under serialized_frame_state(frame):
            match event.kind:
                "tool_turn":        g_harness_dispatch(frame, event.turn, event.tool_calls)
                "authority_change": on_authority_change(frame)
                "context_change":   on_context_change(frame, event.change)
```

- **Status.** Per row, as given in the stages and layers it points to. Section 5.1 assigns no separate status to the self-hosting rule.
- **Tests.** C.1 "Self-hosted agent edits gate source" (also Stage 2).

### End of turn (B.4 End of turn)

```text
end_of_turn(frame, turn, gate_used):          # B.4, unchanged
    if tracked_project_changed(turn):
        commit = commit_to_shadow_history(trailer=proof_record_ids(turn))
        record_turn_commit(commit)
        invalidate_bases_changed_by(commit)          # other frames' observations go stale
        post_commit_verification(frame, commit, gate_used)
            # per changed path: plan obligations against gate_used.evidence;
            # actual effects against declared grants; findings recorded; revert by policy
        resurface_changed_hunks(frame, commit)       # admitted as new observation records
```

**Guide-level choice.** `commit_to_shadow_history` writes into harness-owned history outside the project, such as a shadow repository or ref namespace (Section 6.3), including newly created non-ignored files. The resurfaced hunks are appended with `g_append` and admitted to `frame.admitted` as evidence.

- **Status: Deployed in part.** Section 5.1 reports "Per-turn auto-commit" as "In use"; "Post-commit obligation verification and hunk resurfacing" is a **Specified addition** ("Specified (Section 6.3); not yet in use").
- **Tests.** C.2 "`bash_mutate` changes a path with an unmet plan obligation"; C.2 "`bash_mutate` performs an effect outside a declared grant".
- **Appendix E.** Post-commit verification establishes that every changed path met the plan's obligations or was recorded as a finding, not prevention. Hunk resurfacing establishes that the worker saw what its shell command changed, not that the change was right. The turn commit establishes the net tracked change at the turn boundary, not intermediate changes, ephemeral paths or effects outside the project.
- **Variants.** Appendix F.6 Write paths.

### Structured authorities (B.5 Structured authorities)

A structured authority (Companion B) adds a witness per chunk, "bound to its chunk ID, the authority version, the frame and the epoch", checked at opening and cleared by `start_new_epoch` and `on_authority_change` exactly like the session witness.

```text
frame.g_chunk_witnesses {chunk_id: (nonce, chunk_binding)}    # guide-level sidecar field

g_read_authority_chunk(frame, chunk_id):      # governed read of one chunk
    chunk_binding = (chunk_id, active_plan_auth.version, frame.id, frame.epoch)
    (nonce, bound) = frame.g_chunk_witnesses.get(chunk_id, (None, None))
    if bound != chunk_binding:
        nonce = fresh_unguessable_nonce()
    if not confirmed_delivery(frame, (g_chunk_text(chunk_id), nonce)):
        return DELIVERY_UNCONFIRMED
    frame.g_chunk_witnesses[chunk_id] = (nonce, chunk_binding)
    return (g_chunk_text(chunk_id), nonce)

g_check_chunk_witnesses(frame, cited):        # called from open_gate for the chunks the action relies on
    for (chunk_id, w) in cited:
        (nonce, bound) = frame.g_chunk_witnesses.get(chunk_id, (None, None))
        if w != nonce or bound != (chunk_id, active_plan_auth.version, frame.id, frame.epoch):
            return DENIED("chunk witness not valid for this epoch and version; reread the chunk", chunk_id)
    return OPEN

# start_new_epoch and on_authority_change also set frame.g_chunk_witnesses = {}   (B.5)
```

- **Status: Specified addition.** Section 5.1 lists "chunked plans" under "Companions A and B; not yet in use". Task sub-authorities, each with its own frame and witness, are "In use".
- **Tests.** C.3 "Chunk witness from an earlier epoch (*regression*)"; C.3 "Chunk witness from an earlier authority version (*regression*)"; C.3 "Chunk witness read in this epoch for the active version".
- **Appendix E.** "Chunk witness" establishes that at this opening the worker reproduced the witness issued for that specific authority chunk, bound to its chunk ID, the active authority version, frame and epoch. Does not establish recall or comprehension of other chunks, or that the cited chunk is the correct basis for the action.
- **Variants.** Appendix F.5 Authority structure.

### Management (Section 6. What the gate leaves to management)

"A passing gate establishes that the action is bound to the genuine reference. Everything in this section manages correctness against that fixed reference, scaled to liability."

- **Section 6.2 Evidence: identity is provenance, sufficiency is correctness.** Evidence identity is a lookup and denies the opening (Stage 2). Each operation has a derived evidence floor, `derived_floor(op)` in B.3; the plan can raise any floor, never lower it; the harness derives the expected artifact version from the cited observation, and the worker never supplies it.
- **Section 6.3 Edits, turn commits and post-commit verification.** After a successful structured edit the tool returns the full current read area under a new record ID (`resurface_full_read_areas`); version validation and mutation are one compare-and-update transaction. Path classes: tracked, ephemeral, protected (writes denied for structured tools, read-only for the shell where configured) and the harness directory. Ignore rules, protected paths and sandbox profiles change only through the principal.
- **Section 6.4 Review placement: liability and reversibility.** Irreversible effects get review before the action where liability warrants; reversible effects are audited afterward. A reviewer may reject or escalate but cannot grant authority, and checks claim against authority and evidence, action against claim, and effect against action, claim and authority.
- **Section 6.5 Failure classes.** Track unauthorized effects per consequential action and separate authorization errors (the principal's) from correctness errors under genuine authority.
- **Section 6.6 Acceptance artifacts written by the implementer.** Law 15: an implementer-authored acceptance artifact binds only after principal approval, independent audit or independent authorship with read-only protection.
- **Section 6.7 Worker dispositions and authorization quality.** Measure the rate of unnecessary checks; reduce it with worker instructions that state what the harness guarantees and with authorities that state their discretion.
- **Section 6.8 The allocation rule and favorable path economics.** Decide in code whatever is truly mechanical, and make the grounded path the cheapest: `status` when unsure, read evidence before opening, batch parallel actions, request authority changes, write specific claims after resurfacing.

```text
g_acceptance_binds(artifact):                 # Law 15 (Section 6.6)
    return (g_principal_approved(artifact)
            or g_independently_audited(artifact)
            or (g_independently_authored(artifact) and g_read_only_for_implementer(artifact)))
# Until it binds, a passing run is recorded as testimony, not acceptance.
# A write to a protected acceptance artifact is denied by the protected-path bound, and the
# denial directs the worker to request_plan_change.
```

- **Status.** Section 5.1 lists "Acceptance-artifact audit under Law 15" as a **Specified addition** ("Specified (Section 6.6); not yet in use"). Plan-level evidence obligations are "In use".
- **Tests.** C.1 "Valid gate; action violates the plan" (also Stage 2); C.2 "Structured edit without a covering read" (also Stage 4); C.2 "Structured edit whose basis is stale at commit" (also Stage 4); C.2 "Implementer-authored test cited for acceptance before approval or audit"; C.2 "Implementer edits a protected acceptance artifact".
- **Appendix E.** Law 15 acceptance routes establish that an implementer-authored acceptance artifact was approved, independently audited or independently written before it counted, not that it covers every intent of the plan.
- **Variants.** Appendix F.7 Acceptance artifacts.

### Variants (Appendix F. Embodiments and variants)

"Each variant below is a complete design for its purpose" (Appendix F). This guide builds the reference choice in each row; the others are the paper's alternatives.

| Appendix F subsection | Reference choice in this guide | Alternatives the paper lists |
| --- | --- | --- |
| F.1 Authority testimony | Session witness (Stage 2) | Per-action witness rotation: each witness single-use; tested with no measured benefit over the session witness |
| F.2 Layers at the boundary | Gate, resurfacing and claims (Stages 2 to 4) | Gate only (Stage 2 alone); single-step gate and claims (historical audited variant); gate and resurfacing (Stages 2 and 3); deployed two-step gate, resurfacing and contemporaneous claims (Stage 4 without the receipt check); stricter release policy |
| F.3 Host and context control | Controlled context (the tool-call loop) | Hosted history with heuristic detection (limited variant) |
| F.4 Approval | Restatement loop with ID-bound approval | Direct principal instruction (single tasks); plan programs with compiler checks and plan audit (Companion B) |
| F.5 Authority structure | Single-block `plan_auth` | Task sub-authorities; header and chunks with bound chunk witnesses (B.5) |
| F.6 Write paths | Shell with post-commit verification and hunk resurfacing (end of turn) | Structured tools with pre-write evidence checks; shell with staged effects validated before application |
| F.7 Acceptance artifacts | Any of the three Law 15 routes | Principal-approved artifact or specification; independent audit against the plan; independent authorship with read-only protection |

## Fixture assignment index

Every Fixture row of Appendix C.1, C.2 and C.3, with the guide section that must pass it. No row is out of guide scope. "Stage 1 (analogue)" means Stage 1 runs the warning-profile analogue described there; the row itself passes at the stage named after it.

| Subsection | Fixture | Assigned to |
| --- | --- | --- |
| C.1 | New epoch; active `plan_auth` read | Stage 2 |
| C.1 | Read again in the same epoch | Stage 2 |
| C.1 | Epoch change, then `status()` (*regression*) | Stage 2 |
| C.1 | Plan revision, then `read_authority()` (*regression*) | Stage 2 |
| C.1 | Witness equals a durable record ID | Stage 1 (analogue); Stage 2 |
| C.1 | Valid witness at `open_gate` | Stage 2 |
| C.1 | Same witness for the next batch in the same epoch | Stage 2 |
| C.1 | Witness copied into a note, same epoch | Stage 1 (analogue); Stage 2 |
| C.1 | Witness copied to another frame or epoch | Stage 2 |
| C.1 | Never-issued or wrong-authority witness | Stage 2 |
| C.1 | `authority_unavailable` | Stage 2 |
| C.1 | Failed openings reach the cap | Stage 2 |
| C.1 | `read_authority()` with unconfirmed delivery | Stage 2 |
| C.1 | Correct authority text supplied in place of the required witness | Stage 2 |
| C.1 | Witness supplied without confirmed admission for this frame and epoch | Stage 2 |
| C.1 | Resurfacing delivery fails at opening | Stage 3 |
| C.1 | New opening while an unused gate is pending | Stage 2 |
| C.1 | No gate, an expired gate, or a second batch under one opening | Stage 2 |
| C.1 | `open_gate` and a consequential operation in one turn | Stage 2; Above the gate (Section 3.8) |
| C.1 | Research turn between opening and action, policy permits it | Stage 3 |
| C.1 | Research turn with zero-intervening-turn policy | Stage 3 |
| C.1 | Exact authority delivered, but worker cannot supply the required proof | Stage 2 |
| C.1 | Targeted removal or micro-compaction after authority read | Stage 1 (analogue); Stage 2 |
| C.1 | Context modification after gate opening | Stage 2 |
| C.1 | Authority revoked or expired after opening, without a version increment | Stage 2 |
| C.1 | Valid gate; action violates the plan | Stage 2; Above the gate (Section 6) |
| C.1 | Historical `plan_auth` read through memory search | Stage 2 |
| C.1 | Self-hosted agent edits gate source | Stage 2; Above the gate (Section 3.10) |
| C.1 | Harness directory accessed through the shell | Stage 2; Above the gate (Section 3.7) |
| C.1 | General-provenance citation matches a chunk present in current context | Stage 1 |
| C.1 | General-provenance citation does not match any chunk present in current context | Stage 1 |
| C.2 | Evidence ID not admitted in this epoch | Stage 2 |
| C.2 | Valid gate; no authority claim | Stage 4 |
| C.2 | Claims completed before payload through the trusted generation adapter | Stage 4 |
| C.2 | Action payload generated first, with a claim appended afterward | Stage 4 |
| C.2 | Claims listed first, but no protected generation receipt | Stage 4 |
| C.2 | Worker supplies an asserted or fabricated ordering receipt | Stage 4 |
| C.2 | Claim, action payload or evidence binding changed after receipt | Stage 4 |
| C.2 | Receipt from another gate opening, even with the same valid witness | Stage 4 |
| C.2 | Cited evidence ID with no covering claim | Stage 4 |
| C.2 | Structured edit without a covering read | Stage 4; Above the gate (Section 6) |
| C.2 | Structured edit whose basis is stale at commit | Stage 4; Above the gate (Section 6) |
| C.2 | `bash_mutate` changes a path with an unmet plan obligation | Above the gate (B.4) |
| C.2 | `bash_mutate` performs an effect outside a declared grant | Above the gate (B.4) |
| C.2 | External mutation without principal permission | Stage 4; Above the gate (Section 3.7) |
| C.2 | Implementer-authored test cited for acceptance before approval or audit | Above the gate (Section 6) |
| C.2 | Implementer edits a protected acceptance artifact | Above the gate (Section 6) |
| C.2 | Change request approved | Above the gate (Section 3.9) |
| C.2 | Change request denied | Above the gate (Section 3.9) |
| C.3 | Chunk witness from an earlier epoch (*regression*) | Above the gate (B.5) |
| C.3 | Chunk witness from an earlier authority version (*regression*) | Above the gate (B.5) |
| C.3 | Chunk witness read in this epoch for the active version | Above the gate (B.5) |

## Guide-level helpers

Every identifier below is a guide-level helper: the paper does not specify it, and an implementation may realize it differently. Identifiers in the listings that are not `g_` names and not in this table are either taken unchanged from Appendices A and B, are OpenAI-compatible wire fields (the list in Conventions, plus `type` and `description`), or are local variables and parameters of the listing in which they appear.

**Names the paper uses outside Appendices A and B.** These keep the paper's spelling; their bodies or bindings here are guide-level.

| Name | Source in the paper | Guide-level role |
| --- | --- | --- |
| `plan_auth` | Section 2.1 Authority | The authority record type; Appendix A reads its active instance as `active_plan_auth` |
| `status` | Section 3.3 The gate | Worker-callable tool bound to `bootstrap_status` (B.1) |
| `read_memory` | B.2 Opening the gate, first sentence | Worker-callable tool bound to `g_read_memory` |
| `request_plan_change` | Section 3.9 Approval and change requests | Signature from the paper; body in "Approval and change requests" is guide-level |
| chunk record (`id`, `text`) | Section 3.0 ("context chunk") | The unit a Stage 1 witness is placed in |

**The tool-call loop**

| Helper | Role |
| --- | --- |
| `g_run_session` | Session driver around the chat-completion endpoint |
| `g_new_turn` | Allocates the `turn` record passed to B.3 and B.4 |
| `g_chat_completion` | One OpenAI-compatible chat-completion request |
| `g_tool_definitions` | The tools list sent with each request |
| `g_context` | The frame's append-only message list |
| `g_append` | The only routine that adds to `g_context`; append only |
| `g_modify_context` | The only routine that rewrites, prunes, summarizes or removes cached context |
| `g_apply` | Applies one modification inside `g_modify_context` |
| `g_on_host_context_event` | Entry point for host-reported history changes |
| `g_context_change` | Builds the `change` record whose `kind` B.1 inspects |
| `g_harness_dispatch` | Routes one turn's tool calls to `g_stage2_tool_turn` or `act_tool_turn` |
| `g_stage` | The highest stage the deployment has built |
| `g_parse_call` | Parses one tool call without altering model-generated arguments |
| `g_execute_free_call` | How `dispatch(free)` runs a nonconsequential call |
| `g_run_research_tool` | Runs a nonconsequential research tool in its sandbox |
| `g_gate_used` | The gate a turn consumed, passed to `end_of_turn` |
| `g_session_finished`, `g_next_user_message` | Session control |
| `g_claims_from_adapter`, `g_receipt_from_adapter` | Stage 4 outputs of `g_generation_adapter` for the turn |

**Stage 1**

| Helper | Role |
| --- | --- |
| `g_provenance` | Protected map from witness to chunk ID |
| `g_present_chunks` | Chunks present in the current context |
| `g_place_witness` | Section 3.0 step 1 |
| `g_chunk_message` | Formats a chunk with its witness inside it |
| `g_check_citation` | Section 3.0 steps 2 and 3 |
| `g_warn`, `g_record_warning` | Section 3.0 step 4 and its audit record |
| `g_VALIDATED`, `g_WARNING` | Outcome values of the citation check |
| `g_clear_provenance` | Drops all associations on a non-append context change |
| `g_check_turn_citations` | Runs the citation check over one turn's calls |
| `g_cites` | Optional tool argument carrying model-generated witnesses |

**Stage 2 and Stage 3**

| Helper | Role |
| --- | --- |
| `g_status_message`, `g_task_state`, `g_pending_warnings` | Content of the `bootstrap_status` result |
| `g_read_memory` | Implements B.2 `read_memory`: governed record read that admits the record to the epoch under its harness-assigned role |
| `g_store_get` | Fetches one record from the append-only store |
| `g_harness_assigned_role` | The harness-assigned role of a record (Section 2.2) |
| `g_record_message` | Returns the record's exact text as tool-result content (B.2) |
| `g_stage2_tool_turn` | Stage 2 dispatch wrapper; replaced by `act_tool_turn` at Stage 4 |
| `g_completed_nonconsequential_turns_since` | Turn count used by `within_opening_interval_policy` |

**Stage 4**

| Helper | Role |
| --- | --- |
| `g_generation_adapter` | The trusted generation adapter (two generations) |
| `g_ordinary_generation`, `g_nonconsequential_tools` | Generation when no gate is pending or no action is intended |
| `g_claims_tool`, `g_submit_claims` | The claims-only tool forced in the first generation |
| `g_parse_claims`, `g_no_action` | Parses the claims; marks a turn with no consequential action |
| `g_adapter_clock` | The adapter's trusted clock |
| `g_freeze` | Makes claims, payloads and evidence bindings immutable through dispatch |
| `g_evidence_ids` | Per-call argument naming the evidence the call relies on |
| `g_sign_receipt`, `g_receipt_mac_valid`, `g_digest` | Receipt creation, verification and content digests |
| `g_frame_id`, `g_epoch`, `g_version`, `g_opening_id` | Receipt binding fields |
| `g_claims_digest`, `g_payload_digest`, `g_evidence_digest` | Receipt content fields |
| `g_claims_completed_at`, `g_payload_started_at` | Receipt order fields |
| `g_adapter_mac` | Receipt attestation field |

**Above the gate**

| Helper | Role |
| --- | --- |
| `g_classify_by_effect`, `g_tier`, `g_plan_added_class` | Effect classification behind `derive_actual_effect` and `effect_policy.requires_gate` |
| `g_principal_permission` | Per-action principal permission for external mutation |
| `g_store_append` | Appends a change request to the store as testimony |
| `g_present_to_principal`, `g_clause_diff`, `g_scope_delta`, `g_motivating_source_types` | Change-request presentation (Section 3.9) |
| `g_on_principal_decision`, `g_approved`, `g_proposed_text` | Handling of the principal's decision |
| `g_frame_queue`, `g_queue` | The per-frame serialized event queue (Section 3.10) |
| `g_chunk_witnesses`, `g_read_authority_chunk`, `g_chunk_text`, `g_check_chunk_witnesses` | Chunk witnesses (B.5) |
| `g_acceptance_binds`, `g_principal_approved`, `g_independently_audited`, `g_independently_authored`, `g_read_only_for_implementer` | Law 15 acceptance routes (Section 6.6) |

**Guide-level choices**, each marked where it appears: the tools list; where bootstrap delivery lands; how the model cites (Stage 1); clearing on modification (Stage 1); the warning-profile analogue of three C.1 rows (Stage 1); use of the B.1 epoch pair (Stage 2); `confirmed_delivery` in the tool-call loop (Stage 2); two generations for the ordering contract (Stage 4); and shadow history for turn commits (End of turn).
