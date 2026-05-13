---
implementation_source: routed_internal_model
routed_model_used: True
route_role: method_refiner
route_expected_backend: openai_compatible_api
route_expected_model: deepseek-v4-pro
actual_backend: deepseek
actual_model: deepseek-v4-pro
ledger_call_id: call_5c762b8a3e74
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
task_id: wf_method_refinement_017e1157
context_manifest: D:\Code\Python\Auto-claude-code-research-in-sleep\tmp\wf_method_refinement_manifest.json
allowed_input_files: ["research\\current\\input_normalization.md", "research\\current\\trusted_outputs\\research_contract.md", "research\\current\\literature_notes.md", "research\\current\\trusted_outputs\\literature_search.md", "research\\current\\trusted_outputs\\novelty_check.md", "literature\\search_runs\\current\\top_k.md", "docs\\LITERATURE_REPAIR_QUEUE.md"]
forbidden_context: ["old conclusions", "old experimental results", "unverified novelty conclusions", "mock/dry-run artifact", "external_agent_direct output", "user preference shortcuts", "implementation code", "paper draft", "experiment outputs", "prior optimistic summaries", "generator trace"]
forbidden_context_checked: true
context_hash: 618b19f354146625df828d82445ad4b2ac7ba2a2a576d1cd6d76e956358c93da
prompt_file: 
response_file: 
source_boundary: workflow_method_refinement_minimal_allowed_inputs_only
contamination_scan_status: checked
error_code: 
error: 
---

# Method Refinement — Generic Method Specification

## Scope and Evidence Boundary

- This is **not an experiment plan**.
- This is **not a novelty proof**.
- This is **not a paper claim**.
- It uses **current trusted artifacts** and the **evidence‑bounded novelty_check** only.
- Current evidence limitations remain active: only metadata/abstracts reviewed; no full‑text verification; keyword‑based relevance, not semantic; Semantic Scholar omitted; only OpenAlex examined in the novelty_check (despite other sources in literature_search).

## Research Idea Under Refinement

**Can hallucination in large language models be detected as an anomaly in token‑level hidden state trajectories?**

The idea is to frame hallucination detection as a trajectory‑level anomaly detection problem:

1. Extract the hidden state vector at each generated token (the “trajectory”).
2. Build a reference distribution from trajectories of well‑grounded (truthful) generations.
3. For a new generation, compute how anomalous its trajectory is with respect to that reference – using distance‑based, density‑based, or reconstruction‑based anomaly detection.
4. Use the anomaly score (or a threshold on it) to flag probable hallucinations.

This restatement does not expand claims beyond the input_normalization and research_contract; it remains a candidate framing.

## Method Object Definition

The method is defined abstractly as a **generic trajectory‑anomaly detection framework** for LLM hidden states. It does **not** commit to a single anomaly algorithm or dataset. Instead it specifies:

- **Trajectory**: a sequence \(\mathbf{h}_1, \mathbf{h}_2, \dots, \mathbf{h}_T\) where \(\mathbf{h}_t\) is the hidden state (or a chosen layer’s output) at token position \(t\).
- **Reference distribution**: a model (e.g., set of truthful trajectories, a parametric density, an autoencoder) that captures typical non‑hallucinated trajectory variation.
- **Anomaly score function** \(a(\tau; \mathcal{D}_{\text{ref}})\) that measures how atypical a test trajectory \(\tau\) is relative to the reference.
- **Decision**: an optional threshold on \(a\) to classify a generation as hallucinated.

The specification must be resolvable to a concrete design later, but currently it remains at the conceptual method‑object level.

## Inputs and Outputs

**Inputs** (assumed to be available in a later concrete study):
- LLM with per‑token hidden states accessible (white‑box setting).
- A set of *truthful/well‑grounded* generations with corresponding hidden state trajectories (to form the reference).
- A set of *hallucinated* generations (for evaluation).
- Operational definition of hallucination labels (binary or typed).

**Outputs** (of the method when applied):
- An anomaly score for each test trajectory.
- A binary (or multi‑class) hallucination flag if a threshold is chosen.
- Per‑token or per‑segment contributions to the anomaly score (optional, for interpretability).

Note: the reference distribution itself is a learned/constructed output from the truthful set.

## Proposed Mechanism

The mechanism is a pipeline:

1. **Extraction** – run the LLM on a prompt, record the hidden state vector at each generated token from one or more layers (e.g., a late layer). Store as a matrix \(\mathbf{H} \in \mathbb{R}^{T \times d}\).
2. **Trajectory representation** – convert variable‑length sequences into a fixed‑form representation. Options include: padding/truncation to a maximum length with positional alignment, dynamic time warping (DTW) barycenters, summary statistics (mean, variance) over token positions, or learning an embedding via a recurrent autoencoder.
3. **Reference construction** – from the set of truthful trajectories compute a reference model \(p(\tau)\) or a set of prototypes. Examples: fit a Gaussian mixture model on pooled (or aligned) representations, train an autoencoder to reconstruct truthful trajectories (reconstruction error serves as anomaly score), or keep the raw set and use \(k\)-nearest neighbor density.
4. **Anomaly scoring** – for a new trajectory \(\tau\), compute a score \(a(\tau)\) that quantifies departure from the reference. Candidate families:  
   - *Distance‑based*: DTW distance to the nearest reference trajectory.  
   - *Density‑based*: negative log‑likelihood under the reference density, local outlier factor (LOF).  
   - *Reconstruction‑based*: reconstruction error from an autoencoder trained only on truthful trajectories.
5. **Thresholding (optional)** – a cutoff on \(a\) determines “hallucination”, tuned on a validation set.

The mechanism does not prescribe a specific algorithm; it sets the abstract components that any concrete realisation must supply.

## Differentiator From Closest Prior Work

The **apparent differentiator** of this method specification is the **explicit framing as a trajectory‑level anomaly detection problem with a built reference distribution, variable‑length trajectory handling, and unsupervised anomaly scoring on the full token sequence** – while prior work in the retrieved evidence predominantly uses classification, probing, or single‑token/aggregated features, not a “reference vs. anomalous trajectory” paradigm.

- **Closest work**: INSIDE (2024) uses internal states for hallucination detection but as a probe/classifier, not an unsupervised anomaly detector on full trajectories. ICR Probe (2025) tracks hidden state dynamics, but its abstract suggests probe‑based classification, not anomaly scoring. Unsupervised Real‑Time Hallucination Detection (2024) is unsupervised, but whether it operates on full trajectories or per‑token aggregates is unknown from the abstract.
- **Apparent difference**: In the proposed method, the anomaly score is derived from the whole sequence’s deviation from a *reference distribution of truthful trajectories*, which is not attested in the available abstracts. This contrasts with methods that train a discriminator on labeled “hallucination vs. truth” (supervised) or that use per‑token logit differences.
- **Qualifier**: This differentiator is **apparent only**. Full‑text verification is absent; the ICR Probe or other papers may already implement a trajectory‑level anomaly formulation that would eliminate this difference. The evidence does **not** confirm that the differentiator holds. It is not claimed as novelty.

No claim is made that prior work “lacks this idea”; the assessment is limited to available metadata and abstracts.

## Testable Hypotheses

If the method were implemented, the following hypotheses would become‑testable:

1. **H1 – Separation hypothesis**: For a fixed LLM and domain, the anomaly scores of hallucinated trajectories are statistically significantly higher than those of truthful trajectories (e.g., measured by AUC > 0.5).
2. **H2 – Trajectory alignment matters**: A method that ignores token position (e.g., pooling all hidden states into a single vector) yields lower discriminative power than a method that preserves sequential order (e.g., DTW or RNN‑based autoencoder).
3. **H3 – Hallucination type specificity**: Factual hallucinations produce different trajectory‑anomaly signatures than contextual inconsistency hallucinations; a single anomaly detector may fail to capture both.
4. **H4 – Robustness to confounds**: The anomaly score is not solely driven by output length, token frequency, or decoding temperature; removing those confounds (via stratification or baselines) does not eliminate the hallucination signal.
5. **H5 – Reference stability**: A reference distribution built on one set of prompts (domain A) maintains reasonable anomaly detection on a different set of prompts (domain B) if the model and decoding strategy are held constant.
6. **H6 – Post‑hoc vs. real‑time**: The anomaly score computed after generation is complete (post‑hoc) dominates per‑token rolling scores in detection accuracy, but per‑token scores offer earlier detection.

These hypotheses are presented as design specifications for a future experiment; they are not claimed to be true.

## Non‑Claims and Claim Boundaries

- **No final novelty proof**. The method specification does not establish the idea as novel.
- **No full‑text verification**. All comparisons rely on abstracts and metadata; full‑text may reveal prior trajectory‑level anomaly approaches.
- **No claim of superiority**. The method is not claimed to outperform existing hallucination detection techniques.
- **No claim of general solution**. The specification does not guarantee the method works across all models, domains, or definitions of hallucination.
- **No claim that prior work lacks this idea**. The current evidence only indicates that trajectory‑level anomaly formulation is not visible in retrieved abstracts; it is not a proof of absence.

## Minimum Experiment Boundary

Should the method advance to experiment_plan, the following minimal components must be secured:

- Access to an LLM that exposes per‑token hidden states (e.g., an open‑source transformer).
- A dataset with reliable hallucination labels (e.g., factual QA where answer correctness can be verified).
- A concrete choice of trajectory representation (e.g., last‑layer states, aligned with padding/truncation) and anomaly detection algorithm (e.g., autoencoder reconstruction error).
- A protocol for constructing the reference distribution (e.g., from a dedicated truthful subset).
- Evaluation metrics: at minimum AUC of anomaly scores vs. hallucination labels, and false positive/negative rates at a chosen threshold.
- Control baselines: (a) a per‑token classifier using the same hidden states, (b) a model‑agnostic baseline (e.g., output logit entropy), (c) a randomised anomaly score.

This boundary prevents speculation; it does not constitute an experiment plan.

## Risks and Open Questions

**Risks from current evidence (novelty_check & literature_search):**

- Medium‑to‑high overlap: internal‑state hallucination detection is already well‑represented; the trajectory‑level claim may be incremental rather than a gap.
- Low confidence possible gap on trajectory‑level anomaly: the evidence is too weak to distinguish; full‑texts of ICR Probe and unsupervised real‑time detection could close the gap.
- The method may collapse into detecting length, token frequency, or decoding noise rather than hallucination (research_contract failure condition).
- The needed reference distribution may not be stable across domains, leading to poor transfer.

**Open questions (from input_normalization and contract):**

- How should variable‑length trajectories be aligned or represented? (padding, DTW, recurrent autoencoders, pooling).
- Do different hallucination types produce distinguishable trajectory patterns?
- How does model size, architecture, or decoding strategy affect trajectory behaviour and detectability?
- Can the method operate at inference time (streaming detection) or only post‑hoc?
- Is the reference distribution stable enough across prompts and domains?
- What is the impact of input length, generation length, and sampling temperature on trajectory statistics?
- How should a “truthful” trajectory set be curated to avoid label noise?
- Would a fully synthetic setup (controlled fact perturbations) generalise to natural hallucination conditions?

## Readiness Gate for experiment_plan

**Readiness label: `needs_more_literature_evidence`**

**Justification**: The method specification’s apparent differentiator depends on the trajectory‑level anomaly formulation not being present in prior work. However, the current evidence is limited to metadata and abstracts; critical papers (ICR Probe, INSIDE, unsupervised real‑time) have not been full‑text verified. The novelty_check verdict is “low_confidence_possible_gap” and overall “insufficient_evidence”. Advancing to experiment_plan under these conditions risks building on an increment that may already exist in the literature. Therefore, the minimum requirement is to collect and review the full text of the closest prior works to either confirm or refute the apparent gap.

## Next Allowed Action

**collect_more_literature**

(This action entails obtaining full‑texts of the top‑k papers, especially ICR Probe, INSIDE, and Unsupervised Real‑Time Hallucination Detection, and re‑running the novelty_check stage with the enriched evidence. No experiment_plan step should be taken until the readiness gate is satisfied.)

---

This artifact is a method specification only. It is not an experiment plan, a novelty proof, or a paper claim. Do not advance to experiment_plan without meeting the readiness gate criteria above.
