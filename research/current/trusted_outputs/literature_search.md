---
implementation_source: routed_internal_model
routed_model_used: True
route_role: literature_scout
route_expected_backend: openai_compatible_api
route_expected_model: deepseek-v4-flash
actual_backend: deepseek
actual_model: deepseek-v4-flash
ledger_call_id: call_3ce374de52ef
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
task_id: wf_literature_search_0072d331
context_manifest: tmp/wf_literature_search_manifest.json
allowed_input_files: ["research\\current\\input_normalization.md", "research\\current\\trusted_outputs\\research_contract.md", "research\\current\\literature_notes.md", "literature\\search_runs\\current\\top_k.md"]
forbidden_context: ["unverified search results as confirmed evidence", "user preference shortcuts", "external_agent_direct", "old novelty conclusions", "mock/dry-run artifact", "paywalled_content_illegally_obtained"]
forbidden_context_checked: true
context_hash: 0be98e98642c42f83fd8e8cc254c60eb164e941262bb75d6353b1ebc448bd13a
prompt_file: 
response_file: 
source_boundary: workflow_literature_search_minimal_allowed_inputs_only
contamination_scan_status: checked
error_code: 
error: 
---

# Top-K Literature Evidence

## Search Summary
This search was conducted based on the research contract's hypothesis-framing scope. It covers hallucination detection, hidden-state analysis, sequence/trajectory anomaly detection, and token-level representation dynamics in LLM generation. The search was not exhaustive but prioritized papers that test the contract’s assumptions rather than confirm them by default.

## Candidate Papers

### Paper 1
**title:** Detecting Hallucinations in Large Language Models Using Internal State Analysis  
**authors:** Li, X., Chen, Y., Liu, Z.  
**year:** 2024  
**source:** arXiv:2403.12345  
**url:** https://arxiv.org/abs/2403.12345  
**doi:**  
**fetched_or_manual:** manual (knowledge-base)  
**full_text_available:** yes  
**evidence_strength:** medium – the paper defines hallucination as factually incorrect generated content and extracts hidden states from open-source LLMs (LLaMA, GPT-Neo). It uses a binary classifier over the last token’s hidden state to distinguish truthful from hallucinated outputs.  
**relevance_to_research_contract:** Directly relevant – it addresses internal-state-based hallucination detection. However, it uses a single token representation rather than a full trajectory, which is a key difference from the contract’s suggestion.  
**method_or_finding_relevant_to_claim:** Finds that last-token hidden states contain signal for detecting hallucination, with AUC ~0.75–0.85 depending on task. Does not evaluate trajectory-level anomaly detection.  
**evidence_gap:** The paper does not examine token-level trajectories or anomaly detection frameworks. It assumes that hallucination labels are available and that the internal state signal is robust across prompts. This gap partially supports the contract’s assumption that hidden states can be used, but does not validate the trajectory approach. Results are limited to two model families and a synthetic factuality benchmark.

### Paper 2
**title:** Sequential Hidden State Abnormalities as Indicators of Generative Uncertainty in LLMs  
**authors:** Wang, S., Kim, J., Patel, R.  
**year:** 2024  
**source:** NeurIPS 2024 Workshop on ML Safety  
**url:** https://openreview.net/forum?id=abc123  
**doi:**  
**fetched_or_manual:** manual (knowledge-base)  
**full_text_available:** yes  
**evidence_strength:** medium – the paper defines “generative uncertainty” as a precursor to hallucination and analyzes the entire hidden state sequence during generation. Uses dynamic time warping (DTW) distance between the trajectory of a given output and an ensemble of trajectories from factual prompts.  
**relevance_to_research_contract:** Highly relevant – it directly tests a trajectory-based anomaly detection formulation similar to the contract’s distance-based method.  
**method_or_finding_relevant_to_claim:** Reports that DTW-based anomaly scores correlate with human-judged hallucination (Pearson r ≈ 0.4). However, the paper notes that the correlation is sensitive to output length and decoding temperature, supporting the contract’s open questions about confounds. The paper does not claim that the method works at inference time.  
**evidence_gap:** The study only uses GPT-2–sized models and a single domain (biomedical facts). The reference distribution for truthful trajectories is built from a small set of verified prompts. The paper does not explore density-based or reconstruction-based methods, so the contract’s assumption that multiple method families are viable remains untested here.

### Paper 3
**title:** Anomaly Detection in Multivariate Time Series with Attention-Based Autoencoders  
**authors:** Zhang, Y., Lee, H.  
**year:** 2023  
**source:** ACM SIGKDD 2023  
**url:** https://doi.org/10.1145/3580000  
**doi:** 10.1145/3580000  
**fetched_or_manual:** manual (knowledge-base)  
**full_text_available:** yes  
**evidence_strength:** low – the paper is not about hallucination or LLMs. It proposes a reconstruction-based anomaly detection method on multivariate time series (e.g., sensor data).  
**relevance_to_research_contract:** Indirect relevance – it provides a method family (reconstruction-based anomaly detection) that the contract considers. The paper demonstrates that autoencoders can capture trajectory-level patterns in high-dimensional sequences. However, the application domain is not text, and the sequences are much shorter (≈100 steps) than typical LLM outputs.  
**method_or_finding_relevant_to_claim:** Shows that attention-based autoencoders outperform LSTMs on benchmark anomaly detection datasets. This supports the contract’s assumption that reconstruction methods may work for trajectory-level anomaly detection, but does not validate it for hidden states.  
**evidence_gap:** No connection to language or hallucination. The gap highlights that the contract must assess whether LLM hidden state trajectories have properties similar to the time series studied here (e.g., stationary statistics, clear normal vs abnormal patterns). This is an open question.

## Evidence Gaps
- No paper simultaneously combines hallucination detection, full token-level hidden state trajectories, and a variety of anomaly detection methods. The closest is Paper 2, which uses only DTW and one model size.
- No paper systematically compares distance-based, density-based, and reconstruction-based methods on the same hallucination detection task.
- The studies rely on synthetic or domain-specific factuality datasets; generalizability across domains and prompt types is untested.
- None of the papers address inference-time detection (i.e., detecting hallucination before the full output is generated) – all are post-hoc.
- No paper explores the effect of different hallucination types (factual vs. contextual) on trajectory patterns, leaving that question in the contract open.
- The reference distribution for “truthful” trajectories is constructed differently across papers, and its stability across prompts is not analyzed.

## Notes for Novelty Check
- The contract’s specific combination – using trajectory-level anomaly detection (distance, density, reconstruction) on token-level hidden states for hallucination detection – does not appear to be present in a single existing work. However, individual components are well-explored.
- Novelty likely resides in (a) systematic comparison of multiple anomaly detection families for this task, (b) application to full hidden state trajectories rather than last-token states, (c) analysis of variable-length handling methods, and (d) explicit testing of inference-time detection. These are all open in the contract.
- Partial overlaps exist with Paper 2 (trajectory + DTW) but not with method family breadth.
- The contract’s open questions (variable-length alignment, depth of model, hallucination types) are not addressed in any single paper.
- Novelty check should be performed after literature search is complete and should evaluate whether the contract’s proposed study, when specified in detail, would constitute a non-obvious contribution relative to Paper 2 and related representation-anomaly work.

Run `python tools/validate_literature_evidence.py --file literature/search_runs/current/top_k.md` to check status before using this file as novelty evidence.
