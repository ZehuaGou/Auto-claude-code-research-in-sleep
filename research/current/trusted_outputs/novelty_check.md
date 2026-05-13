---
implementation_source: routed_internal_model
routed_model_used: True
route_role: novelty_checker
route_expected_backend: openai_compatible_api
route_expected_model: deepseek-v4-pro
actual_backend: deepseek
actual_model: deepseek-v4-pro
ledger_call_id: call_fc99bd2156be
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
task_id: wf_novelty_check_5b631de7
context_manifest: tmp\wf_novelty_check_manifest.json
allowed_input_files: ["research\\current\\input_normalization.md", "research\\current\\trusted_outputs\\research_contract.md", "research\\current\\literature_notes.md", "research\\current\\trusted_outputs\\literature_search.md", "literature\\search_runs\\current\\top_k.md", "docs\\LITERATURE_REPAIR_QUEUE.md"]
forbidden_context: ["old novelty conclusions", "unverified experiment results", "other candidates", "user preference", "generator trace", "previous optimistic summaries", "external_agent_direct output", "mock/dry-run artifact"]
forbidden_context_checked: true
context_hash: 1e07a5fc02277a41aca13372c0bc6582471e22599340d283d34ed7db9e82d4fa
prompt_file: 
response_file: 
source_boundary: workflow_novelty_check_minimal_allowed_inputs_only
contamination_scan_status: checked
error_code: 
error: 
---

# Novelty Check — Evidence-Bounded Risk Assessment

## Scope and Evidence Boundary
- **This is not a final novelty proof.**
- Evidence source: **OpenAlex only** (no arXiv, Crossref, Semantic Scholar).
- Evidence type: **metadata and abstracts only**; no full texts verified.
- No experiments conducted; no new data generated.
- This assessment is **bounded strictly by the retrieved and documented literature evidence** (top‑k = 10 papers from a single API pipeline, relevance scored deterministically).
- Absence of evidence in the searched sources does **not** establish absence of prior work.

## Closest Prior Work and Overlap Risks

Each listed work exhibits a **risk of overlap** with the candidate idea, primarily in the use of internal LLM states for hallucination detection.  
**No explicit trajectory‑level formulation was visible in the retrieved abstracts.**  
This does **not** establish that such a formulation is absent; it only reflects the current search boundary.

| Paper | Apparent Relation to Candidate Idea | Overlap Risk | Evidence Limitation |
|-------|--------------------------------------|--------------|---------------------|
| **INSIDE** (Chen et al., 2024) | Internal‑state features used for hallucination detection. | **High** – internal‑state based detection. | Abstract only; unknown if trajectory sequences are used. |
| **Semantic Entropy Probes** (Kossen et al., 2024) | Trains probes on internal representations (likely single‑token). | **High** – probe‑based detection using internal states. | Abstract does not describe probe input beyond “representations”. |
| **LLMs Know More Than They Show** (Orgad et al., 2024) | Analysis of intrinsic representations for hallucination detection. | **High** – focuses on internal representations. | Abstract does not detail sequence‑level analysis. |
| **Prompt‑Guided Internal States** (Zhang et al., 2024) | Prompt‑specific internal state analysis for detection. | **High** – uses single hidden states. | No evidence of trajectory modeling. |
| **MixHD** (Li et al., 2025) | Combines internal state (last token) and output probability. | **Medium** – uses internal state but last‑token only; not sequence. | Abstract lacks method depth. |
| **Unsupervised Real‑Time Hallucination Detection** (Su et al., 2024) | Unsupervised detection using internal states. | **Medium** – internal state based; real‑time suggests single‑step inference. | Trajectory details not in abstract. |
| **Lookback Lens** (Chuang et al., 2024) | Attention‑map‑based detection of contextual hallucinations. | **Low‑Medium** – attention maps are not hidden‑state trajectories, but attention patterns may indirectly reflect trajectory dynamics. | Abstract only; method may not use hidden states. |
| **HaluGNN** (Kong et al., 2025) | Graph neural network on text features, not hidden states. | **Low** – not internal‑state based. | Different signal; no overlap risk for hidden‑state trajectory detection. |
| **SelfCheckGPT** (Manakul et al., 2023) | Black‑box consistency checking; zero‑resource hallucination detection. | **Low for internal‑state methods, but relevant as prior art in hallucination detection.** | No internal state access; black‑box alternative. |
| **Semantic Entropy** (Farquhar et al., 2024) | Probabilistic approach using multiple generations, no hidden states. | **Low for internal‑state methods, but relevant as prior art.** | No hidden‑state trajectory used. |

**Overall Note on Retrieval**  
The literature search was not exhaustive; other databases and full‑text analyses could reveal trajectory‑level approaches that were invisible at the abstract level. The phrase “no explicit trajectory‑level formulation was visible in the retrieved abstracts” should not be misinterpreted as evidence of novelty. **This does not establish absence of direct overlap.**

## Risk Labels

| Dimension | Risk Label | Rationale |
|-----------|------------|-----------|
| **Internal‑state hallucination detection** | **medium_risk_overlap** | Multiple papers use internal states for detection; the general concept is well‑populated. |
| **Token‑level detection** | **high_risk_overlap** | Most existing works operate on token‑level or last‑token hidden states; token‑level usage is pervasive. |
| **Trajectory‑level anomaly framing** | **low_confidence_possible_gap** | No evidence in retrieved abstracts of treating the full sequence of hidden states as a trajectory for anomaly detection, but evidence base is too shallow to confirm a gap. |
| **Unsupervised/real‑time detection** | **medium_risk_overlap** | At least one paper (Su et al.) explicitly addresses unsupervised real‑time detection using internal states. |
| **Black‑box alternatives** | **medium_risk_overlap** | Hallucination detection without internal states (SelfCheckGPT, semantic entropy) already exists; the task domain is not novel. |

## Evidence‑Bounded Assessment

Based on the incomplete evidence (OpenAlex abstracts/metadata only, no full‑text verification):

- The candidate idea’s **internal‑state hallucination detection** component falls into a well‑studied area → **medium_risk_overlap**.
- The specific **trajectory‑level anomaly framing** (treating the full token‑level hidden state sequence as a trajectory and using anomaly detection methods) was not observed in the limited evidence → **low_confidence_possible_gap**.
  - This gap is tentative because:  
    * The search was restricted to one source (OpenAlex).  
    * Abstracts may omit implementation details; full texts could reveal trajectory‑based methods.  
    * Trajectory anomaly detection is a known technique; prior work may exist outside the LLM‑hallucination intersection.  
- Therefore, overall novelty confidence is **insufficient_evidence**. A stronger claim cannot be supported until a broader, full‑text‑verified literature review is completed.

## Required Repairs Before Stronger Claim

1. **Expand search sources**: include arXiv, Semantic Scholar, Crossref, and possibly Google Scholar.  
2. **Full‑text verification**: obtain and analyse full papers for all top‑k candidates and for any additional trajectory‑related matches.  
3. **Precise operationalisation of “trajectory”**: define the exact trajectory representation, alignment, and distance measure, then search for that specific formulation in the literature (not only broad keywords).  
4. **Search for trajectory anomaly detection applied to LLM hidden states** using dedicated queries (e.g., “trajectory anomaly detection LLM”, “hidden state sequence outlier”).  
5. **Comparative analysis**: directly compare the candidate idea’s trajectory‑based method (once fully specified) with the closest internal‑state methods to isolate the novel component.  
6. **Assess overlap beyond the “hallucination detection” domain**: evaluate whether trajectory‑level anomaly detection on neural network hidden states has been done in other safety or reliability contexts.

## Allowed Next Stage Recommendation

**continue_to_method_refinement_only**

The evidence shows a crowded internal‑state hallucination detection field with a potential but unconfirmed gap for trajectory‑level anomaly framing. Before any experiment planning, the method must be sharply refined to distinguish it from existing single‑vector or last‑token approaches and to define the trajectory representation in a way that can be meaningfully compared against prior art. Moving forward with high caution is not yet justified because the very novelty of the trajectory framing remains unverified.

---

This artifact is an evidence‑bounded risk assessment, not a novelty proof.  
It must be re‑evaluated when full‑text evidence becomes available.
