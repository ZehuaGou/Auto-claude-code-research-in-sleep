# Full-text Review Notes

Template for per-paper manual review. Fill in after reading the full text.

**Phase 21B model-assisted review completed 2026-05-13.** Human verification required.

---

## Paper: ftq_001 — Probabilistic distances-based hallucination detection in LLMs with RAG

- **Source file available?** yes
- **Local source type:** latex_source
- **full_text_status:** source_acquired_unreviewed
- **Method summary:** RAG hallucination detection using probabilistic distances (JS, Wasserstein) between generated token distributions and retrieved context distributions. Output-space method, no hidden states.
- **Uses hidden states?** no
- **Uses token-level sequence?** no (output probability distributions)
- **Uses trajectory/dynamics?** no
- **Uses anomaly detection?** no (distance-based confidence score)
- **Uses classifier/probe?** no
- **Has reference distribution?** no (compares to retrieved context distribution)
- **Handles variable length?** yes (collapsed to single score)
- **Closest overlap risk:** low
- **Evidence quotes or section pointers:** Section 3 details distance metrics applied to token probability vectors. Orthogonal to hidden-state trajectory paradigm.
- **Reviewer:** model-assisted (deepseek-v4-pro)
- **Date:** 2026-05-13

---

## Paper: ftq_003 — INSIDE: LLMs' Internal States Retain the Power of Hallucination Detection

- **Source file available?** yes
- **Local source type:** latex_source
- **full_text_status:** source_acquired_unreviewed
- **Method summary:** Supervised binary classifier on pooled hidden states from multiple transformer layers. Mean/max pooling collapses positional information. No trajectory modeling.
- **Uses hidden states?** yes
- **Uses token-level sequence?** partially (per-token states aggregated via pooling)
- **Uses trajectory/dynamics?** no (static classification)
- **Uses anomaly detection?** no (supervised classifier)
- **Uses classifier/probe?** yes (MLP/linear probe)
- **Has reference distribution?** no
- **Handles variable length?** yes (through pooling, loses sequence order)
- **Closest overlap risk:** medium
- **Evidence quotes or section pointers:** Sections 3.1–3.3 describe hidden state extraction, pooling, and binary classifier. Distinct from trajectory-anomaly framing.
- **Reviewer:** model-assisted (deepseek-v4-pro)
- **Date:** 2026-05-13

---

## Paper: ftq_005 — Weakly Supervised Distillation of Hallucination Signals into Transformer Representations

- **Source file available?** yes
- **Local source type:** latex_source
- **full_text_status:** source_acquired_unreviewed
- **Method summary:** Fine-tune LLM so hidden states become linearly separable for hallucination detection. Weak supervision from fact-checking tool. Linear classifier on distilled representations.
- **Uses hidden states?** yes
- **Uses token-level sequence?** unclear (per-token projection, may collapse to sequence-level)
- **Uses trajectory/dynamics?** no (static mapping)
- **Uses anomaly detection?** no (supervised/weakly supervised)
- **Uses classifier/probe?** yes (linear classifier)
- **Has reference distribution?** no
- **Handles variable length?** yes (likely via aggregation)
- **Closest overlap risk:** medium
- **Evidence quotes or section pointers:** Section 4.1 describes linear head on distilled representations. No trajectory model, no reference distribution, no anomaly scoring.
- **Reviewer:** model-assisted (deepseek-v4-pro)
- **Date:** 2026-05-13

---

## Paper: ftq_006 — ICR Probe: Tracking Hidden State Dynamics for Reliable Hallucination Detection in LLMs

- **Source file available?** yes
- **Local source type:** latex_source
- **full_text_status:** source_acquired_unreviewed
- **Method summary:** Tracks hidden state dynamics across tokens/layers. Constructs trajectory representation and uses ICR probe to produce hallucination score. Supervised training but trajectory-based.
- **Uses hidden states?** yes
- **Uses token-level sequence?** yes (explicitly models temporal dynamics)
- **Uses trajectory/dynamics?** yes (core of the method)
- **Uses anomaly detection?** unclear / possibly yes (score from trajectory patterns, but supervised)
- **Uses classifier/probe?** yes (ICR probe)
- **Has reference distribution?** unclear (does not explicitly describe reference distribution of truthful dynamics)
- **Handles variable length?** yes (analyzes sequence of hidden states)
- **Closest overlap risk:** high
- **Evidence quotes or section pointers:** Sections 3–4 describe per-token hidden state extraction, trajectory representation, and ICR probe scoring. Directly competes with trajectory-anomaly framing.
- **Reviewer:** model-assisted (deepseek-v4-pro)
- **Date:** 2026-05-13

---

## Paper: ftq_008 — Hallucination Detection with the Internal Layers of LLMs

- **Source file available?** yes (PDF only)
- **Local source type:** pdf
- **full_text_status:** likely_full_text
- **Method summary:** PDF extraction pending (tool_missing). Cannot review until PDF text extraction tool is available.
- **Uses hidden states?** unknown
- **Uses token-level sequence?** unknown
- **Uses trajectory/dynamics?** unknown
- **Uses anomaly detection?** unknown
- **Uses classifier/probe?** unknown
- **Has reference distribution?** unknown
- **Handles variable length?** unknown
- **Closest overlap risk:** unknown
- **Evidence quotes or section pointers:** N/A — extraction pending
- **Reviewer:** model-assisted (deepseek-v4-pro)
- **Date:** 2026-05-13

---

## Non-Reviewable Papers (model-assisted review 2026-05-13)

| queue_id | title | full_text_status | reason |
|----------|-------|------------------|--------|
| ftq_002 | Lookback Lens | metadata_page_only | OpenAlex metadata page only |
| ftq_004 | LLMs Know More Than They Show | metadata_page_only | OpenAlex metadata page only |
| ftq_007 | Detection of LLM Hallucinations Using Late Internal Representations | landing_page_only | DOI landing page only |
| ftq_009 | MixHD | metadata_page_only | OpenAlex metadata page only |
| ftq_010 | Unsupervised Real-Time Hallucination Detection | metadata_page_only | OpenAlex metadata page only |

**These papers could not be reviewed.** Their titles suggest potential relevance to trajectory/dynamics-based hallucination detection, but full text is not available.

---

(Add more paper sections as needed after human verification)
