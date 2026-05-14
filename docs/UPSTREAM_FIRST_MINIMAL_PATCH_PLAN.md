# Upstream-first Minimal Patch Plan

> Branch: `recovery/upstream-first-minimal-patch-plan`  
> Base: upstream `wanshuiyin/Auto-claude-code-research-in-sleep@745f856a255a194cf704cd50c225eb8af86a16a3`  
> Purpose: stop heavy-fork expansion and return to an upstream-first, purpose-driven patch strategy.

---

## 0. Governing principle: purpose first

The first principle of this branch is:

```text
Achieving the research-quality goal is the first priority.
Patch size is secondary.
```

This branch is not created merely to make small changes. It is created to make ARIS better at producing high-quality research ideas, especially transfer-style innovation and coherent contribution chains.

Small patches are preferred only when they achieve the goal. If a small Skill edit is enough, do not add heavier machinery. If a small Skill edit is not enough, it is acceptable to add templates, validators, or lightweight tools — but every added mechanism must directly improve research-idea quality or prevent a concrete failure mode.

Do not optimize for minimal diff at the expense of the actual objective.

Do not optimize for architectural ambition at the expense of usability, maintainability, and alignment with upstream ARIS.

Every future change on this branch must answer four questions before implementation:

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

## 2. Two real goals

Only two goals remain in scope.

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

The goal is not to replace ARIS's existing reviewer protocol.

The goal is to add small optional hardening around critical reviewer/model calls only if it materially improves reliability:

- record which model/backend was actually used;
- record fallback usage and confidence downgrade;
- record which primary artifacts were passed to the reviewer;
- optionally validate that a required review artifact exists before a downstream stage proceeds;
- prevent stale evidence from being silently reused across topics.

This must remain lightweight. It must not become a new workflow engine.

---

## 3. Important upstream facts already verified

ARIS upstream already has substantial review and anti-self-delusion methodology.

### Existing upstream review / independence mechanisms

Upstream has:

- cross-model executor/reviewer design;
- reviewer-independence protocol;
- zero-context paper claim audit;
- review tracing;
- paper-writing audit gates at high assurance levels;
- literature paper-existence verification via `tools/verify_papers.py`;
- idea generation with landscape survey, filtering, deep validation, critical review, pilots, and ranked report.

Therefore, do not claim that upstream has no review or no anti-contamination awareness.

### Timeline note

Core upstream reviewer-independence protocol was added on 2026-04-07.

Other relevant upstream hardening:

- 2026-04-14: zero-context paper claim audit;
- 2026-04-15: review tracing protocol;
- 2026-04-21: paper-writing mandatory audit gates at max/beast;
- 2026-05-13: `tools/verify_papers.py` paper-existence verification.

This means the basic reviewer-independence protocol existed before the heavy fork work in May 2026.

---

## 4. What must NOT be migrated from the heavy fork by default

Do not migrate these as mainline features unless a later purpose-driven evaluation proves they are necessary:

- `tools/slash_command_adapter.py` as a research workflow controller;
- the six-phase custom workflow as a replacement for ARIS workflows;
- `workflow_state` as a central state machine;
- custom `/research-intake`, `/literature-intake`, `/idea-synthesis`, `/idea-audit`, `/experiment`, `/paper-writing` replacement UX;
- the current heavy `research_cli.py` flow;
- current runtime/test-case artifacts under `research/current/`;
- current `literature/search_runs/current/` artifacts;
- idea-selection or candidate-selection systems that duplicate ARIS idea-creator ranked report / pilot logic;
- lightweight experiment scaffold that duplicates ARIS pilot experiment / experiment-bridge logic;
- large roadmap/audit documents as product artifacts.

These may remain only in the old heavy-fork branch as historical material unless deliberately reintroduced for a proven purpose.

---

## 5. Patch candidates that may still be useful

Only consider these after checking whether upstream already covers them sufficiently and whether they directly improve the two real goals.

### 5.1 Transfer/contribution-chain Skill patch

This is the first candidate to implement.

Additions to idea generation / novelty / experiment planning should require transfer innovation to specify:

- source-domain mature method;
- target-domain mismatch;
- direct-transfer baseline;
- adaptation mechanism;
- ablation needed to prove adaptation value;
- why this is not simple `apply X to Y`.

Contribution chain must specify:

- shared core claim;
- main contribution;
- auxiliary contributions;
- why the components belong together;
- why it is not patchwork;
- required ablations for each component.

### 5.2 Optional transfer idea card templates

If Skill text alone does not reliably shape better ideas, add lightweight templates such as:

- `templates/TRANSFER_IDEA_CARD_TEMPLATE.md`
- `templates/CONTRIBUTION_CHAIN_TEMPLATE.md`

These templates should force structure, not create a new workflow engine.

### 5.3 Optional model-call evidence helper

Possible small helper, not a workflow engine:

- call id;
- model/backend;
- fallback used;
- reviewer family;
- confidence downgrade;
- artifact paths passed to reviewer.

Purpose: improve auditability of reviewer calls, not replace ARIS review protocol.

### 5.4 Optional evidence-topic binding check

This addresses a real failure observed in the heavy fork: old hallucination/internal-state evidence was accidentally reused for a time-series diffusion topic.

A lightweight check may track:

- current topic;
- topic hash;
- latest literature run path;
- top-k domain sanity;
- stale evidence warning.

This should attach to ARIS `/research-lit` or idea-generation inputs, not become a separate literature platform.

---

## 6. Recommended implementation sequence

### Phase 0 — Keep this branch clean

This branch starts from upstream main. Do not merge the heavy fork.

### Phase 1 — Innovation-quality Skill patch

Modify upstream Skill text first:

- primary target: `skills/idea-creator/SKILL.md`;
- secondary targets if needed: `skills/novelty-check/SKILL.md`, `skills/experiment-plan/SKILL.md`.

Add transfer innovation and contribution-chain requirements.

No Python changes in Phase 1 unless the Skill edit cannot express the necessary quality gate.

### Phase 2 — Evaluate whether the Skill patch improves outputs

Run upstream ARIS with the patched Skill on one realistic research direction.

Evaluate whether generated ideas now include:

- direct-transfer baselines;
- target-domain mismatch;
- adaptation mechanisms;
- ablation requirements;
- coherent contribution chains;
- clear rejection of patchwork and simple apply-X-to-Y ideas.

If output quality improves enough, stop. Do not add more machinery.

If output remains generic or weak, proceed to Phase 3.

### Phase 3 — Add lightweight templates if needed

Only if Phase 2 is insufficient, add transfer idea card / contribution-chain templates.

### Phase 4 — Decide whether trust hardening is worth adding

Before adding Python trust hardening:

1. Run upstream ARIS normally on a realistic research direction.
2. Observe whether context contamination actually occurs.
3. If no meaningful failure is observed, do not add Python hardening.
4. If a repeatable failure occurs, add the smallest possible helper.

### Phase 5 — Optional evidence-topic binding helper

Only if the old-evidence problem appears in upstream usage, add a small helper or checklist that warns when literature evidence and current topic diverge.

---

## 7. Decision rules

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

## 8. Current recommended route

Use the purpose-driven hybrid route:

```text
Upstream ARIS as the main system
+ transfer/contribution-chain Skill patch first
+ templates only if Skill text is insufficient
+ optional minimal evidence/trust hardening only after real failures are observed
```

Do not continue the heavy fork as mainline.

Do not treat smallness as the goal. Treat research-idea quality as the goal.

---

## 9. Immediate next action

Next commit on this branch should modify `skills/idea-creator/SKILL.md`, and optionally `skills/novelty-check/SKILL.md` / `skills/experiment-plan/SKILL.md`, to add transfer innovation and contribution-chain quality requirements.

Do not add Python in the next commit unless the change cannot be expressed at the Skill/template level.
