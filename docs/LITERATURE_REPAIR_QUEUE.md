# Literature Repair Queue

**Date:** 2026-05-13

---

## Policy

Every discovered issue must be classified as one of:

- **fix_now**: Must be fixed before next evidence run or next stage promotion.
- **repair_queue**: Should be fixed, but does not block current stage.
- **accepted_limitation**: Known limitation accepted for MVP. Must be documented and revisited.

No issue may be silently ignored. Every issue must be recorded in the table below with status tracked.

---

## Current Issues

| id | issue | discovered_at | severity | classification | action | status | blocking_next_stage | notes |
|----|-------|---------------|----------|----------------|--------|--------|---------------------|-------|
| LRQ-001 | Lookback Lens duplicate arXiv/conference versions not merged | 2026-05-13 | high | fix_now | Enhanced title-based dedup with normalized title matching and year tolerance | fixed in this module | yes — inflates top-k count | Same paper appeared as 2 canonical entries due to different DOIs (arXiv vs EMNLP) |
| LRQ-002 | Pharmaceutical Supply Chain false positive high relevance | 2026-05-13 | high | fix_now | Added strong domain negatives and title-level gating logic | fixed in this module | yes — pollutes top-k with irrelevant papers | Keyword overlap with hallucination/LLM terms caused false high relevance |
| LRQ-003 | Keyword scoring is not semantic relevance | 2026-05-13 | medium | accepted_limitation | Documented in top_k.md limitations section | accepted for MVP | no, but literature_search must mention limitation | Papers with hallucination keywords in non-relevant context may score high |
| LRQ-004 | Only OpenAlex source implemented | 2026-05-13 | medium | repair_queue | Add arXiv/Crossref/Semantic Scholar adapters later | open | no for evidence summary, yes for stronger novelty_check | Single source limits coverage and dedup quality |
| LRQ-005 | No full-text verification | 2026-05-13 | medium | repair_queue | Full-text acquisition layer later | open | yes for strong novelty claims | Evidence is metadata-only, full text not verified |
| LRQ-006 | Title subtitle stripping may over-normalize | 2026-05-13 | low | accepted_limitation | Subtitle after ":" is stripped for dedup; may merge genuinely different papers | accepted for MVP | no | e.g., "X: A Survey" and "X: A Method" would merge |
| LRQ-007 | Year tolerance of ±1 may merge different papers | 2026-05-13 | low | accepted_limitation | Papers within 1 year with same normalized title are merged | accepted for MVP | no | Rare edge case for papers published in consecutive years |
| LRQ-008 | No citation-based ranking | 2026-05-13 | low | repair_queue | Add citation count when available from OpenAlex | open | no | Current ranking uses metadata completeness + recency only |
| LRQ-009 | Path separator mismatch causes contamination scan false positive | 2026-05-13 | high | fix_now | Add normalize_path() helper to context_isolation_check.py for cross-platform comparison | fixed in this module | yes — blocks every prepare on Windows when manifest uses backslashes and input uses forward slashes | Windows Path() produces backslashes; input files use forward slashes; equality check fails |

---

## Usage

When a new issue is discovered during literature layer operation:

1. Add a new row to the table with a new LRQ-XXX id
2. Classify as fix_now / repair_queue / accepted_limitation
3. If fix_now: implement fix in current module sprint
4. If repair_queue: track in future sprints
5. If accepted_limitation: document in top_k.md limitations section
6. Update status when fixed

---

## Rules

- Issues must not be silently skipped
- fix_now issues must be resolved before next evidence promotion
- repair_queue issues must be reviewed at least once per module sprint
- accepted_limitation issues must be re-evaluated when dependencies change (e.g., when full-text verification is added)
