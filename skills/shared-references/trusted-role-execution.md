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

## Rule 3: Ledger Entry Requirements

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

## Rule 4: Codex Gate Requires codex_thread_id

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

## Rule 5: API Backend Requires actual_backend / actual_model

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

## Rule 6: Silent Fallback Is Forbidden

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

## Rule 7: external_agent_direct Is Never Trusted

`external_agent_direct` always means:
- `verification_status` = `unverified_external_execution`
- `allowed_next_stage` = `false`
- `confidence_downgraded` = `true`

It cannot be upgraded to `verified_routed_call` by changing the ledger entry.

---

## Rule 8: No Masquerading

It is a violation to write `implementation_source=routed_internal_model` in an
artifact when the work was done by an external agent. The ledger is the source of
truth. Artifacts that misrepresent their execution source are untrusted.

---

## Rule 9: Dry-Run / Mock Cannot Be Real Evidence

`--dry-run` or `--mock-response` mode:
- `verification_status` → `dry_run_untrusted`
- `allowed_next_stage` → `false`
- `confidence_downgraded` → `true`

Dry-run outputs are for framework self-test only. They cannot enter the research
evidence chain as verified outputs.

---

## Rule 10: Fail Closed When Runner Is Unavailable

If `trusted_role_runner.py` cannot execute (network failure, API unavailable,
Codex MCP unavailable), the skill must fail — not substitute with external agent
output. The framework must not proceed with untrusted results.

This includes `unsupported_runtime_backend`, `call_failed`,
`codex_missing_thread_id`, and `dry_run_untrusted`.

---

## Rule 11: Artifact Provenance Header

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
---
```

Any artifact without this header from a ROLE_* task is untrusted.

---

## Rule 12: User Slash Commands Work Without Extra Reminders

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
