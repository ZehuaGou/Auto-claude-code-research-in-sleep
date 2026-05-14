# Doctrine

> Branch: `recovery/upstream-first-minimal-patch-plan`  
> Base: upstream `wanshuiyin/Auto-claude-code-research-in-sleep@745f856a255a194cf704cd50c225eb8af86a16a3`  
> Purpose: use upstream ARIS as the main system and add only purpose-driven patches that clearly improve research-idea quality.

---

## 0. First principle: purpose first

```text
Improving research-idea quality is the first goal.
Patch size, implementation style, and tooling are secondary.
```

This branch is not about making small changes for their own sake, and it is not about making large architectural changes for their own sake.

If one Skill sentence can achieve the goal, change only that sentence.  
If Skill text is not enough, consider a lightweight template.  
If templates are still not enough, and a repeatable concrete failure appears, consider the smallest possible tool.  
Do not add mechanisms just because they look architecturally clean, make the process feel complete, or preserve effort from the old heavy fork.

Every future change must answer:

1. Which concrete goal does this change serve?
2. Why is upstream ARIS insufficient for that goal?
3. Is this the lightest mechanism likely to achieve the goal?
4. How will we know whether it actually improves research-idea quality?

If these questions cannot be answered, do not implement the change.

---

## 1. Current direction

Use upstream ARIS as the main workflow.

```text
Upstream ARIS
+ research-idea-quality Skill patches
+ lightweight templates only if needed
+ minimal tooling only after repeated real failures
```

Do not continue the current heavy-fork mainline.

Do not migrate by default:

- the custom six-stage workflow;
- slash command adapter as a central workflow controller;
- `workflow_state` as a central state machine;
- IDEA_BANK / CANONICAL_IDEAS as a toolized system;
- run-isolation tooling;
- candidate-selection tooling;
- lightweight experiment scaffold;
- large roadmap / audit documents.

These are not banned forever, but there is currently insufficient evidence that they are worth adding.

---

## 2. Core goal: stronger research ideas

The most important stage is research-idea discovery and verification.

Experiments, paper writing, and result presentation come later.  
A weak idea is hard to rescue downstream.  
A strong idea makes later experiments a matter of verification and refinement.

The current patch scope is limited to three goals:

1. Transfer innovation must not stop at `apply X to Y`.
2. Multiple medium-strength ideas must form a coherent contribution chain, not patchwork.
3. Novelty checking must not turn insufficient evidence, direct transfer, or already-done work into a strong novelty claim.

---

## 3. Transfer innovation rules

Transfer innovation is not low-quality by default.  
Simple wrapper-style transfer is low-quality.

Weak transfer:

```text
Use method X from domain A on domain B.
```

Strong transfer:

```text
X works in domain A because of assumption P.
Domain B has condition Q, so P is not fully valid.
Directly transferring X exposes failure mode R.
We introduce adaptation mechanism S to address Q/R.
A direct-transfer baseline and ablation prove that S is necessary.
```

Every transfer idea must clearly specify:

1. source-domain mature method;
2. why the source method works in its original domain;
3. target-domain opportunity;
4. direct-transfer baseline;
5. target-domain mismatch;
6. adaptation mechanism;
7. why the adaptation solves the mismatch;
8. required ablation;
9. closest-prior-work risk;
10. reviewer attack point.

A transfer idea without a direct-transfer baseline or target-domain mismatch should not be recommended for pilot.

---

## 4. Contribution-chain rules

Two or three medium-strength contributions can form a paper only if they support the same shared core claim.

Valid contribution chain:

```text
Core claim: target-domain structure matters for the method.
Contribution 1: adapt the core method to target-domain structure.
Contribution 2: use that adaptation to improve detection, localization, or interpretability.
Ablations show that each component supports the same core claim.
```

Invalid patchwork:

```text
Add trick A, trick B, and trick C because each might help.
```

Every contribution chain must clearly specify:

1. shared core claim;
2. main contribution;
3. auxiliary contribution(s);
4. how each component supports the same claim;
5. why this is not patchwork;
6. ablation for each component;
7. minimal pilot for the shared claim.

A combined idea without a shared core claim should not be recommended for pilot.

---

## 5. Innovation verification rules

The useful lesson from the old heavy fork is not the workflow. It is this principle:

```text
Evidence quality must cap novelty verdict strength.
```

Therefore:

- `insufficient_evidence` cannot be upgraded to `confirmed_novel`;
- weak literature evidence cannot support a strong novelty claim;
- `already_done` must force stop or pivot;
- `direct_transfer_only` cannot be recommended for pilot;
- contribution chains must be checked for patchwork;
- transfer ideas must be checked against prior work that may already have made the same transfer.

Novelty check must answer:

1. Has the source method already been transferred to the target domain?
2. Does the target-domain mismatch really exist?
3. Has the adaptation already been proposed?
4. Is the idea merely direct transfer?
5. Does the contribution chain have a shared core claim?
6. What evidence is still missing before the idea can enter pilot?

Start by encoding this in `skills/novelty-check/SKILL.md` and `skills/idea-creator/SKILL.md`.  
Do not start with a Python validator.

---

## 6. User oversight principle

The system may decide not to recommend an idea for pilot, but it must not hide the candidate from the user.

If no idea is strongly recommended, output:

```text
No current pilot recommendation.
```

Still show:

- all candidate ideas;
- why each is not recommended;
- what evidence is missing;
- whether the user may override;
- whether the next step is more literature, idea revision, or changing direction.

Do not design the system to silently discard potentially useful ideas before the user sees them.

---

## 7. Lightweight candidate-review isolation

Upstream ARIS already has reviewer-independence rules. This branch does not rebuild an isolation system.

Only add one lightweight idea-stage rule:

```text
When reviewing a candidate, provide only the candidate itself and directly relevant literature/gap evidence.
Do not provide the full brainstorming trace, old scores, old praise, user preference, or unrelated candidate ideas.
```

This is only a Skill rule. It does not introduce IDEA_BANK tooling, central state, or a Python runner.

---

## 8. Tooling principle

Default to no tooling.

Consider tooling only if the system repeatedly fails after Skill patches, for example:

- it still omits direct-transfer baselines;
- it still recommends direct-transfer-only ideas for pilot;
- it still reports evidence-insufficient ideas as confirmed novelty;
- it still treats patchwork without a shared core claim as a contribution chain.

Even then, use the smallest checker possible, such as a field-completeness check or forbidden-verdict-upgrade check.

Do not build:

- a new workflow engine;
- a large state machine;
- database-like IDEA_BANK tooling;
- automatic candidate-selection tooling;
- a replacement for upstream ARIS experiment workflow.

---

## 9. Do not rebuild upstream capabilities

Upstream ARIS already has:

- cross-model review;
- reviewer independence;
- idea generation / filtering / deep validation / pilot / ranked report;
- novelty check;
- experiment bridge;
- paper / citation / claim audit;
- paper verification.

This branch does not rebuild those main workflows.

Only add:

```text
transfer-innovation quality rules
+ contribution-chain quality rules
+ novelty-verdict guardrails
+ lightweight candidate-review input rule
```

---

## 10. Near-term implementation scope

Next steps should modify Skill files only, not Python.

Priority files:

1. `skills/idea-creator/SKILL.md`
2. `skills/novelty-check/SKILL.md`
3. `skills/experiment-plan/SKILL.md`

Optional file:

4. `skills/exec-review/SKILL.md`

For now:

- do not add templates;
- do not add tools;
- do not change workflow;
- do not run experiments;
- do not call models.

---

## 11. No other high-confidence method for now

Beyond the items above, there is currently no other high-confidence, high-impact, low-complexity method that upstream ARIS clearly missed for improving research-idea quality.

If future real runs reveal a stable failure mode, add the smallest mechanism targeted at that failure. Do not invent features in advance.
