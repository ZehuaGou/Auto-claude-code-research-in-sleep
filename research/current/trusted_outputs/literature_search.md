---
implementation_source: routed_internal_model
routed_model_used: True
route_role: literature_scout
route_expected_backend: openai_compatible_api
route_expected_model: deepseek-v4-flash
actual_backend: deepseek
actual_model: deepseek-v4-flash
ledger_call_id: call_8c480cc68437
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
task_id: wf_literature_search_87f08d37
context_manifest: tmp\wf_literature_search_manifest.json
allowed_input_files: ["research\\current\\input_normalization.md", "research\\current\\trusted_outputs\\research_contract.md", "research\\current\\literature_notes.md", "literature\\search_runs\\current\\top_k.md"]
forbidden_context: ["unverified search results as confirmed evidence", "user preference shortcuts", "external_agent_direct", "old novelty conclusions", "mock/dry-run artifact", "paywalled_content_illegally_obtained"]
forbidden_context_checked: true
context_hash: 9916d53727fd7e0038026daa896745b0c939e8f02f5016d413f4fbe3babe3d66
prompt_file: 
response_file: 
source_boundary: workflow_literature_search_minimal_allowed_inputs_only
contamination_scan_status: checked
error_code: 
error: 
---

# Literature Agent: Evidence Integration and Gap Analysis

## Overview

We processed 10 candidate papers from the literature search, all with medium or low evidence strength (full text unavailable). The papers span hallucination detection, internal-state analysis, trajectory-level methods, and adjacent formulations. Below, we assess how the evidence supports or challenges the research contract’s assumptions and identify critical gaps for the novelty check.

---

## Evidence in support of the contract’s core premise

The contract hypothesizes that **token-level hidden state trajectories can be used for anomaly-based hallucination detection**. Several papers provide direct or indirect support for this premise:

| Paper | Relevance | Key Finding | Support Level |
|-------|-----------|-------------|------------|
| 1 (MixHD) | High | Uses hidden states + output probabilities for detection. | Direct: hidden states carry hallucination signal. |
| 4 (INSIDE) | High | Internal states retain richer signal than logits; EigenScore metric. | Direct: internal representations are informative. |
| 5 (LLMs Know More) | High | Truthfulness information concentrated in specific tokens internal states. | Direct: hidden representations encode truthfulness at token level. |
| 7 (TruthX) | High | Truthful space is separable in LLM latent representations. | Supports: truthfulness is a detectable dimension in hidden states. |
| 9 (DoLa) | High | Layer-level hidden state contrasts correlate with factuality. | Supports: trajectory across layers carries factuality signal. |
| 6 (Lookback Lens) | Moderate | Attention maps (internal state) detect contextual hallucination. | Indirect: internal signals beyond hidden states also work. |

**Assessment:** The prior work consistently demonstrates that **internal representations (including hidden states) encode truthfulness/hallucination-relevant information**. This supports the contract’s core assumption that hidden state trajectories *could* be useful. However, none of the papers frame detection as **trajectory-level anomaly detection** over token sequences. Most focus on per-token probing, layer contrasts, or summary statistics—not full trajectory analysis.

---

## Evidence gaps relative to the contract’s research design

| Contract Requirement / Assumption | Evidence Coverage | Gap |
|----------------------------------|------------------|-----|
| Trajectory-level analysis (sequence of hidden states across tokens) | Not found. Papers 1,4,5,7,9 use per-token or layer-level representations, not full token sequences. | **No prior work tests trajectory-level anomaly detection for hallucination.** This is a significant gap. |
| Anomaly detection framing | Not found. Existing detection methods use classifiers, probes, entropy measures, or contrastive scores—not anomaly detection. | **No paper frames hallucination detection as anomaly detection over a reference distribution of trajectories.** This is novel at a framing level. |
| Reference distribution of truthful trajectories | Not found. Papers use labeled ground truth for binary classification, not unsupervised anomaly detection. | **No prior work builds a reference distribution of “normal” trajectories for comparison.** |
| Variable-length trajectory alignment | Not addressed. All papers handle fixed-length or per-token settings. | **Alignment of variable-length outputs remains unresolved.** |
| Hallucination type distinctions | Papers 6 (contextual) and 3 (confabulation) differentiate types. Survey paper 8 provides taxonomy. | **Good background for operational definition, but no paper ties trajectory patterns to specific hallucination types.** |
| Model/decoding effects | Paper 7 (TruthX) uses autoencoder; Paper 9 (DoLa) uses contrastive layer logits. No systematic study of temperature or decoding. | **No evidence on how decoding hyperparameters affect trajectory statistics.** |
| Post-hoc vs. inference-time detection | Not addressed in any paper. | **No prior work compares online vs. offline settings for trajectory-based detection.** |

---

## Competing / adjacent formulations detected

1. **Output-level methods (Paper 3 – Semantic Entropy)**  
   - Detects hallucination using semantic clustering of multiple generations.  
   - Does not require internal states; relies on output probability distributions.  
   - **Challenge to contract:** If output-level methods are sufficient, trajectory analysis may add complexity without benefit. However, Paper 4 (INSIDE) shows internal states provide richer signal than output-level methods, so complementary.

2. **Attention-based methods (Paper 6 – Lookback Lens)**  
   - Uses attention maps, not hidden states.  
   - Suggests that other internal signals may be more efficient or interpretable.  
   - **Opportunity:** The contract could compare hidden-state trajectories against attention-based approaches.

3. **Layer-contrast methods (Paper 9 – DoLa)**  
   - Uses differences between upper and lower layer logits.  
   - Closest current work to trajectory-level analysis (across layers, not tokens).  
   - **Relevant:** The contract’s “trajectory” concept could be extended to layer dimension as well.

4. **Probing-based detection (Papers 4,5)**  
   - Train classifiers on hidden states to predict hallucination.  
   - **Conceptually different from anomaly detection.** Probing requires labeled data and assumes a fixed mapping from representations to labels; anomaly detection assumes a reference distribution without labels.

---

## Implications for novelty check

Based on the available evidence:

- **The specific combination of (a) token-level hidden state trajectories, (b) anomaly detection framing, and (c) hallucination detection appears absent from this literature sample.**  
- **Therefore, the direction has potential conceptual novelty.** However, novelty check must:
  - Verify that this combination is not present in other papers (e.g., papers with full text we could not access).
  - Consider whether the idea is a straightforward extension of probing (Paper 4,5) or layer-contrast (Paper 9) methods.
  - Assess whether the anomaly detection framing adds sufficient novelty beyond existing supervised/internal-state methods.
- **The novelty likely lies in the *methodological framing* rather than the underlying signal** (since hidden states are already known to be informative). This must be clearly distinguished.

---

## Unresolved open questions from the contract

The literature provides partial answers or context for some of the contract’s open questions:

| Contract Open Question | Literature Insight | Remaining Uncertainty |
|-----------------------|-------------------|----------------------|
| How to define a trajectory for variable-length outputs? | No alignment method is proposed in any paper. **Unresolved.** | Full resolution requires new methodological work. |
| Do different hallucination types produce distinct trajectory patterns? | Papers 3,6,8 distinguish hallucination types. **Possible to test.** | No trajectory-specific analysis exists. |
| How does model size/architecture affect behavior? | Papers 4,5,7 use various LLMs (not systematically compared). **Not addressed.** | Effect sizes unknown. |
| Inference-time vs. post-hoc detection? | Not discussed. **Unresolved.** | Important design decision. |
| Impact of input length, generation length, temperature? | Not studied in any paper. **Unresolved.** | Must be controlled in later experiments. |

---

## Recommendations for additional searches (optional)

- Search specifically for “trajectory anomaly detection” + “language model hidden states” or “sequence anomaly detection” + “hallucination”.
- Check papers that do full-text analysis of Papers 1,4,5,7,9 to confirm they do not use trajectory-level anomaly detection.
- Look for papers on “representation dynamics across tokens” or “token-level hidden state analysis” to see if trajectory-level analysis exists in other contexts (e.g., factual recall, knowledge editing).

---

## Summary

The literature supports the contract’s **underlying premise** (hidden states are informative about hallucination), but **does not preempt the specific trajectory-level anomaly detection framing**. This gives the direction potential for conceptual novelty, provided the later design can operationalize trajectory alignment and anomaly scoring without collapsing into known per-token or layer-contrast methods. The novelty check must remain cautious, as full-text access may reveal closer prior work.
