---
implementation_source: routed_internal_model
routed_model_used: True
route_role: novelty_checker
route_expected_backend: openai_compatible_api
route_expected_model: deepseek-v4-pro
actual_backend: deepseek
actual_model: deepseek-v4-pro
ledger_call_id: call_38274b614799
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
task_id: wf_novelty_check_9f41cd0b
context_manifest: D:\Code\Python\Auto-claude-code-research-in-sleep\tmp\wf_novelty_check_manifest.json
allowed_input_files: ["research\\current\\input_normalization.md", "research\\current\\trusted_outputs\\research_contract.md", "research\\current\\literature_notes.md", "research\\current\\trusted_outputs\\literature_search.md", "literature\\search_runs\\current\\top_k.md", "docs\\LITERATURE_REPAIR_QUEUE.md"]
forbidden_context: ["old novelty conclusions", "unverified experiment results", "other candidates", "user preference", "generator trace", "previous optimistic summaries", "external_agent_direct output", "mock/dry-run artifact"]
forbidden_context_checked: true
context_hash: 59d144dce05fbf97059f1f9b43c4c62639287bf7d60d0764db60f9b495292928
prompt_file: 
response_file: 
source_boundary: workflow_novelty_check_minimal_allowed_inputs_only
contamination_scan_status: checked
error_code: 
error: 
---

# Novelty Check — Evidence-Bounded Risk Assessment

## Scope and Evidence Boundary

**This is not a final novelty proof.**  
This assessment is bounded by evidence derived **only from OpenAlex** sources. The search pipeline included arXiv and Crossref records, but these were **not examined** in this novelty check per the stage contract. Semantic Scholar was deferred.  

- Only metadata and abstracts were reviewed; **no full‑text verification** was performed.  
- No experiments were conducted.  
- No claims of novelty are being made; only risk labels are assigned.

The scope is deliberately narrow: the candidate idea proposes framing hallucination detection as an **anomaly detection problem over token‑level hidden state trajectories** (full sequences). The assessment compares that idea against prior work identified through OpenAlex.

---

## Closest Prior Work and Overlap Risks

All items listed below were retrieved from OpenAlex only. For each, the apparent relation, risk type, and evidence limitation are described. The required phrase **“No explicit trajectory‑level formulation was visible in the retrieved abstracts”** is included; the absence of this phrasing in any single entry is not a positive finding.  

**This does not establish absence of direct overlap.** The evidence is limited to abstracts; full-text methods may differ.

1. **Lookback Lens: Detecting and Mitigating Contextual Hallucinations in Large Language Models Using Only Attention Maps**  
   - *Year:* 2024 (EMNLP)  
   - *Apparent relation:* Uses internal model signals (attention maps) to detect contextual hallucinations. This overlaps with the general idea of using internal state‑derived information for hallucination detection.  
   - *Risk type:* Partial overlap – the signal modality (attention maps, not hidden state sequences) is different, but the high‑level approach of extracting discriminative features from the model’s internals is similar.  
   - *Evidence limitation:* Abstract only; it is unknown whether the method implicitly captures trajectory‑like patterns.  
   - *Trajectory‑level formulation:* No explicit trajectory‑level formulation was visible in the retrieved abstracts.

2. **LLMs Know More Than They Show: On the Intrinsic Representation of LLM Hallucinations**  
   - *Year:* 2024 (arXiv preprint; OpenAlex record)  
   - *Apparent relation:* Demonstrates that hidden representations encode hallucination‑related information; uses probing classifiers. This is closely related to the premise that internal states contain detectable hallucination signals.  
   - *Risk type:* High overlap for the “internal‑state hallucination detection” dimension; however, the method is classification‑based, not unsupervised anomaly detection over full trajectories.  
   - *Evidence limitation:* No full text; the probing approach may not consider sequence‑level patterns.  
   - *Trajectory‑level formulation:* No explicit trajectory‑level formulation was visible in the retrieved abstracts.

3. **MixHD: A Method for Detecting Hallucinations Based on the Internal State and Output Probability of Large Language Models**  
   - *Year:* 2025 (ICASSP)  
   - *Apparent relation:* Combines internal state features with output probabilities for hallucination detection. This shares the use of hidden states but as part of a multi‑modal feature set, not a pure trajectory anomaly detector.  
   - *Risk type:* Medium overlap for internal‑state signal usage; no evidence it handles full token‑state sequences as a trajectory.  
   - *Evidence limitation:* Abstract only; the role of temporal/sequential information is unclear.  
   - *Trajectory‑level formulation:* No explicit trajectory‑level formulation was visible in the retrieved abstracts.

4. **Unsupervised Real‑Time Hallucination Detection based on the Internal States of Large Language Models**  
   - *Year:* 2024 (arXiv preprint; OpenAlex record)  
   - *Apparent relation:* Proposes unsupervised, real‑time detection using internal states. This aligns strongly with the candidate’s framing of unsupervised anomaly detection.  
   - *Risk type:* High risk of overlap – unsupervised detection from internal states is already claimed; whether it uses trajectory‑level patterns (vs. per‑token or aggregate features) cannot be determined from the abstract.  
   - *Evidence limitation:* Abstract only; critical details about state representation (single token vs. sequence) are missing.  
   - *Trajectory‑level formulation:* No explicit trajectory‑level formulation was visible in the retrieved abstracts.

**Summary qualification:** All four papers demonstrate that internal‑state signals are usable for hallucination detection. None of the available abstracts describe a method that builds a reference distribution of full token‑level hidden state trajectories and applies standard anomaly detection (e.g., LOF, autoencoder, DTW) to those trajectories. This does not rule out such formulations in the full text.

---

## Risk Labels

Each dimension of the candidate idea is assigned a risk label based on the OpenAlex‑only evidence:

- **Internal‑state hallucination detection:** `medium_risk_overlap`  
  *Rationale:* Multiple OpenAlex papers explicitly detect hallucination from internal states (e.g., probing, classifier, unsupervised). The idea that internal states carry hallucination signals is not novel within the evidence boundary.

- **Token‑level detection:** `medium_risk_overlap`  
  *Rationale:* Token‑level features are implicitly used in many internal‑state methods (e.g., probing at token positions). While the candidate’s emphasis is on trajectories, token‑level hidden‑state analysis is already present.

- **Trajectory‑level anomaly framing:** `low_confidence_possible_gap`  
  *Rationale:* No OpenAlex abstract describes a framework that treats the full sequence of hidden states as a trajectory and applies unsupervised anomaly detection to detect hallucinations. The evidence is insufficient to confirm this gap, but within the constrained search it appears the idea may be distinct. However, full‑text work could reveal prior trajectory formulations.

- **Unsupervised/real‑time detection:** `high_risk_overlap`  
  *Rationale:* Paper 10 explicitly claims unsupervised and real‑time hallucination detection using internal states. If trajectory‑level is not novel, this combination is at very high risk of overlap.

- **Black‑box alternatives:** `low_confidence_possible_gap`  
  *Rationale:* The candidate idea is inherently white‑box (requires hidden states). Black‑box methods (e.g., output probability only) are not directly overlapping; however, they are not the focus of this check and no strong evidence of overlap was found in the OpenAlex set.

---

## Evidence‑Bounded Assessment

After reviewing the available OpenAlex evidence (abstracts only, no full‑text), the following required conclusions are drawn:

- **Internal‑state hallucination detection:** `medium_risk_overlap`  
- **Trajectory‑level anomaly framing:** `low_confidence_possible_gap`  
- **Overall novelty confidence:** `insufficient_evidence`

The combination of these labels reflects the fact that while the core concept of using internal states to detect hallucination is well‑represented, the specific formulation as a *trajectory‑level anomaly detection problem* appears not to be demonstrated in the retrieved abstracts. However
