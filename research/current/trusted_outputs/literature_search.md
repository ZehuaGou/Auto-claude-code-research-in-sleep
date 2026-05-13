---
implementation_source: routed_internal_model
routed_model_used: True
route_role: literature_scout
route_expected_backend: openai_compatible_api
route_expected_model: deepseek-v4-flash
actual_backend: deepseek
actual_model: deepseek-v4-flash
ledger_call_id: call_7ddd16f2e6c8
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
task_id: wf_literature_search_f94d2c63
context_manifest: tmp\wf_literature_search_manifest.json
allowed_input_files: ["research\\current\\input_normalization.md", "research\\current\\trusted_outputs\\research_contract.md", "research\\current\\literature_notes.md", "literature\\search_runs\\current\\top_k.md"]
forbidden_context: ["unverified search results as confirmed evidence", "user preference shortcuts", "external_agent_direct", "old novelty conclusions", "mock/dry-run artifact", "paywalled_content_illegally_obtained"]
forbidden_context_checked: true
context_hash: bcd7a2620de97648c419fa0dcd5ece6f4ae12d8d0e6020dc5c297c0faabbbed8
prompt_file: 
response_file: 
source_boundary: workflow_literature_search_minimal_allowed_inputs_only
contamination_scan_status: checked
error_code: 
error: 
---

# Literature Search Evidence Summary

## Search Strategy

The literature search was conducted using the OpenAlex API pipeline (single source). The search plan targeted concepts related to hallucination detection, hidden-state analysis, sequence or trajectory anomaly detection, and token-level representation dynamics in LLM generation. Five search jobs were executed, all successful. The search plan and job execution passed validation.

**Search Parameters (implied from tools and contract constraints):**
- Sources: OpenAlex only
- Keywords/concept matching groups: hallucination_group, llm_group, internal_state_group, token_group, detection_group, plus a must_include clause
- Relevance scoring: deterministic keyword/concept matching, not semantic relevance
- Recency weighting: present but not documented quantitatively
- Deduplication: by normalized title (11 duplicates found and merged)
- Filtering: applied negative keyword penalization for strong domain negatives (e.g., pharmaceutical, medical, supply chain); 25 candidates filtered as low relevance

**Evidence Sources Considered:**
- Abstract/metadata only via OpenAlex API
- No full-text verification conducted
- No other databases (arXiv, Crossref, Semantic Scholar) used

## Evidence Table

The following table summarizes the top-k evidence items (k=10) returned by the automated pipeline. Relevance scoring is deterministic keyword-based and labeled by the tool as "high" for all ten. No manual relevance assessment has been performed.

| # | Title | Year | Method or Focus (as per abstract) | Relevance Score (tool) | Full Text Available | Key Limitation |
|---|-------|------|----------------------------------|------------------------|---------------------|----------------|
| 1 | Lookback Lens: Detecting and Mitigating Contextual Hallucinations in Large Language Models Using Only Attention Maps | 2024 | Attention-map-based detection/mitigation of contextual hallucinations | 14 | Unknown | Not assessed; no hidden state trajectory analysis |
| 2 | Semantic Entropy Probes: Robust and Cheap Hallucination Detection in LLMs | 2024 | Probes trained on internal representations for hallucination detection | 14 | Unknown | Probes use single-token representations, not full trajectory |
| 3 | INSIDE: LLMs’ Internal States Retain the Power of Hallucination Detection | 2024 | Internal state features used for hallucination detection | 13 | Unknown | Likely uses hidden states at specific layers; trajectory not examined |
| 4 | LLMs Know More Than They Show: On the Intrinsic Representation of LLM Hallucinations | 2024 | Analysis of internal representations for hallucination detection | 12 | Unknown | Representation-level analysis; trajectory dynamics not emphasized |
| 5 | MixHD: A Method for Detecting Hallucinations Based on the Internal State and Output Probability of Large Language Models | 2025 | Combined internal state and output probability for detection | 11 | Unknown | Internal state from last token; not trajectory-level |
| 6 | Prompt-Guided Internal States for Hallucination Detection of Large Language Models | 2024 | Prompt-specific internal state analysis for detection | 11 | Unknown | Single hidden state, not sequential trajectory |
| 7 | Unsupervised Real-Time Hallucination Detection based on the Internal States of Large Language Models | 2024 | Unsupervised detection using internal states | 11 | Unknown | Method likely uses single token state; trajectory not central |
| 8 | HaluGNN: Hallucination detection in large language models using graph neural network | 2025 | GNN-based detection using text features, not hidden states | 8 | Unknown | Not based on hidden state trajectories |
| 9 | SelfCheckGPT: Zero-Resource Black-Box Hallucination Detection for Generative Large Language Models | 2023 | Black-box consistency checking, no internal state access | 8 | Unknown | No hidden state analysis possible |
| 10 | Detecting hallucinations in large language models using semantic entropy | 2024 | Semantic entropy from multiple generations; probabilistic approach | 7 | Unknown | No hidden state trajectory used |

**Note:** Evidence strength is labeled as "medium" for papers 1-7 and 9-10, and "low" for paper 8 by the pipeline. Full text has not been verified for any paper.

## Coverage Assessment

### What Prior Work Exists in This Area
The search found substantial prior work on hallucination detection using **internal states** of LLMs. Papers 2–7 all propose methods that extract hidden representations (typically from the last token or a specific layer) and train classifiers, probes, or unsupervised scorers to detect hallucinated content. This indicates that **using internal representations for hallucination detection is an active research area**.

### Coverage of Trajectory-Level Anomaly Detection
The search did not surface papers that explicitly frame hallucination detection as a **trajectory-level anomaly detection problem** over token-level hidden states. The identified methods typically use:
- A single hidden vector per generation (e.g., last token representation)
- Probe or classifier training on pooled representations
- Attention maps (Paper 1) rather than full state sequences

This suggests that the specific framing of **token-level hidden state trajectory anomaly detection** is not directly covered in the retrieved evidence. However, this is an absence of evidence within the searched sources, not a determination that such work does not exist.

### Coverage of Hallucination Definitions and Labeling
The retrieved abstracts do not provide sufficient detail on how hallucination is operationally defined in each study. No evidence from the search can inform how to reliably label data for the proposed study.

### Coverage of Model Families and Decoding Effects
No evidence in the top-k provides comparisons across model sizes, architectures, or decoding strategies with respect to hidden state trajectories. This gap remains open.

### Types of Hallucination Addressed
The "Lookback Lens" paper specifies *contextual* hallucinations. Other papers may treat hallucination broadly, but the abstracts do not distinguish factual vs. contextual types. No evidence on whether different hallucination types produce distinct trajectory patterns was found.

### Competing Approaches (Non-Hidden-State Methods)
The search found black-box methods that do not require internal state access (Paper 9: SelfCheckGPT, Paper 10: Semantic Entropy). These represent alternative detection paradigms that could serve as baselines but do not provide trajectory-level evidence.

## Open Questions

Based on the evidence gaps and the research contract constraints, the following questions remain open for later stages:

1. **Trajectory formulation in existing work:** Do any prior studies (not captured by this search) analyze sequences of hidden states across tokens, rather than single token representations? If so, what alignment or representation methods were used?

2. **Label reliability:** How have prior studies defined and validated hallucination labels? Do these definitions allow separating truthful from hallucinated trajectories reliably?

3. **Reference distribution stability:** Is there evidence in the broader literature that hidden state statistics remain stable across prompts, domains, or decoding parameters for truthful generations?

4. **Sensitivity to confounds:** Do existing internal-state-based methods actually detect hallucination, or do they correlate with confounding factors such as output length, token position, or prompt difficulty? The retrieved evidence does not address this.

5. **Real-time detection feasibility:** Papers 7 and 10 mention real-time or unsupervised settings. However, no evidence confirms whether trajectory-level anomaly detection can be performed at inference time without gold labels.

6. **Method transferability:** The evidence does not indicate whether methods from one model family (e.g., Llama) generalize to others. This question remains open.

7. **Evaluation metrics used in prior work:** The evidence does not provide sufficient detail on evaluation metrics (e.g., AUC, precision/recall) for state-based hallucination detection, limiting comparability.

## Limitations

1. **Single source (OpenAlex):** Only OpenAlex was queried. Other databases (arXiv, Semantic Scholar, Crossref) were not used, which may have resulted in relevant work being missed.

2. **No full-text verification:** The evidence is based solely on abstracts and metadata. Full-text analysis could reveal trajectory-level approaches not evident from abstracts.

3. **Deterministic relevance scoring:** Relevance scores are based on keyword/concept matching, not semantic judgment. Papers may be misclassified as high relevance due to incidental keyword overlap, or low relevance despite genuine topical alignment.

4. **Abstract-level information only:** Details on methodology (e.g., trajectory construction, model size, dataset) are generally not available from abstracts. This limits the ability to compare the candidate study framework with existing work.

5. **No manual relevance assessment:** The pipeline's "relevance_to_research_contract" field is explicitly unassessed. The evidence table reflects only automated scoring.

6. **Coverage of trajectory anomaly detection:** The search did not explicitly include terms for "trajectory anomaly", "sequential anomaly detection", or "time series anomaly detection on hidden states". This may have missed relevant methods from other domains (e.g., unsupervised sequence anomaly detection applied to representations).

7. **Recency bias:** The top-k is weighted toward 2024–2025. Earlier foundational work on using hidden states for hallucination detection or trajectory analysis may be underrepresented.

8. **Hallucination definitions:** The search did not filter or group by hallucination type (factual, contextual, faithfulness). The retrieved studies may use heterogeneous definitions, making cross-study synthesis challenging.

---

This artifact is literature evidence only. Novelty determination is performed by the novelty_checker stage.
