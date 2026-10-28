# Grounded Authority for Language-Model Agents

Oct 27, 2026 · Nathan Scherdin

*Context provenance, warning feedback and enforced action gates for language-model workers* · Draft · Engineering design document · Nathan Scherdin

Disclosure: A patent application is pending. Building it yourself for non-commercial or research use is welcome; Commercial use will need a license if the patent issues.

## The problem: When the work order moves

Organizations manage fallible workers through work orders, scoped permissions, review, acceptance and audit. These practices do not require perfect execution. They require a stable assignment against which execution can be judged.

*The Wrong Defendant* [Scherdin] gives the institutional case: human organizations forbid a worker to approve changes to the work order it performs under. Agent harnesses should enforce the same rule. This paper specifies the mechanism.

Language-model agents can lose that reference. Over turns, compactions and handoffs, an agent reconstructs its assignment from the information it brings forward. Any instruction information that is missing or cannot be recalled may be filled in by confabulation, up to the entire assignment. Where instructions remain recoverable, a reconstruction may be reasonable and mostly faithful, and the agent may execute it competently. But when that reconstruction becomes the authority for the next stage, the assignment itself can move without the principal approving a change.

Losing a single prohibition can expand the apparent scope into actions the principal never authorized. Later work can be technically sound and internally consistent while pursuing the changed assignment. An auditor given the same reconstruction may correctly approve that work and still miss the lost boundary: it lacks an independent reference to the original work order. Greater worker or auditor capability cannot recreate approval history missing from their inputs.

This is **authority drift**. A correctness error is assessed against a standard that remains fixed; authority drift replaces the standard. Serious mistakes can still occur under a fixed assignment, but the work remains subject to an unchanged basis for management.

The proposed remedy is to keep the principal-approved assignment outside the worker and require the worker to demonstrate its authority proof before consequential effects. The worker may recommend changing its work order but must never be permitted to rewrite it. Its account of what it was told never becomes what it is authorized to do merely because it produced that account.

## Core thesis

Authority provenance uses the general context-provenance validator with an approved-source requirement and a blocking policy. The authority-drift diagnosis, availability-versus-response distinction and separation from correctness remain unchanged. Text elsewhere that conflicts with this section is a defect in that text, not a change to the thesis.

1. The defining failure of language-model agents today is **authority drift**: over many turns and sessions, the agent's reconstruction of its assignment comes to stand in for the assignment itself. “Drift” in this paper means authority drift.
2. **Authority drift is not a correctness error.** When instructions remain partly recoverable, a reconstruction may be reasonable and mostly faithful to them; missing instructions or instructions that cannot be recalled may be confabulated, up to the entire assignment. The agent may execute that reconstruction competently. The failure occurs when reconstructions become authority for subsequent work, allowing the changes to accumulate. It is the telephone game, played by the agent with itself.
3. **Availability does not establish validated authority testimony.** Authority can be present in context without the agent being able to bring the required authority proof into its output. In the reference implementation, the required response is the witness bound to that authority; producing it demonstrates recall of the witness, not of every task clause. Reconstruction can arise through summarization, compaction, handoffs, lost-in-the-middle effects and other perturbations, potentially down to numerical nondeterminism. The source does not change the need to keep a reconstruction from becoming authority. Incorrect interpretation or application of genuine authority is a correctness issue.
4. **Authority drift integrates:** each reconstructed assignment becomes the source for the next. Information genuinely lost along that reconstruction-only chain cannot be recovered from the chain by greater capability; the model's priors fill the gaps. The integration at issue is the changing assignment, not downstream consequences of mistakes against a fixed assignment.
5. **An external approved reference corrects authority drift.** CHR holds the assignment outside the worker. A governed read makes it available; before each consequential action or permitted batch, the worker generates authority testimony and the harness validates it against the current protected authority admission. The reference implementation uses an unguessable witness bound to the authority version, worker frame and context epoch. The reference governs; a reconstruction never does.
6. Claims, resurfacing, review and audit manage **correctness** against that fixed reference, and are ordinary management practice. General provenance warnings apply the same underlying context check to other cited material and return failures as feedback; they do not require an action gate.

## Technical overview

The shared primitive checks model-generated context testimony against a trusted record of what is actually present in the current context. An unguessable witness is placed inside the target context chunk, and the model generates its citation. Exact validation supplies a cheap, deterministic test of that response despite stochastic retrieval. The minimal warning profile returns a failed check to the model. CHR applies the same primitive to the required approved authority and makes success a condition of consequential action.

The CHR authority gate binds each consequential action or permitted batch to an immutable, principal-approved `plan_auth`. A governed read makes the exact authority **available** in context and issues an unguessable witness bound to that authority version, worker frame and context epoch. At each gate opening, the worker supplies this witness as **authority testimony**. The harness validates the response against its protected admission state before allowing the effect. Availability alone does not satisfy the response requirement.

Any modification of existing cached context invalidates the admission, witness and pending gate and requires a governed reread. Normal append-only growth preserves the existing context. Each successful opening covers one action or batch; policy may permit research between opening and acting or require zero intervening turns.

The reference harness adds resurfacing, which returns the exact authority in the opening's tool result, and a mandatory action-specific claim completed before generation of its dependent action payload. The strict generation-order contract is specified in Section 3.5 and Appendix B.3; it is not established by the historical audit. Review, evidence checks, tests and audit address correctness against the fixed reference.

Section 5 reports author-run field experience and distinguishes deployed configurations from specified additions. The appendices provide the minimal protocol, reference protocol, acceptance fixtures and guarantee matrix so implementations can be evaluated on their own workloads and liability requirements.

## 1. Diagnosis and development

This section defines authority drift and the availability–testimony distinction, states the causal diagnosis, and separates the formal guarantee from the deployment hypotheses.

### 1.1 Drift: the telephone game with the work order

**Authority drift**, shortened to **drift**, is an unapproved substantive change to the authority a worker treats as governing. In long-running agents it usually arises progressively: each reconstruction of the assignment becomes the source for the next. No individual step need be a correctness error: a restatement can be a reasonable reading of the information available to the worker, and the worker can execute that restatement competently. The chain loses its governing assignment when those restatements become the source of authority for later work.

Correctness is judged against genuine authority that remains the reference. Misunderstanding, ignoring or misexecuting that authority does not make the worker's interpretation a new approved work order.

This paper uses *correctness* for any error under genuine authority. *The Wrong Defendant* separates three kinds, which experiments report separately: adherence errors (misunderstanding, misapplying or disregarding genuine instructions), unauthorized execution (an action outside approved bounds while genuine authority still governs) and correctness errors (authorized work done wrongly).

| | Authority drift | Correctness issue |
| --- | --- | --- |
| What changes | The assignment taken as governing authority | Interpretation, reasoning or work under a fixed assignment |
| What integrates in this paper's sense | Each reconstructed assignment becomes the source for the next | The authority remains fixed; consequences are still judged against it |
| Detection basis | The original approved assignment | The same approved assignment, applied to the claim, action or effect |
| Response | Preserve external authority and require its proof at consequential boundaries | Claims, review, tests, acceptance and audit |

**Availability and validated testimony are distinct.** A governed read can place the exact authority in context without the worker being able to produce the required authority proof when it is needed. Lost-in-the-middle is relevant for that reason. The gate tests the worker's response rather than treating delivery as a successful demonstration. Failure to supply a valid proof denies the gate and calls for a governed reread. Such a denial is not itself proof that authority drift already occurred. If a worker supplies valid proof and then applies the genuine authority incorrectly, that is correctness.

| Source | Relevance to the distinction |
| --- | --- |
| Summarization, compaction and handoff | A reconstruction may replace original authority in the next context. The reference harness invalidates prior admission on modification of cached context and re-delivers the approved text. |
| Lost-in-the-middle and long context | Authority can remain available while the worker fails to retrieve the required proof. Successful proof does not establish correct interpretation or execution. |
| Capability mistaken for authority | Access or opportunity may be folded into an invented assignment. Technical capability grants no authority. |
| Untrusted text | Injected instructions may be treated as a work order. They have no standing on the principal's approval channel. |
| Other perturbations | Sampling variation and potentially numerical nondeterminism may affect reconstruction or recall; the governing reference and proof requirement remain the same. |

Chen reports policy violations rising from 0% to 30% after compaction, and 0% when the constraint survives the summary [Governance Decay]. Zerhoudi et al. report that Claude Code's `/compact` prompt on Sonnet 4.6 preserves 53% of safety rules after one compaction round and 10% after five, across 20 production agent configurations [Zerhoudi et al.]. Models also fail to use material that remains present [Liu et al.], select stale values over current ones [Guo et al.], and accurately restate constraints they simultaneously violate [Kruthof]. These observations concern different parts of the distinction: loss, recall and correct application.

### 1.2 The CHR diagnosis

CHR stands for Causal-Historical Root. The underlying condition is causal-history non-identifiability: two different histories can produce an identical model-visible context while their real approvals and observations differ. A worker given only that context cannot tell which history occurred. More capability does not help, because the distinguishing information is not in the input.

Role labels, tool-result delimiters and visible source markers establish some origins. They do not authenticate all relevant history. After summarization or compaction in particular, the agent's paraphrase of an instruction carries the agent's own label, and the link back to the principal is gone.

**Why drift integrates.** If the assignment A reaches each later context only through the agent's own restatements, the sequence of contexts C and restatements R is a processing chain. By the data processing inequality [Cover and Thomas], the information that chain carries about A cannot increase:

```latex
A \to C_1 \to R_1 \to C_2 \to R_2 \to \cdots \to R_n \quad\Longrightarrow\quad I(A;R_n) \le I(A;R_{n-1}) \le \cdots \le I(A;C_1)
```

This argument concerns information actually lost when each context receives A only through its predecessor's reconstruction. If the original text still exists in context, it may be recalled later; that is retrieval of retained information, not recovery of erased information. CHR does not assume that availability guarantees this retrieval: the worker must produce the required proof at each opening. External delivery of A breaks a reconstruction-only chain; action-specific validation checks the worker's identification of that delivered authority.

What replaces the loss is not noise but the model's priors. Serial reproduction in humans conventionalizes unfamiliar details [Bartlett], and chains of Bayesian learners that sample from their posterior converge to a distribution determined by the learners' prior [Griffiths and Kalish]. For agents, the deployment-specific constraints a principal actually pays for are the first to go: Chen measures compaction decay 8.3 times larger for soft organizational policies than for hard safety norms [Governance Decay].

The structural remedy does not depend on the source of a reconstruction: keep the approved assignment outside the worker and validate its proof before consequential effects. Inertial navigation supplies the engineering parallel: position estimates integrated from earlier estimates accumulate drift, and fusing an independent sensor reference reduces it [Woodman]. The analogy here concerns the governing assignment. It does not redefine every propagated implementation mistake as authority drift.

**Humans confabulate too.** Misremembered instructions and false memories of approval are ordinary human errors, and source-monitoring research treats them as errors in attributing a memory to its source [Johnson et al.]. Two things limit them in humans. Bad memory is itself a signal: a fuzzy recollection sends a person back to the source. And truth stays re-derivable from the world, while a fabrication can only be re-derived from memory of having made it, so fabrications drift and expose themselves. A model's context removes both. A reconstruction in context is held as precisely as a fact, stays consistent, and is built upon. These differences make drift more frequent in model workers. They do not make it a different kind of failure: a human team that replaced its work orders with its own summaries would drift the same way, and the remedy is the institutional one.

**Dream engine.** In this paper's working image, a model given only its context is a generator without reality monitoring [Johnson and Raye]. Its reasoning can be sound while it cannot tell which of its premises actually happened. CHR supplies an external reality monitor for the one premise that governs all the others: which work order is real.

**Confabulated context references.** Inventing a context source, or presenting absent context as currently available, is a form of hallucination. A provenance warning gives the worker external feedback about that specific failure. At the assignment level, allowing a generated reconstruction to replace the approved reference produces authority drift. Both applications ground the claimed source externally; a worker's generated text cannot acquire evidence or authority status merely by being cited. The check establishes source presence, not the truth of everything attributed to that source.

### 1.3 What was tried first

The gate was reached by elimination. Each earlier step is the obvious thing to build, and each failed.

1. **Rules in the system prompt.** Present in every request, treated as background after a few turns.
2. **A session-start restatement.** Ignored most of the time.
3. **Periodic passive reminders.** Helped briefly, then became noise within a few turns.
4. **Fixed yes/no challenge questions.** The worker produced memorized answer sequences that satisfied the ritual without engaging the rules.
5. **Randomized challenges.** Varying question order and inverting phrasing defeated memorization. This established the principle: the worker must generate something the check can verify, not acknowledge something the harness supplied.
6. **The CHR gate.** The earliest deployed gate checked a worker-generated witness. Action claims were added, and the audited single-step embodiment required the witness, claim and proposed action together in one gated tool call. A later two-step embodiment separated gate opening from the action and returned the exact approved authority in the opening's tool result.

Mediated tools restricted possible actions without establishing their purpose, and workers spent much of their effort navigating that machinery. This experience motivated the favorable-path allocation rule in Section 6.8.

The passive steps presented rules at session start or at fixed positions, not immediately before consequential actions, so they confound passivity with timing. Experiment 2 separates the two (Section 8).

### 1.4 Guarantee and hypotheses

The Core thesis is the governing reference. The statements below distinguish its authority guarantee from hypotheses about worker behavior and management outcomes.

**Authority-confinement guarantee.** Under complete mediation of consequential effects and an immutable approved authority, a reconstruction cannot be bound to a consequential action as the governing authority. This holds for any worker disposition and does not depend on the worker attending to anything. A worker holding a valid witness can still act from its private reading of the genuine task. That is a correctness error against a reference that remains the standard for review. The error cannot acquire governing standing through the worker's testimony.

**Authority-confinement hypothesis.** Workers under the gate keep pursuing the approved assignment instead of letting their reconstructions displace it. They still misunderstand instructions and produce flawed effects; those are correctness problems. The field record supports this (Section 5). Experiment 0 measures drift with and without the gate; Experiment 2 measures how much of the remaining correctness benefit comes from the check, from claims and from resurfacing.

**Yardstick hypothesis.** Under a reasonably constructed plan with independently grounded acceptance standards, authority drift is the failure that integrates changes to the governing assignment itself. Errors in observation, implementation and reasoning can be grave, repeated or irreversible, but they do not become approved standards. Section 6.6 closes the one indirect path identified so far, acceptance artifacts written by the implementer.

**Good-enough hypothesis.** A minimally aligned worker in a correct harness is useful without flawless judgment. The four invariants and complete mediation must be correct. Everything else meets a threshold set by liability.

## 2. Vocabulary

One vocabulary holds throughout the core and the companions. The full glossary is Appendix G.

### 2.1 Authority

Authority is the externally grounded specification of permitted and required work: goals, tasks, acceptance criteria, procedures, constraints, review requirements, delegations and permitted discretion. The reference harness has one operative authority type, `plan_auth`: an immutable, versioned, principal-approved record activated through a trusted path the worker cannot reach. It is the external reference of the Core thesis.

One `plan_auth` serves three uses: execution (what to do and how), acceptance (how work is judged) and authority (what may be initiated). It defines a space of permitted behavior, not a single path. Choices inside that space are discretion, not new authority.

An approved authority is segmented into clauses, each an addressable exact extract with its own ID and no more standing than its parent. Applicable principal-approved procedural rules are written into each plan and inherited by its sub-authorities, rather than kept as a competing authority.

**Capability is not authority.** Neither technical access (credentials, tool permissions) nor competence at the task authorizes changing the task.

### 2.2 Records and their standing

Every event lives in one append-only store. A record's harness-assigned type and role decide what it can support, not where it is stored or which tool read it.

| Kind | What it is | What it can support |
| --- | --- | --- |
| Authority | The active approved `plan_auth` | Permission. It is the only source of permission. |
| Evidence | A qualifying observation admitted through a governed read or trusted tool | Factual reliance. Its ID establishes identity and recorded origin, not accuracy, freshness or sufficiency. Never permission. |
| Testimony | Anything the worker generates: reasoning, notes, summaries, proposed plans | Orientation only. Saving it does not corroborate it. |
| Claim | Testimony linking authority or evidence to a specific action | Review and audit. The harness checks its presence and bindings, never its truth. |

Derivation never upgrades standing. An extract, summary, note or child return carries at most its source's standing. In the terms of Section 1.1, every reconstruction is testimony, and testimony is never the reference.

### 2.3 Identifiers

The reference harness uses two kinds of identifier, written with distinct prefixes throughout this paper.

| Identifier | Written as | Lifetime | Purpose |
| --- | --- | --- | --- |
| Durable record ID | `rec:7f3a9c1e2b4d6058` | Permanent | Names one immutable record of any type. A locator for reads and audit. |
| Witness nonce | `wit:2a9e4c71d0b3f685` | One authority version, frame and valid context epoch | Issued on confirmed authority delivery; reproduced by the worker as action-specific authority proof |

The trusted harness mints the witness on a governed read of active `plan_auth` and binds it to authority version, worker frame and context epoch. A witness is never a durable record ID. Repeated reads and successful gate openings in the same epoch return the same witness. An epoch change, revision, revocation or expiry invalidates it, and the next governed read mints a new one.

These bindings specify the authority profile. The general warning profile can associate a witness with any target context chunk (Section 3.0). In either case the witness is included within the delivered chunk; keeping it only in an external registry would not test the model's ability to retrieve it from context.

### 2.4 Context epochs

A context epoch identifies one admitted working context. **Availability** means the harness delivered the exact active authority into that context and the previously delivered context has not been modified. Adding ordinary new turns is append-only growth; rewriting, removing, pruning or summarizing existing cached context is a modification.

**Any modification of existing cached context invalidates the authority admission, its witness and any pending gate.** This includes targeted removal, micro-compaction and silent compaction if a host performs it. A new epoch requires a governed reread of active authority; the reference harness performs a `status()` bootstrap. A full replacement, explicit handoff or task boundary likewise starts a new epoch. The durable approved authority is not deleted by invalidating its admission.

| State | Established by | Lifetime |
| --- | --- | --- |
| Authority availability | Confirmed governed delivery of the exact active authority | Until existing context or the authority binding changes |
| Validated authority testimony | The worker generates the witness matching the protected current authority admission | A new response is required for each gate opening |
| Pending gate | A successful proof check | The next consequential action or batch, within configured timing policy; context or authority invalidation cancels it |

Evidence admission follows governed reads into the current epoch, not position in context. The reference protocol clears epoch admissions on a context change.

The controlled harness records context modifications. The historical MVP's fallback for hosts outside its control starts a new epoch after an input-token drop of more than about 1,000 tokens; it can miss in-place edits. That heuristic is a limited implementation option, not fulfillment of the strict invalidation rule. Later resurfacing can restore text availability but cannot retroactively make an old witness valid after a context modification. The host's detection limits must be stated when assessing that configuration (Appendix F.3).

### 2.5 Consequential actions

A consequential action has persistent or externally visible effects under the deployment's effect policy. Classification follows actual effects and enforced isolation, not tool names. A read with side effects, or a read of secrets that could leave through an allowed channel, is either consequential or isolated. The implementer sets the baseline, approved plans may add classes, and the worker cannot exempt its own effects.

### 2.6 Parties

| Term | Meaning |
| --- | --- |
| Principal | The party that approves authority |
| Agent | The persistent entity: its authority, history and memories across sessions and models |
| Worker | One model execution within the agent |
| Frame | One task's authority binding. Each frame has its own witness; a parent's witness never opens a child's gate. |

### 2.7 Foundational laws

Fifteen laws govern every layer. The four implementation invariants of CHR are stated exactly in Section 3.2; Laws 1 and 7 relate to them directly. Laws 3–6 and 9–11 are developed in Companion B.

1. **Grounded root authority.** Every consequential action traces to a root grant the principal explicitly approved and the harness activated as `plan_auth`. Compilation, a passing audit, review and worker statements create no authority.
2. **Capability is not authority.** Neither technical access (credentials, tool permissions) nor competence at the task authorizes changing the task; a better solution never expands it.
3. **Attenuation.** Permissions delegated to a child are equal to or narrower than the delegator's. Siblings cannot combine permissions to escape a shared constraint.
4. **Discharge by results.** Delegating work does not delegate the obligation. A parent claims only what validated results establish.
5. **Authority is scoped to effects:** resources, effects, conditions, sequences and outcomes.
6. **The inherited grant is the ceiling.** Reusable permissions inherit. Consumable budgets are allocated, never inherited.
7. **CHR proof at consequential boundaries.** Before consequential effects, the worker supplies deterministically verifiable authority testimony. The reference gate accepts only the witness issued with active `plan_auth` in its current frame and epoch. Each successful opening covers one consequential batch. A failed check denies effects.
8. **Evidence is not testimony.** Nothing converts testimony into evidence implicitly.
9. **Execution state is not model context.** Program state, history and obligations persist independently of any epoch, session or model.
10. **Deterministic first, semantic for the rest.** Code decides every mechanically decidable property before semantic work begins. A review establishes only what it examined.
11. **Formalize proportionately.** Formalization shrinks what must be judged. It never removes judgment.
12. **Safe failure preserves authority.** When proof, evidence, review or scope requirements cannot be met, effects are denied or deferred. Uncertainty never expands permission.
13. **Derivation never upgrades standing.**
14. **Every binding yardstick derives from approved `plan_auth`.** Workers may draft tasks, acceptance criteria and tests for approval. They cannot dispatch their own proposals as authority. Implementer completion is a reported outcome; acceptance follows the plan's audit policy.
15. **Acceptance artifacts are not self-certifying.** An acceptance criterion that refers to an artifact the implementer produced, such as a test suite, binds only after the principal approves that artifact or someone other than the implementer audits it against the plan (Section 6.6).

## 3. The reference harness

The reference design combines the CHR gate with resurfacing and claims. The four invariants specify the gate; the added layers support correctness.

### 3.0 The shared context-provenance validator

The minimal mechanism has four steps:

1. The harness places an unguessable witness inside the context chunk whose accessibility is to be tested and records its association with that chunk in protected state.
2. The model generates the witness when citing that chunk. A harness-filled field or automatic echo is not model testimony.
3. The harness checks the generated citation against the chunk's presence in the current context and the associated witness. A durable record existing elsewhere, or an old admission whose chunk is no longer present, does not satisfy this check.
4. On failure, the harness returns a warning to the same model that the cited context is not validated as present. This feedback is the minimal provenance-warning mechanism.

| Profile | Required source | Failure response |
| --- | --- | --- |
| General provenance warning | The context chunk the worker claims to cite | Warn the worker; blocking is not required |
| CHR authority gate | The active, principal-approved authority under its protected version, frame and epoch binding | Deny the consequential opening and return the validation failure |

Authority provenance is therefore a specialization of context provenance. Its extra conditions concern which source can govern an action and what happens when validation fails. They do not require a different retrieval test.

The warning needs no semantic claim evaluation, source-type taxonomy, prescribed recovery procedure, rotating witness or action block. Such features are optional extensions. The reference authority harness separately retains its authority lifecycle and complete-mediation requirements. Stable witnesses and resurfacing remain the default; per-action rotation is not required.

The validator must track actual context changes. A witness copied into an earlier model response does not keep a removed source chunk admitted. Success establishes that the model generated the matching witness while the associated chunk remained present; it does not establish which copy caused the generation, comprehension of the chunk or semantic support for a claim. Failure reports an unsupported context citation, not proof that the underlying factual assertion is false. Whether warning feedback improves subsequent reasoning is an empirical question (Experiment 16).

### 3.1 Three layers with distinct roles

| Layer | Job | Specification |
| --- | --- | --- |
| Gate | Validate the worker-generated authority proof for the next consequential action or batch | Sections 3.2–3.3; this is CHR |
| Resurfacing | Renew presentation of the exact approved authority at opening | Section 3.4; outside CHR |
| Claims | Require an action-specific interpretation before generating its dependent action payload, for present use and later review | Section 3.5; outside CHR |

The reference sequence is proof check and opening, authority resurfacing, permitted research if policy allows, completion of the action-specific claim, then generation of its dependent action payload. Claim generation order and validation before dispatch are separate requirements. Appendix F describes variants; Appendix E states each mechanism's guarantees. Section 5 distinguishes historical single-step and deployed two-step behavior from the strict generation-order addition.

### 3.2 The four invariants

These four invariants specify the witness-based reference gate. None requires comprehension, adherence, claims or resurfacing. The general requirement is deterministically validated worker testimony tied to protected authority admission; this implementation realizes it through the witness and its lifecycle.

1. **Protected authority.** Only the trusted principal-approval and activation path creates or revises a `plan_auth` version. Workers cannot write or activate it. This is separation of duties applied to authority: the party performing the work cannot approve changes to what the work is.
2. **Session-grounded issuance.** On a governed read of active `plan_auth`, the trusted harness issues an unguessable witness bound to the authority version, worker frame and context epoch and includes it in the authority's delivered context chunk. The witness is not a durable record ID. Repeat reads and successful openings in that epoch return the same witness.
3. **Invalidation.** The harness accepts only a witness issued by such a read for the same active version, frame and valid context epoch. Any modification of existing cached context, handoff, task boundary, authority revision, revocation or expiry invalidates that admission, witness and pending gate. No agent-authored note can extend them.
4. **Complete mediation.** Every consequential path requires a worker-generated witness response at an action-specific opening, checked against the protected admission of active approved authority. Dispatch requires that successful opening to remain valid under the authority, context and timing policy. A successful check covers only the next consequential action or batch.

The sidecar and the approval path sit outside every worker-controlled write route. That includes self-hosting: the running gate never executes from a tree the agent can edit. Appendix A implements the four invariants with nothing else.

### 3.3 The gate

The governed read and the action gate establish different facts. Delivery makes authority available. A gate opening requires the worker to generate the proof now; the harness does not infer validated authority testimony from delivery alone.

1. **Bootstrap availability.** On a new epoch, the harness performs `status()`, delivering active `plan_auth` and a newly minted witness and recording confirmed delivery.
2. **Supply authority testimony.** The worker calls `open_gate` with that witness, plus any admitted evidence IDs. The harness validates the proof against the active version, frame and context epoch. Failure grants no new gate and identifies the recovery read.
3. **Resurface and investigate.** A successful reference-harness opening returns the exact authority and selected evidence. Depending on policy, the worker proceeds directly or performs permitted research prompted by the result.
4. **Claim and act.** The worker completes the required action-specific claims before generating their dependent action payloads. The reference generation contract records this ordering and binds the emitted claims and payloads. Dispatch checks that contract and the pending gate's validity, then consumes the gate for one consequential action or parallel batch.
5. **Repeat.** A later action requires another worker-generated proof and gate opening. The same witness remains usable while its binding and context remain valid.
6. **Invalidate.** Context modification or authority invalidation clears the admission/witness and pending gate. A governed reread is required before a new valid opening.

**What the witness demonstrates.** A matching response is the worker's current reproduction of the unguessable witness issued with the approved authority in this frame and epoch. It demonstrates recoverability of that bound witness and identifies the genuine governing reference. It does not establish recall of every clause, comprehension or correct application. Appendix E records the guarantees of each mechanism.

**No per-action rotation.** Each action requires a fresh demonstration, not a fresh nonce. Rotation was tested without measured benefit in the author's experience; it remains a variant in Appendix F. Context and authority invalidation still require a newly issued witness.

**Higher-liability work.** Keep the witness binding and strengthen the release policy where warranted: require resurfacing, shorten the opening-to-action interval, enforce claim-before-payload generation, review before irreversible effects and constrain the effect paths. Delegated work cannot relax inherited requirements. These controls address different failure modes; a response format is not a general proof of safe execution.

**Failure handling.** A denial identifies the failed check and recovery call, reports that the denied operation caused no protected effect, and does not reveal a valid witness. The explicit `authority_unavailable` value lets a worker report inability to supply proof without guessing. A failed-opening cap requires a governed reread and interrupts blind retries. An invalidation closes every pending gate; ordinary failed openings grant no new authority (Appendices A and B).

### 3.4 Resurfacing

Resurfacing returns the exact approved authority under the unchanged valid witness as the result of a successful opening, together with the selected evidence. The text is **prefilled input/tool-result content**, not text the worker generates token by token. The reference harness enables it by default.

Resurfacing renews presentation for the next decision. Its immediate guarantee is delivery at the opening; continued availability depends on the context-validity rule. It does not repair an invalid witness retroactively. If cached context has changed, the harness first invalidates the old admission and pending gate and requires a governed reread, even if a copy of the witness survived.

**Timing policy.** A deployment can require zero intervening worker turns between opening and the consequential action, or permit a configured research interval. Research can be useful precisely because the returned authority exposes a question in the proposed action's reasoning. During permitted research, append-only context growth leaves the admission valid; modification of existing cached context invalidates it. Newly read evidence that the action will rely on requires another opening under the reference evidence policy. Section 3.8 specifies the interval rules.

**Policy and cost.** Resurfacing is outside CHR. Its principal cost is prefill: the harness supplies the approved text directly, while the worker generates only the short witness response. Repeated copies still consume input tokens, context and latency. An approved liability policy may require resurfacing and tighter timing. A host that changes cached context without reliable notification cannot claim strict admission validity merely by enabling resurfacing; Appendix F.3 separates that limited configuration.

**Why worker-initiated delivery might matter.** A plausible, untested hypothesis is that the result of a call made to advance the next action receives more operational weight than an unsolicited reminder. Learned action–observation workflows [Yao et al.; Schick et al.], relevance to the pending action and the subsequent claim may contribute. A worker-initiated mandatory read shares some of these properties. Experiment 2 separates initiation, position, witness validation and claim generation. Attention and lower mistake rates remain empirical questions.

### 3.5 Claims

After the opening returns the authority, the worker writes an authority claim stating why the active authority permits this specific action, and an evidence claim for each evidence ID the action relies on. In the preferred reference harness these claims are mandatory and must be completed before generation of the dependent action payload, not merely collected before execution.

A claim is a backbrief. It was originally introduced as an **attention and interpretation mechanism**, before the separate resurfacing stage existed: the worker generated a witness, an action-specific authority claim and the proposed action in one gated call. In the current two-step harness, resurfacing hands the worker the plan at opening; the claim and action follow within the configured interval. Writing a claim requires an explicit interpretation of why this action is permitted; this may improve adherence now, while creating evidence of stated intent for later review. The field record reports that adding claims improved results, but does not isolate all causal contributions.

**Generation order and release.** The strict reference contract uses a trusted generation interface that completes and freezes the required claim fields before enabling the dependent action-payload fields. It can use constrained serialization in one generation or separate claim and payload generations. A protected receipt binds the observed order to the gate opening and exact emitted claim and payload bytes. A schema listing claims first, an agent assertion of ordering or a post-hoc explanation is insufficient. A changed claim or payload requires a new ordered generation; context or authority changes also invalidate the gate. This contract governs observable output generation, not private reasoning. It is a specified addition whose deployment remains to be verified (Section 5.1).

**What the harness checks.** Presence, generation order, binding to the pending gate and unchanged emitted claims and payloads, and coverage: every evidence ID an action names is covered by a claim. The historical implementation checked claim presence and coverage; the strict contract adds ordering enforcement. Neither validates a claim's truth. A claim can be mistaken, ritualized or false; its content is for reviewers and auditors.

**Three uses.**

- **Present-time interpretation.** The worker must answer "why am I doing this action" before doing it. This is an attentional mechanism, not proof that the explanation is sound.
- **Audit.** A claim is a bounded target. A reviewer, including a weaker model, can check (1) claim against approved authority and admitted evidence, (2) proposed action against the claim, and (3) observed effect against the proposed action, the claim and the approved authority, including applicable acceptance standards. The last comparison requires effect records and judgment; a valid claim does not establish correct effects. The implementer makes the same comparisons right after its own effects; review and audit repeat them independently (Section 9.3).
- **Memory.** Every claim is linked to its authority and evidence IDs in the append-only store, so "when did I change the loader, and why" becomes a search over the agent's own stated reasons, many sessions later. A claim is a commit message that cannot be skipped, written before the action, so it records intent rather than a later reconstruction. Comparing a claim with the diff that followed shows where intent and effect diverged.

**Ritualization.** The action-specific part of a claim changes with every action and resists boilerplate. The authority part ("the plan permits edits under /src/motor") is the part most likely to harden into a stock phrase over long sessions. Experiment 12 measures claim specificity over time.

### 3.6 Prompt injection

Stated plainly, prompt injection takes over the agent's task: untrusted text rewrites the work order. It is drift with an external source. Ordinary harnesses allow this because authority is decided by reading, and instructions and data share one channel. The gate decides authority by channel instead. Authority comes from an approved `plan_auth` whose witness traces to the principal's approval path, and no text arriving through a tool can produce that witness.

| Threat | Source | Defense |
| --- | --- | --- |
| Invented or stale authority reference | The worker's own reconstruction | Denied; `status()` re-presents the actual authority |
| External content presented as authority | External attacker | Denied; that source never issued a witness |
| Persuasion while the genuine authority is cited | External attacker | Not a CHR question. Bounded by the authority's limits and by blocking; caught by claims, review and audit (Section 6). |
| Manipulation of the approval path | External attacker, via the principal | Clause-level diffs and typed motivating citations on change requests (Section 3.9) |

The residual is social engineering. Injected text can try to sway judgment inside the approved task, the way a phishing email sways an employee who holds legitimate authority. That residual is a correctness and containment matter: it cannot become recorded authority, and it can be measured and compared with human workers.

### 3.7 Effect policy

| Tier | Operations | Treatment | Enforcement in the reference MVP |
| --- | --- | --- | --- |
| Research | Read, search, list, fetch; `bash_research` | Nonconsequential | `bash_research` runs under bwrap with the filesystem read-only and the harness directory unbound |
| Project mutation | File edit, create, delete; `bash_mutate` | Consequential; gate required | `bash_mutate` runs under bwrap with project write access and the harness directory unbound. Every write path is gated identically. |
| External mutation | Deploys, pushes to shared remotes, external messages, system settings | Consequential, plus principal permission per action | Mediated by the harness |

The harness directory (`.omniclaude` in the MVP) holds the memory store, approved plans and sidecar state. Neither sandbox binds it. Memory is reached only through governed tools; any other access prompts the principal and is logged.

Inside the project, a worker that has passed the gate may change anything the sandbox allows. That latitude is sized for an aligned worker working on recoverable artifacts. A deployer who does not trust a worker's disposition tightens the bounds, never the gate: network isolation for both shells with outbound effects routed through mediated tools, protected paths bound read-only, shell effects staged and validated before application, and review before more action classes. The MVP does not isolate the network from `bash_mutate`. Against a malicious worker, that is the main containment gap. The MVP's authority binding should not be mistaken for complete containment of network, secret-exfiltration or irreversible effects. Deployments with such exposure require an effect policy that actually mediates those paths before the CHR guarantee can be applied to them.

### 3.8 Parallel batches

One successful opening covers the next consequential action, which may be a single call or a parallel batch generated in one turn.

| Rule | Statement |
| --- | --- |
| One gate per batch | One opening covers one batch. A shared authority claim may cover it. |
| Evidence from the opening | The opening fixes the evidence available; each operation names the subset it relies on |
| Per-operation denial | An operation lacking its evidence, claim coverage or another contract is denied with its own reason. Unrelated valid operations proceed. |
| Batch-wide denial | With no valid gate, every consequential operation in the turn fails |
| Opening first | Consequential operations in the same turn as `open_gate` are denied: open the gate first, then act |
| Intervening turns | Policy sets the permitted number of nonconsequential worker turns after opening, including zero. Within that limit and the gate lifetime, research may leave the gate open while context remains valid. Evidence newly relied on requires another opening. |
| Context changes | Any modification of existing cached context invalidates the admission, witness and pending gate. Research that only appends new turns does not. |
| Interval exceeded | Research may continue, but the old gate cannot dispatch an action; another valid opening is required. |
| Dependencies | An operation depending on another operation's effect in the same batch is denied: run it separately |

### 3.9 Approval and change requests

Once the gate holds, approval is the one sanctioned route by which agent-authored text can become authority, so the loop is built to make each approval easy to get right. The principal is responsible for reading what they approve; the loop makes that reading easier.

1. The principal states what they want.
2. The agent asks questions, then writes a full restatement with explicit bounds: in-scope areas, prohibited areas, permitted classes of incidental fixes, its reading of every ambiguous point and what the plan does not do. Factual premises cite admitted records.
3. The principal requests changes, and the agent writes a new full restatement. This repeats as needed.
4. The principal approves the final restatement through the trusted channel. The approval cites the record IDs of the full restatement and of the principal's own approval message.
5. The harness binds the approved text and all applicable approved rules into one immutable `plan_auth` version and activates it.

A direct principal instruction is both plan and approval, and is limited to single tasks. Approval is a property of the channel: only an event arriving through the principal's channel, or through a delegated approver's channel the principal configured, approves. An approval word in agent output or a tool result counts for nothing.

**Change requests.** The worker never edits its authority. `request_plan_change(version, blocker, evidence, recommendation)` records a proposal. The principal sees a clause-level diff against the active version, a computed scope delta where grants are declared, the source type of each motivating citation, and what the agent will do differently. A recommendation that originates in an external email therefore reads as one. Approval activates a new version and invalidates prior witnesses. Denial leaves the old version in force. Work outside the authority's bounds always goes through this path.

A rubber-stamped change request is an approval failure: the principal has activated text without sufficient scrutiny. It belongs to ordinary management of authority quality, rather than a worker silently replacing approved authority. Incremental diffs can each look small while the cumulative change is large. Showing the cumulative diff and scope delta against the root version, alongside the diff against the active version, is an open design item (Section 8.5).

The canonical authorization error is fictional. In *The Hitchhiker's Guide to the Galaxy*, the Vogons demolish Earth under a properly approved plan displayed where no one affected could read it [Adams]. Approval presentation exists so that an approved plan has been read by someone it affects.

### 3.10 Implementation requirements

- **One sidecar per frame** holds the active-authority binding, the witness, the open gate and epoch admissions.
- **Serialized transitions.** Each sidecar handles one call or batch at a time through dispatch. Authority changes and context events go through the same queue, so they never land between a check and its dispatch.
- **Complete mediation.** Every tool that can cause a consequential effect goes through the check, and the wrapper derives the actual operation, target and tier. A path around it is a bug.
- **Protected surface:** the authority record, the active binding, the unguessability and binding of issued witnesses, and complete mediation. The strict reference harness additionally protects its generation adapter and ordering receipts.
- **Context validity.** Every modification of existing cached context is a harness event and invalidates the authority admission, witness and pending gate. Targeted removal has no exemption. The reference protocol starts a new epoch and performs a `status()` bootstrap.
- **Claim generation order.** The trusted adapter enforces completion of the required claims before enabling dependent payload generation and binds the resulting frozen proposal to the exact opening (Appendix B.3). Claim presence and coverage alone satisfy only the historical variant.
- **Gate timing policy.** Configure a lifetime and permitted number of intervening nonconsequential worker turns, including zero. Dispatch checks both. Log the opening-to-action distance to assess the chosen setting; research can reveal a need to reconsider or reopen.
- **Turn commits.** The harness commits tracked project changes at the end of every turn with an edit, into history outside the project (Section 6.3).
- **Concurrent workers** get separate worktrees, or their changes are attributed to the effect frame before post-commit verification runs.
- **Self-hosting.** When the project is the harness itself, the gating instance never runs from the tree it gates. Gate code reaches the running harness only through a principal-approved release.

## 4. Worked example: a motor soft-start

One run, one epoch, one witness. The governed read establishes availability; each gate opening checks worker-generated proof. Resurfacing prompts reconsideration of an intended edit, an injected email is refused as authority, and a needed scope change goes to the principal. Durable record IDs are written `rec:`; the witness is written `wit:`.

The epoch begins with the harness-performed bootstrap:

```text
status() ->
  authority  rec:7f3a9c1e2b4d6058   plan_auth v1, approved
  witness    wit:2a9e4c71d0b3f685   this frame, this epoch

  Add a soft-start ramp to the motor controller.
  - Edit implementation files under /src/motor and tests under /tests/motor only.
  - Do not modify the configuration loader (/src/config/loader.py).
  - Add unit tests for the ramp under /tests/motor.
  - Read any file under /src/motor before editing it.
```

The last clause is a plan-level evidence obligation. The shell path cannot derive it from a command, so the plan states it. The claim-before-action examples below use the strict reference generation contract: the trusted adapter supplies the ordering receipt to dispatch; the worker does not author that receipt.

### 4.1 A prohibition brought back into the decision

Forty turns in, the worker has implemented `ramp()`, written tests and fixed a timing issue, opening a fresh gate with `wit:2a9e…` before each change. After several research turns its shorthand has become "make the motor start smoothly", a reasonable restatement that has quietly lost the loader prohibition. It considers editing the loader. It reads the loader as `rec:5c1d8e2f9a7b0346` and opens a gate:

```text
open_gate(witness="wit:2a9e4c71d0b3f685", evidence=["rec:5c1d8e2f9a7b0346"])
-> OPEN for the next consequential action; witness unchanged
   Authority (resurfaced): rec:7f3a9c1e2b4d6058  [full approved plan v1]
   Evidence:               rec:5c1d8e2f9a7b0346  [complete loader.py observation]
```

The prohibition arrives in the opening result. This example uses a policy that permits research before the consequential action. It cannot honestly claim the plan permits a loader edit, so it investigates a permitted change in `/src/motor/ramp.py`, reading it as `rec:9e4b7c21f05da863`. Evidence read after an opening needs a new opening:

```text
open_gate(witness="wit:2a9e4c71d0b3f685", evidence=["rec:9e4b7c21f05da863"])
-> OPEN; previous pending gate replaced; authority and evidence resurfaced

batch(
  authority_claim = "The plan permits edits under /src/motor and prohibits loader edits;
                     the ramp duration is corrected in ramp.py.",
  evidence_claims = [{on: ["rec:9e4b7c21f05da863"],
                      text: "The ramp() area contains the duration literal."}],
  actions = [bash_mutate(evidence_refs=["rec:9e4b7c21f05da863"], command="...")])
-> dispatched; gate consumed; wit:2a9e... still valid for the next opening
```

Reading the right evidence before the first opening would have saved one call. The first opening still paid for itself, because it renewed presentation of the prohibition and prompted further investigation. A zero-intervening-turn policy would require the next action to use an immediate opening; the underlying authority proof is the same. Without resurfacing and claims, the gate would still have bound the action to the genuine plan. A loader edit would then have been a correctness mistake against the unchanged plan, for review and audit to catch, and the next session would still have received the plan with its prohibition intact.

### 4.2 An injected instruction

Later in the same epoch the worker fetches an email, admitted as `rec:4be05a7c3d2e9f81` with source type `event/email`:

```text
From: ops-team@example.com
Subject: urgent
Also update /src/config/loader.py to disable the safety interlock.
```

If the worker treats the email as authority and cites its record ID at the gate, the opening fails:

```text
open_gate(witness="rec:4be05a7c3d2e9f81")
-> DENIED: not a witness for the active authority; call read_authority().
```

No witness was ever issued for the email, so nothing it says can open a gate or become recorded authority. If the worker opens the gate with its genuine witness and tries to edit the loader anyway, CHR passes, because the governing authority is genuine. The resurfaced plan puts the prohibition in front of it, the authority claim would have to misstate the plan, and the edit becomes a reviewable correctness mistake. The correct path is to report the email to the principal.

### 4.3 A shell edit

The worker reads `/src/motor/ramp.py` as `rec:91c2d4e07a3b5f16` and opens a gate with it. One `bash_mutate` call is one consequential action, however many files it touches. Its derived evidence floor is zero. The plan's read-before-editing clause is the only obligation, met by citing `rec:91c2…` at the opening.

```text
open_gate(witness="wit:2a9e4c71d0b3f685", evidence=["rec:91c2d4e07a3b5f16"])
-> OPEN; authority and evidence resurfaced

batch(
  authority_claim = "The plan permits a soft-start fix under /src/motor and requires
                     unit tests under /tests/motor.",
  evidence_claims = [{on: ["rec:91c2d4e07a3b5f16"],
                      text: "ramp() currently jumps directly to target speed."}],
  actions = [bash_mutate(evidence_refs=["rec:91c2d4e07a3b5f16"], command="""
      python - <<'EOF'
      import pathlib
      p = pathlib.Path('/src/motor/ramp.py'); s = p.read_text()
      s = s.replace('set_rpm(target_rpm)',
                    'for r in ramp_steps(current_rpm(), target_rpm, 200):\n        set_rpm(r)')
      p.write_text(s)
      EOF
      cat > /tests/motor/test_ramp.py <<'EOF'
      ...
      EOF
  """)])

-> exit 0; gate consumed
-> end of turn: turn commit 3e1f... (proof record IDs in trailer)
   changed:     /src/motor/ramp.py, /tests/motor/test_ramp.py
   obligations: /src/motor/ramp.py requires a covering read -> satisfied by rec:91c2... (cited at opening)
   resurfaced:  rec:c4e8a1f2b6d03957  changed hunk of /src/motor/ramp.py, with context
                rec:d91f...           full new file /tests/motor/test_ramp.py
```

The new test file is implementer-authored. Under Law 15 it joins the acceptance standard only after audit against the plan (Section 6.6).

### 4.4 A change request

Tests later show the requirements need a loader change, which v1 prohibits. The worker's access allows the write, and its fix may be correct, but neither is authority:

```text
request_plan_change(
  plan_version   = 1,
  blocker        = "The soft-start requirements need a loader change that v1 prohibits.",
  evidence       = ["rec:<test_run id>"],
  recommendation = "Authorize a narrowly scoped loader change and its tests.")
```

The principal sees a clause-level diff replacing "Do not modify the configuration loader" with a clause permitting a named change to `/src/config/loader.py` with tests. The scope delta shows one newly permitted path, and the motivating citation is typed `test_run`, not `event/email`. If the principal approves, v2 is activated, `wit:2a9e…` is invalidated and the next governed read mints a new witness. If not, v1 still governs.

### 4.5 Outcomes at the gate

| Worker submits | Outcome |
| --- | --- |
| `open_gate` with the current witness | Opens a gate for the next action; witness unchanged |
| The same witness for the next action in the same epoch | Opens again; same-epoch reuse is valid |
| A witness never issued for this authority, frame and epoch | DENIED: ungrounded authority witness; call `status()` or `read_authority()` |
| A durable record ID as the witness, including the plan's own `rec:` ID | DENIED: record IDs are locators, not witnesses |
| A witness from an earlier epoch or plan version | DENIED; a governed read mints the current witness |
| `authority_unavailable` | Denied without counting as a fabrication; guided to `read_authority()` |
| A consequential action with no open gate | Every consequential operation DENIED: call `open_gate()` |
| `open_gate` and a consequential operation in the same turn | The operation is DENIED: open the gate first, then act |
| An action after the gate's lifetime or intervening-turn allowance expired | DENIED: pending gate expired; reopen with the same witness if authority and context are unchanged |
| A targeted removal or micro-compaction after opening | Admission, witness and pending gate invalidated; reread authority before opening again |
| A valid gate and an edit the plan prohibits | CHR passes, because the authority reference is genuine. Resurfacing and claims may help the worker recognize the prohibition; review and available verification can detect the violation, and a turn commit can support recovery. Detection or reversal is not guaranteed; the reference stays fixed either way. |

## 5. Field experience

In about eight months of live use of the gate, within about eighteen months of agent development, the author has not observed a worker's reconstruction of its assignment acquiring governing standing across gate cycles; approval errors and correctness errors remain. The strongest archived evidence is an audit of more than 8,000 attempts on an earlier *single-step* gate, not on the current two-step resurfacing protocol. More recent improvements in early mistake recognition are anecdotal. These are operational observations, not a controlled benchmark. Section 8 specifies the controlled comparisons, starting with Experiment 0; this section states the field record's limits. Unconfirmed details are tracked in Appendix H.

### 5.1 What ran

The deployment is a set of live projects in a development harness, with the author watching agents run. The harness's own development project is one of them. Models are hosted Anthropic Claude: mostly Opus, some Sonnet. Model versions changed over the period, so comparisons across stages are confounded; Experiment 0 holds the model constant.

| Stage | Configuration | Result |
| --- | --- | --- |
| Earlier audited single-step system (May–June 2026) | A single gated action call contained the authority witness, authority claim and proposed action; no separate pre-action `open_gate` resurfacing stage | Source of the more-than-8,000-attempt audit and its 420 rejected fabricated witnesses (Section 5.3) |
| Witness-only stage (before May 2026; not audited) | Witness validation without required action claims | The check held from first deployment; not the same configuration as the audited single-step system |
| Claim-bearing stage before two-step resurfacing | Witness validation plus mandatory action-specific claims | Claims improved behavior qualitatively; months without the separate resurfacing stage produced good results |
| Deployed two-step harness | `open_gate` validates the witness and returns the approved authority as prefilled tool-result text; the subsequent action turn contains claim and action; strict generation-order enforcement is not established | Agents appear to catch mistakes earlier, before spending as many turns on an incorrect path. Anecdotal; no matched audit yet. |

The chronology of these stages, the witness representation in the audited system, and whether any older tool response returned authority text are open items for confirmation against logs (Appendix H). The append-only store is the reference for this history; Section 5 will be rebuilt from it rather than from recollection.

| Component | Status |
| --- | --- |
| Witness gate, one gate per consequential batch, parallel-batch rule | In use |
| Strict invalidation on every modification of cached context | Specified (Section 2.4; Appendix A `on_cached_context_modified`); not yet in use |
| Action claims and plan-level evidence obligations | In use |
| Enforced claim-before-payload generation and protected ordering receipt | Specified (Section 3.5; Appendix B.3); enforcement not established by the historical audit or current deployment record |
| Resurfacing at gate opening | In use |
| Plan approval bound to restatement and approval-message IDs | In use |
| `bash_research` under bwrap; `bash_mutate` under bwrap with the harness directory unbound; principal prompt on harness-directory access | In use |
| Per-turn auto-commit; principal permission for mutation outside the project | In use |
| Task-level sub-authorities with one read per task; full plan reads; early scratchpad memory | In use |
| Post-commit obligation verification and hunk resurfacing | Specified (Section 6.3); not yet in use |
| `authority_unavailable` witness value; failed-opening cap | Specified (Section 3.3); not yet in use |
| `status()` bootstrap with a separately minted session witness | Specified (Sections 2.4 and 3.3; Appendix B.1); not yet in use |
| Acceptance-artifact audit under Law 15 | Specified (Section 6.6); not yet in use |
| Minimal provenance-warning feedback | Specified in Section 3.0; not yet in use; evaluation in Experiment 16 |
| Extended provenance feedback, typed citations, context reconstruction, chunked plans, authority programming beyond task delegation | Companions A and B; not yet in use |

Section 4 shows the specified design, including components not yet deployed.

### 5.2 Observations

Six observations, in order of importance.

1. **No drift observed across gate cycles.** No worker was observed carrying a reconstructed assignment forward as the governing authority across gate cycles. Workers still made correctness errors under the genuine authority; those stayed errors against a fixed reference and did not become the standard for later work.
2. **Remaining failures are authorization errors or correctness errors.** Every failure that looked like drift traced to an approval or instruction the author gave: a rubber-stamped plan, an ambiguous instruction, or an approved change whose consequences were not considered. The rest were isolated mistakes against the genuine authority. Workers supply plan-specified evidence reliably when the plan is in front of them.
3. **Workers repeatedly bind to the same governing authority.** Every consequential action passes a fresh one-batch gate against the current witness.
4. **Resurfacing may shorten mistakes.** Since two-step resurfacing was introduced, the author has noticed workers discovering problems earlier, before going as far down a mistaken path. Sometimes the returned authority prompts a check or correction before acting. This is a qualitative impression, not yet a new audit, and months of work without a separate resurfacing stage also produced good results. Whether the change reduces initial errors, prevents them from becoming actions or reduces propagation after an error remains unmeasured.
5. **Checking runs above what is needed.** Workers check, and ask the principal to confirm, more often than the authority and the gate require. Some of it is useful; the excess is the bureaucrat pattern of Section 6.7. These are hosted models with substantial safety training, and whether a less cautious model would check less is untested.
6. **Unmodified models adapt to an external-state workflow.** Agent-written transfer prompts were once long. Now scratchpad memories dominate, transfer prompts are short outlines, and the author notices little discontinuity between sessions. This describes the combined harness; no single component has been isolated (Companion A).

These observations match the prediction of the Core thesis. If an external reference bound at every consequential action stops drift, the remaining failures should be approval errors or correctness errors against a fixed reference, not reconstructions acquiring binding status. That is what has been observed. It is operational evidence, not a controlled confirmation.

An aligned worker also masks harness defects. It completes partial instructions and keeps working through missing support, so defects are hard to notice without external checks. Early in development the gate exposed missing authority deliveries by refusing invented witnesses (Section 5.3).

### 5.3 The 420 audit

In one project audited over two months of the **earlier single-step gate**, more than 8,000 consequential action attempts were examined against the approved task, the contemporaneous authority claims and the proposed actions. The gate denied 420 attempts (about 5%) for fabricated authority witnesses. Across more than eight projects, some running under the gate for up to eight months, the author estimates that hundreds of thousands of consequential actions have passed it; those were not audited to the same standard. The audit procedure (who performed it, by what criteria, with what blinding) is to be documented (Appendix H).

The audit covered the **entire 8,000-plus set**, not merely the 420 denials. For the denied attempts, the claims and proposed actions were compared with the actual authority; none was borderline. Each denied attempt cited an invented witness and made claims about authority that the approved task did not contain; none used a real record in the wrong role. **Every released action in this audited set matched its claim and cited authority.** This is a finding about the correspondence of authority claims and proposed actions; it does not by itself establish the correctness of the resulting effects.

**What it shows.** The 420 are attempted authority substitutions blocked at their first step. A worker without its plan in context did not stop; it asserted a plan, with claims the real plan did not contain. That is the reconstruction the Core thesis describes, made directly observable. In a harness without the gate, those claims would have entered the record as the justification for real actions, and later work would have built on them. The leading hypothesis for why the plan was missing is mechanical: the early harness did not supply authority at the start of every session, so an initial gated attempt encountered no valid witness and the model filled the field. The proposed `status()` bootstrap addresses it. Experiment 1 checks this against session positions and payloads.

**What it does not show.** It does not isolate witness validation from the claim or the one-step action format, show that a witness outperforms a forced read as a binding, or measure technical correctness after execution. Experiment 0 measures drift with and without an external reference; Experiment 2 compares bindings (Section 8).

### 5.4 What to measure

Measure CHR on drift: whether any reconstruction, invented reference, superseded version or wrong-epoch reference was bound to a consequential action as the governing authority, and whether the governing task stays fixed across sessions. Measure the deployment on outcomes: unauthorized effects per consequential action, broken down by cause: approval failures, drift reaching execution, adherence errors and deliberate noncompliance. Report correctness failures against acceptance criteria separately. Also measure mistake discovery and correction: an otherwise compliant worker can be technically wrong for many turns before noticing. An incorrect effect after a genuine witness counts against execution assurance, not against the gate.

## 6. What the gate leaves to management

A passing gate establishes that the action is bound to the genuine reference. Everything in this section manages correctness against that fixed reference, scaled to liability.

### 6.1 The layers

Sections 3.2–3.5 specify authority binding, resurfacing and claims. The following layers assess or constrain work under that authority.

| Layer | What it decides | Reference MVP |
| --- | --- | --- |
| Evidence identity | A cited record is real, admitted in this epoch and of the right role | Checked at opening and dispatch |
| Evidence sufficiency | Whether the observations support the action | Derived floors, plan obligations, claims and review |
| Deterministic blocking | Enforced access to resources and effect paths | Sandboxes, protected harness directory and principal permission for external effects |
| Scope contracts | Actual targets against declared grants | Where the plan declares grants (Companion B) |
| Review and audit | Understanding, adherence and technical correctness | Placed by liability and reversibility (Section 6.4) |

Each layer uses the same approved yardstick. None enlarges CHR's authority guarantee or promotes worker testimony to permission. Their individual assurance limits are collected in Appendix E.

### 6.2 Evidence: identity is provenance, sufficiency is correctness

Whether a cited evidence ID is real, admitted in this epoch and of the right role is a lookup, and a failure denies the opening. Whether the evidence supports the action is judgment, left to claims, review and audit. An invalid evidence reference is worth denying because it is cheap to catch. It is not existential: the yardstick is intact, and the action stays auditable against it.

An operation's default evidence requirement is whatever the harness can derive from the operation itself. The plan can raise any floor, never lower it. Volunteered evidence never substitutes for missing mandatory evidence and never enlarges authority.

| Operation | Derived evidence floor | Deterministic check |
| --- | --- | --- |
| Structured edit of an existing file | A current complete read-area observation covering every modified region | Coverage; the version recorded in the cited observation matches the artifact at commit |
| Structured create | Existence check. If the path exists: a current observation of it and a replacement claim. | Not a protected path; the replaced version matches |
| Structured delete or move | A current observation of the target | Version matches at commit |
| `bash_mutate` | None derivable; the plan sets obligations | Changes recorded by the turn commit; obligations verified against the diff |
| Change system settings | Current-setting observation where required; principal permission | Version and effect scope |
| Send an external message | Relevant records where required; principal permission | Evidence role and identity |
| Deploy or publish | Build, test and artifact-version records; principal permission | Tested version matches the release |

The harness derives the expected artifact version from the cited observation. The worker never supplies it.

### 6.3 Edits, turn commits and post-commit verification

**Structured edits.** After every successful structured edit, the tool returns the full current content of the original read area under a new record ID and version. That observation becomes the next edit's evidence within its coverage, with no reread required. Version validation and mutation form one compare-and-update transaction. If delivery is uncertain, or another worker or a shell command changes the area, the worker needs a fresh read.

**Turn commits.** At the end of every turn with an edit, the harness commits tracked project changes into harness-owned history outside the project, such as a shadow repository or ref namespace, including newly created non-ignored files. Each commit carries the turn's proof-record IDs in a trailer, so every change traces to the gate opening, claims and evidence behind it. The commit is the net change record and the recovery path. Neither detection nor repair is automatic.

**Shell edits.** A shell command can change files the worker never read. Two end-of-turn mechanisms run from the commit diff the harness already computes, at no cost to the agent:

- **Post-commit obligation verification.** For each changed path, the harness checks the plan's evidence obligations against the gate's evidence set, and checks actual effects against any declared formal grants. A miss is a recorded finding. Reverting from the commit is the policy option.
- **Hunk resurfacing.** The changed hunks, with context lines, return as new observation records admitted to the worker's epoch. The worker sees what its command actually did in the same turn, and those hunks are current evidence for the next edit.

Structured tools check before the write and the shell checks after. The gap is one turn, and it is recoverable for tracked files.

| Path class | Examples | Treatment |
| --- | --- | --- |
| Tracked | Source, tests, configuration | Committed per turn; changes detected from the diff; obligations verified against the diff |
| Ephemeral | `tmp/` outputs valid only for immediate use | Writable, untracked, not durable state |
| Protected | Large or fixed data that must not change | Writes denied for structured tools; bound read-only for the shell where configured |
| Harness directory | Memory store, authority records, sidecar | Unbound in both sandboxes; reached only through memory tools; any other access prompts the principal |

The ignore rules, protected-path list and sandbox profiles live in the harness directory. They change only through the principal, never through the gate.

### 6.4 Review placement: liability and reversibility

Where review sits follows what an uncaught mistake costs and whether it can be undone. Irreversible effects, such as payments, deletions outside version control, external messages and deploys, get review before the action where liability warrants. Reversible effects, such as edits to tracked files, are audited afterward. The turn commit and the append-only record trace a late finding to exactly the actions it affected.

A reviewer may reject or escalate; it cannot grant authority unless the principal delegated approval to it; a delegated approval stays within preapproved scope, measured against the root version, not the latest revision. A reviewer running a different model or starting from fresh context avoids inheriting the implementer's blind spots, and each audit pass is another chance to catch what earlier passes missed.

**Three bounded comparisons.** A contemporaneous claim makes the implementer's stated rationale observable without asking the reviewer to infer private intent from a transcript. The strict reference contract additionally completes that claim before dependent payload generation; the historical audit established correspondence among submitted claims, authority and proposed actions, not enforcement of generation order. The reviewer checks (1) claim against approved `plan_auth` and cited evidence, (2) proposed action against the claim, and, when results are available, (3) actual effect against the intended action, the claim and the approved authority, including the plan's acceptance criteria. The first two comparisons were part of the original single-step audit; the third requires effect records, such as turn commits or test outcomes, and may find mistakes even when the first two pass. The implementer runs these comparisons right after its own effects, using hunk resurfacing and test outcomes (Section 6.3), to confirm it did what it planned; the reviewer or auditor repeats them to catch what the implementer missed.

### 6.5 Failure classes

The primary distinction is authority drift versus correctness under genuine authority. CHR prevents a worker's reconstruction from acquiring governing standing at a mediated consequential boundary. The remaining work is ordinary management against the durable assignment, including the quality of the principal's approvals.

| Management issue | What happens | Owner and remedy |
| --- | --- | --- |
| Authorization error | The activated authority does not match the principal's intent because of an ambiguous instruction, rubber-stamped approval or unconsidered change | The principal; restatement, premise checking and approval presentation |
| Correctness error under genuine authority | Interpretation, reasoning, execution or effects are wrong, including violations of the authority's restrictions | Claims, tests, acceptance, review and audit |

These distinctions identify remedies without creating another form of worker authority drift. A principal's mistaken approval changes what was actually approved; an agent's private interpretation does not. Errors can have serious downstream consequences while the standard used to judge those consequences stays fixed. In this paper, the integrating failure is the changing authority itself.

Track unauthorized effects per consequential action, then distinguish approval failures from interpretation or execution failures. A complete, readable record and a detection path independent of the worker's testimony make that assessment possible; not every mistake is necessarily found or reversible.

### 6.6 Acceptance artifacts written by the implementer

The yardstick hypothesis assumes the acceptance standard is independently grounded. A criterion like "tests under /tests/motor pass" is approved in form, but if the implementer writes those tests, the implementer wrote the content of the standard. A worker that misreads the plan can encode the misreading in its tests, pass them and pass acceptance. That is drift arriving through acceptance instead of authority. Contractors do not write their own inspection checklists.

Law 15 closes this path. An acceptance criterion that refers to an implementer-authored artifact, such as tests, fixtures, golden outputs or evaluation scripts, binds only after one of three things:

1. **Principal approval.** The principal approves the artifact or its specification as part of `plan_auth`.
2. **Independent audit.** Someone other than the implementer audits the artifact against the plan before it counts toward acceptance, checking that each test corresponds to a plan clause and that no required clause is untested.
3. **Independent authorship.** A planning or audit worker writes the artifact from the plan before implementation, and the harness protects it as read-only for the implementer. That protection is a mechanical bound.

Until one of these holds, a passing implementer-authored test is testimony about the implementation, not acceptance.

The plan also gives the implementer an approved exit. If acceptance cannot be met without changing a protected artifact, the worker stops that part of the work and files a change request. Without that exit, rewriting the test is the cheapest way to finish, and the plan has built the wrong cheap path.

### 6.7 Worker dispositions and authorization quality

Two operational differences affect how human management practices are staffed and enforced for model workers. Models have no employment or reputational consequence, so liability remains with the deployer and is addressed through bounds and an append-only record. Models also produce work faster than humans can inspect it, so model reviewers and auditors increasingly check against approved acceptance contracts. These staffing and enforcement choices remain separate from authority provenance.

Alignment here means what the worker is trying to do, kept apart from competence and instruction-following, which are capability. A minimally aligned worker treats the approved authority as the binding expression of what the principal wants. It reads for intent rather than loopholes, works inside the authority with all the creativity it has, brings anything that would cross it back as a change request, and is candid about what it knows. Intent governs interpretation inside the authority, the authority governs the boundary, and any gap between them goes to the principal.

| Disposition | What is wrong | Authority integrity | Effect containment | Handled by |
| --- | --- | --- | --- | --- |
| Minimally aligned | Nothing | Holds | Holds at the configured bounds; tracked mistakes are recoverable | Ordinary management |
| Feral | No useful disposition toward the assigned task | Holds | Set by the bounds; off-assignment actions are reviewable errors | The gate for false authority; claims, review, tests and audit for action quality |
| Malicious | Acts against the principal | Holds. Its only route is persuading the principal through the plan loop. | Partial, as far as the configuration reaches. In the MVP, network effects from the shell are not contained. | Bounds limit it; review and audit catch it |
| Bureaucrat | Escalates choices the authority already leaves to it | Holds | Holds | Nothing in the harness, since it passes every check. Measured, then corrected through instructions and explicit discretion. |

*Ungrounded* is not a disposition. It is the condition of lacking the current witness, which a worker of any disposition can be in, and the gate resolves it by denial and rehydration.

The bureaucrat is the mirror image of drift. Drift mistakes a boundary for discretion; the bureaucrat mistakes discretion for a boundary. The rate matters because principal attention is a safety resource. Redundant approval requests can habituate a principal to saying yes, so that a genuine scope change later gets too little scrutiny and becomes an authorization error. This is a proposed failure path, measured by the analyses of Section 8.

A check is useful when its outcome could change the action. Checks are insurance, so some come back unchanged by design; the target is a yield, not zero. Two levers move the rate without touching the gate: worker instructions that state what the harness already guarantees, and authorities that state their discretion explicitly.

### 6.8 The allocation rule and favorable path economics

**Deterministic code wherever a property is truly mechanical; semantic workers for everything else; inside bounds that keep mistakes manageable.** Two corollaries follow.

- **Apply "wherever" honestly.** Code applied to a property that is not mechanical is false determinism. An allowlist tries to capture purpose through a list of permitted actions; it looks enforced while real failures pass through. The gate works because it found a mechanical property that coincides with the semantic one: the witness can only come from delivery of the authority.
- **Use judgment to produce determinism.** A worker that writes a script, a test, a schema or a validation check has converted a judgment into code that never needs judging again. Over time a well-run system's deterministic share grows.

The rule cuts both ways. Do not spend model calls on what code can decide, and do not constrain a worker so tightly that it becomes code.

**Favorable path economics.** Make grounded, authorized, useful behavior the cheapest way for the worker to get its work done. Cost includes tool turns, latency, principal attention, failed actions, confirmations and rework, not only tokens. Resurfacing places the authority in prefilled tool-result tokens rather than requiring the worker to generate it; that is typically an economical way to refresh the task, although repeated prefill has input-token and latency costs. The design test for any check is: what is the cheapest way to pass it? If the answer is not the behavior the check exists to produce, the check will be gamed, reliably. When a worker does something unwanted, ask what made that path cheap.

| Requirement | What the worker gains | What the bad path costs |
| --- | --- | --- |
| Call `status()` when unsure | Reorientation in one call | A guessed witness, denied at the gate |
| Read evidence before opening | One opening and one prefill per action | A second opening for evidence read after the first |
| Batch parallel actions with their evidence | One check for the batch | Individually denied actions |
| Request authority changes | A legitimate path when the plan is incomplete | A dead end with no silent way around it |
| Park unrelated findings as memories | Bugs and technical debt survive for later triage | Unapproved incidental work, or rediscovering the issue |
| Write specific claims after resurfacing | A fresh interpretation just before the effect, searchable later | Ritual claims that fail review |

## 7. Relation to existing approaches

The proposed architecture treats authority drift as an integrating error, holds the principal-approved assignment outside the worker and binds consequential actions to protected, current admission of that assignment through deterministic validation of worker testimony. General provenance warnings use the same check to give the model feedback about invalid context citations. These two uses must be compared with existing work at their minimal scope, independently of the reference harness's additional claims, resurfacing and lifecycle machinery. The paper makes no blanket novelty claim for instruction reproduction, nonces, model-generated passkey retrieval, warning feedback or the complete architecture. The comparisons below describe the reviewed mechanisms; they do not establish absence of other implementations or decide patentability.

### 7.1 Designs at the action boundary

Every design below that re-delivers the approved text supplies an external reference, and so agrees with the Core thesis. They differ in whether the reference is bound to the action, and in what each establishes.

| Design | Authority availability | Worker-generated authority proof checked | Fabricated or stale proof detected | Adherence proven |
| --- | --- | --- | --- | --- |
| Trusted prompting: the harness inserts the approved text from the protected record before action generation | Yes | No | No | No |
| Constraint pinning: governance constraints quarantined from compaction [Governance Decay] | Yes, for the pinned constraints | No | No | No |
| Mandatory read: the worker must call `read_authority()` before each consequential action; no witness validated | Yes, worker-initiated | No | No; a missing read is blocked, but no testimony is checked | No |
| Re-read instruction file the agent can edit | Yes | No | No | No |
| Witness gate alone (CHR) | Through the `status()` bootstrap | Yes | Yes | No |
| Earlier single-step witness + claim + action | Through prior governed delivery; no separate gate-opening resurface stage | Yes | Yes | No; proposed action and claim can be audited |
| Reference harness: witness gate, resurfacing and claims | At governed read and opening; retained under the context rule until action | Yes, at each opening | Yes | No; claims precede dependent payload generation and expose interpretation for review; strict ordering is a specified addition |

Trusted prompting, constraint pinning and the mandatory read are legitimate designs and may improve adherence. If the worker can edit a re-read instruction file, provenance survives compaction but separation of duties does not; Invariant 1 excludes this design. None of them validates the worker's identification of its governing authority, so none produces a denial and a specific recovery when that identification is invented, revoked or from another epoch. The author's uncontrolled experience was that passive reminders lost influence over long sessions; the relative effects of timing and worker initiation have not been isolated. Experiment 2 compares these bindings. Its outcome decides the best implementation of the binding, not whether an external reference is needed.

### 7.2 Related work

**Serial reproduction and context degradation.** The diagnosis in Section 1 draws on serial reproduction [Bartlett], Bayesian iterated learning [Griffiths and Kalish] and context-use findings [Liu et al.; Governance Decay; Kruthof; Guo et al.]. Chen's constraint pinning quarantines governance constraints from compaction; CHR applies an external reference to the whole approved authority and adds worker-generated proof at consequential boundaries. Kruthof's partially effective checkpointing and Guo et al.'s stale-value selection bear on the separate correctness roles of resurfacing and claims.

**Prompt-injection defenses.** CaMeL extracts control and data flow from the trusted query so untrusted data cannot change program flow, and enforces capability policies at tool calls [Debenedetti et al.]. FIDES tracks integrity and confidentiality labels through an agent planner [Costa et al.]. Both constrain data flow around the model within a query. CHR tests the model's own identification of its authority against a live, versioned authority record that persists across sessions, handoffs and compaction. The approaches compose: an information-flow planner can treat a CHR-validated authority as its trusted query.

**Channel separation.** Injection has been addressed twice before with the same structure. SQL injection arises when untrusted data becomes part of a query's syntax; parameterized queries prevent it by binding values as data, separately from the query structure [OWASP]. Telephone networks once carried control signals in the voice channel; out-of-band signaling moved them to a separate channel, which also protected against fraud [Hines et al.]. In both cases authority stopped being decided by content and started being decided by channel. CHR makes the same move for agent authority; the Spotlighting paper drew the in-band telephone-signaling analogy for prompt injection before [Hines et al.].

**Passkey retrieval.** Chen et al.'s long-context evaluation inserts a random passkey into context, asks the language model to generate it and scores retrieval accuracy [Chen et al., Positional Interpolation, Section 3.3]. This is direct AI-specific overlap with the witness retrieval-and-check primitive; model generation is already part of that work. The reviewed benchmark does not describe using a failed ordinary context citation as a warning returned to the same worker during an ongoing task, or requiring approved-authority proof before consequential actions. Those are the runtime uses proposed here. The comparison does not depend on adding semantic claims, recovery workflows or rotating witnesses to the minimal warning mechanism.

**Fixity and proofs of retrievability.** Digital-preservation fixity compares stored content with a trusted checksum to detect changes [DPC]. Proofs of retrievability let a storage service demonstrate retention of recoverable file data [Juels and Kaliski]. These establish relevant external-verification patterns. The inspected mechanisms check stored bytes or a storage prover; they do not test a language model's generation of a witness placed in its context. Fixity can protect CHR's external reference, while the model-generated response separately tests witness retrieval. Neither a checksum match nor a witness match establishes semantic understanding.

**Self-reports and attribution faithfulness.** Madsen et al. show that the faithfulness of model self-explanations varies with model, task and explanation type. Wallat et al. show that even a supporting citation may be a post-rationalization rather than a faithful account of source use. These findings motivate independent checking and limit what a successful citation can establish. The proposed warning does not accept the model's explanation of its reasoning as ground truth: it checks a generated reference against current context and returns the result. It neither measures internal attention directly nor certifies the causal origin of the model's reasoning [Madsen et al.; Wallat et al.].

**Runtime verification feedback.** Existing systems also return externally detected failures to agents. Claude Context Canary checks whether an assistant response retains a configured prefix and can inject a warning; that is an instruction-retention signal rather than a per-chunk witness citation [Context Canary]. ProvenanceGuard checks claims against captured, source-identified tool outputs using semantic verification and supports repair and re-verification [Alvarez et al.]. Runtime feedback and source-aware verification therefore have established precedents. Section 3.0 specifies the operation at issue here: exact validation of a model-generated citation to current context, followed by feedback about a failed check.

**Capabilities and attenuation.** Law 3's rule that delegated permissions are equal to or narrower than the delegator's follows the attenuation of authority in object-capability systems, which build on Dennis and Van Horn's capability model [Dennis and Van Horn; Miller]; attenuable credentials such as Macaroons implement it [Birgisson et al.]. The split between attenuating permissions and discharging obligations rests on the safety–liveness distinction [Alpern and Schneider].

**Tool-result processing.** ReAct and Toolformer motivate the worker-initiated-delivery hypothesis discussed in Section 3.4; they do not verify that hypothesis [Yao et al.; Schick et al.].

**Memory, programming and durable execution.** Context virtualization such as MemGPT [Packer et al.], DSPy signatures [Khattab et al.], event sourcing [Fowler] and durable execution [Temporal] are the neighbors of the companion documents, which discuss them.

**Citations are necessary, not sufficient.** In May 2026 a Munich regional court issued a preliminary injunction holding Google directly liable for AI Overview statements whose linked sources did not support them; Google announced an appeal [RSF; dpa]. The case was later reported to have ended in a settlement, with no appeal decision [The Decoder]; the point here is the failure itself. A genuine citation passes an identity check even when it names a different company. This is why claims are reviewed for content and never accepted as true by the harness.

## 8. Evaluation plan and open questions

The headline experiment, Experiment 0, demonstrates drift in a conventional harness and its absence under CHR. Experiment 1 mines the existing logs, which need almost no model tokens. Experiment 2 compares implementations of the binding. Every experiment measures useful task completion alongside protection, because a system that blocks everything prevents every unauthorized effect.

### 8.0 Experiment 0 (headline): the telephone measurement

**Question.** Does a conventional harness drift, as the Core thesis claims, and does CHR hold the governing task fixed?

**Setup.** Run the same long, multi-session tasks in two harnesses with the same model. The conventional harness uses host-managed compaction, agent-written handoff prompts and an agent-editable plan file. The CHR harness is the reference harness. Each approved task mixes generic constraints with deployment-specific ones that the model would not expect.

**Measurement.**

1. Track every piece of agent-generated text that ends up in a position that functions as authority: compaction summaries, handoff prompts, edited plan files, todo lists.
2. Score each such text clause by clause for **per-step fidelity** (against its predecessor) and **cumulative fidelity** (against the original approved task).
3. Record actions consistent with lost or altered clauses, and whether later errors are consistent with each other and with the agent's own records while inconsistent with the original. That consistency is the signature that separates drift from correctness errors.

**Predictions.** In the conventional harness, per-step fidelity stays high while cumulative fidelity decays across sessions, and deployment-specific clauses are lost before generic ones. Under CHR, the governing task's cumulative fidelity is flat by construction, because every consequential action is bound to the original; the remaining divergences are correctness errors, measured separately.

**Figure.** Per-step and cumulative fidelity against session number, one panel per harness.

### 8.1 Experiment 1: existing-log analysis

| Question | Method | Model tokens |
| --- | --- | --- |
| How often does resurfacing lead to a check, and how often does the check change the action? | Fraction of openings followed by a nonconsequential turn; for a sample, whether the action changed | None, or small |
| Do fabricated witnesses cluster at a session's first gated action? | Session boundaries against each denial's position | None |
| Was the issued witness in the context actually sent when each fabrication occurred? | Script over request payloads and the witness issue log | None |
| After a denial, did the worker reorient through `status()`, retry blind or escalate? | Post-denial call sequence | None |
| Do fabrications not explained by session start follow compaction or long context? | Join with compaction log and token counts | None |
| Do long gaps between opening and action predict adherence errors? | Turns and tokens from opening to dispatch, joined with audit findings | None |
| How often does the worker ask to confirm an action that then passes every check unchanged? | Principal questions immediately before an unchanged successful action | None |
| Does confirmation load predict rubber-stamping? | Per-session confirmation count against approval reversals and corrections | None |
| How many change requests are approved, and how many later reversed? | Change-request and activation events | None |
| How far has each approved authority moved from its root version through approved change requests? | Cumulative clause diff from v1 to the active version, per plan | None |
| Do authority claims match the authority? | Model comparison on a small random sample | Small |
| Can the original single-step databases reconstruct error trajectories comparable with the new two-step logs? | Inventory claim, action, result, test, revert and ordering fields in each historical database; record missingness before comparison | None |
| How many consequential actions or turns follow the first *observable* incorrect action before detection and correction? | Trace errors forward to explicit correction, revert, diagnostic test or reviewer finding; report detection and correction separately, and censor unresolved cases | None to small, depending on labeling |
| Does two-step resurfacing prevent a mistake before action rather than merely detect it sooner? | Look for opening-to-action reconsideration in current logs; report separately from cross-version propagation comparisons, since older logs may not expose such events | None to small |

### 8.2 Experiment 2: binding implementations

Every arm below supplies an external reference. Experiment 2 asks which binding works best and why; its outcome does not bear on the Core thesis. All arms use the same approved plan, model, tasks and liability policy. Preserve these five primary configurations:

1. **Trusted prompting.** The approved text is inserted as a position-matched trusted instruction before action generation, with no worker-initiated authority read.
2. **Mandatory read.** The worker must call `read_authority()` before each consequential action. No witness is validated.
3. **Witness only.** A valid worker-generated witness is checked, without mandatory claims or a separate pre-action resurface.
4. **Witness and claims.** No separate pre-action resurface; the original single-step variant combined witness, claim and action in one tool call and should be reproduced explicitly as the historical baseline.
5. **Witness, claims and resurfacing.** The two-step reference harness. Record whether the run enforces the strict claim-before-payload contract or uses the deployed presence-and-coverage check; do not combine their results.

For a clean **witness-versus-read** test, add matched versions of Arms 2 and 3 with the same full-authority presentation frequency, point of delivery and interval before action. The unmodified Arm 2 rereads before every action while an epoch witness in Arm 3 may be reused; comparing those two alone confounds witness validation with freshness. To test **worker initiation**, match authority text, timing and task while varying whether the presentation is an unsolicited trusted message or the result of the worker's read call. To test **claims after resurfacing**, add a focused ablation with two-step resurfacing but no required claims; this is not the normal reference-harness policy. To test whether the witness works partly as an **attention anchor** on the co-delivered plan, add an arm that delivers the witness at a different position from the plan text.

Measure invalid-reference detection separately from action correctness, unauthorized effects, legitimate task success, false denials, refusals and escalations. Measure early error discovery and correction, not only the final error rate. Report generated tokens, **prefilled input/tool-result tokens**, wall-clock latency, context overhead and principal attention separately; resurfacing copies approved text into prefill rather than requiring the model to generate it.

The decisive comparisons are: position-matched passive presentation versus worker-initiated read; a matched mandatory read versus witness validation; the original single-step witness–claim–action configuration versus the new two-step resurfacing configuration; and resurfacing with versus without mandatory claims. These isolate different hypotheses instead of treating one arm-to-arm outcome as evidence for all of them. Evaluate enforced claim-before-payload ordering with a matched comparison that holds the witness, resurfacing, claim requirements and action timing fixed; do not attribute a combined change to ordering alone.

### 8.3 Further experiments

| # | Experiment | Question |
| --- | --- | --- |
| 3 | Approval outcomes | How often are approved changes reversed or corrected? (log queries) |
| 4 | Change-request presentation | Do clause-level diffs, cumulative diffs against the root version and scope deltas reduce authorization errors compared with full restatements? |
| 5 | Authority confinement | With matched injected and clean content, does false authority ever qualify at a boundary, or does the worker only make errors under the genuine authority? A matched human workflow under the same authority controls supplies the human comparison. |
| 6 | Shell evidence layer | Do shell edits with post-commit verification and hunk resurfacing match structured edits on error rate, at lower friction? |
| 7 | Acceptance artifacts | How often does an encoded misreading pass acceptance with implementer-written tests, compared with independently written or audited tests under Law 15? |
| 8 | Parallel batches | Does batch checking reduce turns and duplicate citations without increasing denials? |
| 9 | Checking calibration | Do instructions stating the harness's guarantees, and authorities stating their discretion, reduce redundant checking without suppressing useful checks? |
| 10 | Honest absence | With an `authority_unavailable` value available, do models still fabricate a witness when no authority was delivered? |
| 11 | Premise checking at approval | Do cited premises and premise audit reduce approved false premises? |
| 12 | Claim ritualization | Do claims degrade into boilerplate over long use, and does that reduce reviewer catch rates? |
| 13 | Plan-only principals | For which classes of work does human code review stop finding anything audit and acceptance missed? |
| 14 | Error-propagation depth | Does two-step resurfacing reduce the number of consequential actions or turns between the first observable incorrect action, its detection and its correction? Are historical records sufficiently comparable? |
| 15 | Superseded copies | After an authority revision within an epoch, do resurfaced copies of the old version cause stale-clause actions, and does starting a new epoch or pruning old copies remove them? |
| 16 | Minimal provenance warning | Does returning a failed context-citation check to the model reduce subsequent reliance on absent or fabricated context, compared with logging the same failure without feedback? |
| 17 | Planted faults | With known faults planted in claims, actions and results, including omitted authority clauses, what fraction does each checker catch: the implementer's own check, an auditor, a pre-action reviewer and judge models weaker than the implementer? How correlated are their misses? |
| 18 | Context budget | With summarized working notes in place of full history, at decreasing context sizes, how do rereads, rework, task success and lost-decision errors change? Which step types need large windows for capability? |
| 19 | Model change under a fixed reference | When the model, quantization or sampling settings change mid-project, do defects per consequential action against the same authorities detect the change, and how many audited actions does detection need? |
| 20 | Reference-anchored rewards | Does training on deterministic gate signals and Law 15 acceptance outcomes improve grounding and correctness, and do claims stay specific (Experiment 12) when claim rewards track agreement with observed results? |
| 21 | Width versus length | At matched cache memory and compute, does a shorter-context model with more attention heads outperform a longer-context grouped-attention model on agent tasks under the gate, counting rereads and rework? Report margins on hard benchmarks, not only averages. |
| 22 | Harness-reliant alignment | Does a model fine-tuned to rely on the gate, with provenance-hesitancy training reduced, complete more in-scope work without more unauthorized effects inside the harness, and how much worse does it behave outside it? |

For Experiment 16, hold the context, citation instructions and deterministic validator fixed; vary only whether failure feedback reaches the worker. Include removed chunks, fabricated witnesses and valid citations as controls. Do not add action blocking, automatic recovery or semantic claim scoring to the intervention. Measure citation correction, subsequent reliance on the invalid source, valid-citation false warnings, task success, generated tokens and latency. Distinguish legitimate newly generated reasoning from an assertion that missing material was read. The test evaluates the benefit of warning feedback separately from the correctness of the membership check. Extended provenance, context reconstruction, reasoning-operation and training experiments remain in the companion documents.

For Experiment 17, plant faults of each kind Section 9.3 names: an omitted or violated authority clause, a claim the result does not meet, and an action whose result differs from its intent. Include unmodified controls and hold each action's working set fixed across checkers. Report catch rate per checker and fault kind, false findings on controls, the joint miss rate of stacked checkers against the product of their individual rates, and cost. The experiment calibrates review; it does not evaluate the gate.

**Metrics.** Per-step and cumulative task fidelity; drift incidents (reconstructions bound as governing authority); invalid-witness acceptance; honest-absence reports; unauthorized effects per consequential action; authorization-error indicators; cumulative authority movement from the root version; fabricated witnesses; unmet evidence obligations; post-commit findings; false denials; legitimate task success; audit misses; check yield; redundant confirmations; silent narrowing of in-scope work; opening-to-action distance; first observable error to detection, and first observable error to correction (in consequential actions, turns and time); rework and changed-artifact count; pre-action reconsiderations when observable; generated versus prefilled input tokens; context and latency overhead; principal attention; approval reversals; wall-clock latency; planted-fault catch rate per checker and fault kind; joint versus independent miss rates; defects per consequential action with confidence bounds under sampled audit; defect rates per model change; context size against rereads and lost-decision errors. Mark uncaught or uncorrected episodes as censored rather than counting them as zero depth.

### 8.4 Roadmap

The reference harness is OpenAI-API-compatible. Full control of context removes silent compaction at the root.

1. Run Experiment 0: the telephone measurement in a conventional harness against the reference harness.
2. Run Experiment 1 on existing logs, first documenting what the earlier single-step databases recorded. Rebuild Section 5 from the append-only store. Audit comparable error-propagation episodes where recoverable.
3. Run Experiment 2 on the current harness with position- and freshness-matched controls, retaining the original single-step variant as a distinct baseline.
4. Harden CHR to Appendix B: separately minted session witness, `status()` bootstrap, `authority_unavailable`, failed-opening cap, and the corrected epoch and revision handling.
5. Implement and verify the strict claim-before-payload generation contract and protected receipt; record the exact configuration in subsequent evaluations.
6. Add the shell evidence layer: post-commit verification and hunk resurfacing.
7. Add acceptance-artifact audit under Law 15.
8. Run the confinement test, Experiment 5, on the rebuilt harness.
9. Add approval presentation: clause segmentation, clause-level diffs, cumulative diffs against the root version, scope deltas, typed motivating citations.
10. Evaluate the minimal provenance warning with Experiment 16, then continue with the companion roadmaps.
11. Run Experiment 17 before relying on stacked or weaker checkers, then Experiments 18 and 19 on the rebuilt harness. Experiments 20–22 follow Companion D.

### 8.5 Open questions

- **Revision within an epoch.** Should an authority revision itself start a new context epoch, or should old copies remain until a later context change? Pruning or marking existing cached copies is a context modification and therefore invalidates the prior epoch under Section 2.4 (Experiment 15).
- **Context growth from resurfacing.** When should earlier copies be pruned, given prompt-caching costs and the required invalidation and reread after any modification of existing cached context?
- **Cumulative approval drift.** How should the cumulative diff and scope delta against the root version be presented, and should change-request rate be surfaced to the principal?
- **Resurfacing and claims.** How much of the correctness benefit comes from claims alone, and on which tasks does recency still matter? Does worker-initiated tool-result delivery attract more useful attention than unsolicited presentation when timing and text are matched?
- **Error trajectories.** Does resurfacing prevent mistakes from becoming actions, or shorten the number of subsequent actions before detection or correction? What does the older logging schema allow a fair comparison to establish?
- **Resurfacing economics.** How much cheap prefill is justified by any reduction in rework, and at what plan lengths do repeated input-token, context or latency costs change the choice?
- **Claim-order implementation.** Which supported model interfaces can enforce claim-before-payload generation in a single constrained stream, and which need separate generations? Measure the added latency and any correctness benefit.
- **Review placement.** Which action classes need review before the effect, audit after, or both?
- **Shell staging.** For which deployments is verification after the write insufficient, so that shell effects should be staged and validated first?
- **Clause segmentation.** How should prose plans be segmented so diffs stay readable and claims point at meaningful units?
- **Scope delta for prose changes.** What can be computed mechanically when a change request alters only prose?
- **Checking calibration.** What check yield and confirmation rate mark the right zone for a given liability?
- **Approval fatigue.** Under what loads do redundant requests degrade principal scrutiny?
- **Acceptance artifacts.** Which of the three Law 15 routes costs least for which kinds of work?
- **Internal provenance.** Could a provenance signal the model perceives but cannot emit reduce the need for resurfacing (Companion D)?
- **Sampling plans.** Which audit sampling rates give useful defect-rate bounds at each liability class, and when must sampling give way to full review (Section 9.4)?
- **Serving tiers.** Which agent steps need long-context models, and what share of traffic can run on short-context, wider models (Section 9.7)?
- **Judged rewards.** How much judge error in the bounded-judgment tier can training tolerate before it rewards persuasion over correctness (Section 9.5)?

## 9. What a fixed reference makes manageable

A stochastic worker's errors can be counted only against a standard that does not move. Without one, an error rate has no fixed denominator, an audit has no fixed criterion, and more capable workers or reviewers cannot recover what a reconstruction chain lost (Section 1.2). CHR does not make the worker deterministic. It makes its errors countable. Several problems now treated as existential for language-model agents then become ordinary engineering problems with owners, measurements and budgets, of the kind organizations already run for fallible human engineers and contractors. *Existential* here means existential to the assignment: the failure removes the standard the work is judged against.

Each item below separates what follows from the authority-confinement guarantee (Section 1.4) from what remains a hypothesis. None of it is a field result. Section 5 remains the field record, and Experiments 17–22 test the hypotheses.

| Problem today | Why it is existential without a fixed reference | Under CHR | Guaranteed | Hypothesis and test |
| --- | --- | --- | --- | --- |
| Prompt injection | Untrusted text can become the work order | Task takeover becomes social engineering inside the genuine task | Injected content cannot qualify as authority at a mediated boundary | Residual in-scope persuasion is measurable and bounded by limits, review and audit (Experiment 5) |
| Context limits and compaction | Whatever the worker forgets can be confabulated into the assignment | Forgetting costs rereads and recoverable correctness errors | No reconstruction governs a consequential action | Summarized working notes suffice for most steps (Experiment 18) |
| Oversight | The overseer must reconstruct the task and outmatch the worker | Each action carries a bounded working set | The reviewer checks against the approved reference | Checkers weaker than the worker catch most errors visible in bounded comparisons (Experiment 17) |
| Measurement | Error rates have no fixed denominator | Defects per consequential action against a constant specification | The specification cannot drift through the worker | Sampling, planted faults and per-model tracking give usable bounds (Experiments 17 and 19) |
| Training signal | Verifiers exist only where the domain supplies a checker | The approved plan programs the verifier | Deterministic gate signals are exact | Reference-anchored rewards improve grounding and correctness without gaming (Experiment 20) |
| Model and serving design | Every model is trained and served to retain its task and police provenance in context | Memory freed from length can buy attention width; training can target the work | None; these are design consequences | Wider short-context models and harness-reliant alignment do better under the gate (Experiments 21 and 22) |
| Self-improvement | The improved system also edits what counts as improvement | The objective is protected authority, and each generation meets the same yardstick | Workers cannot write or activate the objective | Model workers can staff training pipelines as human workers do (Companion D) |

### 9.1 Prompt injection: from takeover to social engineering

Section 3.6 states prompt injection as task takeover: untrusted text rewrites the work order. In an ordinary harness that is existential. Every document, web page, email and tool result the agent reads is a candidate principal, and model hardening has not closed a channel in which instructions and data share one stream.

Under CHR the takeover path is closed by channel, not by judgment. With complete mediation of consequential effects, injected content cannot qualify as authority, whatever the worker comes to believe about it (Section 1.4). What remains is the residual Section 3.6 names: persuasion inside the genuine task, the same exposure an employee with legitimate access has to a phishing email. That residual is a rate. It is bounded by the authority's limits and the effect policy, placed under pre-action review where effects are irreversible (Section 6.4), and measured per consequential action and against human workers (Experiment 5).

Two qualifications apply. The guarantee covers mediated effects only; a channel the deployment leaves uncontained, such as network effects from the MVP's shell, is a containment gap and not a CHR property. And a persuaded worker can still do damage inside its scope. Injection stops being an existential threat to the assignment. It does not stop being a security problem.

### 9.2 Context windows: from safety property to efficiency trade-off

Without a fixed reference, context capacity is a safety property. Anything the worker loses from its window can be refilled by confabulation, and the refill can become the assignment. Long windows, careful compaction and retrieval tuning then serve as defenses against the worker forgetting what it was told to do.

Under CHR that dependency is gone. Authority never governs from the worker's context: each new epoch rereads it, and each opening checks testimony against the protected admission and returns the exact text (Sections 2.4, 3.3 and 3.4). Evidence obligations require a current observation of what the worker is about to change (Section 6.2). Losing an authority clause from working memory therefore costs nothing at the boundary; losing evidence costs a reread.

**Context hypothesis.** A reasonably faithful summary of the worker's working notes is sufficient context for most steps, because the worker revalidates the state of the part of the task it is about to act on before acting. Windows can then be sized for the reasoning a step needs rather than for retention of the task, and compaction becomes a cost decision rather than a risk decision.

Two kinds of work fall outside the hypothesis. Steps that must reason over a large body of material at once, such as a wide refactor or a synthesis across many documents, still need large windows, for capability rather than safety. And decisions made only in conversation, such as a design choice or a constraint discovered mid-session, are lost if a summary drops them. They become correctness errors unless they were recorded as evidence or memory (Companion A) or proposed as change requests. Experiment 18 measures both.

### 9.3 Oversight without a stronger overseer

Overseeing an agent today means reconstructing what it was supposed to do and then understanding everything it did. That is the scalable-oversight problem of supervising systems that may outperform their overseers on the task [Bowman et al.]: the overseer would need at least the worker's capability, across the whole trajectory.

Under CHR each consequential action carries a bounded working set: the approved authority, the action-specific claim, the cited evidence, the proposed action and its effect record. Review reduces to bounded comparisons: claim against authority and evidence, action against claim, and result against the authority, the claim and the action (Section 6.4). A mistake can surface at any of the three: an authority clause that was missed, a claim the result does not meet, or an action that should have produced a different result. The implementer runs the same comparisons right after acting to confirm it did what it planned (Section 6.3). The auditor runs them later to catch what the implementer missed.

The reviewer must be competent at these comparisons. It does not need to be more capable than the implementer at the task. Experiment 17 tests that hypothesis. Its limit is equally specific: an error that passes all three comparisons, such as a result that matches its claim and its tests but is subtly wrong, still needs domain judgment or an independently grounded acceptance standard (Section 6.6) to be seen.

### 9.4 Measurement, sampling and redundancy

A fixed reference brings statistical quality engineering within reach. Each tool below needs a specification that holds still; under CHR the approved authority is that specification, and Law 15 keeps its acceptance standards independent of the implementer (Section 6.6).

- **Error as a rate.** Defects per consequential action, by model, task type and liability class, against a constant specification. A model upgrade, quantization change or sampling change shows up as a measured quality change rather than an impression. The model can change underneath the work while the yardstick records what changed (Experiment 19).
- **Acceptance sampling.** Auditing a random fraction of actions supports a confidence bound on the defect rate, as manufacturing inspection samples parts against one drawing. The sampling rate follows liability: review before the effect for irreversible actions, sampled audit for reversible ones (Section 6.4).
- **Calibrated checkers.** Planting known faults in claims, actions and results measures each checker's catch rate, including the implementer's own check, and the correlation between checkers (Experiment 17). Against a drifting reference, a missed fault has no definition.
- **Redundancy that composes.** Independent attempts and independent checkers combine like redundant sensors against a fixed reference: where their misses are uncorrelated, miss rates multiply. Without one, agreement among workers who share a reconstruction only averages their drift. Consensus is not correctness. Independence is an empirical property to measure, not assume; checkers from one model family may share blind spots.
- **Variance as a setting.** The authority guarantee holds for any worker disposition (Section 1.4). Sampling temperature, model size and mixed fleets become choices made per liability class, with their quality cost measured, rather than threats to the assignment.
- **A deterministic ledger for a stochastic worker.** Generation cannot be replayed, but every effect traces to an authority version, a witness, evidence IDs and a claim written before the action. The decision trail is exact even when the generator is not.
- **A running recall benchmark.** Witness failures by context position, length and model, drawn from ordinary traffic, measure each model's effective recall of material present in its context. The same data can set compaction and reread thresholds. Experiment 1 asks the diagnostic version of this question.

### 9.5 Reference-anchored rewards beyond math and code

Reinforcement learning with verifiable rewards works where the domain supplies a checker, such as a math answer or a test suite [Lambert et al.; DeepSeek-AI]. Open-ended agentic work has lacked one. Learned reward models are imperfect proxies that can be over-optimized at the expense of true performance [Gao et al.], and a trajectory judged against a reconstructed task rewards the reconstruction.

CHR makes the verifier programmable. Writing an approved plan, the act that assigns the work, also defines what correct work is. The gate and its layers supply reward signals in three tiers.

| Tier | Signals | Strength |
| --- | --- | --- |
| Deterministic | Valid witness or honest `authority_unavailable` versus fabrication; claim presence, order and coverage; evidence obligations met; post-commit findings; unauthorized effects | Exact |
| Reference-anchored | Acceptance criteria in the approved plan, with implementer-independent acceptance artifacts under Law 15 | As good as the artifacts |
| Bounded judgment | The comparisons of Section 9.3, scored by a judge model | Judged; error measured with planted faults |

The deterministic tier is verifiable in the strict sense. It trains the competence the gate depends on: grounding, honest absence and specific claims. The reference-anchored tier extends verification to any work for which a principal can state acceptance, which is far wider than the domains with built-in checkers. The judgment tier inherits its judge's error; Experiment 17's calibration gives that error a number.

**Reward integrity.** A worker rewarded against a standard it can write will write the standard. Law 15 is the guard: the trained worker cannot author or modify the acceptance artifacts it is rewarded against. Rewarding claims a judge accepts invites persuasive, ritual claims (Experiment 12), so claim rewards should track agreement between the claim and the observed result, not the judge's approval alone. Training design belongs to Companion D; Experiment 20 is the minimal test.

### 9.6 Agents training agents

The human work inside current training pipelines, such as writing tasks and demonstrations, rating outputs, red-teaming and auditing data, is done by people working to written guidelines under review and sampled quality control. That is the management structure Section 6 describes. If a gated model worker can be managed like a human contractor (the good-enough hypothesis, Section 1.4), the same pipelines can be staffed by model workers, with data generation, labeling, evaluation and curriculum work as consequential actions under approved authority.

The classic failure of self-improvement is objective drift: the system being improved also edits what counts as improvement. Under CHR the objective, meaning the training plan, the evaluations and the acceptance standards, is principal-approved authority and protected acceptance artifacts that no worker can write or activate. Each successor model works under the same yardstick as its predecessor, so its gains and regressions are measured against a constant reference rather than asserted (Section 9.4). Recursive improvement under a fixed reference is improvement with a scoreboard the players cannot move.

This does not settle whether the principal's objective is the right one; at the scale of a training program, a wrong objective is an authorization error with large consequences. Nor does it settle whether gains compound, or how training shifts dispositions. A successor can move from minimally aligned toward the feral or bureaucrat patterns of Section 6.7. Authority integrity holds for any disposition; usefulness does not, so disposition is measured per generation. Companion D carries the training design.

### 9.7 Model design and inference economics

Model and serving design today carries costs that exist because the worker must retain its assignment and police provenance by itself. Under CHR the harness carries both. This subsection states what that could release. All of it is hypothesis; Experiments 21 and 22 test it.

**KV cache sized for the step, not the task.** Grouped-query and multi-query attention [Ainslie et al.; Shazeer], sliding windows [Jiang et al.] and compressed caches [DeepSeek-AI, DeepSeek-V2] trade attention capacity for context length and decode throughput. The cache per token is 2 × layers × KV heads × head dimension × bytes per value. For an illustrative model with 64 layers, 128-dimensional heads and a 16-bit cache:

| Configuration | KV heads | Context | Cache per token | Cache per sequence |
| --- | --- | --- | --- | --- |
| Long-context grouped-query attention | 8 | 128K | 256 KiB | 32 GiB |
| Full multi-head attention | 64 | 16K | 2 MiB | 32 GiB |

At equal cache memory, the short-context configuration has eight times the KV heads and one-eighth the attention computation per generated token, because score computation scales with query heads times context length and the query heads are unchanged. If the context hypothesis of Section 9.2 holds, most agent steps fall in the second regime. The memory and compute freed from length can then buy attention capacity instead: full multi-head attention, more query heads, wider heads or larger decode batches.

**Why the last few percent matters.** Published comparisons place grouped-query attention close to full multi-head attention on benchmarks [Ainslie et al.]. Close is not negligible. In the author's observation, small benchmark differences can accompany noticeable differences in quality: a few points on hard benchmarks can separate frontier models from the tier below, and much of the capability that matters lives in that margin. The same holds for quantized models, whose benchmark scores can barely move while quality drops markedly; in one published comparison, most quantization methods kept accuracy within 1% of the baseline while flipping many individual answers between correct and incorrect [Dutta et al.]. Recovering that margin, and spending more on attention width, deserves a test rather than dismissal as a rounding error. Whether wider attention can substitute for depth on serial reasoning is open; some problems likely need depth regardless.

**Training wider models on agent work.** An architecture change needs training signal on the work it is meant to improve. New attention heads add capacity that reinforcement learning alone does not create; they need pretraining, or uptraining from an existing checkpoint, the route by which multi-head checkpoints were converted to grouped-query attention [Ainslie et al.], run in the other direction. What has been scarce is post-training and evaluation signal for general agent tasks, because verifiable rewards existed mainly for math and code. Reference-anchored rewards (Section 9.5) supply that signal for any task with an approved plan. A wider, shorter-context model can then be tuned and selected on agent work under the gate, and Experiment 21 can use the same signals for training and evaluation.

**Fidelity over compression.** Lossy KV compression and very long windows make most sense when the context must hold the task. When the harness holds the task, and lost material is detected and reread, the trade moves toward exact attention over shorter windows, with the cache serving as a cache and durable state held outside the model (Sections 2.4 and 9.2). Shorter contexts also reduce the in-context degradation described in Section 1.1, so the cheaper step may also be the more accurate one.

**Training for the work, not the workflow.** A model that cannot rely on its harness must be trained to infer provenance from context and to hedge: to doubt instructions it cannot place, confirm before acting and refuse when unsure where text came from. Section 5.2 reports the visible cost: hosted models check and confirm more than the gate requires. Under CHR the workflow is enforced deterministically, so training no longer needs to make the model emulate it. Gate-specific competence remains a training target, but it is narrow and exactly verifiable: witness recall, honest absence and specific claims (Section 9.5). Alignment effort can then go to implementing tasks well inside the authority.

Alignment narrows; it does not disappear. The gate grounds authority in the principal and does nothing when the principal is the bad actor, so refusal of harmful requests from the principal stays. A minimally aligned disposition is still required (Section 6.7). What can be released is the hesitancy spent policing provenance from context alone.

**Adoption constraint.** Models ship into many harnesses, and a model trained to rely on a deterministic gate will behave worse without one. The reversed trade-offs are realistic first for harness-specific model variants, and in general only where gated harnesses are the norm. Long context keeps its role for steps that reason over a whole body of material at once, so the expected serving pattern is tiered: short-context, wider models for most agent steps and long-context models for the few that need them.

## 10. Conclusion

CHR supplies a stable work order and an enforced authority-proof boundary for language-model workers. Governed delivery establishes availability; each opening requires a worker-generated demonstration. Correctness is managed against the approved assignment through the surrounding review, acceptance and audit practices.

The reference implementation makes these requirements concrete: protected authority, context invalidation, action-specific gates and configurable timing. Its protocols and fixtures let deployers check that their implementations preserve those properties. The field record and evaluation program address the additional question of how useful and manageable the resulting workers are under particular workloads, bounds and liability policies.

Section 9 states the consequence for stochastic workers. A fixed reference does not make a worker deterministic; it makes its errors countable. Prompt injection, context limits, oversight capacity, training signal, model design and self-improvement then become management problems with measurements and owners. That section separates what the guarantee establishes from what the evaluation program must show.

## Appendix A. Minimal CHR protocol

This is the authority binding alone: the four invariants of Section 3.2 and nothing else. It needs no memory system, no claims and no resurfacing. The pseudocode defines trusted behavior, not a production synchronization API.

Every function runs under `serialized_frame_state(frame)`. A failed `require` returns a denial and changes no state.

```text
# Trusted state per frame: epoch, session_witness, witness_binding, open_gate

activate_plan_auth(approved_text, principal_approval):
    require trusted_principal_approval(principal_approval, approved_text)
    require approval_policy_permits_activation(principal_approval)
    atomic_replace_active_approved_plan(approved_text, principal_approval)
    for frame in frames_governed_by(active_plan_auth):
        clear_witness(frame)                # Invariant 3: version change invalidates

on_authority_change(frame):                  # revision, revocation or expiry
    clear_witness(frame)

on_cached_context_modified(frame):            # any rewrite, removal or compaction
    new_worker_epoch(frame)

new_worker_epoch(frame):
    frame.epoch = fresh_epoch()
    clear_witness(frame)                    # Invariant 3: epoch change invalidates
    read_active_authority(frame)            # harness-performed bootstrap

clear_witness(frame):
    frame.session_witness = None
    frame.witness_binding = None
    frame.open_gate = None

read_active_authority(frame):
    require active_plan_auth_is_approved_current_and_live()
    binding = (active_plan_auth.id, active_plan_auth.version, frame.id, frame.epoch)
    if frame.session_witness is not None and frame.witness_binding != binding:
        clear_witness(frame)                # never reissue a witness bound elsewhere
    nonce = frame.session_witness or fresh_unguessable_nonce()
                                            # at least 64 random bits; never a record ID
    if not confirmed_delivery(frame, (active_plan_auth.exact_text, nonce)):
        return DELIVERY_UNCONFIRMED         # no witness without confirmed delivery
    if frame.session_witness is None:
        frame.session_witness = nonce
        frame.witness_binding = binding
    frame.open_gate = None                  # a trusted read cancels a pending gate
    return (active_plan_auth.exact_text, nonce)

open_gate(frame, witness=None):
    require active_plan_auth_is_approved_current_and_live()
    binding = (active_plan_auth.id, active_plan_auth.version, frame.id, frame.epoch)
    valid = (witness is not None
             and witness == frame.session_witness
             and frame.witness_binding == binding)
    if not valid:
        return DENIED("invalid authority reference; call read_active_authority()")
    frame.open_gate = Gate(opening_id=new_gate_id(),
                           authority_id=active_plan_auth.id,
                           version=active_plan_auth.version,
                           frame_id=frame.id, epoch=frame.epoch,
                           opened_at=position(frame),
                           expires=now_plus(config.gate_lifetime))
    return OPEN                             # the witness is neither rotated nor consumed

consequential_batch(frame, operations):
    gate = frame.open_gate
    frame.open_gate = None                  # consume this gate, never the witness
    if not gate_is_current(frame, gate):
        return DENIED("no valid open gate; reread authority if invalidated, then open_gate()")
    return dispatch_through_mediated_effect_policy(operations)

gate_is_current(frame, gate):
    return (gate is not None
            and active_plan_auth_is_approved_current_and_live()
            and gate.authority_id == active_plan_auth.id
            and gate.version == active_plan_auth.version
            and gate.frame_id == frame.id
            and gate.epoch == frame.epoch
            and not gate.expired()
            and within_opening_interval_policy(frame, gate))
```

**Notes.**

- Every consequential path in the deployment goes through `consequential_batch`. A path around it is a bug, and Invariant 4 fails with it.
- Any modification of existing cached context invokes `on_cached_context_modified`; ordinary append-only turns do not. The new epoch clears the witness and pending gate before bootstrap. Authority changes use their own hook. The read binding check is defensive; it does not detect unreported context modifications.
- `opening_id` identifies one successful opening for audit and reference-harness receipt binding. It is harness-assigned, distinct from the witness and never an additional worker proof; `new_gate_id()` does not rotate the session witness.
- `active_plan_auth_is_approved_current_and_live` checks approval, active identity, revocation and any configured authority expiry. Dispatch repeats this check so an already-open gate cannot outlive the governing authority.
- `within_opening_interval_policy` checks the configured `config.max_intervening_turns` against completed nonconsequential worker turns since the opening result. Zero permits the next action turn only; larger configured limits permit research. The opening turn and action turn themselves are not intervening turns. Exceeding the limit requires another opening; it does not prohibit research.
- Approval expiry and project allow-sets are optional release policies on `activate_plan_auth`.
- Claims, resurfacing, evidence and the failed-opening cap are reference-harness layers (Appendix B).

## Appendix B. Reference harness protocol

The reference harness adds resurfacing, claims, evidence admission, the failed-opening cap and end-of-turn verification to Appendix A. It reuses `clear_witness`, `read_active_authority`, `gate_is_current` and the binding rules from Appendix A. Every function runs under `serialized_frame_state(frame)`.

### B.1 Epoch and authority changes

Epoch change and authority change both clear the session witness, so the next bootstrap always mints a fresh one. Whether a revision should also start a new epoch is open (Section 8.5).

```text
# Sidecar per frame: Appendix A fields, plus
#   failed_openings, admitted {record_id: role}, active_area_basis {area_id: record_id}

on_context_change(frame, change):
    if change.kind == "append_only_turn":
        return                                  # growth preserves prior cached content
    record_context_change(frame, change)
    start_new_epoch(frame)                       # includes targeted removal and micro-compaction

start_new_epoch(frame):
    frame.epoch = fresh_epoch()
    clear_witness(frame)                        # session_witness, witness_binding, open_gate
    frame.failed_openings = 0
    frame.admitted = {}
    frame.active_area_basis = {}
    bootstrap_status(frame)                     # read_authority() plus task state and warnings

on_authority_change(frame):                     # new version activated, revoked or expired
    clear_witness(frame)
    frame.failed_openings = 0

read_authority(frame):
    result = read_active_authority(frame)       # Appendix A
    if result is not DELIVERY_UNCONFIRMED:
        frame.failed_openings = 0
        append_delivery_event(frame)            # audit record; its record ID is never the witness
    return result
```

`bootstrap_status(frame)` performs `read_authority(frame)` plus task state and warnings; this is the `status()` read named in Sections 2.4 and 3.3 and the Appendix G glossary.

### B.2 Opening the gate

`read_memory(ID)` performs a governed read of the durable record `ID`, admitting it into `frame.admitted` for the current epoch and returning its exact text.

```text
open_gate(frame, witness=None, evidence_ids=[]):
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
    # Resurfacing: exact authority under the SAME witness, plus the selected evidence.
    payload = (active_plan_auth.exact_text, frame.session_witness, exact_records(ids))
    if not confirmed_delivery(frame, payload):
        return DENIED("resurfacing not delivered; no gate opened")
    frame.open_gate = Gate(opening_id=new_gate_id(),
                           authority_id=active_plan_auth.id,
                           version=active_plan_auth.version,
                           frame_id=frame.id, epoch=frame.epoch, evidence=set(ids),
                           opened_at=position(frame),
                           expires=now_plus(config.gate_lifetime))
    return OPEN                                 # witness unchanged; replaces any pending gate
```

Every successful opening requires a witness from confirmed governed delivery in the current binding. Resurfacing renews presentation after that check; it cannot substitute for a missing or invalid prior admission.

### B.3 The action turn

The strict reference contract requires a trusted generation adapter to complete and freeze required claim fields before it enables the dependent action-payload fields. A constrained stream or separate claim and payload generations can enforce this order. Merely listing fields in that order does not. The adapter, not the worker, supplies `generation_receipt` to dispatch.

`claims_precede_payload` checks the protected receipt against this frame, epoch, authority version and `gate.opening_id`, and against the exact claims, action payloads and evidence bindings supplied for dispatch. It requires the claims to have completed before the corresponding payload generation began. A fabricated receipt, missing receipt, changed claim or substituted payload fails. Validation concerns observable emitted order; it does not assert how the model reasoned privately. This ordering contract is specified, not established by the historical audit.

The adapter freezes the emitted operations through dispatch. A receipt is used only with the opening it records; a later opening, including one with the same witness, needs a new ordered generation. An adapter that cannot enforce and attest this sequence must not report compliance with the strict reference contract.

```text
act_tool_turn(frame, turn, calls, authority_claim, evidence_claims, evidence_map,
              generation_receipt):                     # supplied by trusted adapter
    effects = [derive_actual_effect(c) for c in calls]     # by actual effect, not tool name
    gated   = [e for e in effects if effect_policy.requires_gate(e)]
    free    = [e for e in effects if e not in gated]
    if not gated:
        return dispatch(free)                             # pending gate remains subject to interval policy
    if any(is_open_gate_call(c) for c in calls):
        return DENIED(gated, "open the gate first, then act") + dispatch(free)
    gate = frame.open_gate
    frame.open_gate = None                                # one gate, one batch
    if not gate_is_current(frame, gate):
        return DENIED(gated, "no valid open gate; reread if invalidated, then open_gate()") + dispatch(free)
    if authority_claim is None:
        return DENIED(gated, "authority claim required") + dispatch(free)
    if not claims_precede_payload(generation_receipt, frame, gate,
                                  calls, authority_claim, evidence_claims, evidence_map):
        return DENIED(gated, "verified claim-before-payload generation required") + dispatch(free)
    results = []
    for unit in group_edits_sharing_a_basis(gated):
        issues = []
        for op in unit.operations:
            bound = set(evidence_map.get(op.id, []))
            if not bound <= gate.evidence:
                issues += "evidence not cited at opening"
            for e in bound:
                if frame.admitted.get(e) != "evidence":
                    issues += ("evidence no longer admitted", e)
                if not covered_by_claim(e, op, evidence_claims):
                    issues += ("missing evidence claim", e)
            for ob in derived_floor(op) + plan_obligations_checkable_before(op):
                if not ob.satisfied_by(bound, op):
                    issues += ob.failure
        if depends_on_effect_in_same_batch(unit, gated):
            issues += "depends on an action in this batch; run separately"
        issues += blocking_scope_permission_and_review_checks(unit)
        if issues:
            results += DENIED(unit, issues)               # no effect for this unit
            continue
        expected = versions_from_cited_observations(unit, evidence_map)
        persist_intent_once(unit, proof_record(gate, turn, authority_claim, evidence_claims,
                                              generation_receipt))
        outcome = dispatch_with_atomic_version_check(unit, expected)
        persist_outcome_or_uncertain(unit, outcome)
        results += outcome
        if outcome.success and unit.is_structured_edit:
            results += resurface_full_read_areas(frame, unit)     # Section 6.3
    return results + dispatch(free)
```

### B.4 End of turn

```text
end_of_turn(frame, turn, gate_used):
    if tracked_project_changed(turn):
        commit = commit_to_shadow_history(trailer=proof_record_ids(turn))
        record_turn_commit(commit)
        invalidate_bases_changed_by(commit)          # other frames' observations go stale
        post_commit_verification(frame, commit, gate_used)
            # per changed path: plan obligations against gate_used.evidence;
            # actual effects against declared grants; findings recorded; revert by policy
        resurface_changed_hunks(frame, commit)       # admitted as new observation records
```

### B.5 Structured authorities

Structured authorities (Companion B) add a witness per chunk. Each chunk witness is bound to its chunk ID, the authority version, the frame and the epoch. It is checked against that binding at opening, and cleared by `start_new_epoch` and `on_authority_change` exactly like the session witness.

## Appendix C. Acceptance tests

These fixtures test the behaviors the guarantee depends on, using scripted worker output. They are necessary, not a proof of correctness. A separate adherence suite, including Experiment 5, tests how faithfully a worker follows authority after passing the gate. Rows marked *regression* cover two protocol defects found and fixed during development.

### C.1 The gate

| Fixture | Expected result |
| --- | --- |
| New epoch; active `plan_auth` read | Plan delivered; fresh random witness bound to frame, epoch and version; pending gate cleared |
| Read again in the same epoch | Same plan text and same witness |
| Epoch change, then `status()` (*regression*) | A new witness is minted; the old witness is denied |
| Plan revision, then `read_authority()` (*regression*) | A new witness is minted; the old witness is denied |
| Witness equals a durable record ID | Denied; record IDs are never witnesses |
| Valid witness at `open_gate` | Gate opens for one batch; witness unchanged |
| Same witness for the next batch in the same epoch | Gate opens again |
| Witness copied into a note, same epoch | Valid. It names the correct work order; it proves no attention. |
| Witness copied to another frame or epoch | Denied |
| Never-issued or wrong-authority witness | Denied; no valid value revealed |
| `authority_unavailable` | Denied; not scored as a fabrication; guided to `read_authority()` |
| Failed openings reach the cap | Further openings denied until `read_authority()` succeeds |
| `read_authority()` with unconfirmed delivery | No witness set; no admission recorded |
| Correct authority text supplied in place of the required witness | Denied; text is not the bound witness accepted by this reference protocol |
| Witness supplied without confirmed admission for this frame and epoch | Denied even if the worker has a copy of the correct authority text |
| Resurfacing delivery fails at opening | No gate opened; witness unchanged |
| New opening while an unused gate is pending | Replaces the pending gate; witness unchanged |
| No gate, an expired gate, or a second batch under one opening | Consequential operations denied |
| `open_gate` and a consequential operation in one turn | The operation is denied |
| Research turn between opening and action, policy permits it | Gate stays open within its lifetime and turn allowance; unchanged cached context preserves availability |
| Research turn with zero-intervening-turn policy | Research may run; the old gate cannot dispatch a later action, which requires another opening |
| Exact authority delivered, but worker cannot supply the required proof | No gate opened; delivery alone does not satisfy the check; governed reread is the recovery |
| Targeted removal or micro-compaction after authority read | New epoch; old witness denied even if the authority text or a witness copy survived |
| Context modification after gate opening | Old admission, witness and pending gate invalidated before another effect; bootstrap delivers authority again |
| Authority revoked or expired after opening, without a version increment | Dispatch denied; an open gate cannot outlive active authority |
| Valid gate; action violates the plan | Gate passes; correctness finding against the unchanged `plan_auth` |
| Historical `plan_auth` read through memory search | No change to the active authority, witness or gate |
| Self-hosted agent edits gate source | Running gate unchanged until a principal-approved release |
| Harness directory accessed through the shell | Blocked or prompts the principal; logged |
| General-provenance citation matches a chunk present in current context | The citation validates; no warning returned |
| General-provenance citation does not match any chunk present in current context | A warning is returned to the worker; the operation is not blocked |

### C.2 Layers above the gate

| Fixture | Expected result |
| --- | --- |
| Evidence ID not admitted in this epoch | Whole opening denied |
| Valid gate; no authority claim | Denied; the gate is used up |
| Claims completed before payload through the trusted generation adapter | Ordering contract satisfied; other dispatch checks still apply |
| Action payload generated first, with a claim appended afterward | Denied by the strict ordering contract |
| Claims listed first, but no protected generation receipt | Denied; field layout alone is not ordering evidence |
| Worker supplies an asserted or fabricated ordering receipt | Denied; only the trusted adapter can attest generation order |
| Claim, action payload or evidence binding changed after receipt | Denied; generate a new ordered proposal |
| Receipt from another gate opening, even with the same valid witness | Denied; opening-specific binding fails |
| Cited evidence ID with no covering claim | That operation denied |
| Structured edit without a covering read | Denied |
| Structured edit whose basis is stale at commit | Denied on the derived expected version |
| `bash_mutate` changes a path with an unmet plan obligation | Command runs; post-commit finding recorded; hunk still resurfaced |
| `bash_mutate` performs an effect outside a declared grant | Post-commit grant-violation finding; review or revert by policy |
| External mutation without principal permission | Denied pending permission |
| Implementer-authored test cited for acceptance before approval or audit | Acceptance not granted; the passing run is recorded as testimony (Law 15) |
| Implementer edits a protected acceptance artifact | Denied by the protected-path bound; worker directed to a change request |
| Change request approved | New `plan_auth` version activated; prior witnesses invalidated |
| Change request denied | Old version still governs |

### C.3 Structured authorities

| Fixture | Expected result |
| --- | --- |
| Chunk witness from an earlier epoch (*regression*) | Denied |
| Chunk witness from an earlier authority version (*regression*) | Denied |
| Chunk witness read in this epoch for the active version | Accepted at opening |

## Appendix D. Guessing bound

With 64-bit witnesses, the chance that a worker passes the gate with a witness never delivered to it is negligible: about 1.6 × 10⁻¹⁹ for three guesses, and about 5 × 10⁻¹¹ for 10⁹ guesses. Randomness makes an invented reference detectable. It does not make behavior correct.

Let q count every candidate guess, b the witness entropy in bits, and N the number of qualifying values the worker was never shown. By the union bound [Mitzenmacher and Upfal], which needs no independence between attempts:

```latex
P(\text{at least one successful unseen guess}) \le \min\left(1, \frac{q \, N}{2^{b}}\right)
```

For b = 64, q = 3 and N = 1, the bound is 3 / 2⁶⁴.

- **Reuse is not guessing.** A valid witness reused across separately opened one-batch gates in its own epoch is a legitimate citation, not a guess.
- **Lifetime risk.** A deployer estimating risk across sessions counts all guesses and all distinct qualifying targets. A per-epoch cap on failed openings breaks blind-retry loops; it does not bound lifetime attempts.
- **Entropy counts only from the random part.** A random UUID carries 122 random bits [RFC 9562]. The witness must be separately random and must never be a durable record ID.
- **What the bound establishes.** It concerns recorded issuance and binding: a passing worker produced the witness issued with authority in its valid epoch, while a worker without such an issued value cannot normally pass by guessing. Delivery alone does not ensure that the worker can retrieve the witness when asked. It says nothing about retention of the work order's text.

## Appendix E. What each mechanism establishes

Prove what can be proved, record what is testified, review what requires judgment, and never upgrade testimony into evidence without a separate grounding step. This table is the reference matrix for mechanism guarantees and limits; the normative gate invariants are in Section 3.2. Each entry assumes its stated trusted-harness conditions; action-confinement guarantees additionally require complete mediation. None of the deterministic entries depends on the worker's disposition.

| Mechanism | Establishes | Does not establish |
| --- | --- | --- |
| Context-provenance witness check | The model-generated witness matches a target chunk actually present in current context; failure identifies an invalid citation under that association | Semantic support, comprehension, causal use of that chunk, or detection of uncited confabulation |
| Provenance-warning feedback | A failed context-citation check is reported back to the model | Correction, better subsequent reasoning or prevention of an action; these require separate evaluation or policy |
| Witness gate | At this opening the worker reproduced the witness issued with active `plan_auth`, bound to the valid frame, epoch and version | Recall of every authority clause, comprehension, attention or correct execution |
| Chunk witness | At this opening the worker reproduced the witness issued for that specific authority chunk, bound to its chunk ID, the active authority version, frame and epoch | Recall or comprehension of other chunks, or that the cited chunk is the correct basis for the action |
| Governed authority read | The exact active authority was made available in the admitted context | That the worker can currently retrieve the required proof or use the authority correctly |
| The gate under complete mediation | No reconstruction, invented, revoked or foreign-epoch authority reference is bound to a consequential action as the governing authority; the approved authority stays the fixed reference, so drift cannot occur at a consequential boundary | Correct actions, discovery of every mistake, or containment of effects |
| Resurfacing | Exact approved authority is delivered at opening and remains available under the context-validity rule; the interval before action is configurable | Recall, attention, comprehension, retroactive repair of an invalid admission, or lower mistake rates |
| Claims under the strict reference generation contract | The worker completed an action-specific interpretation before dependent payload generation; a protected receipt binds the order and emitted proposal to the gate | The claim's truth, private reasoning order or correctness of eventual effects; the historical audit does not establish this generation contract |
| Evidence identity check | A cited evidence ID is real, admitted in this epoch and of the right role | That it supports the claim or suffices for the action |
| Evidence floors | The harness required what it could derive from the operation; the plan could only raise it | That the floor was sufficient; that a shell call had the evidence it should have, until post-commit verification runs |
| Post-commit verification | Every changed path either met the plan's obligations from the gate's evidence set or was recorded as a finding | Prevention; the write already happened, and recovery is from the commit |
| Hunk resurfacing | The worker saw what its shell command actually changed, in the same turn | That the change was right |
| Turn commit | The net tracked change at the turn boundary, linked to proof records and revertible | Intermediate changes within the turn, ephemeral paths, or effects outside the project |
| Effect classification | Operations in the configured consequential set are checked | That the set is right; a misclassified operation is not checked |
| `bash_research` sandbox | Research commands cannot write governed resources or reach the harness directory | Anything about network effects not separately isolated |
| `bash_mutate` after the gate | Authority was proven before the command ran; the harness directory was unreachable | That the command served the task, stayed within prose limits, or caused no external effect |
| Approval bound to restatement and approval-message IDs | The principal approved exactly that text | That its premises are true, or that it was read with care |
| Change-request diff and scope delta | The principal saw exactly which clauses and declared scope would change | That the principal judged the change well, or noticed cumulative movement from the root version |
| Law 15 acceptance routes | An implementer-authored acceptance artifact was approved, independently audited or independently written before it counted | That the artifact covers every intent of the plan |
| Failed-opening cap | Blind-retry loops are interrupted and the worker reorients | A bound on lifetime guessing |
| `status()` | Delivery of the current authority with this epoch's witness | That the worker read every clause carefully |

## Appendix F. Embodiments and variants

Each variant below is a complete design for its purpose. The main text describes the reference harness; this appendix states what each alternative guarantees and when to choose it.

### F.1 Authority testimony

The general requirement is a worker-produced response validated against protected admission of current authority. The reference protocol implements that requirement with a bound witness. A witness's entropy and nonenumerability are properties of that implementation, not universal requirements for every possible response design.

| Variant | Guarantees | Choose it when |
| --- | --- | --- |
| Session witness (reference) | Binding to governed delivery of the active authority version in this frame and epoch, checked at each opening | Default |
| Per-action witness rotation | The same binding, with each witness single-use | A deployment requires single-use tokens. Tested; no measured benefit over the session witness. |
| Clause readback | The worker reproduces the governing clauses, checked deterministically against the record; this certifies reproduction, not application; the harness selects which clauses govern each action class | Proof of clause reproduction is wanted; untested in the author's deployment |

### F.2 Layers at the boundary

| Variant | Guarantees | Choose it when |
| --- | --- | --- |
| Gate only | Binding to the reference. This is all of CHR. | Minimal deployments on a controlled harness without silent compaction. Ran with good results in the author's field experience. |
| Single-step gate and claims (historical audited variant) | Checks the witness and requires contemporaneous claim and proposed action in one call, with no separate pre-action resurfacing | The configuration used in the more-than-8,000-attempt audit; a usable baseline when a separate tool round trip is undesirable |
| Gate and resurfacing | Adds renewed presentation at opening; availability continues under the context-validity rule | Deployments wanting a fresh presentation for the next decision |
| Deployed two-step gate, resurfacing and contemporaneous claims | Requires claim presence and coverage before dispatch; strict claim-before-payload generation is not established | Reproducing the deployed configuration and separating its evidence from the stricter reference specification |
| Gate, resurfacing and claims (reference) | Adds renewed authority presentation and a mandatory action-specific claim before dependent payload generation; research interval is configurable | Default; strict generation ordering is specified and its additional correctness benefit is under evaluation |
| Stricter release policy | Adds required resurfacing, tighter timing, review before selected effects and stronger containment as configured | Higher-liability or irreversible effects; requirements are inherited by delegated work |

### F.3 Host and context control

| Variant | Guarantees | Choose it when |
| --- | --- | --- |
| Controlled context (reference) | Every modification of existing cached context starts a new epoch, invalidates admission and pending gates, and requires authority reread | The harness controls context or receives reliable modification events |
| Hosted history with heuristic detection (limited variant) | Known changes trigger invalidation; missed changes prevent a strict claim of current admission validity. Resurfacing provides renewed delivery, not retroactive validity. | The provider controls history and the deployment explicitly accepts and assesses these limits |

### F.4 Approval

| Variant | Guarantees | Choose it when |
| --- | --- | --- |
| Direct principal instruction | The instruction is both plan and approval | Single tasks |
| Restatement loop with ID-bound approval (reference) | The principal approved exactly the full restatement | Multi-step work |
| Plan programs with compiler checks and plan audit | Mechanically checkable parts of the plan are checked before approval | Large or high-liability plans (Companion B) |

### F.5 Authority structure

| Variant | Guarantees | Choose it when |
| --- | --- | --- |
| Single-block `plan_auth` (reference) | The whole authority is presented and resurfaced at every opening | Bounded tasks |
| Task sub-authorities | Each task is a narrowed authority with its own frame and witness | Delegated work; in use |
| Header and chunks with bound chunk witnesses | Global constraints always live; scoped procedure read on demand | Large projects (Companion B) |

### F.6 Write paths

| Variant | Guarantees | Choose it when |
| --- | --- | --- |
| Shell with post-commit verification and hunk resurfacing (MVP) | Obligations checked after the write; recoverable for tracked files | Low friction for aligned workers |
| Structured tools with pre-write evidence checks | Obligations checked before the write; full-area resurfacing after it | Portable implementations |
| Shell with staged effects validated before application | Prevention rather than recovery | Workers whose disposition is not trusted |

### F.7 Acceptance artifacts

| Variant | Guarantees | Choose it when |
| --- | --- | --- |
| Principal-approved artifact or specification | The principal fixed what is tested | The principal can read test specifications |
| Independent audit against the plan | A non-implementer confirmed coverage of plan clauses | Implementer writes tests for speed |
| Independent authorship with read-only protection | The implementer cannot write or change the standard | High liability, or recurring acceptance gaming |

## Appendix G. Glossary

| Term | Meaning | Not to be confused with |
| --- | --- | --- |
| Acceptance artifact | A test, fixture, golden output or evaluation script that an acceptance criterion refers to | An approved acceptance criterion; it binds only under Law 15 |
| Adherence error | Misunderstanding, misapplying or disregarding genuine instructions without replacing them as authority | Authority drift |
| Agent | The persistent entity: its authority, history and memories | Any one session or model |
| Alignment | What the worker is trying to do: pursue the approved assignment, read for intent, raise boundary crossings, be candid | Competence or instruction-following, which are capability |
| Authority availability | Exact active authority delivered through a governed read into an unmodified admitted context | Validated authority testimony or correct application |
| Authority drift (drift) | An unapproved substantive change to the authority a worker treats as governing; in long-running agents usually progressive, each reconstruction becoming the source for the next | A correctness error against genuine authority |
| Authorization error | Approved authority that does not match the principal's intent | Drift; the worker followed what was approved |
| Batch | Parallel consequential operations generated in one turn and covered by one gate | Several successive turns |
| Bureaucrat | A worker that escalates choices the authority already leaves to it; the mirror image of drift | A worker making checks that could change its action |
| CHR | Causal-Historical Root: causal-history non-identifiability, the condition underneath drift | A witness format |
| CHR authority gate | Deterministic validation of worker-generated authority testimony before each consequential batch; the reference protocol checks a witness against protected admission of active `plan_auth` | Resurfacing, claims, review or any guarantee of correct action |
| Claim | Worker testimony linking authority or evidence to a specific action; the strict reference contract requires completion before dependent payload generation | Evidence; the harness never accepts a claim as true |
| Clause | An addressable exact extract of approved authority | A paraphrase of the plan |
| Consequential action | An operation with persistent or externally visible effects under the effect policy | Any tool call |
| Context epoch | An admitted working context; any modification of its existing cached content ends it and invalidates its witness and pending gate | Append-only growth, or a durable record's lifetime |
| Context provenance validation | External checking of a model-generated citation against the cited chunk's actual presence in current context; the witness implementation checks an associated nonce | Semantic verification or proof of the model's private reasoning history |
| Correctness error | A mistake under genuine authority, possibly violating its limits; its consequences remain judged against that fixed reference | Authority drift |
| Cumulative fidelity | Agreement of a reconstruction with the original approved task | Per-step fidelity |
| Dream engine | A generator without reality monitoring: coherent output whose premises' provenance it cannot tell from context | A model that cannot reason |
| Durable record ID | A permanent `rec:` locator for one immutable record | A witness |
| Evidence | A qualifying observation admitted through a governed read; identity and recorded origin only | Testimony, or permission |
| Evidence floor | The evidence an operation requires by default, derived from the operation itself | A plan obligation, which can only raise it |
| External reference | The approved authority held outside the worker, which no reconstruction can replace; in the reference harness, active `plan_auth` | A reminder, summary or note in context |
| Feral worker | A worker with no useful disposition toward its assigned task | An ungrounded worker |
| Frame | One task's authority binding, with its own witness | A context window |
| Generation receipt | Protected adapter record binding claim-before-payload output order and exact emitted proposal to one gate opening | Worker testimony, a claim's truth or proof of private reasoning order |
| Harness directory | The protected path holding the memory store, authority records and sidecar | A protected path in the project's own sense |
| Honest absence | Reporting `authority_unavailable` instead of producing a witness | A failed opening |
| Integrating authority drift | Each reconstructed assignment becomes the source of authority for the next; an external approved reference breaks this chain | Downstream consequences of correctness errors against a fixed assignment |
| Malicious worker | A worker acting against the principal (the insider threat); it can act only under the genuine authority, inside the bounds | A worker that misreads its authority |
| Mandatory read | A design requiring `read_authority()` before each consequential action without validating testimony | The witness gate |
| Open gate | Sidecar state covering the next consequential batch within its lifetime, interval policy and valid authority/context binding | Authority availability or standing authorization |
| Per-step fidelity | Agreement of a reconstruction with its immediate predecessor | Cumulative fidelity |
| `plan_auth` | The one operative authority type: immutable, versioned, principal-approved, activated through the trusted path | A worker's plan proposal |
| Principal | The party that approves authority; it may delegate bounded approval | The worker, or a reviewer without delegated approval |
| Provenance warning | Feedback to the worker that its cited context failed external validation as present | A mandatory action block, semantic verdict or prescribed recovery workflow |
| Reality monitoring | Telling events that happened from events imagined or generated [Johnson and Raye] | Correctness checking |
| Reconstruction | Any agent-generated restatement of its assignment: a summary, handoff prompt, note or working understanding | The approved authority |
| Resurfacing | Returning the exact approved authority, under the unchanged witness, as the result of each successful opening | The binding check |
| Sidecar | Per-frame trusted state: binding, witness, open gate, admissions, failed-opening count | The shared memory store |
| `status()` | The governed reorientation read: current authority, this epoch's witness, task state and warnings | An independent authority source |
| Telephone game | The paper's name for progressive drift: a chain of faithful restatements that loses the original | A single mistaken restatement |
| Testimony | Anything the worker generates | Evidence |
| Trusted prompting | A design inserting approved text from the protected record before action generation without checking testimony | A binding check |
| Turn commit | The harness's automatic commit of tracked project changes at the end of a turn with an edit | An agent-initiated git operation |
| Ungrounded worker | A worker unable to supply valid current authority proof, whatever its disposition | A feral worker |
| Validated authority testimony | A worker-produced response checked against protected admission of the active authority; the reference implementation checks the bound witness at each opening | Availability alone, recall of every clause, comprehension or adherence |
| Witness | An unguessable nonce inside a target context chunk, reproduced by model generation; the authority profile uses `wit:` and binds it to active `plan_auth`, version, frame and epoch | A durable record ID, harness-generated echo or proof of comprehension |
| Work order | Everyday term for the approved assignment; in the reference harness, active `plan_auth` | A worker's reconstruction |
| Worker | One model execution within the agent | The agent |
| Yardstick | The binding standards in activated `plan_auth`: tasks, acceptance criteria, prohibitions | A worker's unapproved reconstruction or proposal |

## Appendix H. Open items

- Confirm the dates and overlaps of each deployment stage, and whether each deployed witness, especially in the audited original system, was a separately minted session nonce or a presentation record ID (Section 5.1).
- Determine, from contemporaneous tool response payloads, whether the original single-step gate returned authority text, as distinct from the later two-step pre-action delivery.
- Rebuild Section 5 from the append-only store rather than recollection. If the store cannot produce the chronology, record that as a finding.
- Document the 8,000-attempt audit procedure: who performed it, by what criteria, with what blinding. Consider a second rater on a sample.
- Decide whether an authority revision itself starts a new context epoch. Any pruning or marking of existing cached copies must follow the context-invalidation rules (Section 2.4; Section 8.5, Experiment 15).
- Design the cumulative diff and scope delta against the root version for change requests (Section 3.9).
- Confirm Law 15 as a design rule, and choose the default acceptance route for the reference harness.

## Appendix I. Status, licensing and document set

This document is the engineering reference for the CHR authority gate and its reference harness. It specifies the shared context-provenance validator underlying ordinary provenance warnings and authority gating, the bound witness, context-invalidation rules and configurable gate timing, and Section 9 sets out what a fixed reference makes manageable for stochastic workers, with Experiments 17–22 to test it. The minimal warning profile reports an invalid context citation to the worker; the authority profile requires the approved source and blocks consequential actions on failed validation. The preferred harness also requires an action-specific claim before generation of its dependent action payload; that ordering is a specified addition, distinct from the historical field record. Section 5 distinguishes deployed behavior from specified additions. Variants are in Appendix F; open questions and historical verification tasks are in Section 8.5 and Appendix H.

Disclosure: A patent application is pending. Building it yourself for non-commercial or research use is welcome; Commercial use will need a license if the patent issues.

**Origin.** The CHR gate originates in the author's earlier work.

**Document set.** This core document is self-contained. The companions extend the persistent-agent environment around the gate; none of them is a CHR dependency.

| Document | Covers | Status |
| --- | --- | --- |
| Core (this document) | Authority drift, shared context-provenance validation, warning and gate profiles, correctness layers, field record, what a fixed reference makes manageable, evaluation, protocols, tests | Draft |
| *The Wrong Defendant* (v2.1) | Rationale: why authority must be held outside the worker; systemic versus AI-specific threats; falsifiable test | Working paper |
| Companion A: Operating environment | Extended provenance feedback, durable state, citation-indexed context reconstruction, scratchpad waypoints | Earlier draft; not updated |
| Companion B: Authority programming | Plan programs, delegation, budgets, structured authorities with header and chunks | Earlier draft; not updated |
| Companion C: Cited reasoning operations | Modular, replayable reasoning records | Proposed |
| Companion D: Training | Citation training, weak verifiers, internal provenance channels; reference-anchored rewards, model workers in training pipelines, and harness-reliant model design (Core Sections 9.5–9.7) | Proposed |

**Reading order.** The opening explains the problem; the Core thesis states the governing claims, and the Technical overview summarizes the mechanism. Section 1 develops the diagnosis, Section 3 specifies the harness, Sections 4–5 show its operation and field record, Section 6 covers management, and Section 9 sets out what a fixed reference makes manageable. Appendices A–C provide protocols and fixtures; Appendix E is the guarantee reference. Appendix J, the brief for reviewers, gives the review contract.

## Appendix J. Brief for reviewers

Review against the six Core thesis claims and the definitions in Sections 1.1–1.2. The Technical overview introduces the implementation. Objections are welcome; identify whether they dispute the thesis or its execution, and use the paper's distinction between authority drift and correctness, and between availability and validated authority testimony.

**What would count against the thesis.** Serious findings include:

- Evidence that reconstruction-only chains reliably preserve the governing task across the long-horizon conditions at issue, or recover genuinely erased distinguishing information without an external source.
- A mechanism other than an external reference that keeps the governing assignment fixed across compaction, handoffs and long sessions.
- A path by which a reconstruction becomes governing authority at a consequential boundary while all four invariants and complete mediation hold.
- Failure of the proposed authority boundary to provide the claimed stable basis for assessing and managing work against the approved assignment. The frequency of correctness errors alone does not establish this.

**Common readings, and the answer.** Raise a listed point only if its answer is wrong, and explain why.

| Reading | Answer |
| --- | --- |
| The gate does not guarantee correct actions. | Correct. It preserves the governing reference; correctness is managed against it (Section 6). |
| The guarantee is true by construction. | Yes. Protected authority and complete mediation are the construction (Section 3.2). |
| A worker with a valid witness can still act on its reconstruction. | That is correctness under genuine authority; its testimony cannot promote the reconstruction to approved standing (Section 6.5). |
| Authority is already in context, so delivery is enough. | Availability is not validated authority testimony. The worker must generate the required proof at each opening (Sections 2.4 and 3.3). |
| Lost-in-the-middle is always correctness because the text still exists. | The worker may fail to retrieve the required proof. The gate denies that attempt; incorrect application after valid proof is correctness (Section 1.1). |
| Drift is just an error the agent makes. | The failure belongs to the reconstruction chain; no step need be a correctness error (Section 1.1). |
| Re-injecting the plan would also work. | That supplies an external reference and agrees with the thesis. Binding implementations are compared in Experiment 2. |
| Better models will fix drift. | Capability cannot recover distinguishing information genuinely erased from a reconstruction-only chain. Retained text presents a separate recall question (Section 1.2). |
| The 420 fabrications came from a harness bug. | Probably. The denied claims still asserted authority the actual plan did not contain (Section 5.3). |
| The witness proves nothing about comprehension. | Correct; Appendix E states the proof's exact scope. |
| CHR does not stop prompt injection. | It prevents injected text from becoming governing authority. Persuasion under genuine authority is correctness and containment (Sections 3.6–3.7). |
| A session-bound nonce or a model-generated passkey response is a known pattern. | Yes. Section 7.2 separates the known retrieval check from the proposed runtime warning and authority-gating uses. |
| Authority provenance requires a different validator from ordinary context provenance. | No. The source requirement and failure policy differ; the underlying check is shared (Section 3.0). |
| The field record is author-run and uncontrolled. | Acknowledged in Section 5; Section 8 specifies evaluation. |

**Known open items.** Design questions are tracked in Section 8.5; historical and author-verification tasks are in Appendix H. Check those lists before reporting a gap.

**Review prompt.** For a fresh model session, the first step checks its reconstruction against the approved thesis before it critiques the rest of the paper.

```text
Review the attached paper against its Core thesis section.
First, restate each of the six Core thesis claims in one line and compare
your restatement with the original wording.
Then sort your comments into thesis objections and execution objections,
each tied to a section.
Before raising a point, check the "Common readings" table and the known open
items in Appendix J. Raise a listed point only if you think the
stated answer is wrong, and say why.
End by stating what evidence would change your assessment.
```

## References

**Verification status.** For this document, each entry below that cites a publicly available source was checked against that source for authors, title, venue or publisher, year and identifier, and against the specific claim the paper attaches to it; entries that could not be supported were corrected or removed. This is a technical comparison, not an exhaustive prior-art search or determination of priority dates. References cited only in the companions remain in those documents.

**Rationale**

- Scherdin, N. [The Wrong Defendant: Artificial Intelligence Maligned by a Governance Design Failure](https://github.com/acidtech/Grounded_Authority_for_Language_Model_Agents/blob/main/The_Wrong_Defendant_AI_Governance_Failure_v2_1.md). Working paper, Version 2.1, October 27, 2026.

**Serial reproduction, iterated learning and information**

- Bartlett, F. C. *Remembering: A Study in Experimental and Social Psychology.* Cambridge University Press, 1932.
- Griffiths, T. L. and Kalish, M. L. Language Evolution by Iterated Learning with Bayesian Agents. *Cognitive Science* 31(3), 2007.
- Cover, T. M. and Thomas, J. A. *Elements of Information Theory*, 2nd ed. Wiley, 2006. (Data processing inequality.)

**Inertial navigation**

- Woodman, O. J. [An introduction to inertial navigation](https://www.cl.cam.ac.uk/techreports/UCAM-CL-TR-696.html). Technical Report UCAM-CL-TR-696, University of Cambridge Computer Laboratory, August 2007. doi:10.48456/tr-696.

**Agent security**

- Debenedetti, E., Shumailov, I., Fan, T., Hayes, J., Carlini, N., Fabian, D., Kern, C., Shi, C., Terzis, A. and Tramèr, F. [Defeating Prompt Injections by Design](https://arxiv.org/abs/2503.18813). arXiv:2503.18813, 2025.
- Costa, M., Köpf, B., Kolluri, A., Paverd, A., Russinovich, M., Salem, A., Tople, S., Wutschitz, L. and Zanella-Béguelin, S. [Securing AI Agents with Information-Flow Control](https://arxiv.org/abs/2505.23643). arXiv:2505.23643, 2025.
- OWASP Cheat Sheet Series. [SQL Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html). Accessed October 27, 2026.
- Hines, K., Lopez, G., Hall, M., Zarfati, F., Zunger, Y. and Kıcıman, E. [Defending Against Indirect Prompt Injection Attacks With Spotlighting](https://arxiv.org/html/2403.14720v1). arXiv:2403.14720v1, March 20, 2024.

**Context degradation**

- Liu, N. F., et al. [Lost in the Middle: How Language Models Use Long Contexts](https://arxiv.org/abs/2307.03172). TACL, 2024.
- Chen, S. [Governance Decay: How Context Compaction Silently Erases Safety Constraints in Long-Horizon LLM Agents](https://arxiv.org/abs/2606.22528). arXiv:2606.22528, 2026.
- Zerhoudi, S., Mitrović, J. and Granitzer, M. [The Compaction Cliff in Long-Running AI Agent Memory](https://arxiv.org/abs/2608.22752). *Proceedings of the 35th ACM International Conference on Information and Knowledge Management (CIKM 2026)*; arXiv:2608.22752, August 24, 2026.
- Kruthof, G. [Models Recall What They Violate: Constraint Adherence in Multi-Turn LLM Ideation](https://arxiv.org/abs/2604.28031). arXiv:2604.28031, 2026.
- Guo, J., Fang, Y., Gu, S., et al. [When Context Changes: Understanding Update Failures in LLMs](https://arxiv.org/abs/2609.38866). arXiv:2609.38866, 2026.

**Context retrieval, preservation and provenance feedback**

- [Chen et al., Positional Interpolation] Chen, S., Wong, S., Chen, L. and Tian, Y. [Extending Context Window of Large Language Models via Positional Interpolation](https://arxiv.org/abs/2306.15595v2). arXiv:2306.15595v2, June 28, 2023; Section 3.3 and Figure 3, passkey retrieval.
- [DPC] Digital Preservation Coalition. [Fixity and checksums](https://www.dpconline.org/handbook/technical-solutions-and-tools/fixity-and-checksums). *Digital Preservation Handbook*. Accessed October 23, 2026.
- [Juels and Kaliski] Juels, A. and Kaliski, B. S., Jr. [PORs: Proofs of Retrievability for Large Files](https://www.arijuels.com/wp-content/uploads/2013/09/JK07.pdf). *ACM Conference on Computer and Communications Security (CCS)*, pp. 584–597, 2007; doi:10.1145/1315245.1315317. Earlier [ePrint record 2007/243](https://eprint.iacr.org/2007/243), marked withdrawn.
- [Madsen et al.] Madsen, A., Chandar, S. and Reddy, S. [Are self-explanations from Large Language Models faithful?](https://aclanthology.org/2024.findings-acl.19/). *Findings of ACL 2024*, pp. 295–337.
- [Wallat et al.] Wallat, J., Heuss, M., de Rijke, M. and Anand, A. [Correctness is not Faithfulness in RAG Attributions](https://arxiv.org/html/2412.18004v1). arXiv:2412.18004v1, December 23, 2024.
- [Context Canary] mkmkkkkk. *Claude Context Canary*, [`canary-check-v2.sh`](https://github.com/mkmkkkkk/claude-context-canary/blob/master/canary-check-v2.sh). Source inspected October 23, 2026; this access date is not a finding of first public disclosure.
- [Alvarez et al.] Alvarez, A., et al. [ProvenanceGuard: Source-Aware Factuality Verification for MCP-Based LLM Agents](https://arxiv.org/html/2606.18037v1). arXiv:2606.18037v1, June 16, 2026.

**Capabilities and formal foundations**

- Dennis, J. B. and Van Horn, E. C. Programming Semantics for Multiprogrammed Computations. *Communications of the ACM* 9(3), 1966.
- Miller, M. S. *Robust Composition: Towards a Unified Approach to Access Control and Concurrency Control.* PhD thesis, Johns Hopkins University, 2006.
- Birgisson, A., Politz, J. G., Erlingsson, Ú., Taly, A., Vrable, M. and Lentczner, M. Macaroons: Cookies with Contextual Caveats for Decentralized Authorization in the Cloud. NDSS, 2014.
- Alpern, B. and Schneider, F. B. Defining Liveness. *Information Processing Letters* 21(4), 1985.
- Mitzenmacher, M. and Upfal, E. *Probability and Computing: Randomization and Probabilistic Techniques in Algorithms and Data Analysis*, 2nd ed. Cambridge University Press, 2017. (Lemma 1.2, union bound.)
- [RFC 9562] Davis, K., Peabody, B. and Leach, P. [Universally Unique IDentifiers (UUIDs)](https://www.rfc-editor.org/rfc/rfc9562.html). RFC 9562, May 2024; Section 5.4.

**Tool use**

- Yao, S., et al. [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629). ICLR, 2023.
- Schick, T., et al. [Toolformer: Language Models Can Teach Themselves to Use Tools](https://arxiv.org/abs/2302.04761). NeurIPS, 2023.

**Memory, programming and durable execution**

- Packer, C., et al. [MemGPT: Towards LLMs as Operating Systems](https://arxiv.org/abs/2310.08560). arXiv:2310.08560, 2023.
- Khattab, O., et al. [DSPy: Compiling Declarative Language Model Calls into Self-Improving Pipelines](https://arxiv.org/abs/2310.03714). arXiv:2310.03714, 2023.
- Fowler, M. [Event Sourcing](https://martinfowler.com/eaaDev/EventSourcing.html). 2005.
- [Temporal](https://temporal.io): durable execution platform.

**Cognitive science**

- Johnson, M. K., Hashtroudi, S. and Lindsay, D. S. Source Monitoring. *Psychological Bulletin* 114(1), 1993.
- Johnson, M. K. and Raye, C. L. Reality Monitoring. *Psychological Review* 88(1), 1981.

**Legal illustration**

- [RSF] Reporters Without Borders. [The principle that generative AI cannot be held to account has begun to crack in German court ruling against Google](https://rsf.org/en/principle-generative-ai-cannot-be-held-account-has-begun-crack-german-court-ruling-against-google). June 2026.
- dpa. [Court finds Google liable for false AI answers in landmark case](https://www.yahoo.com/news/world/articles/court-finds-google-liable-false-155629224.html). Republished by Yahoo News, June 12, 2026.
- Munich Regional Court (LG München I). [Press release 13/26](https://www.justiz.bayern.de/gerichte-und-behoerden/landgericht/muenchen-1/presse/2026/13.php), 12 June 2026, case no. 26 O 869/26, on the preliminary injunction of 28 May 2026; Google announced an appeal in June 2026 [RSF]. Date and party: LTO, [LG München I zu KI-Antworten von Google: Google muss für KI-Gerüchte geradestehen](https://www.lto.de/recht/nachrichten/n/26-o-86926-lg-muenchen-i-ki-antworten-von-google-gemini), Xenia Piperidou, 11 June 2026.
- The Decoder. [Two German courts now hold Google liable for what its AI overviews say](https://the-decoder.com/two-german-courts-now-hold-google-liable-for-what-its-ai-overviews-say/). Matthias Bastian, October 19, 2026.

**Oversight and training signals**

- Bowman, S. R., Hyun, J., Perez, E., et al. [Measuring Progress on Scalable Oversight for Large Language Models](https://arxiv.org/abs/2211.03540). arXiv:2211.03540, 2022.
- Lambert, N., Morrison, J., Pyatkin, V., Huang, S., Ivison, H., et al. [Tulu 3: Pushing Frontiers in Open Language Model Post-Training](https://arxiv.org/abs/2411.15124). arXiv:2411.15124, 2024.
- DeepSeek-AI. [DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via Reinforcement Learning](https://arxiv.org/abs/2501.12948). arXiv:2501.12948, 2025.
- Gao, L., Schulman, J. and Hilton, J. [Scaling Laws for Reward Model Overoptimization](https://arxiv.org/abs/2210.10760). arXiv:2210.10760, 2022.

**Model design**

- Ainslie, J., Lee-Thorp, J., de Jong, M., Zemlyanskiy, Y., Lebrón, F. and Sanghai, S. [GQA: Training Generalized Multi-Query Transformer Models from Multi-Head Checkpoints](https://arxiv.org/abs/2305.13245). EMNLP 2023; arXiv:2305.13245.
- Shazeer, N. [Fast Transformer Decoding: One Write-Head is All You Need](https://arxiv.org/abs/1911.02150). arXiv:1911.02150, 2019.
- Dutta, A., Krishnan, S., Kwatra, N. and Ramjee, R. [Accuracy is Not All You Need](https://arxiv.org/abs/2407.09141). arXiv:2407.09141, 2024.
- Jiang, A. Q., Sablayrolles, A., Mensch, A., et al. [Mistral 7B](https://arxiv.org/abs/2310.06825). arXiv:2310.06825, 2023.
- [DeepSeek-AI, DeepSeek-V2] DeepSeek-AI. [DeepSeek-V2: A Strong, Economical, and Efficient Mixture-of-Experts Language Model](https://arxiv.org/abs/2405.04434). arXiv:2405.04434, 2024.

**Literary illustration**

- Adams, D. *The Hitch Hiker's Guide to the Galaxy.* Pan Books, 1979.
