---
name: novelty-check
description: Verify research idea novelty against recent literature. Use when user says "查新", "novelty check", "有没有人做过", "check novelty", or wants to verify a research idea is novel before implementing.
argument-hint: [method-or-idea-description]
allowed-tools: WebSearch, WebFetch, Grep, Read, Glob, mcp__codex__codex
---

# Novelty Check Skill

Check whether a proposed method/idea has already been done in the literature: **$ARGUMENTS**

## Constants

- REVIEWER_MODEL = `gpt-5.5` — Model used via Codex MCP. Must be an OpenAI model (e.g., `gpt-5.5`, `o3`, `gpt-4o`)

## Instructions

Given a method description, systematically verify its novelty:

### Phase A: Extract Key Claims
1. Read the user's method description
2. Identify 3-5 core technical claims that would need to be novel:
   - What is the method?
   - What problem does it solve?
   - What is the mechanism?
   - What makes it different from obvious baselines?
   - If this is a transfer idea: what is the source-domain method, target-domain mismatch, direct-transfer baseline, and adaptation mechanism?
   - If this is a multi-component idea: what is the shared core claim, and how does each component support it?

### Phase B: Multi-Source Literature Search
For EACH core claim, search using ALL available sources:

1. **Web Search** (via `WebSearch`):
   - Search arXiv, Google Scholar, Semantic Scholar
   - Use specific technical terms from the claim
   - Try at least 3 different query formulations per claim
   - Include year filters for 2024-2026

2. **Known paper databases**: Check against:
   - ICLR 2025/2026, NeurIPS 2025, ICML 2025/2026
   - Recent arXiv preprints (2025-2026)

3. **Read abstracts**: For each potentially overlapping paper, WebFetch its abstract and related work section

4. **Transfer-specific search**: If the idea transfers a method from another field, explicitly search for:
   - the source method already applied to the target domain
   - the claimed target-domain mismatch
   - the proposed adaptation mechanism
   - the direct-transfer baseline or equivalent baseline

5. **Contribution-chain search**: If the idea combines multiple components, search both:
   - each component independently
   - the shared core claim tying the components together

### Phase C: Cross-Model Verification
Call REVIEWER_MODEL via Codex MCP (`mcp__codex__codex`) with xhigh reasoning:
```
config: {"model_reasoning_effort": "xhigh"}
```
Prompt should include:
- The proposed method description
- All papers found in Phase B
- Ask: "Is this method novel? What is the closest prior work? What is the delta?"
- For transfer ideas, ask: "Is this more than direct transfer? Has the source method already been transferred to this target domain? Does the adaptation solve a real target-domain mismatch?"
- For contribution-chain ideas, ask: "Is this one coherent core claim, or patchwork? Which component is the main contribution? Which ablations are required?"

### Phase D: Novelty Report
Output a structured report:

```markdown
## Novelty Check Report

### Proposed Method
[1-2 sentence description]

### Core Claims
1. [Claim 1] — Novelty: HIGH/MEDIUM/LOW — Closest: [paper]
2. [Claim 2] — Novelty: HIGH/MEDIUM/LOW — Closest: [paper]
...

### Closest Prior Work
| Paper | Year | Venue | Overlap | Key Difference |
|-------|------|-------|---------|----------------|

### Transfer Innovation Check
- Source-domain method: [method or N/A]
- Target-domain mismatch: [mismatch or N/A]
- Direct-transfer baseline: [baseline or missing]
- Adaptation mechanism: [mechanism or missing]
- Verdict: VALID_TRANSFER / DIRECT_TRANSFER_ONLY / INSUFFICIENT_EVIDENCE / N/A

### Contribution Chain Check
- Shared core claim: [claim or missing]
- Main contribution: [contribution]
- Auxiliary contribution(s): [contributions]
- Patchwork risk: LOW/MEDIUM/HIGH
- Required ablations: [list]
- Verdict: COHERENT_CHAIN / PATCHWORK_RISK / INSUFFICIENT_EVIDENCE / N/A

### Overall Novelty Assessment
- Score: X/10
- Evidence state: SUFFICIENT / VALID_WITH_GAPS / INSUFFICIENT / ALREADY_DONE
- Recommendation: PROCEED / PROCEED WITH CAUTION / REVISE / ABANDON
- Key differentiator: [what makes this unique, if anything]
- Risk: [what a reviewer would cite as prior work]

### Suggested Positioning
[How to frame the contribution to maximize novelty perception]
```

### Important Rules
- Be BRUTALLY honest — false novelty claims waste months of research time
- "Applying X to Y" is NOT novel unless the application reveals surprising insights
- Check both the method AND the experimental setting for novelty
- If the method is not novel but the FINDING would be, say so explicitly
- Always check the most recent 6 months of arXiv — the field moves fast
- Evidence quality caps novelty strength: insufficient evidence must not be reported as strong novelty
- `ALREADY_DONE` must force ABANDON or REVISE, not PROCEED
- `DIRECT_TRANSFER_ONLY` must not be treated as pilot-ready unless a real target-domain mismatch and adaptation are added
- A contribution chain without a shared core claim is patchwork risk, not a strong unified contribution
- Do not hide weak ideas from the user: report why they are not recommended and what would be needed to revive them
- **Anti-hallucination for Closest Prior Work.** Every paper in the prior-work table must pass pre-search verification via `tools/verify_papers.py` (3-layer arXiv / CrossRef / Semantic Scholar fallback) before being included. Never fabricate arXiv IDs, DOIs, or titles from memory; tag unverifiable entries as `[UNVERIFIED]` and surface the uncertainty to the user. Full protocol in [`shared-references/citation-discipline.md`](../shared-references/citation-discipline.md) § Pre-Search Verification Protocol.

## Review Tracing

After each `mcp__codex__codex` or `mcp__codex__codex-reply` reviewer call, save the trace following `shared-references/review-tracing.md`. Use `tools/save_trace.sh` or write files directly to `.aris/traces/<skill>/<date>_run<NN>/`. Respect the `--- trace:` parameter (default: `full`).
