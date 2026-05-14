# Upstream-first Purpose-driven Patch Plan

> Branch: `recovery/upstream-first-minimal-patch-plan`  
> Base: upstream `wanshuiyin/Auto-claude-code-research-in-sleep@745f856a255a194cf704cd50c225eb8af86a16a3`  
> Purpose: return to upstream ARIS as the main system, while preserving only the heavy-fork ideas that directly improve research-idea quality or prevent concrete failures.

---

## 0. Governing principle: purpose first

```text
Achieving the research-quality goal is the first priority.
Patch size is secondary.
```

This branch is not created merely to make small changes. It is created to make ARIS better at producing high-quality research ideas, especially transfer-style innovation and coherent contribution chains.

Small patches are preferred only when they achieve the goal. If a small Skill edit is enough, do not add heavier machinery. If a small Skill edit is not enough, templates, guardrails, validators, or lightweight tools are allowed — but every mechanism must directly improve research-idea quality or prevent a concrete failure mode.

Every future change must answer four questions:

1. Which goal does this change serve?
2. Why is upstream ARIS insufficient for this specific goal?
3. Why is this the lightest mechanism that can plausibly achieve the goal?
4. How will we know whether the change actually improves research-idea quality?

If a change cannot answer these questions, do not implement it.

---

## 1. Current decision

The current heavy fork should not continue as the main development line.

The correct direction is:

```text
Original ARIS upstream workflow
+ purpose-driven patches only where they are needed to improve research quality or prevent concrete failures
```

Do not continue building a separate six-stage workflow engine, slash-command adapter, workflow state machine, or replacement idea/experiment/paper pipeline unless a later evaluation proves that upstream plus lighter patches cannot achieve the research-quality goal.

---

## 2. Core goals

### Goal A — Research-quality improvement for transfer innovation

This is the primary goal.

ARIS should become better at generating, filtering, and advancing research ideas that are more than simple `apply X to Y` transfers.

The system should explicitly support:

- source-domain mature methods;
- target-domain opportunities;
- target-domain mismatch analysis;
- direct-transfer baselines;
- adaptation mechanisms;
- ablations proving that the adaptation matters;
- multiple medium-strength ideas forming one coherent contribution chain;
- a shared core claim that prevents patchwork.

The intended outcome is not prettier prompts. The intended outcome is higher-quality candidate ideas that are more likely to survive novelty check, pilot experiments, and reviewer scrutiny.

### Goal B — Minimal trust / context-contamination hardening

This goal is secondary and should not dominate the project.

The goal is not to replace ARIS's existing reviewer protocol. The goal is to add small optional hardening only if it materially improves reliability:

- record which model/backend was actually used;
- record fallback usage and confidence downgrade;
- record which primary artifacts were passed to the reviewer;
- optionally validate that a required review artifact exists before a downstream stage proceeds;
- prevent stale evidence from being silently reused across topics.

This must remain lightweight. It must not become a new workflow engine.

---

## 3. Why idea quality is the front-loaded bottleneck

For this project, the most important stage is not paper writing and not heavy experiments. The most important stage is finding a strong research idea.

A strong idea can make later experiments and paper writing tractable. A weak idea cannot be rescued by large experiments or polished writing.

Therefore, changes should prioritize:

- better problem framing;
- stronger novelty reasoning;
- clearer adaptation gap discovery;
- better rejection of weak ideas;
- better formation of coherent contribution chains;
- better pilot-readiness judgment.

Experiment planning matters, but it is downstream. It should verify and refine a promising idea; it should not compensate for a weak idea.

---

## 4. Transfer innovation doctrine

Transfer innovation is valid when it follows this pattern:

```text
source-domain mature method
→ target-domain opportunity
→ direct-transfer baseline
→ observed or predicted mismatch
→ target-specific adaptation
→ ablation proving the adaptation matters
```

A weak transfer idea says:

```text
Use method X from domain A on domain B.
```

A strong transfer idea says:

```text
Method X works in domain A because of assumption P.
Domain B violates or stresses assumption P in way Q.
Directly transferring X produces failure mode R.
We adapt X by mechanism S to address Q/R.
A direct-transfer baseline and ablation can test whether S is necessary.
```

Required fields for every transfer idea:

1. Source-domain mature method.
2. Why the method is strong in the source domain.
3. Target-domain opportunity.
4. Direct-transfer baseline.
5. Target-domain mismatch.
6. Adaptation mechanism.
7. Expected empirical signal.
8. Required ablation.
9. Closest-prior-work risk.
10. Reviewer attack point.

Reject or revise any transfer idea that lacks a direct-transfer baseline or target-domain mismatch.

---

## 5. Contribution-chain doctrine

A paper may be built from two or three medium-strength contributions if they serve one coherent core claim.

A valid contribution chain has:

1. Shared core claim.
2. Main contribution.
3. Auxiliary contribution(s).
4. Explanation of why the components belong together.
5. Explanation of why this is not patchwork.
6. Required ablation for each component.
7. A minimal pilot that can test the shared claim.

Invalid patchwork:

```text
Add trick A, trick B, and trick C because each sounds useful.
```

Valid contribution chain:

```text
Core claim: target-domain structure matters for diffusion-based anomaly detection.
Contribution 1 adapts the diffusion process to preserve temporal structure.
Contribution 2 uses the adapted denoising dynamics to localize anomalies.
Each ablation tests one part of the same claim.
```

Reject or revise any contribution chain that lacks a shared core claim.

---

## 6. Innovation verification doctrine

The heavy fork's novelty-check work contains one useful principle: evidence quality must constrain novelty claims.

Do not migrate the heavy workflow, but preserve this doctrine:

- `insufficient_evidence` cannot become `confirmed_novel`.
- `template_only` or weak literature evidence cannot support strong novelty claims.
- `valid_with_gaps` evidence should produce caution, not overconfidence.
- `already_done` must stop or force a pivot.
- `direct_transfer_only` should not be promoted to pilot-ready.
- A contribution chain must be checked for patchwork before pilot.
- A transfer idea must be checked against prior work that may already have transferred the same method.

Novelty checking should answer:

1. Has the source method already been transferred to the target domain?
2. Has the same target-domain mismatch already been identified?
3. Has the same adaptation already been proposed?
4. Is the proposed change merely a direct transfer?
5. Is the contribution chain one coherent claim or a patchwork bundle?
6. What evidence would be needed before the idea can be called pilot-ready?

---

## 7. Useful mechanisms from the heavy fork to salvage

The heavy fork contains useful design ideas in the innovation stage. Salvage the ideas, not the whole heavy system.

### 7.1 Literature → gap → idea → review → novelty → adversarial → selection pipeline

The heavy fork's agentic idea discovery design proposed a valuable staged chain:

```text
literature_scout
→ gap_extractor
→ idea_generator
→ idea_deduplicator
→ independent idea_reviewer
→ novelty_checker
→ adversarial_reviewer
→ final_selection
```

This is useful because it separates:

- literature understanding;
- gap extraction;
- idea generation;
- deduplication;
- independent review;
- novelty verification;
- adversarial criticism;
- final selection.

Do not migrate the whole Python pipeline by default. Instead, transplant the staged reasoning discipline into ARIS Skills and templates first.

### 7.2 Run isolation and immutable idea runs

The heavy fork design required each idea-discovery run to be saved separately and never overwritten.

Useful principle:

- each run has a run_id;
- raw idea cards are immutable;
- multiple runs do not merge into one giant untraceable idea report;
- later dedup/canonicalization references source runs instead of rewriting history.

This is worth preserving conceptually because repeated idea search is common and stale/merged idea state can corrupt judgment.

Implementation priority:

1. First add this as a Skill rule.
2. Add templates if needed.
3. Add tooling only if repeated manual runs become unmanageable.

### 7.3 IDEA_BANK / CANONICAL_IDEAS separation

The heavy fork's IDEA_BANK protocol is useful:

- IDEA_BANK stores only index/status.
- CANONICAL_IDEAS stores clean candidate files.
- Candidate files exclude generator trace, old scores, old praise, and user preference.
- Reviewer and novelty checker read one candidate at a time.
- Metadata/provenance can exist, but reviewers should not read it.

This is directly relevant to idea quality and context-contamination control.

Salvage this as a lightweight ARIS convention:

```text
idea-stage/IDEA_BANK.md
idea-stage/CANONICAL_IDEAS/CAND_*.md
idea-stage/REVIEWS/
idea-stage/NOVELTY/
idea-stage/ADVERSARIAL/
idea-stage/FINAL_SELECTION/
```

Do not introduce a central state machine unless the convention proves insufficient.

### 7.4 No strong idea found is a valid outcome

This is important and should be preserved.

The system must be allowed to say:

```text
no strong idea found
```

This is better than forcing weak ideas into experiments.

No strong idea found applies when:

- all ideas are killed;
- dedup shows all ideas are minor variants;
- novelty check returns already_done or insufficient_evidence for all survivors;
- adversarial review finds fatal flaws;
- all surviving ideas are direct_transfer_only or patchwork.

### 7.5 Reviewer isolation for candidate-level review

The heavy fork's idea-bank protocol correctly says reviewer input must exclude:

- other candidates;
- generator reasoning;
- previous scores;
- old praise;
- user preference;
- candidate provenance metadata.

This overlaps with upstream reviewer-independence but is useful because it specializes the rule for idea discovery.

Salvage it as a candidate-review rule in `idea-creator`, `exec-review`, and `novelty-check`.

### 7.6 Gap excerpt rather than whole raw run

The heavy fork used candidate-specific gap excerpts for review jobs.

This is useful because the reviewer gets enough context to judge the candidate without reading the full raw run.

Possible lightweight rule:

```text
Each CAND_*.md should reference one or more GAP_IDs.
Reviewers may read only the candidate and the relevant gap excerpt, not the full brainstorming run.
```

### 7.7 Innovation-verdict guardrails

The heavy fork's novelty-check discipline is useful:

- evidence state caps novelty verdict;
- insufficient evidence cannot be upgraded to confirmed novelty;
- direct transfer only cannot be pilot-ready;
- already-done stops or forces pivot;
- valid-with-gaps requires caution;
- contribution-chain candidates need patchwork check.

Salvage these into upstream Skill text first.

---

## 8. What must NOT be migrated from the heavy fork by default

Do not migrate these as mainline features unless a later purpose-driven evaluation proves they are necessary:

- `tools/slash_command_adapter.py` as a research workflow controller;
- the six-phase custom workflow as a replacement for ARIS workflows;
- `workflow_state` as a central state machine;
- custom `/research-intake`, `/literature-intake`, `/idea-synthesis`, `/idea-audit`, `/experiment`, `/paper-writing` replacement UX;
- the current heavy `research_cli.py` flow;
- current runtime/test-case artifacts under `research/current/`;
- current `literature/search_runs/current/` artifacts;
- heavyweight idea-selection/candidate-selection systems that duplicate ARIS idea-creator ranked report / pilot logic;
- lightweight experiment scaffold that duplicates ARIS pilot experiment / experiment-bridge logic;
- large roadmap/audit documents as product artifacts.

These may remain only in the old heavy-fork branch as historical material unless deliberately reintroduced for a proven purpose.

---

## 9. Patch candidates

Only consider these after checking whether upstream already covers them sufficiently and whether they directly improve the real goals.

### 9.1 Transfer/contribution-chain Skill patch

This is the first candidate to implement.

Additions to idea generation / novelty / experiment planning should require transfer innovation and contribution-chain quality fields.

### 9.2 Lightweight candidate templates

If Skill text alone does not reliably shape better ideas, add lightweight templates such as:

- `templates/TRANSFER_IDEA_CARD_TEMPLATE.md`
- `templates/CONTRIBUTION_CHAIN_TEMPLATE.md`
- `templates/CANONICAL_IDEA_TEMPLATE.md`

These templates should force structure, not create a new workflow engine.

### 9.3 IDEA_BANK convention

If repeated idea runs become hard to track, add a lightweight IDEA_BANK convention before adding Python tooling.

### 9.4 Innovation-verdict guardrails

Add guardrails to Skill text first. Add a validator only if the Skill-only version proves insufficient.

### 9.5 Optional model-call evidence helper

Possible small helper, not a workflow engine:

- call id;
- model/backend;
- fallback used;
- reviewer family;
- confidence downgrade;
- artifact paths passed to reviewer.

### 9.6 Optional evidence-topic binding check

Only if stale evidence actually appears in upstream usage, add a lightweight check for topic/evidence mismatch.

---

## 10. Recommended implementation sequence

### Phase 0 — Keep this branch clean

This branch starts from upstream main. Do not merge the heavy fork.

### Phase 1 — Innovation-quality Skill patch

Modify upstream Skill text first:

- primary target: `skills/idea-creator/SKILL.md`;
- secondary targets if needed: `skills/novelty-check/SKILL.md`, `skills/experiment-plan/SKILL.md`, `skills/exec-review/SKILL.md`.

Add:

- transfer innovation doctrine;
- contribution-chain doctrine;
- no-strong-idea-found as valid outcome;
- evidence-quality guardrails;
- candidate-level reviewer isolation;
- direct-transfer-only rejection or revise rule.

No Python changes in Phase 1 unless Skill text cannot express the quality gate.

### Phase 2 — Add lightweight templates if needed

Only if Phase 1 output remains generic or weak, add candidate templates.

### Phase 3 — Evaluate outputs

Run patched ARIS on one realistic research direction and evaluate whether generated ideas include:

- direct-transfer baselines;
- target-domain mismatch;
- adaptation mechanisms;
- ablation requirements;
- coherent contribution chains;
- clear rejection of patchwork and simple apply-X-to-Y ideas;
- novelty verdicts that respect evidence quality.

If output quality improves enough, stop. Do not add more machinery.

### Phase 4 — Add lightweight validators only if needed

Only if Skill/template instructions still allow weak ideas to pass as pilot-ready, add a small validator that checks idea cards for required fields and forbidden verdict upgrades.

### Phase 5 — Optional trust hardening

Only if repeatable context-contamination failures occur, add the smallest possible helper.

### Phase 6 — Optional evidence-topic binding helper

Only if stale evidence appears in upstream usage, add a small helper or checklist.

---

## 11. Decision rules

### Keep or add a change only if all are true

- It directly serves Goal A or Goal B.
- It improves research-idea quality or prevents a concrete failure mode.
- Upstream does not already solve it well enough.
- It is the lightest mechanism likely to work.
- It does not replace ARIS's existing workflow unless replacement is proven necessary.
- It does not require users to operate a new heavy system.

### Reject a change if any are true

- It duplicates upstream idea/pilot/review/paper workflow without measurable benefit.
- It adds a new central workflow engine without proving the Skill/template route failed.
- It mostly exists because of earlier heavy-fork state bugs.
- It makes debugging harder than upstream.
- It requires a large amount of new documentation to explain.
- It optimizes for architectural neatness rather than research-idea quality.

---

## 12. Current recommended route

Use the purpose-driven hybrid route:

```text
Upstream ARIS as the main system
+ transfer/contribution-chain Skill patch first
+ candidate-level isolation and no-strong-idea-found doctrine
+ innovation-verdict guardrails in Skill text
+ templates only if Skill text is insufficient
+ optional validators only if weak ideas still pass
+ optional minimal evidence/trust hardening only after real failures are observed
```

Do not continue the heavy fork as mainline.

Do not treat smallness as the goal. Treat research-idea quality as the goal.

---

## 13. Immediate next action

Next commit on this branch should modify upstream Skills, not Python:

- `skills/idea-creator/SKILL.md`
- `skills/novelty-check/SKILL.md`
- optionally `skills/experiment-plan/SKILL.md`
- optionally `skills/exec-review/SKILL.md`

The patch should add transfer innovation, contribution-chain quality requirements, candidate-level isolation, no-strong-idea-found as a valid result, and novelty-verdict guardrails.

Do not add Python in the next commit unless the change cannot be expressed at the Skill/template level.
