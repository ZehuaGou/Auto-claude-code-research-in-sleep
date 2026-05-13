---
implementation_source: routed_internal_model
routed_model_used: True
route_role: full_text_reviewer
route_expected_backend: openai_compatible_api
route_expected_model: deepseek-v4-pro
actual_backend: deepseek
actual_model: deepseek-v4-pro
ledger_call_id: call_5a83358c4210
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
task_id: wf_full_text_review_2435a459
context_manifest: D:\Code\Python\Auto-claude-code-research-in-sleep\tmp\wf_full_text_review_manifest.json
allowed_input_files: ["literature\\full_text_store\\current\\manifest.json", "literature\\full_text_store\\current\\full_text_queue.json", "literature\\full_text_store\\current\\review_notes.md", "literature\\search_runs\\current\\top_k.md", "research\\current\\trusted_outputs\\method_refinement.md", "literature\\full_text_store\\current\\extracted_text\\ftq_002.txt", "literature\\full_text_store\\current\\extracted_text\\ftq_004.txt", "literature\\full_text_store\\current\\extracted_text\\ftq_008.txt", "literature\\full_text_store\\current\\extracted_text\\ftq_010.txt"]
forbidden_context: ["old novelty conclusions", "unverified experiment results", "mock/dry-run artifact", "external_agent_direct output", "user preference shortcuts", "paper draft", "paywalled_content_illegally_obtained", "metadata_pages_treated_as_full_text"]
forbidden_context_checked: true
context_hash: 44da20dcd0d3a59c5514827593525d0461ea0d10b18720d2549ec502bc255c44
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
- It reviews **only currently acquired open-access/local materials**.
- Metadata‑only and landing‑page‑only items are **not** treated as full text.
- **No paywalled text** was used.
- The evidence presented here is limited to the items in the full‑text store manifest; any missing full texts or external resources are explicitly identified as gaps.

---

## Reviewable Papers

| queue_id | title | full_text_status | source type | local extracted material status | reviewed |
|----------|-------|------------------|-------------|---------------------------------|----------|
| ftq_001 | Probabilistic distances-based hallucination detection in LLMs with RAG | source_acquired_unreviewed | arxiv_source | extracted_markdown | yes |
| ftq_002 | Lookback Lens: Detecting and Mitigating Contextual Hallucinations in Large Language Models Using Only Attention Maps | likely_full_text | open_pdf | extracted_text (PDF) | yes |
| ftq_003 | INSIDE: LLMs' Internal States Retain the Power of Hallucination Detection | source_acquired_unreviewed | arxiv_source | extracted_markdown | yes |
| ftq_004 | LLMs Know More Than They Show: On the Intrinsic Representation of LLM Hallucinations | likely_full_text | arxiv_source & openalex | extracted_text (pypdf) | yes |
| ftq_005 | Weakly Supervised Distillation of Hallucination Signals into Transformer Representations | source_acquired_unreviewed | arxiv_source | extracted_markdown | yes |
| ftq_006 | ICR Probe: Tracking Hidden State Dynamics for Reliable Hallucination Detection in LLMs | source_acquired_unreviewed | arxiv_source | extracted_markdown | yes |
| ftq_008 | Hallucination Detection with the Internal Layers of LLMs | likely_full_text | arxiv_pdf | extracted_text (PDF) | yes |
| ftq_010 | Unsupervised Real-Time Hallucination Detection based on the Internal States of Large Language Models | likely_full_text | arxiv_source & openalex | extracted_text (pypdf) | yes |

## Non‑reviewable Papers

| queue_id | title | full_text_status | reason |
|----------|-------|------------------|--------|
| ftq_007 | Detection of LLM Hallucinations Using Late Internal Representations | manual_required (paywall) | IEEE DOI, paywall protected; no open‑access path without Sci‑Hub, full text not acquired |
| ftq_009 | MixHD: A Method for Detecting Hallucinations Based on the Internal State and Output Probability of Large Language Models | manual_required (paywall) | IEEE DOI, paywall protected; no open‑access path without Sci‑Hub, full text not acquired |

These two papers could not be reviewed because the full text is behind a paywall and no open‑access alternative was obtained. Their titles suggest potential overlap (internal representations, late layers, mixing internal states), but without full text their methods remain unknown.

---

## Per‑Paper Method Review

### ftq_001 – Probabilistic distances-based hallucination detection in LLMs with RAG
- **Uses hidden states?** no
- **Uses token‑level sequence?** no (operates on output probability distributions)
- **Uses trajectory/dynamics?** no
- **Uses anomaly detection?** no (distance‑based confidence score)
- **Uses classifier/probe?** no
- **Defines a reference distribution?** no (compares to retrieved context distribution)
- **Handles variable‑length generated outputs?** yes (collapsed to a single score)
- **Closest overlap risk:** low
- **Evidence supports this with:** The method (Section 3) computes JS/Wasserstein distances between token probability vectors from the generated answer and retrieved context. It does not involve hidden states, sequences, or anomaly detection, making it orthogonal to the trajectory‑anomaly paradigm.

### ftq_002 – Lookback Lens
- **Uses hidden states?** no (uses attention weights)
- **Uses token‑level sequence?** yes (attention weights over generated tokens, averaged within spans)
- **Uses trajectory/dynamics?** no (attention‑weight ratios, not hidden‑state dynamics)
- **Uses anomaly detection?** no (supervised logistic regression)
- **Uses classifier/probe?** yes (linear classifier on lookback ratio features)
- **Defines a reference distribution?** no
- **Handles variable‑length generated outputs?** yes (span‑based averaging)
- **Closest overlap risk:** low
- **Evidence supports this with:** The Lookback Lens (Section 2.1) extracts the ratio of attention weights on context vs. newly generated tokens and uses a logistic regression classifier. It does not leverage hidden states, train a reference distribution, or perform anomaly detection. The paper explicitly contrasts against hidden‑state‑based detectors (Table 2) and focuses on attention maps.

### ftq_003 – INSIDE
- **Uses hidden states?** yes
- **Uses token‑level sequence?** partially (per‑token states aggregated via pooling)
- **Uses trajectory/dynamics?** no (static classification)
- **Uses anomaly detection?** no (supervised classifier)
- **Uses classifier/probe?** yes (MLP/linear probe)
- **Defines a reference distribution?** no
- **Handles variable‑length generated outputs?** yes (through pooling, loses sequence order)
- **Closest overlap risk:** medium
- **Evidence supports this with:** INSIDE (Sections 3.1–3.3) extracts hidden states from multiple layers, applies mean/max pooling to collapse token positions, and trains a binary classifier. It does not model trajectory dynamics, define a reference distribution of truthful trajectories, or use anomaly scoring. The risk is medium because it uses internal states for hallucination detection, but the approach is fundamentally supervised probe‑based, not an unsupervised anomaly‑detection framework.

### ftq_004 – LLMs Know More Than They Show
- **Uses hidden states?** yes
- **Uses token‑level sequence?** yes (investigates per‑token hidden states, especially exact answer tokens)
- **Uses trajectory/dynamics?** no (probes are applied to static token positions, not a trajectory sequence)
- **Uses anomaly detection?** no (supervised probing classifiers; error types are predicted by classification, not anomaly)
- **Uses classifier/probe?** yes (linear probing classifiers)
- **Defines a reference distribution?** no
- **Handles variable‑length generated outputs?** yes (exact answer token selection handles variable length; probes are trained on specific token positions)
- **Closest overlap risk:** medium
- **Evidence supports this with:** The paper (Sections 3–5) demonstrates probing classifiers on hidden states at exact answer tokens, achieving strong detection but in a supervised manner. It explores error types and internal/external misalignment, but always through classification, not anomaly detection with a reference distribution. The broad coverage of internal representations makes it a medium risk for overlap in the sense that it shares the use of hidden states, but it does not formulate the problem as trajectory anomaly detection.

### ftq_005 – Weakly Supervised Distillation
- **Uses hidden states?** yes
- **Uses token‑level sequence?** unclear (per‑token projection may be aggregated to sequence level)
- **Uses trajectory/dynamics?** no (static mapping)
- **Uses anomaly detection?** no (supervised/weakly supervised)
- **Uses classifier/probe?** yes (linear classifier)
- **Defines a reference distribution?** no
- **Handles variable‑length generated outputs?** yes (likely via aggregation)
- **Closest overlap risk:** medium
- **Evidence supports this with:** The proposed method (Section 4.1) fine‑tunes the LLM so that hidden states become linearly separable for hallucination detection, then applies a linear classifier. It does not involve trajectory dynamics, anomaly scoring, or a reference distribution. The risk is medium because it uses hidden states and supervised learning, but the approach is fundamentally a fine‑tuned probe, not an unsupervised trajectory‑anomaly detector.

### ftq_006 – ICR Probe: Tracking Hidden State Dynamics
- **Uses hidden states?** yes
- **Uses token‑level sequence?** yes (explicitly models temporal dynamics)
- **Uses trajectory/dynamics?** yes (core of the method)
- **Uses anomaly detection?** unclear (score derived from trajectory patterns, but supervised training)
- **Uses classifier/probe?** yes (ICR probe)
- **Defines a reference distribution?** unclear (no explicit description of a reference distribution of truthful dynamics)
- **Handles variable‑length generated outputs?** yes (analyzes sequence of hidden states)
- **Closest overlap risk:** high
- **Evidence supports this with:** The paper (Sections 3–4) describes per‑token hidden state extraction, construction of a trajectory representation, and the ICR probe that outputs a hallucination score. This is the closest prior work to the research idea because it directly models hidden‑state dynamics across tokens and layers. Although the technique uses supervised training for the probe and does not explicitly define a reference distribution, the overlap in the core concept of tracking hidden state trajectories to detect hallucination is substantial.

### ftq_008 – Hallucination Detection with the Internal Layers of LLMs
- **Uses hidden states?** yes
- **Uses token‑level sequence?** yes (for text classification, the last token of each layer; for sequence labeling, all tokens per layer)
- **Uses trajectory/dynamics?** no (for text classification, only the last token’s multi‑layer representation is used; the comparison module operates on layer‑wise encodings, not temporal dynamics)
- **Uses anomaly detection?** no (supervised MLP classifiers)
- **Uses classifier/probe?** yes (MLP with layer‑wise encoding and optional cosine similarity comparison)
- **Defines a reference distribution?** no
- **Handles variable‑length generated outputs?** yes (via token‑level classification and tagging schemes for sequential labeling)
- **Closest overlap risk:** medium
- **Evidence supports this with:** The thesis (Sections 4.4, 5.2) proposes a new architecture that encodes each LLM layer with the same MLP and compares encodings; the final classification is supervised. The work does not model trajectory dynamics over token positions in the text‑classification setting (it uses the last token’s representations) and does not use anomaly detection or a reference distribution. The risk is medium because it uses internal states and explores layer weighting, but it remains a supervised probe‑based approach.

### ftq_010 – MIND (Unsupervised Real‑Time Hallucination Detection)
- **Uses hidden states?** yes (contextualized embeddings)
- **Uses token‑level sequence?** yes (the detector inspects the last token’s hidden state of the final layer; for training, pseudo‑labels are derived from entity matching over the continuation)
- **Uses trajectory/dynamics?** no (no sequence‑level trajectory modeling; static single‑token representation)
- **Uses anomaly detection?** no (unsupervised pseudo‑label generation followed by supervised MLP training)
- **Uses classifier/probe?** yes (4‑layer MLP classifier)
- **Defines a reference distribution?** no
- **Handles variable‑length generated outputs?** yes (classification on the last token’s hidden state is length‑agnostic)
- **Closest overlap risk:** medium
- **Evidence supports this with:** MIND (Sections 3, 6) uses internal states and an unsupervised data‑generation pipeline to train a classifier, but the detection relies on a single token’s hidden state, not a full trajectory. It does not construct a reference distribution or apply anomaly detection. The overlap risk is medium because it demonstrates that unsupervised learning from internal states is possible, but the method is still a classifier, not a trajectory‑anomaly detector.

---

## Cross‑Paper Overlap Assessment

**Overall verdict: high_risk_overlap**

The review of eight reviewable full‑text papers reveals a dense landscape of internal‑state‑based hallucination detection. While no reviewed work explicitly adopts the combination of (a) a reference distribution of truthful trajectories, (b) token‑level trajectory anomaly detection, and (c) overall unsupervised anomaly scoring, the closest prior work—**ICR Probe (ftq_006)**—directly models hidden‑state dynamics across tokens and layers, constructs a trajectory representation, and outputs a hallucination score. Although it relies on supervised probe training, the conceptual overlap in tracking hidden‑state trajectories is high.  

Several other papers (ftq_003, ftq_004, ftq_005, ftq_008, ftq_010) all use hidden states for classification or probing, indicating that the general approach of leveraging internal representations for hallucination detection is well‑established. The specific differentiator of the research idea (unsupervised trajectory anomaly detection with a learned reference distribution) is not yet attested, but the existing trajectory‑based work (ICR Probe) makes the risk of non‑novelty substantial, especially if the supervised probe in ICR Probe already captures the same trajectory patterns that an anomaly detector would exploit.

Therefore, based on the currently acquired materials, the closest prior work presents a **high risk of overlap** with the intended trajectory‑anomaly framing. The remaining evidence gaps (especially the paywalled papers ftq_007 and ftq_009) could further increase this risk or, less likely, confirm the gap, but they cannot lower the current risk assessment.

---

## Implications for Current Research Idea

**Parts already covered by prior work**
- Using hidden states for hallucination detection is thoroughly explored (ftq_003, ftq_004, ftq_006, ftq_008, ftq_010).
- Token‑level hidden state representations (including exact answer tokens and sequence positions) are common (ftq_004, ftq_006).
- Probing/classifying hidden states with MLP or linear probes is standard (ftq_003, ftq_004, ftq_005, ftq_006, ftq_008, ftq_010).
- Tracking hidden state dynamics across tokens is explicitly handled by ICR Probe (ftq_006).

**What remains unclear**
- Whether **any** prior work frames hallucination detection as an **unsupervised anomaly detection** problem with a **reference distribution** built from truthful trajectories.
- Whether the variable‑length handling and explicit trajectory alignment (e.g., DTW) introduce a meaningful distinction beyond what ICR Probe already captures.
- The full text of ftq_007 (Detection of LLM Hallucinations Using Late Internal Representations) and ftq_009 (MixHD) are unavailable; the titles suggest they could be even closer to the idea.

**What needs more review**
- Complete full‑text verification of ftq_006 (ICR Probe) beyond the current extracted markdown to confirm there is no anomaly‑like scoring; the current evidence only says “supervised probe” but ambiguous wording could hide an anomaly component.
- Acquisition of full texts for ftq_007 and ftq_009; without them, the evidence base is incomplete and the risk of hidden overlap remains.

**Trajectory‑anomaly framing: distinguishable or high‑risk?**
Given that ICR Probe already constructs and scores a trajectory representation, the proposed unsupervised anomaly framing is **high‑risk** and may be incremental rather than a distinct gap. The lack of an explicit reference distribution in ICR Probe is a minor difference; a supervised probe that outputs hallucination probabilities can be trivially converted into an anomaly detector by thresholding, and it implicitly learns what constitutes “normal” (truthful) trajectories from its training data. Thus, the core claim may be pre‑empted by this work. Without conclusive full‑text evidence to the contrary, the trajectory‑anomaly framing must be considered as having a high probability of overlap.

---

## Remaining Evidence Gaps
- **Paywalled papers ftq_007 and ftq_009** still lack full text. Their titles (“Detection of LLM Hallucinations Using Late Internal Representations”, “MixHD: … Internal State and Output Probability”) are highly relevant and could directly cover the idea. Full‑text acquisition is mandatory before any novelty claim.
- **ICR Probe (ftq_006)** is currently reviewed from an extracted Markdown; a human review of the raw LaTeX source or a re‑extraction may reveal subtleties about anomaly scoring that are not fully captured.
- **Semantic Scholar sources were deferred** – literature search did not include Semantic Scholar; additional papers may exist that are even closer to the trajectory‑anomaly concept.
- **The current review is model‑assisted.** The per‑paper assessments for ftq_001, ftq_003, ftq_005, and ftq_006 rely on model‑assisted summaries; **human validation is still required** before firm conclusions.

---

## Readiness for Rerunning Trusted Stages

`needs_more_full_text_acquisition`

**Justification:** The paywalled papers ftq_007 and ftq_009 are missing, and they represent a potential high‑risk gap. Additionally, human validation of the model‑assisted reviews is pending. Rerunning the literature search and novelty check stages would be premature without these sources and the human verification.

---

## Next Allowed Action

`collect_more_full_text`

(This action entails obtaining the full texts of ftq_007 and ftq_009, completing human validation of all model‑assisted reviews, and if necessary, re‑extracting/verifying ftq_006. Only after those steps should a rerun of literature search/novelty check be considered.)

---

This artifact is a full‑text review of locally acquired materials only.  
It is not a novelty proof, an experiment plan, or a paper claim.  
Do not advance to experiment_plan without meeting the readiness gate criteria above.
