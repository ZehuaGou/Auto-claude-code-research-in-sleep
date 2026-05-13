---
implementation_source: routed_internal_model
routed_model_used: True
route_role: method_refiner
route_expected_backend: openai_compatible_api
route_expected_model: deepseek-v4-pro
actual_backend: deepseek
actual_model: deepseek-v4-pro
ledger_call_id: call_74a3b9561c50
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
task_id: wf_method_refinement_8a1ed5b1
context_manifest: D:\Code\Python\Auto-claude-code-research-in-sleep\tmp\wf_method_refinement_manifest.json
allowed_input_files: ["research\\current\\input_normalization.md", "research\\current\\trusted_outputs\\research_contract.md", "research\\current\\literature_notes.md", "research\\current\\trusted_outputs\\literature_search.md", "research\\current\\trusted_outputs\\novelty_check.md", "literature\\search_runs\\current\\top_k.md", "docs\\LITERATURE_REPAIR_QUEUE.md"]
forbidden_context: ["old conclusions", "old experimental results", "unverified novelty conclusions", "mock/dry-run artifact", "external_agent_direct output", "user preference shortcuts", "implementation code", "paper draft", "experiment outputs", "prior optimistic summaries", "generator trace"]
forbidden_context_checked: true
context_hash: fb4e59066c120b91f8c70f20fb2456458ec152dbced52e1c18af6460421d10c4
prompt_file: 
response_file: 
source_boundary: workflow_method_refinement_minimal_allowed_inputs_only
contamination_scan_status: checked
error_code: 
error: 
---

# Method Refinement — Generic Method Specification

## 1. Scope and Evidence Boundary
- This is not an experiment plan.
- This is not a novelty proof.
- This is not a paper claim.
- It uses current trusted artifacts and the evidence-bounded novelty_check only.
- The evidence base is limited to OpenAlex metadata/abstracts only; no full‑text verification.
- Current evidence limitations remain active, including unverified abstracts, single‑source coverage, and absence of trajectory‑specific queries.

## 2. Research Idea Under Refinement
The candidate idea proposes detecting hallucination (factually incorrect or ungrounded generation) in large language models by treating the token‑level hidden state trajectory as an anomaly detection target.  
A reference distribution of hidden‑state trajectories is built from known‑truthful generations. Trajectories from hallucinated outputs are then scored for deviation from this reference using trajectory‑level anomaly detection methods (distance‑, density‑, or reconstruction‑based). The hypothesis is that hallucination causes detectable trajectory‑level deviations, allowing the method to identify potentially hallucinated content.

This restatement does not expand claims; it remains bounded by the input_normalization and research_contract documents.

## 3. Method Object Definition
The method under refinement is a **trajectory‑level hallucination detector** that operates solely on token‑wise hidden‑state sequences produced by a large language model during autoregressive generation.  
It does not use output text directly, logits, or attention maps. The detector includes:
- A trajectory extraction and representation procedure.
- A reference‑distribution construction mechanism (trained or defined on truthful trajectories).
- An anomaly scoring function that quantifies how atypical a test trajectory is relative to that reference.
- A decision threshold (or continuous score) that maps anomaly scores to a hallucination indication.

## 4. Inputs and Outputs
**Inputs**
- A sequence of hidden state vectors \(\{h_1, h_2, \dots, h_T\}\) for the generated tokens (one vector per output token, from one or more specified layers of the LLM).
- Optionally: metadata about the generation (e.g., prompt, generation length, sampling temperature) to support conditioning or normalization.

**Outputs**
- A continuous anomaly score \(s \in \mathbb{R}\) representing trajectory atypicality.
- Interpretation: higher scores indicate greater likelihood of hallucination (to be validated by correlation with human labels or ground‑truth hallucination annotations).

## 5. Proposed Mechanism
The detector is constructed in three stages:

1. **Trajectory representation**  
   - Each generation is represented as a sequence of hidden states (possibly truncated/padded to a fixed length, or embedded into a fixed‑dimensional summary via a learned sequence encoder like an LSTM/Transformer).  
   - Alignment decisions (e.g., time warping) or position‑wise aggregation are applied to handle variable‑length outputs.

2. **Reference distribution building**  
   - A set of known‑truthful generations (verified by human annotations, knowledge‑grounded corpora, or controlled tasks) is collected.  
   - Trajectories from this set are used to fit an anomaly detection model:  
     - *Distance‑based*: compute pairwise distances (e.g., dynamic time warping distance) to define a typical distance profile or a cluster centroid; anomaly score = distance to centroid or average distance to k‑nearest neighbours.  
     - *Density‑based*: train a density estimator (e.g., Gaussian mixture model on trajectory embeddings) and compute likelihood of test trajectory.  
     - *Reconstruction‑based*: train an autoencoder on truthful trajectories; anomaly score = reconstruction error.

3. **Anomaly scoring and thresholding**  
   - For a test generation, extract the trajectory, compute the anomaly score using the chosen method.  
   - A threshold can be calibrated on a validation set to balance precision/recall (though threshold‑free evaluation via AUC is also envisioned).

The mechanism does not commit to a specific anomaly detection algorithm but requires that the choice be sensitive to trajectory‑level patterns, not just single‑token statistics.

## 6. Differentiator From Closest Prior Work

The **apparent differentiator** of the current method specification is the explicit treatment of the full token‑level hidden‑state sequence as a *trajectory* and the application of *trajectory‑ (sequence‑) level anomaly detection methods*, as opposed to the prevalent single‑vector, last‑token, or probe‑based approaches found in the introduced evidence.

Comparisons against closest prior works (from novelty_check):
- **INSIDE** (Chen et al., 2024) uses internal‑state features but does not operate on the full temporal sequence; likely aggregates or uses selected token states. The proposed method focuses on the sequence dynamics.
- **Semantic Entropy Probes** (Kossen et al., 2024) trains probes on internal representations, typically single‑vector per generation. No trajectory‑level anomaly scoring is involved.
- **LLMs Know More Than They Show** (Orgad et al., 2024) analyses intrinsic representations but does not frame hallucination detection as trajectory anomaly detection.
- **MixHD** (Li et al., 2025) and **Prompt‑Guided Internal States** (Zhang et al., 2024) use last‑token or prompt‑specific single hidden states. The trajectory notion is absent.
- **Lookback Lens** (Chuang et al., 2024) uses attention maps, not hidden‑state sequences; a different signal.

The differentiator is qualified as **apparent** because:
- Full texts have not been verified; existing papers could describe trajectory‑like usage in their methodology.
- The literature search was incomplete (OpenAlex‑only, metadata‑only).
- No direct comparison was performed.

## 7. Testable Hypotheses
If the method is later instantiated with a concrete trajectory representation and anomaly detection algorithm, the following hypotheses can be tested:

- H1: The distribution of trajectory‑level anomaly scores for hallucinated generations is statistically different from that of truthful generations (e.g., Mann‑Whitney U test, AUC > 0.5).
- H2: A trajectory‑based detector outperforms a detector that uses only the last‑token hidden state (or the mean pooled state) on a common hallucination‑detection benchmark, holding other factors constant.
- H3: The chosen trajectory representation (e.g., DTW distance) captures hallucination‑relevant structural differences beyond length or token‑position artefacts (testable by controlling for length and token position as confounders).

These hypotheses are framed as testable but await a fully specified experimental setup.

## 8. Non‑Claims and Claim Boundaries
- **No final novelty proof.**  
- **No full‑text verification** of prior art has been performed.  
- **No claim of superiority** over existing methods.  
- **No claim of general solution** that works across all models, domains, or hallucination types.  
- **No claim that prior work lacks this idea**—absence of evidence in the current limited search does not imply absence of prior work.

## 9. Minimum Experiment Boundary
Any experiment plan derived from this method specification must at minimum:
- Define a concrete trajectory representation (including length handling, alignment, and possibly layer selection).
- Choose a specific anomaly detection algorithm and reference‑distribution construction.
- Use a dataset with curated ground‑truth hallucination labels (not just synthetic length‑based proxies).
- Control for confounds: generation length, prompt complexity, decoding temperature.
- Compare against at least one single‑vector baseline (e.g., last‑token anomaly score or probe).
- Report evaluation in a threshold‑free manner (e.g., AUC) to avoid cherry‑picking of operating points.

## 10. Risks and Open Questions
**Risks**
- **Confound capture**: The anomaly score may detect output length, token position, or prompt difficulty rather than hallucination, especially if not carefully controlled.
- **Reference‑distribution instability**: Truthful trajectories may vary widely across domains or prompts, making a single reference distribution ineffective.
- **Insufficient signal**: Hidden states might not encode hallucination in a way that is detectable at the trajectory level; token‑level noise could obscure systematic deviations.
- **Method overlap**: Full‑text examination may reveal prior work that already uses trajectory‑level anomaly detection on hidden states, reducing the apparent differentiator to a replication.

**Open Questions**
- How should variable‑length trajectories be aligned or embedded without destroying temporal information?
- Do different types of hallucination (factual, contextual) require distinct trajectory representations or detectors?
- What is the optimal layer or combination of layers to extract hidden states for trajectory analysis?
- How does the choice of decoding strategy (greedy vs. sampling) affect trajectory consistency and detectability?
- Is a static reference distribution sufficient, or must it be conditioned on the prompt or domain?
- Can the method operate in a zero‑shot setting with no access to hallucination labels for threshold calibration?

## 11. Readiness Gate for experiment_plan
**needs_more_literature_evidence**

**Justification**  
- The current evidence base (OpenAlex metadata only, no full‑text) is too shallow to confirm that the trajectory‑level anomaly framing is not already present in the literature.  
- Key implementation choices (trajectory representation, alignment method) depend on whether prior art has already addressed them; committing to a method specification for experiments without that knowledge risks duplicating existing work or missing critical baselines.  
- Several open questions (Section 10) cannot be resolved without a broader search that includes full‑text analysis and queries specifically targeting trajectory anomaly detection on LLM representations.  
- Therefore, the method specification cannot yet credibly support an experiment plan with the required differentiation and rigorous control.

## 12. Next Allowed Action
**collect_more_literature**

*(Do not proceed to experiment_plan. Expand literature search to include arXiv, Semantic Scholar, Crossref; pursue full‑text verification for top candidates; and add dedicated queries for “trajectory anomaly detection LLM hidden states”. After evidence expansion, revisit method refinement and reassess readiness.)*

---

This artifact is a method specification only. It is not an experiment plan, a novelty proof, or a paper claim. Do not advance to experiment_plan without meeting the readiness gate criteria above.
