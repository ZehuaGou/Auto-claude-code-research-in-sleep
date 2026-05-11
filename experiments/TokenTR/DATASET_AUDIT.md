# TokenTR Dataset Audit

**Date**: 2026-05-11
**Purpose**: Find real token-level hallucination labels for formal M1 TokenTR evaluation

---

## Summary

Formal token-level M1 (per-token AUROC/AUPRC/F1) requires **token_labels** or **hallucination_spans**
with binary labels aligned to individual response tokens. Sample-level labels (is_hallucinated)
are insufficient. No labeled data found locally.

---

## Candidate Datasets

### 1. RAGTruth_Xtended (PRIMARY — token-level, ideal fit)

| Field | Value |
|-------|-------|
| Source | `github.com/jakobsnl/RAGTruth_Xtended` |
| Paper | `2507.20836` (in literature-md/) |
| Label type | **Token-level** hallucination annotations |
| Volume | Large-scale, multiple LLMs |
| Format | `token_labels` (list of 0/1) aligned to response tokens |
| LongFact-compatible | Yes — uses LongFact prompts |
| Formal M1 suitability | ✅ **Fully compatible** — direct token_labels |
| Download | `git clone https://github.com/jakobsnl/RAGTruth_Xtended.git` |

**Assessment**: Best match. Token-level binary labels per response token, aligns with LongFact
prompts, exactly what TokenTR formal M1 requires.

### 2. LongFact-Objects (SECONDARY — entity span-level, usable)

| Field | Value |
|-------|-------|
| Source | `ZhongangQi/LongFact-Objects` (HuggingFace) |
| Paper | `2512.20949` (in literature-md/) |
| Label type | **Entity span-level** annotations: `s=[start, end]` (token indices), `ys=binary` |
| Volume | ~500 samples |
| Format | `hallucination_spans` (list of {start, end} with binary per span) |
| Token-level adaptation | ⚠️ Requires converting span boundaries → per-token labels |
| Formal M1 suitability | ✅ Compatible via span-to-token conversion |
| Download | `python -c "from datasets import load_dataset; ds = load_dataset('ZhongangQi/LongFact-Objects')"` |

**Assessment**: Spans annotate entity mentions (person/org/location/date/citation). Each span has a
binary label. Converting to per-token labels is straightforward — span → expand to token range.
LongFact-Objects is already the dataset used in the current scaffold.

### 3. HaluEval (NOT SUITABLE)

| Field | Value |
|-------|-------|
| Source | `HaluEval` (HuggingFace) |
| Label type | **Sentence-level** hallucination labels |
| Formal M1 suitability | ❌ Insufficient — only sample-level labels, no token-level annotations |

### 4. FELM / FAVA (NOT FOUND)

- No local copies found in project literature-md/ or papers/
- Web search did not surface definitive token-level labeled datasets for hallucination

---

## Local Audit Results

```
literature-md/2507.20836/   → RAGTruth_Xtended paper + reference (token-level annotations exist)
literature-md/2512.20949/   → LongFact paper + entity-level token spans
literature-md/2507.16488/   → ICR Probe paper, references LongFact-annotations dataset

experiments/TokenTR/fixtures/tokentr_sanity.jsonl  → 5 synthetic samples (sample_weak mode only)
experiments/TokenTR/data/splits/longfact_metadata.json  → block_reason: label_mode=synthetic
```

---

## Recommended Download Commands

### Option A: RAGTruth_Xtended (preferred — already has token_labels)

```bash
cd D:/Code/Python/Auto-claude-code-research-in-sleep
git clone https://github.com/jakobsnl/RAGTruth_Xtended.git experiments/TokenTR/data/raw/RAGTruth_Xtended
```

Then inspect for token-level label files. Expected structure: JSON/JSONL with per-sample
`token_labels` array matching response token count.

### Option B: LongFact-Objects (immediate — already scaffolded)

```bash
# Uses HF mirror for China access
export HF_ENDPOINT=https://hf-mirror.com
python -c "from datasets import load_dataset; ds = load_dataset('ZhongangQi/LongFact-Objects', split='train'); print(ds[0])"
```

Validate annotations:
```bash
python experiments/TokenTR/validate_tokentr_data.py \
    --dataset_path experiments/TokenTR/fixtures/tokentr_sanity.jsonl
```

Expected output: `PASS_SPAN_LABELS` (if span files downloaded) or `PASS_FORMAL_TOKEN_LABELS` (if RAGTruth token-level files found).

---

## Next Steps After Download

1. **Validate with `validate_tokentr_data.py`**
   ```bash
   python experiments/TokenTR/validate_tokentr_data.py \
       --dataset_path experiments/TokenTR/data/raw/RAGTruth_Xtended/data.jsonl
   ```

2. **Run M0 formal extraction**
   ```bash
   python experiments/TokenTR/m0_hidden_extraction.py \
       --dataset_path experiments/TokenTR/data/raw/RAGTruth_Xtended/data.jsonl \
       --label_mode token \
       --max_samples 500 \
       --seed 42
   ```

3. **Verify metadata.json says `can_run_formal_m1: true`**
   ```bash
   cat experiments/TokenTR/data/splits/longfact_metadata.json | grep -E "can_run_formal_m1|block_reason"
   ```

4. **Run M1 formal pilot**
   ```bash
   python experiments/TokenTR/m1_tokentr_pilot.py \
       --dataset_path experiments/TokenTR/data/raw/RAGTruth_Xtended/data.jsonl \
       --label_mode token
   ```

---

## If No Network Access

The scaffold supports `--dataset_path` for local JSON/JSONL. Any dataset with:
- `sample_id` field per row
- Either `token_labels` (list of 0/1, len = response tokens) OR
  `hallucination_spans` (list of {start, end} per hallucinated span)
- Same prompt structure as LongFact (or any factual QA response)

is sufficient to unlock formal M1.

---

## Abbreviations

| Term | Meaning |
|------|---------|
| token_labels | Per-token binary hallucination labels (0=factual, 1=hallucinated) |
| hallucination_spans | List of {start, end} span boundaries, binary per span |
| is_hallucinated | Sample-level binary label (insufficient for formal M1) |