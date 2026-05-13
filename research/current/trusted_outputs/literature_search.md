---
implementation_source: routed_internal_model
routed_model_used: True
route_role: literature_scout
route_expected_backend: openai_compatible_api
route_expected_model: deepseek-v4-flash
actual_backend: deepseek
actual_model: deepseek-v4-flash
ledger_call_id: call_1aa9746795ae
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
task_id: wf_literature_search_e316d902
context_manifest: D:\Code\Python\Auto-claude-code-research-in-sleep\tmp\wf_literature_search_manifest.json
allowed_input_files: ["research\\current\\input_normalization.md", "research\\current\\trusted_outputs\\research_contract.md", "research\\current\\literature_notes.md", "literature\\search_runs\\current\\top_k.md"]
forbidden_context: ["unverified search results as confirmed evidence", "user preference shortcuts", "external_agent_direct", "old novelty conclusions", "mock/dry-run artifact", "paywalled_content_illegally_obtained"]
forbidden_context_checked: true
context_hash: 4adeba7aa77274bcaa215818d7d55aa7bea8b40975597378d75b584adecc742a
prompt_file: 
response_file: 
source_boundary: workflow_literature_search_minimal_allowed_inputs_only
contamination_scan_status: checked
error_code: 
error: 
---

# Literature Search Evidence Summary

## Search Strategy

The literature search was conducted via a multi-source automated pipeline covering arXiv, Crossref, and OpenAlex. Semantic Scholar was deferred due to rate limits. The search plan consisted of 36 job definitions targeting the following concept groups:
- hallucination detection in LLMs
- internal state / hidden state analysis
- token-level representation dynamics
- sequence or trajectory anomaly detection
- methods using attention maps, probabilities, or probe-based approaches

Execution yielded 36 job results (31 successful, 5 failed/rate-limited). From 155 raw candidates, 73 canonical papers were identified after duplicate removal (82 duplicates). A deterministic keyword/concept scoring system was used to rank relevance. The top 10 papers (relevance score ≥ 11) were selected for closer review. 23 low-relevance candidates were filtered out. Full-text verification was not performed for any paper; all evidence is based on metadata and abstracts where available.

## Evidence Table

| # | Paper (Year, Source) | Key Finding / Method | Relevance to Research Question | Evidence Limitations |
|---|---|---|---|---|
| 1 | Probabilistic distances-based hallucination detection in LLMs with RAG (2025, arXiv 2506.09886) | Proposes using probabilistic distance metrics on hidden states for hallucination detection, specifically in RAG contexts. | Directly relevant: uses hidden state representations for hallucination detection; shares the goal of anomaly-based detection via distances. | Full text not verified; RAG-specific setting may limit generalizability to non-RAG LLM generation. |
| 2 | Lookback Lens: Detecting and Mitigating Contextual Hallucinations in LLMs Using Only Attention Maps (2024, EMNLP 2024) | Uses attention map analysis (not hidden state trajectories) to detect contextual hallucinations. | Tangential but relevant: addresses hallucination detection using internal model signals; contrasts with trajectory-level approach. | Method relies on attention maps, not hidden state sequences; may not be directly comparable. |
| 3 | INSIDE: LLMs' Internal States Retain the Power of Hallucination Detection (2024, arXiv 2402.03744) | Proposes using hidden state representations (internal states) for hallucination detection; likely uses classification or probing, not trajectory anomaly. | Highly relevant: leverages internal states for hallucination detection; provides baseline for state-based approaches. | Abstract only; exact method (probing vs. anomaly detection) not confirmed; trajectory-level analysis not specified. |
| 4 | LLMs Know More Than They Show: On the Intrinsic Representation of LLM Hallucinations (2024, arXiv 2410.02707) | Investigates hidden representations of hallucinations, showing that internal states contain signals about factual accuracy. | Relevant: establishes that hidden states encode hallucination-related information; foundational for trajectory-level hypothesis. | Focuses on representation analysis (e.g., probing), not trajectory anomaly detection; variable-length handling not addressed. |
| 5 | Weakly Supervised Distillation of Hallucination Signals into Transformer Representations (2026, arXiv 2604.06277) | Distills hallucination signals into model representations using weak supervision. | Relevant: uses internal state signals to improve representation; could inform trajectory-level anomaly features. | Preprint (2026); full text not verified; method may not involve trajectory analysis. |
| 6 | ICR Probe: Tracking Hidden State Dynamics for Reliable Hallucination Detection in LLMs (2025, arXiv 2507.16488) | Probes hidden state dynamics over time to detect hallucinations; directly tracks state sequences. | Highly relevant: explicitly tracks hidden state *dynamics* across tokens, closest to trajectory-level approach. | Full text not verified; "dynamics" may refer to layer-wise or temporal patterns; alignment with variable-length sequences unclear. |
| 7 | Detection of LLM Hallucinations Using Late Internal Representations (2025, IEEE ICMLA 2025) | Uses late-layer internal representations (single token or summary) to classify hallucination. | Partially relevant: uses hidden states but not as a trajectory; focuses on static or aggregated representations. | Conference paper; full text not accessible; method is classification, not anomaly detection over sequences. |
| 8 | Hallucination Detection with the Internal Layers of LLMs (2025, arXiv 2509.14254) | Explores multiple internal layers for hallucination detection; likely uses layer-wise features for classification. | Relevant: internal layers are source of hidden state information; but approach is classification rather than trajectory anomaly detection. | Abstract only; trajectory-level representation not mentioned. |
| 9 | MixHD: A Method for Detecting Hallucinations Based on the Internal State and Output Probability of LLMs (2025, ICASSP 2025) | Combines internal state and output probability features for hallucination detection. | Relevant: uses internal states but as part of a multimodal feature set; not purely trajectory based. | Full text not verified; method fuses multiple signals; trajectory dynamics not explicitly discussed. |
| 10 | Unsupervised Real-Time Hallucination Detection based on the Internal States of LLMs (2024, arXiv 2403.06448) | Proposes unsupervised detection using internal states, suitable for real-time inference. | Highly relevant: unsupervised, real-time detection using internal states; aligns with anomaly detection framing. | Abstract only; method may use single-token features or aggregated statistics; trajectory-level detail unknown. |

## Coverage Assessment

**Areas with direct evidence from searched sources:**
- Multiple papers confirm that LLM internal states carry detectable signals related to hallucination (Papers 3, 4, 6, 10).
- Unsupervised and real-time detection from internal states has been explored (Paper 10).
- Hidden state dynamics and temporal patterns are investigated in at least one paper (Paper 6: ICR Probe).
- Distance-based and probe-based methods on hidden states exist for hallucination detection (Papers 1, 3, 6).

**Areas with limited or ambiguous coverage:**
- Trajectory-level anomaly detection as a distinct framework (i.e., comparing full token sequences against a reference distribution) is not explicitly found in the top-k set. Paper 6 (ICR Probe) comes closest but uses probe-based classification, not unsupervised anomaly scoring.
- Variable-length trajectory alignment: no evidence found in searched sources that prior work addresses the question of how to align or represent variable-length hidden state sequences for anomaly detection.
- Distinction between hallucination types (factual vs. contextual) and their trajectory signatures: no evidence found in searched sources.
- Impact of model size, architecture, or decoding strategy on trajectory behavior: not addressed in the retrieved evidence.
- Reference distribution stability across prompts and domains: no evidence found in searched sources.
- Application of standard anomaly detection methods (e.g., LOF, autoencoder, DTW) to token-level hidden state trajectories for hallucination detection: no direct evidence found in searched sources.

**Gaps identified through partial evidence:**
- Attention-map-based detection (Paper 2) uses a different signal modality than hidden states; relationship to trajectory anomaly is not established.
- Many papers use classification or probing (not unsupervised anomaly detection) on internal states.
- Full-text verification is absent for all papers; abstracts may omit crucial details about trajectory-level analysis.

## Open Questions

Based on the evidence gathered, the following questions remain unanswered by the searched literature:

1. **Trajectory-level anomaly detection framework:** Does any prior work explicitly frame hallucination detection as an anomaly detection problem over complete token-level hidden state trajectories (rather than probing single tokens or aggregated statistics)? The retrievals suggest probe-based or distance-based methods exist, but a unified trajectory anomaly approach appears underrepresented.
2. **Variable-length trajectory handling:** How do existing studies that track hidden state dynamics (e.g., ICR Probe) address variable output lengths? No evidence found in searched sources regarding alignment or padding strategies.
3. **Anomaly detection method families:** Are distance-based, density-based, or reconstruction-based anomaly detection methods (e.g., LOF, autoencoders) applied to hidden state trajectories in any evaluated paper? The retrieved papers either use probabilistic distances (Paper 1) or probes but do not clearly describe unsupervised anomaly detectors on full sequences.
4. **Inference-time vs. post-hoc detection:** Is there work on detecting hallucination as it occurs using trajectory-level signals? Paper 10 (unsupervised real-time) may be relevant but its trajectory-level granularity is unknown.
5. **Robustness to confounds:** Does existing literature address confounding factors such as output length, prompt variation, or decoding noise when using internal state signals? No evidence found in searched sources.
6. **Reference distribution construction:** How do prior studies define a “reference” set of truthful/hallucinated trajectories? The concept of a reference distribution for unsupervised comparison is not explicitly discussed in retrieved abstracts.

## Limitations

- **Full-text verification:** No full-text PDFs were downloaded; conclusions are based solely on metadata and abstracts. Methods and findings may differ from what is inferred here.
- **Relevance scoring is keyword-based, not semantic:** The top-k selection used deterministic keyword/concept matching, which may have included or excluded papers whose relevance depends on deeper semantic understanding.
- **Source coverage:** Three sources (arXiv, Crossref, OpenAlex) were used; Semantic Scholar and other databases were not included due to rate limits, potentially missing relevant work.
- **Repair queue items:** Known issues include duplicate records (82 duplicates), potential false positives from domain applications (e.g., medicine), and lack of full-text availability.
- **Time constraints:** Papers published after the search cutoff may not be captured; the search includes papers up to 2026 (preprint), but ongoing work may exist.
- **Hallucination definition varies:** The literature may adopt different definitions of hallucination (factual, contextual, faithfulness) that are not uniformly comparable to the research contract’s framing.
- **No manual assessment:** Relevance scores and evidence strength were assigned by automated tools; no human expert evaluated the papers.
- **Methodological details missing:** For several high-relevance papers (e.g., Papers 1, 6, 10), the specific method (e.g., how trajectories are defined, whether anomaly detection is used) cannot be confirmed from abstracts alone.

---

This artifact is literature evidence only. Novelty determination is performed by the novelty_checker stage.
