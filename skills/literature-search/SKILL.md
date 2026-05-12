---
name: literature-search
description: Gather and normalize literature evidence via trusted workflow. Use after research-contract when evidence-based novelty checking is needed.
argument-hint: [research/current/input_normalization.md]
allowed-tools: Bash(*), Read, Write, Grep, Glob, WebSearch, WebFetch
---

# /literature-search

## What it is

`/literature-search` is a **native ARIS command wrapper**. It does not organize the final prompt, does not select models, does not call models directly, and does not produce trusted conclusions on its own.

It maps to the `literature_search` workflow stage and delegates everything to the ARIS workflow stack.

## User invocation

```
/literature-search
```

## How it works

1. User invokes `/literature-search`
2. Skill maps to the `literature_search` workflow stage
3. Skill calls `tools/research_workflow.py prepare literature_search`
4. `context_isolation_check.py` scans inputs — FAIL stops execution
5. `trusted_role_runner.py` executes `literature_scout` role (DeepSeek API)
6. `validate_model_invocation.py --role literature_scout` — PASS means search is verified
7. If `allowed_next_stage=false`, the skill stops

## WebSearch / WebFetch usage boundaries

WebSearch and WebFetch are **allowed tools** for this skill, but with strict limits:

- WebSearch **may** be used to discover candidate paper links and titles
- WebFetch **may** be used to read abstract or metadata from publicly accessible URLs (arXiv, Semantic Scholar, OpenAlex)
- WebSearch/WebFetch results **must not** be treated as confirmed novelty evidence
- WebSearch/WebFetch results **must not** replace full-text evidence
- Do not bulk scrape any source
- Do not attempt to bypass paywalls
- Do not fetch copyrighted material illegally
- All evidence entries must record: URL, title, authors, year, source, fetched_or_manual

## Output structure

`research/current/trusted_outputs/literature_search.md` must contain:

### Literature Evidence Summary
Structured summary of relevant papers found.

### Evidence Entries
For each paper, record:
- title
- authors
- year
- source (e.g. arXiv, Semantic Scholar)
- URL / DOI
- fetched_or_manual (how obtained)
- relevance_to_research_contract (brief)
- method_or_finding_relevant_to_claim (brief)

### Search Process Record
- sources searched
- query or topic used
- date of search
- number of papers found

### Evidence Gaps
Papers that could not be obtained, especially if they may be closest prior work.

## What the skill does NOT do

- Does NOT organize the final prompt sent to the model
- Does NOT select the model or backend
- Does NOT directly call models except through trusted_role_runner
- Does NOT produce a trusted novelty verdict
- Does NOT bypass `validate_model_invocation.py`
- Does NOT treat search results as confirmed evidence
- Does NOT treat paper abstracts as confirmed novelty proof

## Hard rules

- No `validate_model_invocation.py` PASS = no trusted output
- `allowed_next_stage=false` = stop immediately
- WebSearch results are candidate evidence, not confirmed evidence
- All literature evidence must record source URL, title, authors, year, source
- Evidence that could not be verified must be flagged in Evidence Gaps
- Do not produce a verdict — novelty_check role does that
