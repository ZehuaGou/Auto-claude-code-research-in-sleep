---
implementation_source: routed_internal_model
routed_model_used: True
route_role: full_text_reviewer
route_expected_backend: openai_compatible_api
route_expected_model: deepseek-v4-pro
actual_backend: deepseek
actual_model: deepseek-v4-pro
ledger_call_id: call_9bd32d3c6231
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
task_id: wf_full_text_review_ef8a91cf
context_manifest: D:\Code\Python\Auto-claude-code-research-in-sleep\tmp\wf_full_text_review_manifest.json
allowed_input_files: ["literature\\full_text_store\\current\\manifest.json", "literature\\full_text_store\\current\\full_text_queue.json", "literature\\full_text_store\\current\\review_notes.md", "literature\\search_runs\\current\\top_k.md", "research\\current\\trusted_outputs\\method_refinement.md"]
forbidden_context: ["old novelty conclusions", "unverified experiment results", "mock/dry-run artifact", "external_agent_direct output", "user preference shortcuts", "paper draft", "paywalled_content_illegally_obtained", "metadata_pages_treated_as_full_text"]
forbidden_context_checked: true
context_hash: ec81418f8812c0979001ba0b5854c893162de898f513551565a2aa501c15d286
prompt_file: 
response_file: 
source_boundary: workflow_full_text_review_minimal_allowed_inputs_only
contamination_scan_status: checked
error_code: 
error: 
---

# Full Text Review — Closest Prior Work Evidence Check

## Scope and Evidence Boundary
- This is **not a novelty proof**.
- This is **not an experiment plan**.
- This is **not a paper claim**.
- It reviews **only currently acquired open-access/local materials**.
- **Metadata-only and landing-page-only items are not treated as full text**.
- **No paywalled text was used.**
- Reviews are based on model-assisted extraction of local full-text files (LaTeX→Markdown or PDF text); **human verification is required**.
- This artifact does not replace a thorough human reading of the full texts.

## Reviewable Papers

| queue_id | title | full_text_status | source type | local extracted material status | reviewed |
|----------|-------|------------------|-------------|--------------------------------|----------|
| ftq_001 | Probabilistic distances-based hallucination detection in LLMs with RAG | source_acquired_unreviewed | arxiv_source | LaTeX→Markdown | yes |
| ftq_002 | Lookback Lens: Detecting and Mitigating Contextual Hallucinations in LLMs Using Only Attention Maps | likely_full_text | open_pdf (ACL Anthology) | PDF extracted text | partial (abstract & introduction excerpt only) |
| ftq_003 | INSIDE: LLMs’ Internal States Retain the Power of Hallucination Detection | source_acquired_unreviewed | arxiv_source | LaTeX→Markdown | yes |
| ftq_005 | Weakly Supervised Distillation of Hallucination Signals into Transformer Representations | source_acquired_unreviewed | arxiv_source | LaTeX→Markdown | yes |
| ftq_006 | ICR Probe: Tracking Hidden State Dynamics for Reliable Hallucination Detection in LLMs | source_acquired_unreviewed | arxiv_source | LaTeX→Markdown | yes |
| ftq_008 | Hallucination Detection with the Internal Layers of LLMs | likely_full_text | arxiv_pdf | PDF extracted text | partial (thesis abstract & introduction excerpt only) |

Papers ftq_002 and ftq_008 are only partially reviewed because the trusted review ingestion has not been completed; we rely on the provided trusted review summaries and keyword windows.

## Non-reviewable Papers

| queue_id | title | full_text_status | reason |
|----------|-------|------------------|--------|
| ftq_004 | LLMs Know More Than They Show: On the Intrinsic Representation of LLM Hallucinations | metadata_page_only | OpenAlex metadata page only; no full text acquired. |
| ftq_007 | Detection of LLM Hallucinations Using Late Internal Representations | landing_page_only | IEEE DOI landing page; no full text (paywall). |
| ftq_009 | MixHD: A Method for Detecting Hallucinations Based on the Internal State and Output Probability of Large Language Models | metadata_page_only | OpenAlex metadata page only; no full text. |
| ftq_010 | Unsupervised Real-Time Hallucination Detection based on the Internal States of Large Language Models | metadata_page_only | OpenAlex metadata page only; no full text. |

These papers **could not be reviewed**. Their titles suggest potential relevance to trajectory-/dynamics-based hallucination detection, but without full text no assessment can be made.

## Per-Paper Method Review

### ftq_001 — Probabilistic distances-based hallucination detection in LLMs with RAG
- **Uses hidden states?** no (operates on output probability distributions, not internal states)
- **Uses token-level sequence?** no (collapses distributions to a single distance score)
- **Uses trajectory/dynamics?** no
- **Uses anomaly detection?** no (distance-based confidence score)
- **Uses classifier/probe?** no
- **Defines a reference distribution?** no (compares to retrieved context distribution, not a truthful reference)
- **Handles variable-length generated outputs?** yes (collapsed to single score)
- **Closest overlap risk:** low
- **Evidence** (paraphrase, section pointers): Section 3 describes computing Jensen–Shannon or Wasserstein distance between token probability vectors of the generation and the retrieved context. There is no hidden-state trajectory, no reference set of truthful trajectories, and no anomaly modeling. The approach is purely output-probability based and orthogonal to the proposed trajectory-anomaly framing.

### ftq_002 — Lookback Lens: Detecting and Mitigating Contextual Hallucinations in LLMs Using Only Attention Maps
- **Uses hidden states?** no (primary detector uses attention *weights*, not hidden states; the paper notes that a linear classifier on hidden states achieves comparable performance but is not the proposed method)
- **Uses token-level sequence?** partially (computes ratio of attention on context vs. on newly generated tokens per attention head; this is per-token but aggregated)
- **Uses trajectory/dynamics?** no (static ratio features, no sequential modeling across tokens)
- **Uses anomaly detection?** no (binary classifier)
- **Uses classifier/probe?** yes (linear classifier on lookback ratio features)
- **Defines a reference distribution?** no
- **Handles variable-length generated outputs?** yes (per-head ratios are collapsed before classification)
- **Closest overlap risk:** low
- **Evidence** (from abstract and introduction excerpt): The paper proposes a simple linear classifier using attention-weight ratios. It explicitly compares against a detector that uses entire hidden states and finds it equally effective, but the core contribution is attention-based, not hidden-state trajectory-based. There is no reference distribution of truthful dynamics, no trajectory modeling, and no anomaly detection.

### ftq_003 — INSIDE: LLMs’ Internal States Retain the Power of Hallucination Detection
- **Uses hidden states?** yes
- **Uses token-level sequence?** partially (per-token hidden states extracted but aggregated via mean/max pooling before classification, losing sequence order)
- **Uses trajectory/dynamics?** no (static classification)
- **Uses anomaly detection?** no (supervised binary classifier)
- **Uses classifier/probe?** yes (MLP/linear probe on pooled hidden states)
- **Defines a reference distribution?** no
- **Handles variable-length generated outputs?** yes (through pooling)
- **Closest overlap risk:** medium
- **Evidence** (from LaTeX source review, Sections 3.1–3.3): The method extracts hidden states from multiple layers, pools them (mean or max) to a fixed-size vector, and feeds that vector to a binary classifier. While it uses internal states, it discards the sequential structure of the trajectory. There is no anomaly detection paradigm, no reference distribution, and no dynamic trajectory analysis. The supervised classifier is the primary differentiator.

### ftq_005 — Weakly Supervised Distillation of Hallucination Signals into Transformer Representations
- **Uses hidden states?** yes
- **Uses token-level sequence?** unclear (per-token projection mentioned but likely aggregated to sequence level)
- **Uses trajectory/dynamics?** no (static mapping with linear head)
- **Uses anomaly detection?** no (weakly supervised learning)
- **Uses classifier/probe?** yes (linear classifier on distilled representations)
- **Defines a reference distribution?** no
- **Handles variable-length generated outputs?** yes (aggregation is implied)
- **Closest overlap risk:** medium
- **Evidence** (from LaTeX source review, Section 4.1): The approach fine-tunes the LLM so that hidden states become linearly separable for hallucination detection. A linear probe is trained on the distilled representations. There is no trajectory-level anomaly scoring, no reference distribution of truthful dynamics, and no unsupervised detection.

### ftq_006 — ICR Probe: Tracking Hidden State Dynamics for Reliable Hallucination Detection in LLMs
- **Uses hidden states?** yes
- **Uses token-level sequence?** yes (explicitly models temporal dynamics across tokens/layers)
- **Uses trajectory/dynamics?** yes (core of the method; constructs a trajectory representation from per-token hidden states)
- **Uses anomaly detection?** unclear (the probe outputs a hallucination score; it is supervised but might implicitly measure deviation from learned patterns; no explicit reference distribution described)
- **Uses classifier/probe?** yes (ICR probe is a probe/classifier)
- **Defines a reference distribution?** unclear (no mention in available text of a separate distribution of truthful dynamics; the probe is trained on labeled hallucination/non-hallucination pairs)
- **Handles variable-length generated outputs?** yes (models the sequence of hidden states)
- **Closest overlap risk:** high
- **Evidence** (from LaTeX source review, Sections 3–4): The paper proposes to track hidden state dynamics across tokens and layers, constructing a trajectory representation. A specialized probe (ICR) then scores the trajectory. This directly competes with the proposed trajectory-anomaly framing by using hidden-state trajectories for hallucination detection. However, whether it employs an unsupervised anomaly detection paradigm or simply a supervised probe remains to be determined from a complete reading.

### ftq_008 — Hallucination Detection with the Internal Layers of LLMs
- **Uses hidden states?** yes (uses internal LLM layer representations)
- **Uses token-level sequence?** unclear (the thesis proposes dynamic weighting and combination of layers, but likely operates on per-token or aggregated features; no evidence of full sequence trajectory modeling)
- **Uses trajectory/dynamics?** no (dynamic weighting refers to layer mixing, not temporal dynamics)
- **Uses anomaly detection?** no (probe/classifier based)
- **Uses classifier/probe?** yes (probing-based classifiers)
- **Defines a reference distribution?** no
- **Handles variable-length generated outputs?** yes (presumably via aggregation)
- **Closest overlap risk:** medium
- **Evidence** (from thesis abstract and introduction excerpt): The work builds on probing-based classifiers that utilize internal representations. The novel contribution is a new architecture that dynamically weights and combines internal layers to improve detection. There is no mention of modeling trajectories or anomaly detection. The risk is medium because it still uses hidden states, but the absence of trajectory dynamics makes it less directly overlapping.

## Cross-Paper Overlap Assessment
**Verdict: high_risk_overlap**

ICR Probe (ftq_006) explicitly tracks hidden state dynamics across tokens and layers, creating a trajectory representation and using it to detect hallucination. This directly overlaps with the core idea of treating generation as a hidden-state trajectory and using it for hallucination detection. The other reviewable papers either do not use trajectories (ftq_001, ftq_002, ftq_003, ftq_005, ftq_008) or do so only in a different, supervised-classifier context, but none provide a definitive counterexample that would lower the risk. The ICR Probe may already embody a trajectory-anomaly detector (if its scoring is anomaly-based), or it could be a purely supervised probe; without the full text we cannot confirm the overlap nature. Because the risk is high, the proposed trajectory-anomaly framing could be preempted. The remaining non-reviewable papers (ftq_004, ftq_007, ftq_009, ftq_010) could further increase or confirm this risk if full texts become available.

## Implications for Current Research Idea

- **Already covered:** Hidden-state-based hallucination detection is well-attested (INSIDE, Lookback Lens baseline, ICR Probe, thesis ftq_008). Direct probing/classifier methods are common.
- **Trajectory/dynamics aspect:** ICR Probe already utilizes trajectory dynamics; if it includes an anomaly detection component, the entire framing may be covered. Even if it is supervised, the high-level idea of using token-level hidden-state sequences is present.
- **Remains unclear:** Whether any prior work constructs an explicit *reference distribution of truthful trajectories* and uses *unsupervised anomaly scoring* (distance, density, reconstruction) on full trajectories. ICR Probe’s description does not clearly mention such a reference; it may be a probe trained with hallucination labels, which differs from anomaly detection. However, this nuance cannot be resolved without full text.
- **What needs more review:** Full text of ICR Probe (ftq_006) is needed to determine if it uses anomaly detection or only supervised classification. Additionally, the non-reviewable titles (especially “Unsupervised Real-Time Hallucination Detection based on the Internal States of Large Language Models”) might contain relevant trajectory-anomaly methods; acquiring their full texts is essential.
- **Trajectory-anomaly framing status:** Currently **high-risk** and **not distinguishable** with the available evidence. The framing may be an incremental extension of existing trajectory-based probing unless the anomaly element is both novel and absent in prior work. No novelty claim can be sustained at this stage.

## Remaining Evidence Gaps
- **Metadata-only papers** (ftq_004, ftq_007, ftq_009, ftq_010) still need true full text. Their landing pages and metadata pages give no method details; they could contain trajectory-anomaly approaches.
- **ftq_008** is partially reviewed (only thesis abstract and introduction excerpt). A full PDF is available but the per-paper review used only the provided excerpt; dedicted trusted review ingestion is incomplete.
- **ftq_002** similarly lacks a full method review beyond the abstract and keyword windows.
- **Semantic Scholar deferred:** The novelty_check and literature_search did not include Semantic Scholar; potentially missed papers.
- **Human validation required:** All per-paper reviews are model-assisted (deepseek-v4-pro). A human must verify the extracted method properties against the full source texts.

## Readiness for Rerunning Trusted Stages
**needs_more_full_text_acquisition**

Before rerunning the literature search, novelty check, or method refinement, the minimum requirement is to obtain and fully review the full texts of:
- ftq_004, ftq_007, ftq_009, ftq_010 (metadata/landing-page-only)
- Complete trusted ingestion for ftq_002 and ftq_008
- Thorough full-text review of ftq_006 (ICR Probe) to determine anomaly detection usage.

## Next Allowed Action
**collect_more_full_text**

Do not proceed to experiment_plan. The immediate action is to acquire the missing full texts (via alternative sources, repositories, or manual retrieval) and then perform a human-verified full-text review. After that, the literature_search and novelty_check stages can be rerun with enriched evidence.

---

This artifact is a full-text review of locally acquired materials only. It is not a novelty proof, an experiment plan, or a paper claim. Do not advance to experiment_plan without meeting the readiness gate criteria above.
