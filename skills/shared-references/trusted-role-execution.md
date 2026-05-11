# ARIS Trusted Role Execution — Global Protocol

> This is the **global binding protocol** for all ARIS skills. It overrides any
> skill-specific rules that conflict with this document. All ROLE_* tasks must
> follow this protocol — no exceptions.

## Core Principle

**model_route.py only declares routing — it does NOT call any model.**

The actual model invocation must happen through `tools/trusted_role_runner.py`,
which records to the ledger and can be verified by `tools/validate_model_invocation.py`.

`trusted_role_runner.py` must call backends through the explicit adapters in
`tools/model_backends/`. It must not directly depend on ad hoc imports such as
`mcp_codex_client` or `llm_chat_client`.

Codex MCP is available to the **outer Agent tool environment**. A plain Python
script cannot directly invoke the outer Agent's `mcp__codex__codex` tool, so
Codex routes may require an external MCP handoff prepared and completed through
`trusted_role_runner.py`.

---

## Rule 1: External Agents Are Orchestrators Only

External agents (MiniMax, Happy, Claude Code outer agent, human operators) can:
- Read files and summarize context
- Construct prompts for internal model calls
- Call tools and run deterministic scripts
- Move verified artifacts between stages
- Format output and write logs

External agents **CANNOT**:
- Directly perform any ROLE_* core cognitive task (review, generate, audit, select, judge, implement, write, summarize)
- Claim their output is a verified internal model execution
- Masquerade as DeepSeek / Codex / OpenAI / Kimi / MiniMax internal execution

---

## Rule 2: All ROLE_* Tasks Must Use trusted_role_runner.py

Every skill that triggers a ROLE_* task must call:

```bash
python tools/trusted_role_runner.py --role <role> --input <context> --output <artifact>
```

For Codex-assigned roles (idea_reviewer, novelty_checker, etc.), add `--require-codex-thread`.

The runner will:
1. Create a ledger entry with `implementation_source=routed_internal_model`
2. Call the actual backend (Codex MCP or API), or prepare/complete an external
   Codex MCP handoff when Python cannot directly access the Codex tool
3. Record `codex_thread_id` (for Codex) or `actual_backend`/`actual_model` (for API)
4. Write a provenance header in the output artifact

If the current Python runtime has no explicit Codex MCP adapter, the runner must
return `unsupported_runtime_backend` and fail closed.

For Codex external handoff, use:

```bash
python tools/trusted_role_runner.py --role <role> --input <context> --output <artifact> --prepare-external-mcp --require-codex-thread
python tools/trusted_role_runner.py --complete-external-mcp --call-id <call_id> --codex-thread-id <real_thread_id> --response-file <response_file> --output <artifact>
```

The outer Agent performs the real `mcp__codex__codex` call between those two
steps. DeepSeek/OpenAI-compatible API roles do **not** use this handoff and
must execute directly through `tools/model_backends/openai_compatible.py`.

---

## Rule 3: Context Isolation Is Part Of Trust

Trusted execution is not only about which backend ran. It is also about which
context the role was allowed to see.

External agents must not freely stuff arbitrary chat state into a role prompt.
Forbidden context includes:

- 当前聊天记录
- 旧结论
- 其他候选
- 用户偏好
- 历史 praise
- raw brainstorm trace
- 旧 review positive conclusion
- 未验证实验结果
- `external_agent_direct` output
- mock/dry-run artifact

Each trusted role artifact header must include or reserve:

```text
isolation_mode:
task_id:
context_manifest:
allowed_input_files:
forbidden_context:
forbidden_context_checked:
context_hash:
prompt_file:
response_file:
source_boundary:
contamination_scan_status:
```

If `--context-manifest` is provided, `trusted_role_runner.py` must record the
manifest path, allowed inputs, forbidden context list, source boundary, and a
`context_hash`. If no manifest is provided, the runner must still record:

- `context_manifest: none`
- `forbidden_context_checked: false`
- `contamination_scan_status: not_checked`

`pending_external_mcp` is not completed trusted evidence. It may represent a
successful handoff preparation, but it must keep `allowed_next_stage=false`.

---

## Rule 4: Ledger Entry Requirements

### For real model calls (routed_internal_model):

```
implementation_source: routed_internal_model
routed_model_used: true
route_role: <role>
route_expected_backend: <from model_route.py>
route_expected_model: <from model_route.py>
actual_backend: codex | deepseek | kimi | minimax | openai
actual_model: <model name>
ledger_call_id: <call_id>
codex_thread_id: <thread_id>   # required for Codex
fallback_used: false
verification_status: verified_routed_call
allowed_next_stage: true
confidence_downgraded: false
```

### For fallback calls:

```
fallback_used: true
fallback_reason: <explicit reason>
verification_status: verified_with_fallback
allowed_next_stage: false  # unless role explicitly allows fallback
confidence_downgraded: true
```

### For external_agent_direct (untrusted):

```
implementation_source: external_agent_direct
routed_model_used: false
actual_backend: external_agent
actual_model: <agent name or "unknown">
verification_status: unverified_external_execution
allowed_next_stage: false
confidence_downgraded: true
```

---

## Rule 5: Codex Gate Requires codex_thread_id

Every Codex call must produce a `codex_thread_id`. Without it:
- `verification_status` → `codex_missing_thread_id`
- `allowed_next_stage` → `false`
- `confidence_downgraded` → `true`

No skill may claim "Codex review completed" without a valid `codex_thread_id`.
Do not fabricate `codex_thread_id` from normal CLI output, commit hashes,
human-written strings, or model self-description. Only real Codex tool/session
metadata is acceptable.

`pending_external_mcp` is not a completed Codex call. It must keep
`allowed_next_stage=false` until `complete-external-mcp` verifies the real
thread id and response artifact.

---

## Rule 6: API Backend Requires actual_backend / actual_model

For non-Codex backends (DeepSeek, Kimi, etc.), the ledger must contain:
- `actual_backend` (provider name)
- `actual_model` (model name)
- `ledger_call_id`

Missing either → `verification_status` → `missing_actual_backend`.
If the backend is configured but missing API key, `base_url`, or model, the
runner must mark the call as `call_failed` and fail closed.

DeepSeek/OpenAI-compatible API roles do not require `codex_thread_id` and must
not be forced through Codex handoff mode.

---

## Rule 7: Silent Fallback Is Forbidden

Fallbacks must always be explicit. The ledger must contain:
- `fallback_used: true`
- `fallback_reason: <explicit string>`

Without `fallback_reason`:
- `verification_status` → `fallback_unverified`
- `allowed_next_stage` → `false`

`verified_with_fallback` does not automatically permit the next stage. The
default is `allowed_next_stage=false`, and `trusted_role_runner.py` must exit 1
unless fallback next-stage use is explicitly allowed.

---

## Rule 8: external_agent_direct Is Never Trusted

`external_agent_direct` always means:
- `verification_status` = `unverified_external_execution`
- `allowed_next_stage` = `false`
- `confidence_downgraded` = `true`

It cannot be upgraded to `verified_routed_call` by changing the ledger entry.

---

## Rule 9: No Masquerading

It is a violation to write `implementation_source=routed_internal_model` in an
artifact when the work was done by an external agent. The ledger is the source of
truth. Artifacts that misrepresent their execution source are untrusted.

---

## Rule 10: Dry-Run / Mock Cannot Be Real Evidence

`--dry-run` or `--mock-response` mode:
- `verification_status` → `dry_run_untrusted`
- `allowed_next_stage` → `false`
- `confidence_downgraded` → `true`

Dry-run outputs are for framework self-test only. They cannot enter the research
evidence chain as verified outputs.

---

## Rule 11: Fail Closed When Runner Is Unavailable

If `trusted_role_runner.py` cannot execute (network failure, API unavailable,
Codex MCP unavailable), the skill must fail — not substitute with external agent
output. The framework must not proceed with untrusted results.

This includes `unsupported_runtime_backend`, `call_failed`,
`codex_missing_thread_id`, and `dry_run_untrusted`.

---

## Rule 12: Artifact Provenance Header

All artifacts produced by trusted_role_runner.py must include:

```
---
implementation_source:
routed_model_used:
route_role:
route_expected_backend:
route_expected_model:
actual_backend:
actual_model:
ledger_call_id:
codex_used:
codex_thread_id:
fallback_used:
fallback_reason:
confidence_downgraded:
verification_status:
allowed_next_stage:
routing_source:
isolation_mode:
task_id:
context_manifest:
allowed_input_files:
forbidden_context:
forbidden_context_checked:
context_hash:
prompt_file:
response_file:
source_boundary:
contamination_scan_status:
---
```

Any artifact without this header from a ROLE_* task is untrusted.

---

## Rule 13: Role Context Rules

### novelty_checker

Allowed context:
- 当前 candidate
- 相关 literature
- 明确检索结果
- `LITERATURE_INDEX.md`
- `GAP_MAP.md`

Forbidden context:
- 其他 candidates
- 旧 novelty 结论
- 用户偏好
- generator trace
- ad_hoc 结果
- `RUNS/IDEA_CARDS/`

### idea_reviewer / adversarial_reviewer

Allowed context:
- 当前 candidate
- 必要背景
- 明确 evidence

Forbidden context:
- generator trace
- 其他 candidate
- 旧评分
- 用户偏好
- 历史 praise

### final_selector

Allowed context:
- canonical candidates
- 独立 reviews
- novelty reports
- selection criteria

Forbidden context:
- raw brainstorm trace
- 用户偏好
- 旧 final selection
- 外层 Agent 主观总结

### experiment_implementer

Allowed context:
- experiment plan
- final proposal
- 必要代码上下文
- research contract

Forbidden context:
- 旧失败解释
- 未验证实验结果
- 外层 Agent 自己的实现偏好

### experiment_code_reviewer

Allowed context:
- 被审代码
- 实验计划
- metric 定义
- data split 定义
- expected behavior

Forbidden context:
- 实现者自我辩解
- 外层 Agent 说“已经没问题”
- 旧 positive review
- 无关实验结果

### result_judge

Allowed context:
- 实验结果
- 日志
- metric 定义
- research contract

Forbidden context:
- 外层 Agent 主观乐观总结
- 未验证结果
- 旧 conclusion
- mock/dry-run artifact

### paper_writer / final_paper_auditor

Allowed context:
- verified results
- research contract
- approved claims
- verified reviews

Forbidden context:
- unverified exploratory notes
- `external_agent_direct` output
- mock/dry-run artifact
- 未验证结果

---

## Rule 14: User Slash Commands Work Without Extra Reminders

Users running `/idea-discovery`, `/novelty-check`, `/exec-review`, `/experiment-plan`,
`/experiment-bridge`, `/auto-review-loop`, `/paper-writing`, `/status` do NOT need
to manually invoke trusted_role_runner.py or remember these rules. The skills
themselves must enforce this protocol. The framework is built to default to trusted
execution — no user reminder required.

---

## Verification

After any trusted role execution, skills should call:

```bash
python tools/validate_model_invocation.py --role <role>
```

Only `verification_status` of `verified_routed_call` or `verified_with_fallback`
with `allowed_next_stage=true` can proceed to the next stage.

---

## Reference Implementation

- `tools/trusted_role_runner.py` — trusted execution entry point
- `tools/model_backends/base.py` — shared backend result contract
- `tools/model_backends/openai_compatible.py` — OpenAI-compatible API adapter
- `tools/model_backends/codex_mcp.py` — Codex MCP adapter with fail-closed runtime detection
- `tools/llm_call_ledger.py` — ledger with trust fields
- `tools/validate_model_invocation.py` — trust verification
- `tools/model_route.py` — routing declaration (no real calls)
- `docs/MODEL_ROUTING_OVERVIEW.md` — routing architecture docs
