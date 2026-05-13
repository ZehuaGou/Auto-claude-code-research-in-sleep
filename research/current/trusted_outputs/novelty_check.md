---
implementation_source: routed_internal_model
routed_model_used: True
route_role: novelty_checker
route_expected_backend: openai_compatible_api
route_expected_model: deepseek-v4-pro
actual_backend: deepseek
actual_model: deepseek-v4-pro
ledger_call_id: call_80e3557c245f
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
task_id: wf_novelty_check_f4e61176
context_manifest: tmp\wf_novelty_check_manifest.json
allowed_input_files: ["research\\current\\input_normalization.md", "research\\current\\trusted_outputs\\research_contract.md", "research\\current\\literature_notes.md", "research\\current\\trusted_outputs\\literature_search.md", "literature\\search_runs\\current\\top_k.md", "docs\\LITERATURE_REPAIR_QUEUE.md"]
forbidden_context: ["old novelty conclusions", "unverified experiment results", "other candidates", "user preference", "generator trace", "previous optimistic summaries", "external_agent_direct output", "mock/dry-run artifact"]
forbidden_context_checked: true
context_hash: 2c4f0d51ae69a5e414fdbfe271d1f5ac7bf3920dd3620c15dd9c6aff016d746e
prompt_file: 
response_file: 
source_boundary: workflow_novelty_check_minimal_allowed_inputs_only
contamination_scan_status: checked
error_code: 
error: 
---

# Novelty Check

## Candidate Idea Recap

The research proposes to frame hallucination detection in LLMs as a **trajectory-level anomaly detection problem** over **token-level hidden state sequences**. Instead of using single-token hidden representations or aggregate statistics, the idea is to model the full sequence of hidden vectors produced during generation and compare new trajectories against a reference distribution of truthful/well-grounded generations.

## Prior Work Landscape (from Literature Evidence)

The evidence search (OpenAlex, top‑k = 10) revealed that using internal representations for hallucination detection is an active area:

1. **Internal state‑based classifiers/probes** (Papers 2–7, 10): Most works extract hidden states (often last‑token or layer‑pooled) and train supervised or unsupervised detectors. No evidence of treating the entire token‑level sequence as a trajectory was found in the retrieved abstracts.
2. **Attention‑map‑based methods** (Paper 1): Uses attention patterns rather than hidden states.
3. **Black‑box approaches** (Papers 9,10): Do not access internal states at all.
4. **Graph‑based method** (Paper 8): Not directly relevant to hidden state trajectories.

**Key gap in retrieved evidence:** None of the top‑k papers explicitly formulate the problem as **anomaly detection on multi‑variate time‑series of hidden states**. The retrieved works predominantly:
- Use a **single vector per generation** (e.g., last token, mean pooling, or probe‑trained representation)
- Do not model the **sequential dependency** among hidden states beyond the final token
- Do not apply **trajectory‑level anomaly detection** (e.g., dynamic time warping, sequence outlier detection) to hidden state sequences

However, **this absence is not proof of novelty** due to the search limitations (see below).

## Overlap Analysis

### Direct Overlap
No direct overlap found in the top‑k where a method explicitly uses hidden state trajectory comparison for hallucination detection.

### Partial Overlap / Adjacent Ideas
- **INSIDE (Paper 3)**: Extracts “internal state features” – while the abstract does not detail whether these are per‑token features or aggregated, it is possible (but not verified) that they capture cross‑token relationships. If they do, the trajectory idea may be a re‑phrasing.
- **Semantic Entropy Probes (Paper 2)**: Already uses hidden states for detection; adding a trajectory view is an incremental variation.
- **Unsupervised Real‑Time (Paper 7)**: Might use online state sequences, but again abstract does not confirm trajectory‑level modeling.

Thus the core novelty would lie in the **explicit framing as a sequence anomaly problem**, including how trajectories are aligned, represented, and compared. This is a **methodological nuance** rather than a completely new paradigm.

### Potential Novelties (Conditional)
If it can be demonstrated that:
- Treating the whole sequence captures **temporal coherence** that single‑vector methods miss
- **Trajectory‑level anomaly detection** yields better separation than per‑token or last‑token approaches
- The method is **agnostic to output length** (unlike fixed‑dimension probes)

then the idea could be incrementally novel. The novelty would be in the **formulation and application of trajectory anomaly detection to LLM hidden states**, not in the use of hidden states per se.

## Evaluation Against Research Contract Constraints

The contract required the novelty checker to:
- **Not treat novelty as default** ✔
- **Identify overlap, partial overlap, and incremental variations** ✔
- **Not certify novelty from absence of matches alone** ✔ (this is emphasized throughout)
- **Consider dependencies**: trajectory formulation, anomaly objective, labeling setup, inference‑time/post‑hoc setting, domain design.
    - The search did not return papers with those explicit dependencies, so the novelty might hinge on **whether the trajectory framing is genuinely distinct** from existing “internal state” methods after full‑text review.
- **Report competing explanations**: The evidence notes many internal‑state methods already exist; the candidate is a variation, not a first‑of‑its‑kind.

## Will Full‑Text Review Change This Assessment?
**Unknown.** The current evidence is abstract‑only. Full‑text of papers like INSIDE or Semantic Entropy Probes might reveal that they already:
- Extract per‑token hidden states
- Use sequence models (RNN/Transformer) on the state sequence
- Treat hallucination detection as a time‑series classification/anomaly task

If any such method is found, the proposed trajectory anomaly framing would be a **direct duplication** or a very narrow variation (e.g., swapping the anomaly detection algorithm). Without full‑text verification, we cannot confirm that the trajectory aspect is absent.

## Limitations That Affect Novelty Confidence
1. **Single source (OpenAlex)** – other databases may contain work explicitly on “hidden state trajectory anomaly detection”.
2. **No full‑text verification** – the novelty gap might disappear upon detailed reading.
3. **Deterministic keyword relevance** – a paper that actually uses trajectory concepts might have been missed if its abstract lacked matching keywords.
4. **Novelty is not evaluated from a comprehensive prior‑art search** – this is a limited, automated scan, not a systematic review.

## Required Repairs Before Stronger Novelty Claim
1. Add arXiv adapter to expand source coverage beyond OpenAlex.
2. Add Crossref/Semantic Scholar adapters if feasible.
3. Perform full-text/manual review of closest works: INSIDE, Semantic Entropy Probes, MixHD, Prompt-Guided Internal States.
4. Verify whether any work explicitly models sequences of hidden states across generated tokens.
5. Check labeling/evaluation compatibility with the proposed trajectory formulation.

## Repair Queue Updates (Blocking Items)
- **LRQ-004**: Only OpenAlex source implemented — blocks comprehensive prior-art coverage. Remaining blocking.
- **LRQ-005**: No full-text verification — blocks confirming absence of trajectory-level methods in closest works. Remaining blocking.

## Conclusion
- The candidate idea is **likely incremental** but **potentially novel in its explicit framing** if no prior work has treated LLM hidden state sequences as full trajectories for anomaly detection.
- **Novelty cannot be confirmed at this stage** due to evidence limitations.
- **Risk**: The idea may be preempted by existing internal‑state methods that already capture sequential dynamics, or by future full‑text discovery.
- **Recommendation**: Proceed to later stages only with the explicit understanding that the trajectory framing is a **hypothesis, not a proven differentiator**, and that a deeper literature review (including arXiv, Semantic Scholar, and full‑text analysis) must be completed before any claim of originality.

---

This artifact is a novelty assessment, not a final verdict. It does not claim that the idea is novel or unoriginal. It must be re‑evaluated when full‑text evidence becomes available.
