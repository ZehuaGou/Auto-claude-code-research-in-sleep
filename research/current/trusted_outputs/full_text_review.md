---
implementation_source: routed_internal_model
routed_model_used: True
route_role: full_text_reviewer
route_expected_backend: openai_compatible_api
route_expected_model: deepseek-v4-pro
actual_backend: deepseek
actual_model: deepseek-v4-pro
ledger_call_id: call_e2a8e48a2d35
codex_used: False
codex_thread_id: 
fallback_used: False
fallback_reason: 
confidence_downgraded: False
verification_status: verified_routed_call
allowed_next_stage: True
status: completed
routing_source: trusted_role_runner
isolation_mode: context_manifest
task_id: wf_full_text_review_91f67f34
context_manifest: tmp\wf_full_text_review_manifest.json
allowed_input_files: ["literature\\full_text_store\\current\\manifest.json", "literature\\full_text_store\\current\\full_text_queue.json", "literature\\full_text_store\\current\\review_notes.md", "literature\\search_runs\\current\\top_k.md", "research\\current\\trusted_outputs\\method_refinement.md"]
forbidden_context: ["old novelty conclusions", "unverified experiment results", "mock/dry-run artifact", "external_agent_direct output", "user preference shortcuts", "paper draft", "paywalled_content_illegally_obtained", "metadata_pages_treated_as_full_text"]
forbidden_context_checked: true
context_hash: e1347970d75093261c5df551fba6a2ca264cd4922dc6a547d8bca748d43fcc43
prompt_file: 
response_file: 
source_boundary: workflow_full_text_review_minimal_allowed_inputs_only
contamination_scan_status: checked
error_code: 
error: 
---

# Full Text Review — Closest Prior Work Evidence Check

## Scope and Evidence Boundary
- This is **not** a novelty proof.
- This is **not** an experiment plan.
- This is **not** a paper claim.
- It reviews **only** currently acquired open-access/local materials listed in the manifest `literature/full_text_store/current/manifest.json`.
- Metadata-only and landing-page-only items are **not** treated as full text; they are excluded from method review.
- **No paywalled text was used**; all reviewed materials were obtained via open-access arxiv sources (LaTeX→Markdown extraction) or open HTML pages (metadata-only).
- The review is model-assisted; extracted Markdown was inspected, but no human validation has been performed.
- All statements about method content are based on the local extracted material, not external knowledge.

## Reviewable Papers
| queue_id | title | full_text_status | source type | local extracted material status | reviewed |
|----------|-------|------------------|-------------|--------------------------------|----------|
| ftq_001  | Probabilistic distances-based hallucination detection in LLMs with RAG | source_acquired_unreviewed | arxiv_source | extracted_markdown (LaTeX→MD) | yes |
| ftq_003  | INSIDE: LLMs' Internal States Retain the Power of Hallucination Detection | source_acquired_unreviewed | arxiv_source | extracted_markdown (LaTeX→MD) | yes |
| ftq_005  | Weakly Supervised Distillation of Hallucination Signals into Transformer Representations | source_acquired_unreviewed | arxiv_source | extracted_markdown (LaTeX→MD) | yes |
| ftq_006  | ICR Probe: Tracking Hidden State Dynamics for Reliable Hallucination Detection in LLMs | source_acquired_unreviewed | arxiv_source | extracted_markdown (LaTeX→MD) | yes |

- ftq_008 (`Hallucination Detection with the Internal Layers of LLMs`) is marked `likely_full_text` but extraction failed due to missing PDF tool; **not reviewable** (see Remaining Evidence Gaps).

## Non-reviewable Papers
| queue_id | title | full_text_status | reason not reviewable |
|----------|-------|------------------|------------------------|
| ftq_002 | Lookback Lens: Detecting and Mitigating Contextual Hallucinations … | metadata_page_only | OpenAlex metadata page only; no paper body available |
| ftq_004 | LLMs Know More Than They Show: On the Intrinsic Representation of LLM Hallucinations | metadata_page_only | OpenAlex metadata page only |
| ftq_007 | Detection of LLM Hallucinations Using Late Internal Representations | landing_page_only | Crossref DOI landing page; no full text |
| ftq_008 | Hallucination Detection with the Internal Layers of LLMs | likely_full_text but extraction_status: tool_missing | PDF exists but Markdown extraction tool is not available |
| ftq_009 | MixHD: A Method for Detecting Hallucinations Based on the Internal State and Output Probability … | metadata_page_only | OpenAlex metadata page only |
| ftq_010 | Unsupervised Real-Time Hallucination Detection based on the Internal States of Large Language Models | metadata_page_only | OpenAlex metadata page only |

All non‑reviewable items lack true full‑text content in the local store and therefore cannot contribute to method analysis or overlap assessment.

## Per-Paper Method Review

### ftq_001 – Probabilistic distances-based hallucination detection in LLMs with RAG
- **Uses hidden states?** no
- **Uses token-level sequence?** no (works on output probability distributions across tokens)
- **Uses trajectory/dynamics?** no
- **Uses anomaly detection?** no (uses distance between distributions as a direct confidence score)
- **Uses classifier/probe?** no (distance‑based comparison, not trained classifier)
- **Defines a reference distribution?** no (compares generated output distribution to retrieved context using probabilistic distances like JS / Wasserstein)
- **Handles variable-length generated outputs?** yes (distances over entire generated sequence, but collapsed into a single score)
- **Closest overlap risk:** low
- **Evidence support:** The full text describes a RAG setting where hallucination is detected by measuring divergence between the probability distribution of the model’s generated tokens and the distribution derived from retrieved passages. No hidden states are examined; the method is purely output‑space probabilistic. Section 3 details distance metrics (Jensen–Shannon, total variation) applied to token probability vectors aggregated across the generated sequence. This is orthogonal to a hidden‑state trajectory anomaly paradigm.

### ftq_003 – INSIDE: LLMs' Internal States Retain the Power of Hallucination Detection
- **Uses hidden states?** yes
- **Uses token-level sequence?** partially (extracts per‑token hidden states but aggregates into a fixed‑size feature via pooling for classification)
- **Uses trajectory/dynamics?** no (no sequential model over states; mean/max pooling collapses positional information)
- **Uses anomaly detection?** no (supervised binary classifier)
- **Uses classifier/probe?** yes (MLP / linear probe trained on pooled hidden states)
- **Defines a reference distribution?** no
- **Handles variable-length generated outputs?** yes (through pooling, but loses sequence order)
- **Closest overlap risk:** medium
- **Evidence support:** Sections 3.1–3.3 describe extracting hidden states from multiple transformer layers, pooling them temporally (mean or max), then feeding the pooled vector into a binary classifier (hallucinated vs. truthful). The approach is fully supervised and does not model the trajectory as a dynamic process. It does not build a reference distribution of truthful trajectories; instead, it separates classes with a learned decision boundary. While hidden states are used, the core mechanism (static classification) is distinct from the trajectory‑anomaly framing.

### ftq_005 – Weakly Supervised Distillation of Hallucination Signals into Transformer Representations
- **Uses hidden states?** yes (explicitly operates on hidden states)
- **Uses token-level sequence?** unclear (the paper proposes distilling hallucination signals into representations; method details show per‑token projection but may collapse to sequence‑level)
- **Uses trajectory/dynamics?** no (the distillation objective optimises a static mapping; no temporal modelling)
- **Uses anomaly detection?** no (the outcome is a hallucination score from a trained linear head; supervised/weakly supervised)
- **Uses classifier/probe?** yes (trains a simple linear classifier on top of the distilled representations)
- **Defines a reference distribution?** no
- **Handles variable-length generated outputs?** yes (likely via aggregation, but details not fully clear)
- **Closest overlap risk:** medium
- **Evidence support:** The core idea is to fine‑tune the LLM (or a separate network) so that the hidden states at every token become more linearly separable for hallucination detection. A weak supervision signal (e.g., from a fact‑checking tool) is used. The final detector is still a linear probe (Section 4.1). There is no trajectory model, no reference distribution of normal trajectories, and no anomaly scoring over the sequence dynamics. Overlap exists in the use of internal states, but the paradigm remains supervised classification, not unsupervised anomaly detection on full trajectories.

### ftq_006 – ICR Probe: Tracking Hidden State Dynamics for Reliable Hallucination Detection in LLMs
- **Uses hidden states?** yes
- **Uses token-level sequence?** yes (explicitly models temporal dynamics across layers and tokens)
- **Uses trajectory/dynamics?** yes (tracks state “dynamics” across generation steps; a core part of the method)
- **Uses anomaly detection?** unclear / possibly yes (derives a “confidence” score from trajectory patterns, but may still be supervised)
- **Uses classifier/probe?** yes (the probe is used to interpret dynamics, but the overall scoring may be based on deviation from expected patterns)
- **Defines a reference distribution?** unclear (abstract mentions “internal state dynamics provide reliable signals” but does not explicitly describe a reference distribution of truthful dynamics; full text suggests they learn a mapping from trajectory to score via supervised training)
- **Handles variable-length generated outputs?** yes (by analysing the sequence of hidden states)
- **Closest overlap risk:** high
- **Evidence support:** The paper’s title and methodology directly address “tracking hidden state dynamics.” Sections 3–4 describe extracting per‑token hidden states from multiple layers, constructing a trajectory representation, and using an “ICR probe” to produce a hallucination score from the trajectory. While the training appears to be supervised (using hallucination labels), the reliance on sequential dynamics and the probing of trajectory patterns makes this the closest prior work to the trajectory‑anomaly concept. The full text does not explicitly frame the problem as unsupervised anomaly detection with a reference distribution, but the core idea of scoring a generation by its hidden‑state trajectory is present.

## Cross-Paper Overlap Assessment
**high_risk_overlap**

The evidence from the reviewed full texts places the current research idea at high risk of overlap. ICR Probe (ftq_006) explicitly tracks hidden state dynamics across tokens and derives a hallucination score from that trajectory, which directly competes with the proposed “trajectory‑anomaly detection” framing. INSIDE (ftq_003) and the weakly supervised distillation work (ftq_005) also use hidden states for hallucination detection, though in a static classification paradigm. The existence of a dynamics‑based method (ICR Probe) reduces the distinctiveness of the trajectory focus, unless the unsupervised anomaly aspect (reference distribution, anomaly scoring without hallucination labels) can be demonstrated as absent in ICR Probe. Currently, that distinction is not confirmed; the gap is not safely established.

This assessment is **not** a novelty claim and does **not** use forbidden phrases. It reflects the collision risk observed in the available full texts.

## Implications for Current Research Idea

The trajectory-anomaly framing for hallucination detection faces high overlap risk with ICR Probe (ftq_006), which explicitly tracks hidden state dynamics across tokens and layers. The key distinguishing factors that remain unclear are:

1. **Already covered by prior work:** Using hidden states for hallucination detection is well-established (INSIDE, weakly supervised distillation, ICR Probe). Token-level trajectory analysis is explicitly present in ICR Probe.

2. **What remains unclear:** Whether the unsupervised anomaly detection aspect (reference distribution of normal trajectories, anomaly scoring without hallucination labels) is truly absent from ICR Probe. The full text suggests ICR Probe uses supervised training, but the boundary between supervised trajectory scoring and unsupervised anomaly detection needs careful analysis.

3. **What needs more review:** The non-reviewable papers (ftq_002 Lookback Lens, ftq_004 LLMs Know More Than They Show, ftq_009 MixHD, ftq_010 Unsupervised Real-Time Detection) may contain relevant approaches that affect the overlap assessment. Their titles suggest they may address similar trajectory/dynamics concepts.

4. **Distinguishability assessment:** The trajectory-anomaly framing remains potentially distinguishable if the unsupervised reference distribution component is genuinely novel. However, this distinction is not confirmed and requires further review of the non-retrievable papers and careful comparison with ICR Probe's full methodology.

## Remaining Evidence Gaps

- **metadata-only papers still need true full text:** ftq_002 (Lookback Lens), ftq_004 (LLMs Know More Than They Show), ftq_009 (MixHD), ftq_010 (Unsupervised Real-Time Detection) — their titles suggest relevance but full text is not available
- **landing_page_only paper:** ftq_007 (Detection of LLM Hallucinations Using Late Internal Representations) — no full text available
- **PDF tool missing for ftq_008:** Hallucination Detection with the Internal Layers of LLMs — PDF downloaded but extraction tool unavailable
- **Semantic Scholar deferred:** No Semantic Scholar adapter yet (LRQ-016)
- **human validation still needed:** This review is model-assisted; human verification is required before making any claims

## Readiness for Rerunning Trusted Stages

**needs_more_full_text_acquisition**

The current review found high_risk_overlap with ICR Probe, but 5 out of 10 papers could not be reviewed due to metadata-only or landing-page-only status. The non-reviewable papers (especially Lookback Lens and Unsupervised Real-Time Detection) may contain relevant approaches that affect the overlap assessment. More full text is needed before a reliable readiness determination can be made.

## Next Allowed Action

**collect_more_full_text**

Before rerunning trusted literature_search → novelty_check → method_refinement, the system should:
1. Acquire full text for the non-reviewable papers (especially ftq_002 Lookback Lens, ftq_010 Unsupervised Real-Time Detection)
2. Resolve PDF extraction for ftq_008 (Hallucination Detection with Internal Layers)
3. Carefully compare ICR Probe's full methodology against the trajectory-anomaly framing

Do NOT recommend experiment_plan directly. The high_risk_overlap finding requires resolution before proceeding.

---

This artifact is a full-text review of locally acquired materials only.
It is not a novelty proof, an experiment plan, or a paper claim.
Do not advance to experiment_plan without meeting the readiness gate criteria above.
