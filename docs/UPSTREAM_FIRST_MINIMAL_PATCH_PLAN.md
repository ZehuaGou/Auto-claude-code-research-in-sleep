# Upstream-first Minimal Patch Plan

> Branch: `recovery/upstream-first-minimal-patch-plan`  
> Base: upstream `wanshuiyin/Auto-claude-code-research-in-sleep@745f856a255a194cf704cd50c225eb8af86a16a3`  
> Purpose: stop heavy-fork expansion and return to an upstream-first patch strategy.

---

## 1. Current decision

The current heavy fork should not continue as the main development line.

The correct direction is:

```text
Original ARIS upstream workflow
+ small, targeted patches only where upstream is weak or missing
```

Do not continue building a separate six-stage workflow engine, slash-command adapter, workflow state machine, or replacement idea/experiment/paper pipeline.

---

## 2. Two real goals

Only two goals remain in scope.

### Goal A — Minimal trust / context-contamination hardening

The goal is not to replace ARIS's existing reviewer protocol.

The goal is to add small optional hardening around critical reviewer/model calls if useful:

- record which model/backend was actually used;
- record fallback usage and confidence downgrade;
- record which primary artifacts were passed to the reviewer;
- optionally validate that a required review artifact exists before a downstream stage proceeds;
- prevent stale evidence from being silently reused across topics.

This must remain lightweight. It must not become a new workflow engine.

### Goal B — Transfer innovation and contribution-chain guidance

Add research-method guidance to help ARIS distinguish:

- weak direct transfer: `apply X to Y`;
- valid transfer innovation: source-domain method + target-domain mismatch + adaptation mechanism;
- valid contribution chain: multiple medium ideas serving one shared core claim;
- invalid patchwork: unrelated tricks bundled into one paper.

This should be a small Skill-level patch, mainly to `skills/idea-creator/SKILL.md`, and possibly `skills/novelty-check/SKILL.md` / `skills/experiment-plan/SKILL.md` if needed.

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

## 4. What must NOT be migrated from the heavy fork

Do not migrate these as mainline features:

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

These may remain only in the old heavy-fork branch as historical material.

---

## 5. Patch candidates that may still be useful

Only consider these after checking whether upstream already covers them sufficiently.

### 5.1 Model-call evidence helper

Possible small helper, not a workflow engine:

- call id;
- model/backend;
- fallback used;
- reviewer family;
- confidence downgrade;
- artifact paths passed to reviewer.

Purpose: improve auditability of reviewer calls, not replace ARIS review protocol.

### 5.2 Evidence-topic binding check

This addresses a real failure observed in the heavy fork: old hallucination/internal-state evidence was accidentally reused for a time-series diffusion topic.

A lightweight check may track:

- current topic;
- topic hash;
- latest literature run path;
- top-k domain sanity;
- stale evidence warning.

This should attach to ARIS `/research-lit` or idea-generation inputs, not become a separate literature platform.

### 5.3 Transfer/contribution-chain Skill patch

Small additions to idea generation / novelty / experiment planning:

Transfer innovation must specify:

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

---

## 6. Recommended implementation sequence

### Phase 0 — Keep this branch clean

This branch starts from upstream main. Do not merge the heavy fork.

### Phase 1 — Small Skill patch only

Modify only upstream Skill text:

- primary target: `skills/idea-creator/SKILL.md`;
- optional secondary targets: `skills/novelty-check/SKILL.md`, `skills/experiment-plan/SKILL.md`.

Add transfer innovation and contribution-chain requirements.

No Python changes in Phase 1.

### Phase 2 — Decide whether trust hardening is worth adding

Before adding Python:

1. Run upstream ARIS normally on a realistic research direction.
2. Observe whether context contamination actually occurs.
3. If no meaningful failure is observed, do not add Python hardening.
4. If a repeatable failure occurs, add the smallest possible helper.

### Phase 3 — Optional evidence-topic binding helper

Only if the old-evidence problem appears in upstream usage, add a small helper or checklist that warns when literature evidence and current topic diverge.

---

## 7. Decision rules

### Keep a change only if all are true

- It directly serves Goal A or Goal B.
- Upstream does not already solve it well enough.
- It is small and low-maintenance.
- It does not replace ARIS's existing workflow.
- It does not require users to operate a new heavy system.

### Reject a change if any are true

- It duplicates upstream idea/pilot/review/paper workflow.
- It adds a new central workflow engine.
- It mostly exists because of earlier heavy-fork state bugs.
- It makes debugging harder than upstream.
- It requires a large amount of new documentation to explain.

---

## 8. Current recommended route

Use the hybrid route:

```text
Upstream ARIS as the main system
+ small transfer/contribution-chain Skill patch first
+ optional minimal evidence/trust hardening only after real failures are observed
```

Do not continue the heavy fork as mainline.

---

## 9. Immediate next action

Next commit on this branch should only modify `skills/idea-creator/SKILL.md` with a small transfer innovation / contribution-chain patch.

Do not add new Python in the next commit.
