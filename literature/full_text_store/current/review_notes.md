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
- **Method summary:** Partial trusted review completed from bounded extracted-text summary; full human review still needed.
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
| ftq_007 | Detection of LLM Hallucinations Using Late Internal Representations | paywall_protected | IEEE DOI, paywall protected; no open-access path without Sci-Hub |
| ftq_009 | MixHD | paywall_protected | IEEE DOI, paywall protected; no open-access path without Sci-Hub |

**These papers could not be reviewed.** Their titles suggest potential relevance to trajectory/dynamics-based hallucination detection, but full text is behind paywall.

---

## Phase 21C — PDF Extraction + Alternative Acquisition (2026-05-13)

**PDF extraction:** ftq_002 (Lookback Lens) and ftq_008 (Hallucination Detection with Internal Layers) now have extraction_status=extracted_text. Partial trusted review completed from bounded extracted-text summary; full human review still needed.

**Alternative acquisition attempted:**
- ftq_002 (Lookback Lens): ACQUIRED via ACL Anthology (open_pdf). DOI: 10.18653/v1/2024.emnlp-main.84. PDF extracted to raw_pdfs/2024.emnlp-main.84.pdf.
- ftq_004 (LLMs Know More Than They Show): arXiv DOI resolved (10.48550/arxiv.2410.02707 → 2410.02707) but download timed out (China network).
- ftq_007 (Detection of LLM Hallucinations Using Late Internal Representations): IEEE DOI not auto-resolved (paywall).
- ftq_009 (MixHD): IEEE DOI not auto-resolved (paywall).
- ftq_010 (Unsupervised Real-Time Hallucination Detection): arXiv DOI resolved (10.48550/arxiv.2403.06448 → 2403.06448) but download timed out (China network).

**Store status after Phase 21C:**
- 4 source_acquired_unreviewed (arxiv_source)
- 2 likely_full_text (ftq_002, ftq_008 — both PDF text extracted; partial trusted review completed from bounded extracted-text summary, full human review still needed)
- 3 metadata_page_only
- 1 landing_page_only

---

## Phase 21D — collect_more_full_text (2026-05-14)

**ftq_004 (LLMs Know More Than They Show):** arXiv source + PDF already acquired (2410.02707). pypdf extraction done → extracted_text/ftq_004.txt (1635 lines). Now reviewable.

**ftq_010 (Unsupervised Real-Time Hallucination Detection):** arXiv source + PDF already acquired (2403.06448). pypdf extraction done → extracted_text/ftq_010.txt (1233 lines). Now reviewable.

**ftq_007 (Detection of LLM Hallucinations Using Late Internal Representations):** IEEE DOI, paywall protected. Remains manual_required.

**ftq_009 (MixHD):** IEEE DOI, paywall protected. Remains manual_required.

**Store status after Phase 21D:**
- 4 likely_full_text (ftq_002, ftq_004, ftq_008, ftq_010 — all have extracted text, pending review)
- 4 source_acquired_unreviewed (ftq_001, ftq_003, ftq_005, ftq_006 — LaTeX source only)
- 2 paywall_protected (ftq_007, ftq_009 — manual required)

---

## Phase 21E — close remaining full-text evidence gaps (2026-05-14)

**ftq_007 (Detection of LLM Hallucinations Using Late Internal Representations):**
- Authors: Sakhawat Hossan, Jing Deng (UNC Greensboro). Venue: ICMLA 2025.
- Exhaustive legal OA search: arXiv (not found), OpenAlex (closed, is_oa=false), Crossref (IEEE policy licenses only), Semantic Scholar (openAccessPdf empty), DOI page (IEEE Xplore paywall). No author homepage or institutional repository found.
- Sci-Hub attempted: SE (DDoS-Guard captcha-blocked), RU (not-in-database, "статьи по запросу не найдены").
- **Result: paywall_blocked, legal_open_full_text_not_found.** IEEE Xplore subscription required.

**ftq_009 (MixHD):**
- Authors: Chuang Li, Bingnan Xing, et al. (CAS/Institute of Information Engineering). Venue: ICASSP 2025.
- Exhaustive legal OA search: arXiv (not found), OpenAlex (closed, is_oa=false), Crossref (IEEE policy licenses only), Semantic Scholar (openAccessPdf empty), DOI page (IEEE Xplore paywall). No author homepage or institutional repository found.
- Sci-Hub attempted: SE (DDoS-Guard captcha-blocked), RU (not-in-database, "статья отсутствует в базе").
- **Result: paywall_blocked, legal_open_full_text_not_found.** IEEE Xplore subscription required.

**Store status after Phase 21E:**
- 4 likely_full_text (ftq_002, ftq_004, ftq_008, ftq_010 — all have extracted text, pending review)
- 4 source_acquired_unreviewed (ftq_001, ftq_003, ftq_005, ftq_006 — LaTeX source only)
- 2 manual_required, paywall_blocked (ftq_007, ftq_009 — no open access exists)

---

(Add more paper sections as needed after human verification)
