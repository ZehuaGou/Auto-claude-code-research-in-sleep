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
| LRQ-004 | Only OpenAlex source implemented | 2026-05-13 | medium | repair_queue | Add arXiv/Crossref adapters; Semantic Scholar deferred | fixed in Phase 20 | no for evidence summary, yes for stronger novelty_check | arXiv + Crossref adapters implemented. 3-source pipeline operational. Semantic Scholar deferred. |
| LRQ-005 | No full-text verification | 2026-05-13 | medium | repair_queue | Full-text acquisition layer later | partially addressed | yes for strong novelty claims | 8/10 papers now have extracted text (ftq_001-006 via LaTeX, ftq_002/004/008/010 via PDF). ftq_007/009 confirmed paywall_blocked (Phase 21E). Model-assisted review completed for all reviewable papers. |
| LRQ-006 | Title subtitle stripping may over-normalize | 2026-05-13 | low | accepted_limitation | Subtitle after ":" is stripped for dedup; may merge genuinely different papers | accepted for MVP | no | e.g., "X: A Survey" and "X: A Method" would merge |
| LRQ-007 | Year tolerance of ±1 may merge different papers | 2026-05-13 | low | accepted_limitation | Papers within 1 year with same normalized title are merged | accepted for MVP | no | Rare edge case for papers published in consecutive years |
| LRQ-008 | No citation-based ranking | 2026-05-13 | low | repair_queue | Add citation count when available from OpenAlex | open | no | Current ranking uses metadata completeness + recency only |
| LRQ-009 | Path separator mismatch causes contamination scan false positive | 2026-05-13 | high | fix_now | Add normalize_context_path() helper with traversal rejection, duplicate slash collapse, leading ./ strip; remove basename-only fallback; tighten staging prefix to tmp/ only | fixed in this module | yes — blocks every prepare on Windows when manifest uses backslashes and input uses forward slashes | Initial fix was expanded to reject traversal/spoofed basename paths. Added 15 self-tests including negative cases for .bak spoof, same-basename-different-dir, and parent traversal. |
| LRQ-010 | Core workflow self-test coverage gaps | 2026-05-13 | medium | repair_queue | Add focused self-tests for research_workflow / validate_model_invocation / context isolation integration | open | no, but should be addressed before larger automation expansion | Earlier report noted limited tests around core workflow tools. trusted_role_runner and validate_model_invocation self-tests have pre-existing Codex-related failures. |
| LRQ-011 | Native command / one-command orchestrator missing | 2026-05-13 | high | fix_now | Implemented research_cli.py with start/status/validate/repair-queue subcommands | partial — status/validate/repair-queue/start --dry-run done in Phase 18A/B/C; continue/live start remain | yes for product usability, no for internal manual testing | Phase 18A/B/C done; Phase 18D live start and continue remain future work. Dry-run planner shows planned workflow but does NOT execute stages. Target doc Section 5 requires native command layer. |
| LRQ-012 | Method refinement stage missing | 2026-05-13 | high | fix_now | Add generic method_refinement stage to research_default.yaml with output contract and validator | partial — method_refinement stage added and trusted output generated (Phase 19); readiness gate: needs_more_literature_evidence — experiment_plan blocked | yes before experiment_plan | Phase 19: method_refinement stage added to research_default.yaml. Trusted output generated via trusted_role_runner (deepseek-v4-pro). Validator PASS. Readiness gate is needs_more_literature_evidence. experiment_plan remains blocked until more literature evidence collected. |
| LRQ-013 | Multi-source adapters missing | 2026-05-13 | high | repair_queue | Add arXiv/Crossref adapters to literature pipeline; Semantic Scholar deferred | fixed in Phase 20 | yes for strong novelty claims | arXiv and Crossref adapters implemented. Semantic Scholar deferred (aggressive rate limits). Target doc Section 8.3 requires multi-source. |
| LRQ-014 | Full-text acquisition and parsing missing | 2026-05-13 | high | partial | Open-access acquisition + local Markdown extraction MVP implemented (Phase 21A); human review still pending | partial | yes for strong novelty claims and paper writing | Open-access full-text acquisition MVP implemented. arXiv LaTeX source preferred over PDF. Generated Markdown is local ignored artifact. No paywall bypass. experiment_plan remains blocked until critical reviews completed. |
| LRQ-015 | Status tracking layer incomplete | 2026-05-13 | high | near_term_mvp | Implement unified status summary in research_cli.py | partial — research_cli.py status/validate/repair-queue done; full autonomous tracking remains | yes for user-friendly automation | Phase 18A/B implemented status/validate/repair-queue in research_cli.py. Full status history and integrated /status slash command remain future work. |
| LRQ-016 | Semantic Scholar adapter deferred | 2026-05-13 | medium | repair_queue | Add Semantic Scholar adapter with aggressive rate-limit handling | open | no for current scope, yes for broader coverage | Deferred from Phase 20 due to aggressive rate limits. arXiv + Crossref + OpenAlex sufficient for MVP. |
| LRQ-017 | Forbidden-token false positive in top_k limitation text | 2026-05-13 | high | fix_now | Removed confirmed_novel from generated limitation wording | fixed in Phase 20B | yes — can trigger boundary/contamination false positive | Replaced with safe wording in literature_evidence_landing.py top_k generator. |
| LRQ-018 | Full-text review automation not yet trusted | 2026-05-13 | high | repair_queue | Review critical papers, then rerun trusted stages | open | yes before experiment_plan | Acquisition store exists with 10 papers acquired; human review of closest prior work (ICR Probe, INSIDE, Unsupervised Real-Time Detection) required before experiment_plan can advance. |
| LRQ-019 | OpenAlex URLs are metadata pages, not full text | 2026-05-13 | high | fix_now | Added full_text_status classification: source_acquired_unreviewed, likely_full_text, metadata_page_only, landing_page_only, manual_required | fixed | no, but clarifies evidence quality | 4/10 papers from openalex.org are metadata_page_only, 1 from DOI is landing_page_only. Only 4 arxiv_source + 1 arxiv_pdf provide actual full text potential. Manifest/queue consistency validated. |
| LRQ-020 | Full-text review found high_risk_overlap with ICR Probe | 2026-05-13 | high | repair_queue | Acquire full text for non-reviewable papers; compare ICR Probe methodology carefully | partially addressed | yes before experiment_plan | Phase 21D/E: 8/10 papers now reviewable. Phase 21D full_text_review: high_risk_overlap with ICR Probe (ftq_006). ftq_007/009 confirmed paywall_blocked — titles suggest potential overlap but full text unavailable. trajectory-anomaly framing remains distinguishable but high-risk per reviewer. |
| LRQ-021 | PDF extraction tool_missing (no library installed) | 2026-05-13 | medium | repair_queue | Install pymupdf, pypdf, or pdfminer.six; re-run extract-fulltext-store | open | no, but blocks PDF-based papers | ftq_002 (Lookback Lens) and ftq_008 (Hallucination Detection with Internal Layers) have PDF but extraction_status=tool_missing. Install one of: pymupdf, pypdf, pdfminer.six. |
| LRQ-022 | arXiv network timeout in China | 2026-05-13 | medium | accepted_limitation | Document network limitation; arXiv source/PDF downloads timeout in China | accepted | no, but limits alternative acquisition | arXiv e-print and PDF downloads fail with timeout in China. ftq_004 and ftq_010 have arXiv DOIs but cannot be downloaded. Use VPN or proxy for arXiv access. |
| LRQ-023 | ftq_007/ftq_009 IEEE paywall fully blocked | 2026-05-14 | high | accepted_limitation | Exhaustive OA search + Sci-Hub attempted; both confirmed closed access | accepted (paywall_blocked) | yes — titles suggest potential high overlap but full text unavailable | ftq_007 (ICMLA 2025) and ftq_009 (ICASSP 2025) are IEEE closed access. arXiv, OpenAlex, Crossref, Semantic Scholar all confirm is_oa=false. Sci-Hub RU: not-in-database. Sci-Hub SE: captcha-blocked. No author homepage or institutional repository found. These papers cannot be obtained without IEEE Xplore subscription. Their titles ("Late Internal Representations", "Internal State and Output Probability") suggest possible overlap with trajectory-anomaly framing. This gap must be acknowledged in novelty claims. |

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
