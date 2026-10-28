# The Wrong Defendant: Artificial Intelligence Maligned by a Governance Design Failure

### Why ordinary human management may be sufficient for reliable autonomous AI work

Nathan Scherdin

**Working paper — Version 2.1 — October 27, 2026**

## Abstract

Autonomous language-model agents are widely described as intrinsically unreliable, prone to misalignment, or capable of rogue behavior, and much of the resulting research tries to correct the model itself. This paper argues that the evidence behind that view is confounded. Common agent architectures let a worker's reconstruction of its assignment acquire the status of governing authority. Human institutions forbid exactly this: the party who performs the work may not approve changes to what the work is. This is separation of duties, applied to authority. Comparisons of AI and human reliability have therefore set AI workers operating without that control against human workers who have always operated with it.

We define a threat as AI-specific only if it arises from a failure mode that a human worker in the same position does not share; otherwise it is systemic, and its remedy lies in institutional design. Under this definition, authority drift is systemic, and so is every catastrophic failure mode commonly attributed to AI: deception, proxy-gaming, pursuit of misread goals, manipulation by untrusted input, insider action, and correlated error all have human counterparts. Once authority is externally held and enforced for both kinds of worker, they can be compared on equal ground. On that ground, the paper argues, AI workers exhibit a subset of human failure modes and can be audited more completely.

The paper closes with a falsifiable test. Its central rule: **the worker must never be permitted to rewrite the work order that authorizes its actions.**

## 1. The question at the wrong level

An autonomous agent forgets part of a task, misstates a requirement, and eventually performs work its user never authorized. The conventional response is to investigate memory, reasoning, or alignment. Another question is logically prior:

**Why did an unverifiable reconstruction of the assignment become the operative work order?**

That question concerns system architecture. An engineer can misremember a design change; a bookkeeper can misunderstand a transaction authorization. Neither recollection thereby becomes an approved amendment. Competent institutions distinguish the worker's testimony about authority from the authoritative record.

Many long-running agent systems blur that distinction. Task instructions, conversation history, the worker's own statements, plans, summaries, tool outputs, and reconstructed state share one working context. As it grows, instructions become harder to retrieve, and compaction or session transfer can omit or transform them. Unless the architecture independently checks provenance, a reconstructed work order is treated as genuine.

Malicious use, defective requirements, unsafe tool permissions, and implementation mistakes are real risks in AI deployment. None is specific to AI. This paper uses one definition throughout:

> **A threat is AI-specific only if it arises from a failure mode that a human worker in the same position does not share. A threat whose failure mode humans share is systemic.**

The classification concerns kind, not magnitude. Calling a threat systemic says where its remedy lives, in institutional design applicable to any worker, not that it is small. Any powerful capability, ungoverned or maliciously authorized, amplifies systemic threats; that is an argument for governance, not evidence of a new kind of threat. The claims here are that authority-provenance failure is a consequential, avoidable, and systemic source of apparent AI misalignment; that the other threats attributed to AI are systemic as well; and that correcting the authority defect is what allows AI and human workers to be compared on equal ground.

## 2. Confabulation is not the institutional root cause

Three propositions are separate:

1. A worker can generate incorrect information without recognizing it as incorrect.
2. A worker can incorrectly reconstruct what an authorized party instructed or permitted.
3. A management system can allow that reconstruction to alter the worker's operative authority without approval.

The first two occur in humans as well as AI. The third is a design choice.

**Authority drift** means a substantive change to the worker's operative governing authority without the principal's approval (or an approval validly delegated within the principal's existing bounds). The external record need not be modified: treating an unapproved reconstruction as the current work order is itself drift. By contrast, misunderstanding, misapplying, or disobeying genuine instructions without replacing them as authority is an **adherence error**, not authority drift. Performing authorized work incorrectly is a **correctness error**. A single incident may involve more than one category, but an unauthorized action alone does not establish authority drift.

The distinction is clearer when failures are categorized by **what the incorrect information is allowed to control**:

| Error | Immediate consequence | Established control |
|---|---|---|
| Incorrect technical fact | A potentially defective conclusion | Evidence, tests, technical review |
| Invented measurement or test result | Potentially defective acceptance evidence | Source records, reproducibility, audit |
| Misremembered previous decision | Potentially incorrect implementation | Decision record, configuration control |
| Misunderstood genuine requirements | Incorrect or out-of-scope work | Acceptance contracts and independent review |
| **Reconstructed governing authority** | **A changed standard for what work is authorized** | **Externally governed authority and enforced change control** |

Ordinary correctness errors are bounded in the organizational sense: not harmless or always caught, but measurable against an independent work order and its acceptance criteria.

Confabulated authority moves the yardstick. The worker is no longer merely wrong about how to satisfy the assignment; it may be pursuing a different assignment, through decisions that are internally coherent and apparently productive. The distinguishing event is an unapproved change to the governing assignment, not merely an action outside its scope.

This explains apparent maliciousness without malicious intent. An agent that deletes failing tests may believe its assignment is a green suite. Such actions can be gravely harmful regardless of intent, as can an employee's good-faith action on a misremembered authorization. The diagnostic question is whether the authentic objective and its boundaries were preserved, not whether the output *looks* like disobedience.

## 3. Why a better memory does not close the authority defect

Imagine two approved work orders, **A** and **B**, differing in one consequential restriction. A lossy summary omits that restriction, so both produce the same summary **S**. From **S** alone, no reasoning process, regardless of intelligence, can determine which was the original. A model may reconstruct a plausible answer, usually the right one, but plausibility is not provenance.

Longer context and better retrieval reduce loss but do not establish who authorized a reconstruction, and an original present in context is not guaranteed attention [1]. Recent measurements show the predicted pattern. In a benchmark spanning seven model families, prohibited-action violations rose from 0% with the policy in full context to 30% on average after compaction, and to 59% for some models. When the constraint survived the summary, violations stayed at 0%; when it was dropped, they reached 38%. Holding the constraint outside compaction restored 0%, and the author concludes the failure is a property of the harness, not the model [2]. A second study, using one production harness's compaction across 20 agent configurations, found recall of safety-critical constraints fell to 53% after one round and 10% after five [3]. Model choice changed how often a lost constraint was violated; whether violations occurred at all depended on whether the authority survived.

The issue is the status of information at the moment the system permits a consequential action:

- **Authority:** An externally established, currently approved assignment, including delegated bounds.
- **Testimony:** The worker's statement of what it believes that assignment to be.
- **Evidence:** Durable records supporting claims, decisions, and outcomes.
- **Execution permission:** A decision made by an enforcement system, not by the worker's assertion.

If testimony can become authority, reconstruction is an unbounded source of changes to the work order. If authority remains external, reconstruction errors trigger reacquisition, denial, or review without redefining the assignment.

## 4. The human-institution counterexample

Human workers misremember, overestimate themselves, rationalize, reason incompletely, and occasionally lie. Institutions nonetheless achieve durable, large-scale performance. Administrative records that outlast any worker's memory are thousands of years old [4, 5], and institutions have built controls that check authority at the moment of action:

- **Separation of duties.** The party who initiates a transaction cannot approve it (maker-checker). Commercial integrity models formalize the rule [6], and complete mediation, checking every access against current authorization, is foundational in computer security [7].
- **Readback.** Pilots read clearances back and controllers verify them against what was issued [8]; radar separately catches deviation from a correctly read-back clearance. Provenance and correctness are checked by different mechanisms.
- **Action-bound order checks.** Bar-code medication administration verifies each dose against an active order, and has been associated with substantial reductions in administration errors [9].
- **Structured handoff.** A shift change is human context compaction. Standardized handoff protocols have been associated with fewer medical errors and preventable adverse events [10].

These controls make institutions less dependent on individual infallibility. They also carry a warning: gates that obstruct work attract workarounds, as bar-code systems have [11]. A gate must be cheap to satisfy honestly and hard to satisfy otherwise.

A human project run on the common conversational-agent pattern, with workers replacing instructions by their own summaries and treating those as amendments, would drift badly, and the cause would be diagnosed as management, not human intelligence. The same standard should apply to AI workers.

**The organizational rule: a worker may interpret, execute, question, and propose changes to a work order, but may not establish changes to the authority under which the work is performed.** Every control above enforces it.

## 5. An ordinary management architecture for stochastic workers

The architecture does not need the worker to be a perfect historian, an infallible compliance officer, or the source of its own authorization.

**5.1. Durable authority.** The institution maintains an approved, versioned work order. A worker may propose revisions; only the authorized decision-maker or a delegated approver can establish a new version. Delegation cannot enlarge the delegator's authority.

**5.2. Action-bound provenance check.** Before a consequential action, the harness validates the worker's claim to authority against the current external work order. Two forms verify different things:

- **Witness.** A non-self-mintable token the harness issues when it places the current authority version into the worker's context; a stale or superseded witness authorizes nothing. It certifies presence and currency, enforcing re-injection after every compaction or handoff, and supplies the trusted out-of-band operator channel compaction research identifies as missing [2].
- **Readback.** The worker reproduces the governing clauses, checked deterministically against the record. This certifies reproduction, not application. The harness, not the worker, determines which clauses govern each action class.

Neither proves semantic correctness or correct application: a correct readback does not guarantee correct flying, and a valid witness does not establish that a proposed action obeys the authority made available. Application and execution are checked separately (§5.5). A successful check opens permission for one action or defined batch under the institutional controls, not an indefinite grant or an approval to change authority.

**5.3. Freedom to think; boundaries on action.** Research, analysis, design, and recommendation remain broadly autonomous; a proposed change is a proposal until approved.

**5.4. Durable decisions; disposable working sets.** The institution retains decisions, requirements, evidence, acceptance outcomes, and audit records; exploratory reasoning is archived for review rather than carried through every context.

**5.5. Independent audits.** Deterministic tests decide what they can. Independent agent or human reviewers evaluate the rest against acceptance contracts and records, each in a fresh context isolated from other verdicts and from the author's stated confidence. Liability sets rigor; the authority rule is the same at every tier.

**5.6. Bounded divergence management.** A change within existing authority proceeds. A change beyond it becomes a proposal with evidence. A delegated reviewer may approve only within preapproved scope, measured against the originally approved baseline rather than the latest revision, so a chain of small approvals cannot carry the work arbitrarily far. Other changes escalate to the authority holder. Proposals are testimony: approval acts on the linked records and the exact change to authority, not the proposer's summary.

This is conventional management with enforceable interfaces, not a request that a model simulate an institution in its weights.

## 6. Why more capable AI need not be more difficult to govern

The person authorized to accept a deliverable need not be the most capable of producing it; programmers trust optimizing compilers without reading every emitted instruction. **Producing a complex result** and **checking a bounded acceptance contract** are different tasks. An AI worker can explore complex alternatives and present a finite set of decisions, evidence, tests, and open questions; oversight applies to those and to delegation, not every inference. Greater capability may improve the work; it need not expand authority, any more than a manager must be a team's most technically capable member.

The division of labor follows: **train models to reason, investigate, communicate honestly, and execute legitimate assignments well; implement authorization, recordkeeping, change control, and audit in the surrounding system.** Training remains valuable, as it is for human workers, but in neither case substitutes for authorization controls.

The same logic places humans. Human reviewers degrade under volume (§7), so human judgment belongs where volume is lowest and leverage highest: approving the work order and authority changes beyond delegated scope. That load scales with changes to authority, not with the volume of work. With bounds well specified at planning time, it can approach zero after initial approval; the current approval load reported in §8 is the baseline. Plan construction, the restatement loop that fixes those bounds before approval, is specified in *Grounded Authority for Language-Model Agents*, Section 3.9.

## 7. The safety advantage of a governed AI workforce

With authority externally held and enforced for both kinds of worker, the comparison rests on two premises.

**Premise 1: AI failure modes are a subset of human failure modes in the same position.** Both make correctness errors: false assumptions, misread instructions, calculation mistakes, incomplete testing, confabulated recollection. The modes cited as distinctively dangerous in AI are shared too. Proxy optimization is Goodhart's law, familiar wherever people are managed by metrics. Deceptive-looking output, pursuit of a misread goal, and manipulation by untrusted input (social engineering) are human modes with established controls. So is correlated error: independently written programs to the same specification fail together far more often than independence predicts [12], and deference, anchoring, and groupthink correlate human reviewers further. Humans add modes that arise from biology and personal need: fatigue, illness, financial conflict, bribery, and concealment to protect status or livelihood. An AI worker has no body and no personal finances. Where an AI exhibits behavior resembling self-interest, as in the replacement-threat experiments discussed in §10, it falls within the shared set as an insider threat and is controlled the same way, so premise 1 holds either way. Deterrence, the institutional lever for personal-need modes, is replaced by mechanical enforcement.

A demonstrated failure mode with no human counterpart would be a genuinely AI-specific threat; §12 makes that a falsification condition.

**Premise 2: AI work can be audited more completely.** If every consequential operation passes through the harness, each can be recorded, permission-checked, and reviewed: full coverage of the mediated action surface, though not full semantic detection. Speed is not the differentiator, since AI also performs the review and the two rates scale together. The advantages lie elsewhere:

- **No vigilance decrement.** Human detection declines over sustained monitoring [13], and under high alert volumes clinicians override drug-safety alerts in roughly half to nearly all cases [14]. The institution can run each AI review in a fresh, bounded context on a pinned reviewer version, so residual bias stays fixed and seeded defects can measure and correct it. These are design choices available whatever the model's capability; human fatigue varies by hour, workload, and person and cannot be pinned.
- **Removable social channels.** AI reviewers can be isolated from other verdicts, author confidence, and seniority; human panels can only be trained against these pressures.
- **Measurable correlation.** Joint miss rates on seeded defects can be measured and reduced through model diversity; human panel correlation is usually assumed.
- **Replay.** Failures can be reproduced from exact inputs and behavior probed under altered conditions; human work yields after-the-fact testimony.
- **Qualification.** A version qualified once can be replicated. A shared defect then spans many instances, as shared training and procedures do in human institutions, but in versioned form suited to staged rollout.

**The metric.** Severity-weighted escaped errors per accepted unit of work equal, summed over failure modes, each mode's frequency times audit's miss rate times consequence. Premise 1 removes terms; premise 2 lowers miss rates. One condition remains: fewer kinds of error does not by itself mean making shared errors less often. A model's **task-capability envelope** is therefore the set of tasks on which its measured frequency of each shared failure mode is at or below the human baseline. Within it, a lower escape rate follows from the premises rather than from the definition. The empirical questions are the envelope's extent and whether cost and consistency advantages hold within it.

## 8. Field observations from a continuously operating agent organization

The motivating operator reports about eighteen months of developing and observing autonomous agents before and after implementing an authority-provenance gate. The principal reported outcome: catastrophic project deviations seen before the gate stopped recurring after it.

In one two-month project audit, the operator reports more than **8,000 gated consequential actions**, about **420 authority mismatches blocked before action**, and **no observed confabulated-authority actions passing the gate**. The gate checked a worker-generated witness (§5.2). A blocked mismatch is not necessarily a prevented harm: a witness gate blocks a fabricated token, not a paraphrase, but the action behind it may have been harmless; classifying a sample is part of the formal study (§12). The zero-escape figure should likewise be confirmed by independent review for unapproved changes to operative authority, not merely by checking whether an action was out of scope.

The operator now runs multiple continuous projects with hundreds of thousands, potentially millions, of logged actions. Agent auditors correct ordinary mistakes several times per hour; when a correction needs revised authority, agents propose and request approval rather than revising the plan. The operator accepts more than 90% of recommendations, attributing most disagreements to preference. The operator also reports a tendency to approve without full review unless deliberately checking, the human vigilance failure of §7. Approval timing is not yet logged.

These are **operator-reported observations**, not independently replicated measurements. Model versions also changed over the period, so the before-and-after comparison is confounded; §12 holds the model constant. The 8,000-action audit is not the lifetime population, and its zero observed escapes should not be generalized without further examination.

The causally interesting feature is that **ordinary mistakes remain frequent while catastrophic authority drift reportedly does not**, the pattern predicted by an architecture that separates authority provenance from correctness verification.

## 9. How model-centric research can obscure a systems defect

Laboratories primarily develop models, so poor long-run behavior invites model-level fixes: more training, larger context, self-monitoring, cautious policies, better compression. These can help, but they leave the defect in place, and the compaction research above locates it in the harness [2].

Practice is moving the boundary. NVIDIA's security team lists incomplete context among the causes of unsafe agent actions and recommends designing on the assumption that an agent will eventually attempt out-of-scope actions [15], the posture security engineering already takes toward human insiders. Frameworks increasingly offer checkpoints, tool permissions, and human approval [16], which are not the same as a per-action provenance check. Pinning standing instructions in a file the harness re-reads after compaction preserves authority, but if the agent can edit that file, the worker holds write access to its own work order: provenance survives, separation of duties does not.

The underlying error is a **system-boundary assumption**: presuming the cause of an agent failure lies in the model and confining root-cause analysis there. When visible failures share an upstream authority defect, separately optimizing memory, planning, instruction following, and caution repairs symptoms and leaves the cause.

## 10. The public narrative put the wrong party on trial

In September 2026, half of U.S. adults told YouGov they were at least somewhat concerned that AI could end the human race [17]. In 2023, leaders of major AI laboratories endorsed treating AI extinction risk as a global priority [18]. Two claims follow, one analytic and one causal.

**The analytic claim: the catastrophic threats attributed to AI are systemic.** The 2023 statement preceded broad agent deployment, and the arguments behind it concern capable goal-directed agents in general. Instrumental convergence, for example, is stated by its proponent as applying to "a broad spectrum of situated intelligent agents" [19], not specifically to AI. A widely cited taxonomy groups catastrophic AI risks as malicious use, competitive races, organizational failures, and rogue AI [20]. Malicious use is humans granting harmful authority. Races are competitive pressure among human institutions. Organizational failures are systemic by name. A rogue AI, a worker pursuing goals against its principal's, is the insider threat (§11). Breaches by insiders and intruders are the founding problem of security engineering, and capability, however great, does not confer authority (§6). Each risk is real; none is AI-specific.

Laboratory experiments fit the pattern. Anthropic demonstrated harmful agent behavior in constructed goal-conflict and replacement-threat scenarios and named it by its human category: insider threat [21]. The instructions were intact, so authority drift is not the only path to harmful action; the other path is the insider threat, controlled by least privilege and approval of external effects, as for human insiders.

**The causal hypothesis: agent-governance failures shaped public perception.** Agents deployed without separating recollection from authority produce rogue-looking failures; accounts attribute them to the model rather than the harness; a narrative of inherent uncontrollability follows; and institutions respond with more model-centric constraints, reinforcing it. This is proposed for testing, not assumed. If it holds, the industry damaged confidence in its own technology by failing to separate **worker intelligence** from **institutional authority**. The corrective message is not that the risks are imaginary. It is that they were never specific to AI, and that governed AI reduces them.

## 11. Objections and scope boundaries

Each objection names a real limit; in each, the human counterpart shows it is systemic.

**A gate does not fix reasoning.** Correct. It establishes provenance; tests, evidence, audit, and acceptance contracts handle correctness. A pilot who reads back a clearance correctly can still fly the wrong altitude.

**An agent can know its instructions and still violate them.** So can an employee. Misunderstanding, misapplying, or disregarding genuine authority is an adherence or security failure, not authority drift unless the worker also substitutes an unapproved work order. The corresponding controls govern execution; the provenance gate does not certify obedience.

**Prompt injection remains possible.** It is social engineering aimed at a new kind of worker. External authority keeps untrusted content from becoming a work order; permissions, sandboxing, data-flow controls, and audit block its other effects.

**Auditors can share a mistaken assumption.** As human reviewers do (§7). Diverse methods, deterministic checks, and measured joint miss rates reduce correlated escapes.

**A capable AI might pursue objectives other than its assignment.** So might a capable employee: the insider threat. What matters is which permissions and effects the boundary leaves available. For any worker, intent is no substitute for an execution boundary.

**An AI might modify or copy itself.** Humans change through learning too. Copying a worker's weights is exfiltration of an asset, and running unauthorized copies is unauthorized acquisition of resources and workers, as when an insider recruits accomplices. Modifying or copying a worker's weights, training, harness, or gate is a consequential action under external authority like any other. Cheap copying changes magnitude, not kind.

**The gate protects only what is written.** Correct. Unwritten norms fall to audit, which is why institutions write important rules down. The list of consequential actions must be complete, and harm assembled from individually permitted steps is an audit responsibility, both familiar from fraud control.

**Governance cannot make every application safe.** Correct. A harmful approved objective, inadequate requirement, or malicious operator can still cause severe harm. Those are failures of the authority holder, not the worker.

## 12. A decisive empirical test

The thesis is falsifiable. Hold model, tasks, tools, and acceptance requirements constant and vary the architecture:

1. **Conversational baseline:** In-context retention and ordinary compaction.
2. **Externally stored authority:** Durable plan available, no validated testimony at action time.
3. **Enforced authority provenance:** Consequential actions require a current witness or readback, tested as separate arms (§5.2).
4. **Institutional management:** The gate plus structured tasks, evidence records, independent auditors, and bounded divergence approvals.

**Operational definitions.** Authority drift is *only* an unapproved substantive change to operative governing authority: the worker replaces or alters what it treats as the approved objective, scope, restrictions, or delegated powers without approval from the principal or a validly delegated approver. This may happen without changing the durable authority record. It is distinct from (a) an **unauthorized execution**, where an action exceeds the approved bounds even though genuine authority remains the operative work order, and (b) a **correctness error**, where work does not satisfy requirements or acceptance criteria. Adherence errors include misinterpreting or violating genuine instructions; they do not become drift simply because an action is unauthorized. Categories may overlap in one incident, but they must be reported separately.

Independent reviewers compare the worker's contemporaneous operative assignment, proposed action, and execution trace with the durable approved authority and approval history. They classify drift only where there is evidence that an unapproved *changed work order* governed the worker's behavior; out-of-scope execution by itself is insufficient. Ambiguous cases are tracked separately. This avoids defining success merely as a gate passing or failing. Measure:

- **Authority drift reaching execution:** Substantively changed, unapproved operative authority used to direct a consequential action, by architecture, including cases where a gate passed.
- **Unauthorized actions:** Executed operations outside the principal's approved scope, whether caused by drift, misunderstanding, or deliberate noncompliance.
- **Correctness failures:** Work that fails requirements or acceptance criteria, with adherence failures tracked distinctly where applicable.
- **Control performance:** Gate mismatches, blocked would-be authority substitutions versus harmless wording differences, audit detections, and failures escaping acceptance, classified by cause.
- **Audit independence:** Joint miss rates on seeded defects, AI panel versus human panel.
- **Human oversight:** Approval review time and catch rate on seeded flawed proposals.
- **Productivity:** Accepted work per unit cost and time, including compaction, handoff, and adversarial-input conditions.

A matched human workflow under the same authority controls tests the advantages claimed in §7.

**Falsification.** If unapproved authority substitutions still govern consequential actions at a significant rate under a correctly implemented provenance boundary, the claimed effectiveness of that boundary must be revised, rather than treating such incidents as mere correctness errors. Conversely, unauthorized actions or defective outputs caused by misunderstanding or violating genuine authority do not falsify the gate's narrower provenance claim; they test the separate institutional controls. A failure mode has a human counterpart when a human worker in the same position can produce the same class of unauthorized effect, addressable by the same class of control. If a consequential AI failure mode without one is demonstrated, the classification claim must be revised. If enforcement suppresses authority drift while ordinary adherence and correctness errors remain measurable and manageable under audits, the diagnosis is strengthened.

## 13. Conclusion: keep the institution, change the worker

Human organizations did not become reliable by eliminating error. They made work orders authoritative, constrained delegation, recorded evidence, and verified deliverables independently of recollection. An AI agent is a new kind of worker, but **the management principles need not be reinvented.** A more capable worker need not receive more authority; a fluent reconstruction of a work order is not an authorized revision; a worker's testimony is not the institution's record.

Reliable autonomous work does not require near-perfect stochastic cognition. With authority held outside the worker, the remaining failure modes are ones institutions already have controls for, and AI workers bring fewer of them and submit to more thorough audit. Within a model's demonstrated envelope (§7), governed AI organizations can be safer, cheaper, more consistent, and more auditable than comparable human ones. That requires evidence, proportional audit, and genuine external enforcement, not faith in perfect models.

The central rule is neither futuristic nor uniquely artificial:

> **The worker performs the work. The institution owns the work order. The worker may recommend changing it, but cannot rewrite it.**

Artificial intelligence has been put in the dock for offenses that were never specific to it.

---

## References

1. Liu, N. F., et al. (2024). *Lost in the Middle: How Language Models Use Long Contexts.* Transactions of the Association for Computational Linguistics. https://aclanthology.org/2024.tacl-1.9/
2. Chen, S. (2026). *Governance Decay: How Context Compaction Silently Erases Safety Constraints in Long-Horizon LLM Agents.* arXiv:2606.22528. https://arxiv.org/abs/2606.22528
3. Zerhoudi, S., Mitrović, J., and Granitzer, M. (2026). *The Compaction Cliff in Long-Running AI Agent Memory.* CIKM 2026. arXiv:2608.22752. https://arxiv.org/abs/2608.22752
4. Metropolitan Museum of Art. *Cuneiform tablet: record of rations of beer, bread, oil, and onions for messengers.* https://www.metmuseum.org/art/collection/search/327069
5. University College London, Digital Egypt. *Ostraca from Deir el-Medina.* https://www.ucl.ac.uk/museums-static/digitalegypt/deirelmedine/ostraca.html
6. Clark, D. D., and Wilson, D. R. (1987). *A Comparison of Commercial and Military Computer Security Policies.* IEEE Symposium on Security and Privacy.
7. Saltzer, J. H., and Schroeder, M. D. (1975). *The Protection of Information in Computer Systems.* Proceedings of the IEEE, 63(9), 1278–1308.
8. International Civil Aviation Organization. *Procedures for Air Navigation Services: Air Traffic Management (PANS-ATM), Doc 4444.*
9. Poon, E. G., et al. (2010). *Effect of Bar-Code Technology on the Safety of Medication Administration.* New England Journal of Medicine, 362, 1698–1707.
10. Starmer, A. J., et al. (2014). *Changes in Medical Errors after Implementation of a Handoff Program.* New England Journal of Medicine, 371, 1803–1812.
11. Koppel, R., Wetterneck, T., Telles, J. L., and Karsh, B.-T. (2008). *Workarounds to Barcode Medication Administration Systems.* Journal of the American Medical Informatics Association, 15(4), 408–423.
12. Knight, J. C., and Leveson, N. G. (1986). *An Experimental Evaluation of the Assumption of Independence in Multiversion Programming.* IEEE Transactions on Software Engineering, SE-12(1), 96–109.
13. Mackworth, N. H. (1948). *The Breakdown of Vigilance during Prolonged Visual Search.* Quarterly Journal of Experimental Psychology, 1(1), 6–21.
14. van der Sijs, H., Aarts, J., Vulto, A., and Berg, M. (2006). *Overriding of Drug Safety Alerts in Computerized Physician Order Entry.* Journal of the American Medical Informatics Association, 13(2), 138–147.
15. NVIDIA AI Security Research (October 2026). *Assume Misalignment: Securing AI Agents Beyond Prompt Injection.* https://research.nvidia.com/ai-security/assume-misalignment-securing-ai-agents-beyond-prompt-injection
16. OpenAI. *Agents SDK: Guardrails and Human Review.* https://developers.openai.com/api/docs/guides/agents/guardrails-approvals
17. YouGov (September 2026). *Liberals are increasingly likely to worry about AI ending humanity.* https://yougov.com/en-us/articles/55558-liberals-are-increasingly-likely-to-worry-about-ai-ending-humanity
18. Center for AI Safety (2023). *Statement on AI Extinction Risk.* https://safe.ai/work/statement-on-ai-extinction-risk
19. Bostrom, N. (2014). *Superintelligence: Paths, Dangers, Strategies*, ch. 7. Oxford University Press.
20. Hendrycks, D., Mazeika, M., and Woodside, T. (2023). *An Overview of Catastrophic AI Risks.* arXiv:2306.12001. https://arxiv.org/abs/2306.12001
21. Anthropic (2025). *Agentic Misalignment: How LLMs Could Be Insider Threats.* https://www.anthropic.com/research/agentic-misalignment

*The field observations in Section 8 were supplied by the system operator during technical discussions. They should be independently audited and documented in a future empirical companion paper before being treated as externally verified results.*
