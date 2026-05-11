# TokenTR Data Requirements

> Specifies what token-level hallucination labels are required for formal M1 evaluation.
> Without formal token-level labels, only synthetic/sample-weak smoke tests are permitted.

## Label Modes

### Formal (token | span)

| Mode | Required | Can Run Formal M1 |
|------|----------|-------------------|
| `token` | `token_labels: List[int]` per sample, aligned to tokenizer output | YES |
| `span` | `hallucination_spans: List[Dict]` with char or token offsets mappable to tokenizer | YES |
| `sentence` | sentence-level labels + verified token-mapping rule in dataset metadata | YES (if mapping verified) |
| `sample_weak` | `is_hallucinated: int` per sample only | NO — only weak-label sanity |
| `synthetic` | programmatically generated (for pipeline shape sanity only) | NO |

**Formal M1 requires `token`, `span`, or `sentence` (with verified mapping).**

## Prohibited Patterns

| Forbidden | Reason |
|-----------|--------|
| Copy `is_hallucinated` to all tokens as identical label | Token-level signal must be per-token |
| Use model output as ground truth | Eval must use dataset ground truth |
| Select F1 threshold on test set | Threshold must be selected on validation, applied once on test |
| Random token-level split | Leaks tokens from same prompt/sentence across train/val/test |
| Use another model's output as label proxy | All baselines must share the same ground truth labels |

## Split Requirements

- **LongFact**: 60/20/20 train/val/test, **grouped by `sample_id` or document/prompt**, NOT random token split
- **HaluEval**: 70/30 val/test only (no training needed for Gaussian-fitting methods)
- All baselines and TokenTR must use the **identical split**
- Token indices must be derived from sample-level train/val/test groups

## Sample-Level Weak Label Protocol

If only `is_hallucinated` is available (no token-level spans):

1. **Can**: run sequence-level / aggregate weak-label sanity
2. **Must**: set `--label_mode sample_weak`
3. **Must not**: claim token-level results
4. **Must not**: use to pass success/failure gates
5. **Must not**: report as token-level AUROC/AUPRC

## Metadata Contract

After M0 extraction, the following metadata must be saved to
`experiments/TokenTR/data/splits/longfact_metadata.json`:

```json
{
  "label_mode": "token | span | sentence | sample_weak | synthetic",
  "dataset_source": "ZhongangQi/LongFact-Objects | local_path",
  "split_mode": "sample_grouped | random_token (forbidden for formal)",
  "n_samples": <int>,
  "n_tokens": <int>,
  "has_token_labels": true | false,
  "has_spans": true | false,
  "hallu_prevalence": <float>,
  "can_run_formal_m1": true | false,
  "block_reason": null | "<reason string>"
}
```

## Success Gate Constraint

Formal M1 success/failure gates (AUROC > 0.60, MLP gate, identity gate, etc.)
**cannot be claimed** when `label_mode != token | span | sentence (verified)`.

Only `label_mode=token` with properly aligned subword labels can produce
contract-compliant results.
