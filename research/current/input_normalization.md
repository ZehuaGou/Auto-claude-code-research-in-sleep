---
implementation_source: routed_internal_model
routed_model_used: True
route_role: input_normalizer
route_expected_backend: openai_compatible_api
route_expected_model: deepseek-v4-flash
actual_backend: deepseek
actual_model: deepseek-v4-flash
ledger_call_id: call_913451ff60ff
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
task_id: wf_input_normalization_6c567850
context_manifest: tmp/wf_input_normalization_manifest.json
allowed_input_files: ["research\\current\\raw_user_input.md"]
forbidden_context: ["old conclusions", "previous experiment results", "mock results", "external_agent_direct", "user preference shortcuts", "unverified literature conclusions", "generator trace", "other candidates"]
forbidden_context_checked: true
context_hash: 88524a287ec9ca9fca3b9f40c1079ce1d1e11e2acbc73b4a50d3adfd2d10f43c
prompt_file: 
response_file: 
source_boundary: workflow_input_normalization_minimal_allowed_inputs_only
contamination_scan_status: checked
error_code: 
error: 
---

# Normalized Research Brief & Candidate Idea

## Structured Brief

### Core Question
Can hallucination in large language models be detected as an anomaly in token-level hidden state trajectories?

### Initial Hypothesis
When a model begins to hallucinate (i.e., generate content that is not factually grounded or coherent with prior context), its hidden state trajectory—the sequence of hidden states across tokens—may deviate from the trajectories observed during truthful or well-grounded generations. Such deviations might be measurable using trajectory-level anomaly detection methods.

### Key Concepts
- **Token-level hidden state trajectory**: The sequence of hidden state vectors produced by the LLM at each token position during generation.
- **Hallucination**: Generation of plausible-sounding but factually incorrect or ungrounded content.
- **Trajectory-level anomaly detection**: Techniques that identify sequences of data points (here, hidden state vectors) that differ significantly from a reference distribution.

### Constraints (Acknowledged from User)
- No experiments are to be conducted at this stage.
- No claims of novelty are to be made.
- No web searches are performed in input normalization.
- No old experiment results are used as evidence.
- Uncertainty must be explicitly marked as assumptions or open questions.

---

## Candidate Idea

### Proposed Study Framework
1. **Collect reference trajectories** from generations that are known to be truthful/well-grounded (e.g., based on verifiable sources or human annotations).
2. **Analyze trajectories** from model outputs that are known to contain hallucinations (using a separate evaluation set).
3. **Apply anomaly detection** to quantify the deviation of a candidate trajectory from the reference distribution. Methods could include:
   - Distance-based measures (e.g., dynamic time warping, Euclidean distance of summary statistics).
   - Density-based methods (e.g., local outlier factor on trajectory embeddings).
   - Reconstruction-based methods (e.g., autoencoder reconstruction error).
4. **Evaluate** whether the anomaly scores correlate with the presence of hallucination, using metrics like precision/recall or AUC.

### Assumptions (to be validated or revised)
- *Assumption*: Hidden state trajectories during hallucination are systematically different from those during truthful generation.
- *Assumption*: The deviation is large enough to be detectable by standard anomaly detection methods given token-level noise.
- *Assumption*: Ground truth labels for hallucination vs. truthful generation are available or can be reliably produced.
- *Assumption*: The chosen anomaly detection method is sensitive to trajectory-level patterns rather than token-level noise.

### Open Questions (requiring further investigation)
- *Question*: How do we define a "trajectory" for variable-length outputs? (e.g., align by token position, use padding, or treat each output as a multivariate series?)
- *Question*: Do different types of hallucination (e.g., factual vs. contextual) produce distinct trajectory patterns?
- *Question*: How does the model size, architecture, or decoding strategy affect trajectory behavior and anomaly detectability?
- *Question*: Can the approach be applied at inference time (e.g., detect hallucination as it occurs) or only post-hoc?
- *Question*: Is the reference distribution of "truthful" trajectories stable across different prompts and domains?
- *Question*: What is the impact of input length, generation length, and sampling temperature on trajectory statistics?

### Next Steps (conceptual, not experimental)
- Define precise criteria for what constitutes a "hallucination" in the study.
- Select or design a synthetic dataset where ground truth is known (e.g., factual recall tasks with controlled perturbations).
- Choose a candidate LLM and a set of anomaly detection algorithms to evaluate.
- Outline metrics for success (e.g., detection accuracy, false positive rate, robustness to benign variability).
