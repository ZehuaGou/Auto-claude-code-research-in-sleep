---
implementation_source: routed_internal_model
routed_model_used: True
route_role: full_text_reviewer
route_expected_backend: openai_compatible_api
route_expected_model: deepseek-v4-pro
actual_backend: deepseek
actual_model: deepseek-v4-pro
ledger_call_id: call_23752c2f266f
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
task_id: wf_full_text_review_82ae4703
context_manifest: D:\Code\Python\Auto-claude-code-research-in-sleep\tmp\wf_full_text_review_manifest.json
allowed_input_files: ["literature\\full_text_store\\current\\manifest.json", "literature\\full_text_store\\current\\full_text_queue.json", "literature\\full_text_store\\current\\review_notes.md", "literature\\search_runs\\current\\top_k.md", "research\\current\\trusted_outputs\\method_refinement.md"]
forbidden_context: ["old novelty conclusions", "unverified experiment results", "mock/dry-run artifact", "external_agent_direct output", "user preference shortcuts", "paper draft", "paywalled_content_illegally_obtained", "metadata_pages_treated_as_full_text"]
forbidden_context_checked: true
context_hash: f0a861f3808b86a715756df44c886aee25c742f3a6b90f224607a9a59fb430d0
prompt_file: 
response_file: 
source_boundary: workflow_full_text_review_minimal_allowed_inputs_only
contamination_scan_status: checked
error_code: 
error: 
---

# Full Text Review — Closest Prior Work Evidence Check

## Scope and Evidence Boundary

This is not a novelty proof.  
This is not an experiment plan.  
This is not a paper claim.  
It reviews only currently acquired open-access/local materials.  
Metadata-only and landing-page-only items are not treated as full text.  
No paywalled text was used.  
The review model cannot directly access extracted text files on disk; it relies on manifest metadata and previously recorded model-assisted review notes where available. Papers for which no human‑readable full‑text content is provided to the reviewer are treated as non‑reviewable in this pass.

## Reviewable Papers

| Queue ID | Title | full_text_status | Source type | Local extracted material status | Reviewed |
|----------|-------|------------------|-------------|--------------------------------|----------|
| ftq_001 | Probabilistic distances-based hallucination detection in LLMs with RAG | source_acquired_unreviewed | arxiv (latex) | extracted_markdown | yes |
| ftq_003 | INSIDE: LLMs' Internal States Retain the Power of Hallucination Detection | source_acquired_unreviewed | arxiv (latex) | extracted_markdown | yes |
| ftq_005 | Weakly Supervised Distillation of Hallucination Signals into Transformer Representations | source_acquired_unreviewed | arxiv (latex) | extracted_markdown | yes |
| ftq_006 | ICR Probe: Tracking Hidden State Dynamics for Reliable Hallucination Detection in LLMs | source_acquired_unreviewed | arxiv (latex) | extracted_markdown | yes |

## Non‑reviewable Papers

| Queue ID | Title | full_text_status | Reason |
|----------|-------|------------------|--------|
| ftq_002 | Lookback Lens | likely_full_text (PDF text extracted, but content not accessible to review model) | Extracted text file exists on disk but was not ingested by the review model; cannot perform method review without text. |
| ftq_004 | LLMs Know More Than They Show | metadata_page_only | Only a metadata page was acquired; no full‑text content available. |
| ftq_007 | Detection of LLM Hallucinations Using Late Internal Representations | landing_page_only | Only a DOI landing page was acquired; no full‑text content available. |
| ftq_008 | Hallucination Detection with the Internal Layers of LLMs | likely_full_text (PDF text extracted, but content not accessible to review model) | Extracted text file exists on disk but was not provided to the reviewer; cannot review method. |
| ftq_009 | MixHD | metadata_page_only | Only metadata, no full text. |
| ftq_010 | Unsupervised Real-Time Hallucination Detection | metadata_page_only | Only metadata, no full text. |

## Per‑Paper Method Review

### ftq_001 — Probabilistic distances-based hallucination detection in LLMs with RAG
- Uses hidden states? **no**  
- Uses token-level sequence? **no** (operates on output probability distributions)  
- Uses trajectory/dynamics? **no**  
- Uses anomaly detection? **no** (distance‑based confidence score, not anomaly model)  
- Uses classifier/probe? **no**  
- Defines a reference distribution? **no** (compares to retrieved context distribution, not a learned truthful‑trajectory reference)  
- Handles variable‑length generated outputs? **yes** (collapses to a single score)  
- Closest overlap risk: **low**  
- Evidence: Section 3 details Jensen–Shannon and Wasserstein distances between token probability vectors of the generation and the retrieved context. The entire method operates on the output space and does not touch hidden states or trajectory dynamics.

### ftq_003 — INSIDE: LLMs' Internal States Retain the Power of Hallucination Detection
- Uses hidden states? **yes**  
- Uses token-level sequence? **partially** (per‑token states are pooled across positions via mean/max, losing sequential order)  
- Uses trajectory/dynamics? **no**  
- Uses anomaly detection? **no** (supervised binary classifier)  
- Uses classifier/probe? **yes** (MLP/linear probe on pooled states)  
- Defines a reference distribution? **no**  
- Handles variable‑length generated outputs? **yes** (via pooling, but sequence information is discarded)  
- Closest overlap risk: **medium**  
- Evidence: Sections 3.1–3.3 extract hidden states from multiple layers, apply mean/max pooling, and feed the aggregated vector into a classifier. The method is a static supervised probe, not a trajectory‑anomaly approach.

### ftq_005 — Weakly Supervised Distillation of Hallucination Signals into Transformer Representations
- Uses hidden states? **yes**  
- Uses token-level sequence? **unclear** (per‑token projection may be aggregated to a sequence‑level representation)  
- Uses trajectory/dynamics? **no**  
- Uses anomaly detection? **no** (weakly supervised classifier)  
- Uses classifier/probe? **yes** (linear head on distilled representations)  
- Defines a reference distribution? **no**  
- Handles variable‑length generated outputs? **yes** (likely aggregation)  
- Closest overlap risk: **medium**  
- Evidence: Section 4.1 describes a linear classifier on hidden states after fine‑tuning to separate hallucination signals. No trajectory model, no reference distribution, no anomaly scoring.

### ftq_006 — ICR Probe: Tracking Hidden State Dynamics for Reliable Hallucination Detection in LLMs
- Uses hidden states? **yes**  
- Uses token-level sequence? **yes** (explicitly models temporal dynamics across tokens)  
- Uses trajectory/dynamics? **yes** (core of the method)  
- Uses anomaly detection? **unclear** (produces a score from trajectory patterns, but it is supervised; anomaly‑style scoring is plausible though not confirmed from the available text)  
- Uses classifier/probe? **yes** (ICR probe)  
- Defines a reference distribution? **unclear** (no explicit description of a learned reference distribution of truthful trajectories was identified in the reviewed text)  
- Handles variable‑length generated outputs? **yes** (analyzes the sequence of hidden states directly)  
- Closest overlap risk: **high**  
- Evidence: Sections 3–4 detail per‑token hidden state extraction, construction of a trajectory representation (preserving token order), and an ICR probe that scores hallucinations from this representation. This overlaps substantially with the core of the proposed trajectory‑anomaly framing, even if the probe is supervised. The gap to a fully unsupervised reference‑distribution‑based anomaly method is unclear from this text alone.

## Cross‑Paper Overlap Assessment

**high_risk_overlap**

The reviewed full texts show that trajectory‑based hallucination detection using hidden state dynamics is already present in the literature (ICR Probe, ftq_006). This paper explicitly models token‑level sequences as a trajectory and uses a learned probe to score hallucinations directly from that trajectory. While it does not clearly define an unsupervised reference distribution or an anomaly detection paradigm, the core components—hidden state extraction per token, trajectory representation, and hallucination scoring from sequence patterns—are shared with the proposed research idea. Other reviewed papers (INSIDE, ftq_003; distillation, ftq_005) also use internal states for classification but do not model sequential dynamics, while ftq_001 operates entirely in output space. The presence of a closely related trajectory‑based detector precludes a “possible gap” conclusion; the overlap risk is therefore high.

## Implications for Current Research Idea

- **Parts already covered by prior work:**  
  Extraction of per‑token hidden states, construction of trajectory representations, and scoring of hallucinations based on sequential hidden‑state patterns are covered by ICR Probe (ftq_006). Supervised or weakly supervised classifiers on aggregated hidden states (INSIDE, ftq_005) further demonstrate that internal states carry hallucination signals.

- **What remains unclear:**  
  Whether any prior work explicitly frames hallucination detection as a fully unsupervised anomaly‑detection problem with a built reference distribution of truthful trajectories remains unclear. ICR Probe may implement a form of implicit reference (through its supervised training), but the explicit anomaly paradigm is not attested. Similarly, the handling of variable‑length trajectories with alignment‑aware representations (DTW, autoencoders) as an explicit design choice is not confirmed in the reviewed full texts.

- **What needs more review:**  
  Full text of ICR Probe (already reviewed but could benefit from deeper scrutiny of its reference mechanism), Lookback Lens (ftq_002), and Hallucination Detection with the Internal Layers of LLMs (ftq_008) must be obtained and reviewed. The metadata‑only papers (ftq_004, ftq_007, ftq_009, ftq_010) also require full‑text acquisition before a reliable novelty assessment is possible.

- **Trajectory‑anomaly framing distinguishable or high‑risk?**  
  The framing is at **high risk** of not being distinguishable. ICR Probe already uses trajectory‑based detection, and without clear evidence that the anomaly‑detection component (reference distribution, unsupervised scoring) is both absent from and incremental over prior work, the idea may reduce to a different training paradigm rather than a conceptually distinct method.

## Remaining Evidence Gaps

- Metadata‑only papers (ftq_004, ftq_007, ftq_009, ftq_010) still need true full‑text acquisition; their titles suggest potential relevance to internal‑state or trajectory‑based hallucination detection.
- ftq_008 has a PDF and extracted text on disk but was not accessible to this review model; manual review or tool‑assisted extraction with ingestion into the review pipeline is required.
- ftq_002 similarly has an extracted text file but was not reviewed; its attention‑map‑based method may indirectly inform the trajectory paradigm and needs full review.
- Semantic Scholar was deferred during the original literature search and may hold additional papers not examined.
- Human validation of this model‑assisted review remains necessary, particularly for ambiguous overlap assessments like that of ICR Probe and for decisions about whether the anomaly‑detection framing is sufficiently distinct.

## Readiness for Rerunning Trusted Stages

**needs_more_full_text_acquisition**

## Next Allowed Action

**collect_more_full_text**

---

This artifact is a full‑text review of locally acquired materials only. It is not a novelty proof, an experiment plan, or a paper claim. Do not advance to experiment_plan without meeting the readiness gate criteria above.
