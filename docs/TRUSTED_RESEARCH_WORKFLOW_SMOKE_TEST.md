# Trusted Research Workflow Smoke Test

This document is for local static verification that the trusted research workflow lists stages correctly, displays status, blocks untrusted input, and validates the literature evidence chain. It does NOT run experiments, call model APIs, access the network, or download papers.

---

## Trusted Workflow Main Chain

```
input_normalization
  → research_contract
    → literature_search
      → novelty_check
        → experiment_plan
          → implementation_plan
            → result_judge
              → paper_writing
```

Each stage requires a trusted artifact header (`--- ... ---`) and `allowed_next_stage=true` before the next stage can proceed.

---

## Literature Evidence Chain

```
local JSONL evidence
  → append-raw          (append to raw_results.jsonl)
    → validate-raw       (check raw record format)
      → build-candidates  (normalize + dedup → candidates.jsonl)
        → validate-candidates
          → build-top-k   (deterministic scoring → top_k.md)
            → validate_literature_evidence.py
              → literature_search (workflow stage)
                → novelty_check precheck (blocks on invalid evidence)
```

`raw_results.jsonl` and `candidates.jsonl` are NOT novelty verdicts — they must become `top_k.md` and pass `validate_literature_evidence.py` before reaching `novelty_check`.

---

## Smoke Test Commands

### Basic workflow inspection

```bash
# List all workflow stages
python tools/research_workflow.py list-stages

# Show status of all stages (human-readable)
python tools/research_status.py

# Show status of all stages (JSON)
python tools/research_status.py --json
```

### Literature tool help

```bash
# Evidence landing tool help
python tools/literature_evidence_landing.py --help

# Literature evidence validator help
python tools/validate_literature_evidence.py --help
```

### Current skeleton checks

These run against the current `literature/search_runs/current/` skeleton files. Expected results reflect the current empty/template state — not a broken system.

```bash
# Validate raw_results.jsonl (currently empty → expected: empty)
python tools/literature_evidence_landing.py validate-raw \
  --file literature/search_runs/current/raw_results.jsonl

# Validate candidates.jsonl (currently empty → expected: empty)
python tools/literature_evidence_landing.py validate-candidates \
  --file literature/search_runs/current/candidates.jsonl

# Validate top_k.md (currently template_only → expected: blocked / exit 1)
python tools/validate_literature_evidence.py \
  --file literature/search_runs/current/top_k.md
```

**Expected outcomes (current skeleton state):**
- `raw_results.jsonl`: `status: empty` — no records yet
- `candidates.jsonl`: `status: empty` — not yet built
- `top_k.md`: `status: template_only` → blocked by validator; `validate_literature_evidence.py` exits 1

All of these are normal until real literature search is conducted.

---

## Temporary Literature Pipeline Test

Run this in a **temporary directory only**. Do NOT write to `literature/search_runs/current/`. Do NOT commit temporary files.

```bash
mkdir -p tmp/lit_smoke

cat > tmp/lit_smoke/raw_results.jsonl <<'EOF'
{"source":"arxiv","title":"Alpha Search","authors":["A. Author"],"year":"2024","url":"https://arxiv.org/abs/0000.00001","evidence_origin":"manual","retrieved_at":"2026-05-12","arxiv_id":"0000.00001","abstract":"A short abstract."}
{"source":"arxiv","title":"Alpha Search Duplicate","authors":["A. Author"],"year":"2024","url":"https://arxiv.org/abs/0000.00001","evidence_origin":"manual","retrieved_at":"2026-05-12","arxiv_id":"0000.00001","abstract":"Duplicate metadata."}
{"source":"openreview","title":"Zebra Optimization","authors":["B. Author"],"year":"2023","url":"https://openreview.net/forum?id=test","evidence_origin":"manual","retrieved_at":"2026-05-12","abstract":"Another short abstract."}
EOF

# Step 1: validate raw records
python tools/literature_evidence_landing.py validate-raw \
  --file tmp/lit_smoke/raw_results.jsonl

# Step 2: build candidates (normalize + dedup)
python tools/literature_evidence_landing.py build-candidates \
  --run-dir tmp/lit_smoke

# Step 3: validate candidates
python tools/literature_evidence_landing.py validate-candidates \
  --file tmp/lit_smoke/candidates.jsonl

# Step 4: build top_k (select top 2 by metadata completeness)
python tools/literature_evidence_landing.py build-top-k \
  --run-dir tmp/lit_smoke --k 2

# Step 5: validate top_k evidence
python tools/validate_literature_evidence.py \
  --file tmp/lit_smoke/top_k.md

# Clean up
rm -rf tmp/lit_smoke
```

**Expected outcomes:**
- `validate-raw`: no crash; records parsed
- `build-candidates`: produces `candidates.jsonl`; arXiv ID `0000.00001` records share one canonical `candidate_id`; one marked `duplicate_of`
- `build-top-k`: produces `top_k.md` with 2 papers; no `confirmed_novel` / `already_done` / `likely_incremental` verdict
- `validate_literature_evidence.py`: `insufficient_evidence` (full text not verified) — this is expected and correct; tool does not fake `full_text_available=yes`

---

## Novelty Precheck Blocking Test

Test that `novelty_check` blocks when `top_k.md` is still a template.

```bash
# Plan novelty_check — shows plan only, no execution
python tools/research_workflow.py plan novelty_check
```

**Expected:** plan displayed; no model call; no evidence precheck triggered.

```bash
# Prepare novelty_check — will block if top_k.md is template_only
python tools/research_workflow.py prepare novelty_check
```

**Expected:**
- If required inputs are missing → reports missing inputs
- If required inputs exist but `top_k.md` is `template_only` → blocked by `LITERATURE EVIDENCE PRECHECK FAILED`
- In any case: **no model API called**

---

## Local Env Requirement

`input_normalization` stage requires `ROLE_INPUT_NORMALIZER=DS_FLASH` in the local `.env` before running `prepare`.

- `.env.example` (commit `4f3dd8e`) contains this value.
- Existing `.env` files created before `4f3dd8e` may not have it.
- If `python tools/research_workflow.py plan input_normalization` fails with:
  `ERROR: model_route failed for role 'input_normalizer'`
  then add `ROLE_INPUT_NORMALIZER=DS_FLASH` to local `.env`.
- **Do not commit `.env`** — it contains real API keys.

---

## Safety Rules

- Do NOT commit `tmp/` directories or temporary test output
- Do NOT commit real PDFs to the repository
- Do NOT commit `raw_results.jsonl` / `candidates.jsonl` / `top_k.md` from temporary tests
- Do NOT use `git add .` — add files explicitly by name
- Smoke tests must NOT call model APIs
- Smoke tests must NOT access the network
- Smoke tests must NOT run experiments
- `top_k.md` is a literature evidence summary, **not a novelty verdict**
- `confirmed_novel`, `already_done`, `likely_incremental` must NOT appear in tool output — only the `novelty_check` role produces those verdicts
