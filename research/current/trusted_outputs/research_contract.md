---
implementation_source: routed_internal_model
routed_model_used: True
route_role: contract_reviewer
route_expected_backend: mcp
route_expected_model: auto
actual_backend: codex
actual_model: auto
ledger_call_id: call_1e0fb69719ec
codex_used: True
codex_thread_id: 019e1bfb-0f9e-7862-aead-bd24b0f822f1
fallback_used: False
fallback_reason: 
confidence_downgraded: False
verification_status: verified_routed_call
allowed_next_stage: True
status: completed
routing_source: trusted_role_runner_external_mcp
isolation_mode: context_manifest
task_id: wf_research_contract_1d56394f
context_manifest: tmp/wf_research_contract_manifest.json
allowed_input_files: ["research\\current\\input_normalization.md"]
forbidden_context: ["old conclusions", "unverified experiment results", "other candidates", "user preference", "generator trace", "external_agent_direct output", "mock/dry-run artifact"]
forbidden_context_checked: true
context_hash: db255938a0af398e6acc2896f3bb075bd8eaf32a6a5ffe81c878dfbc2e0e6213
prompt_file: .aris/calls/call_1e0fb69719ec_prompt.md
response_file: tmp/research_contract_codex_response.md
source_boundary: workflow_research_contract_minimal_allowed_inputs_only
contamination_scan_status: checked
error_code: 
error: 
---

# Research Contract

## Research Question / Scope

This research will assess whether hallucination in large language model outputs can be framed as an anomaly detection problem over token-level hidden state trajectories.

The specific scope is to define a study framework in which:
- a reference distribution is built from hidden state trajectories associated with truthful or well-grounded generations,
- trajectories from hallucinated generations are compared against that reference, and
- anomaly scores are evaluated for association with hallucination labels.

The contract covers the conceptual validity of this framing and the requirements needed to investigate it later. It does not establish that the method works.

## In-Scope

- Defining the target phenomenon as hallucination in model-generated text, understood here as plausible-sounding but factually incorrect or ungrounded content.
- Defining token-level hidden state trajectories as sequences of hidden state vectors across generated tokens.
- Framing the proposed detection problem as trajectory-level anomaly detection.
- Considering a study structure with:
  - reference trajectories from truthful or well-grounded generations,
  - comparison trajectories from hallucinated generations,
  - anomaly scoring based on deviation from a reference distribution.
- Considering candidate method families already named in the input:
  - distance-based methods,
  - density-based methods,
  - reconstruction-based methods.
- Defining later-evaluation goals in abstract terms, such as correlation between anomaly score and hallucination labels.
- Identifying design questions that later stages must resolve, including:
  - trajectory representation for variable-length outputs,
  - hallucination type distinctions,
  - model, architecture, and decoding effects,
  - post-hoc versus inference-time detection,
  - reference-distribution stability across prompts and domains,
  - effects of input length, output length, and sampling temperature.
- Defining requirements for later dataset selection, label definition, metric definition, and model/method selection.

## Out-of-Scope (Forbidden)

- Claiming that hallucination is in fact detectable from hidden state trajectories.
- Claiming that any specific anomaly detection method is effective for this task.
- Claiming novelty, uniqueness, or prior-art separation.
- Using any external literature, prior experiments, benchmark results, or web evidence inside this contract.
- Using old conclusions, mock results, or unverified findings as support.
- Running experiments, reporting metrics, or implying observed empirical performance.
- Fixing one final operational definition of hallucination beyond the brief's current wording.
- Fixing one final trajectory representation, alignment scheme, or preprocessing pipeline.
- Fixing one final model, dataset, prompt set, decoding strategy, or evaluation protocol.
- Extending the claim to all model families, all domains, or real-time deployment settings.
- Treating feasibility, scalability, robustness, or deployability as established.

## Assumptions

- Hidden state trajectories can be observed and extracted at token level for the candidate model studied later.
- Hallucinated generations and truthful or well-grounded generations can be separated into distinct labeled groups for later analysis.
- Ground-truth labels for hallucination versus truthful generation are available or can be produced with sufficient reliability.
- Hidden state trajectories during hallucination may differ systematically from those during truthful generation.
- Any such difference may be detectable despite token-level noise.
- Standard anomaly detection methods may be capable of capturing trajectory-level deviations relevant to hallucination.
- A reference distribution of truthful or well-grounded trajectories can be defined for the later study.
- Later work will need to resolve how variable-length trajectories are represented or aligned.
- Later work will need to determine whether different hallucination types should be treated jointly or separately.
- Later work will need to assess whether prompt domain, model properties, and decoding conditions materially affect trajectory behavior.

## Success Criteria

This research direction will be considered successful at the contract level if later stages can specify a coherent and testable study design satisfying all of the following:

- Hallucination is defined operationally enough to support consistent labeling.
- Token-level hidden state trajectories are defined precisely enough to support extraction and comparison.
- A valid reference set for truthful or well-grounded trajectories can be specified.
- At least one anomaly detection formulation can be stated without depending on circular labels or undefined constructs.
- Evaluation criteria can be stated clearly, including how association between anomaly score and hallucination labels would be judged.
- The proposed setup can distinguish the main research question from confounds such as output length, prompt variation, or decoding noise at the design level.
- The study design yields falsifiable predictions rather than narrative intuition alone.

## Failure / Abandon Criteria

This direction should be abandoned, narrowed, or reformulated if any of the following becomes true in later stages:

- Hallucination cannot be operationally defined in a way that supports reliable labeling.
- Hidden state access is not available or is too poorly specified for the intended study.
- The reference class of truthful or well-grounded trajectories cannot be defined without major ambiguity.
- The formulation collapses into detecting superficial confounds such as sequence length, token position, prompt family, or decoding settings rather than hallucination.
- Variable-length trajectory handling cannot be specified without undermining comparability.
- The central hypothesis cannot be translated into a falsifiable evaluation plan.
- Later literature or novelty review shows that the idea, as framed, is too underspecified to distinguish from existing generic representation-anomaly proposals unless the scope is tightened.
- The required assumptions about labels, trajectory stability, or detectable deviation appear unjustified even as working assumptions for a future experiment design.

## Constraints for literature_search

- Literature search must treat this contract as a hypothesis-framing document, not as evidence.
- It must not assume novelty, feasibility, or positive empirical outcomes.
- It must search for prior work relevant to:
  - hallucination detection,
  - hidden-state analysis,
  - sequence or trajectory anomaly detection,
  - token-level representation dynamics in LLM generation.
- It must test the contract's assumptions rather than confirm them by default.
- It must identify definitions used for hallucination, grounding, and trajectory comparison in prior work.
- It must surface competing explanations and adjacent formulations, including methods that use signals other than hidden states.
- It must not import unsupported claims back into this contract as settled fact.
- It must explicitly flag where prior work depends on specific datasets, model families, or decoding regimes that may limit comparability.

## Constraints for novelty_check

- Novelty check must evaluate novelty only after separating the contract's broad idea from its still-open implementation details.
- It must not treat the mere use of hidden states, anomaly detection, or hallucination detection as novel by default.
- It must compare this direction against existing work on:
  - internal-state-based uncertainty or hallucination detection,
  - representation-space anomaly detection,
  - generation trajectory analysis.
- It must identify whether novelty, if any, would depend on:
  - the trajectory formulation,
  - the anomaly objective,
  - the labeling setup,
  - the inference-time or post-hoc setting,
  - the domain or benchmark design.
- It must not certify novelty from absence of obvious matches alone.
- It must report overlap, partial overlap, and likely incremental variations, not only exact matches.

## What Is NOT Claimed

- This contract does not claim that hidden state trajectories actually separate hallucinated from truthful generations.
- This contract does not claim that anomaly detection is the correct or best formulation.
- This contract does not claim that any listed method will succeed.
- This contract does not claim novelty.
- This contract does not claim feasibility for real-time deployment.
- This contract does not claim robustness across models, prompts, domains, or decoding strategies.
- This contract does not claim that suitable labels, datasets, or reference distributions already exist.
- This contract does not claim any experimental result, benchmark score, correlation, precision, recall, AUC, or false positive rate.
- This contract does not claim causal understanding of why hallucination would alter hidden state trajectories.
