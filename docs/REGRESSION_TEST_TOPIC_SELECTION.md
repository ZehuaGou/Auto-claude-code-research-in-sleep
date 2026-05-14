# Regression Test Topic Selection

**Date:** 2026-05-14
**HEAD:** ff2ab60
**Goal:** Select a new lightweight regression test topic for end-to-end system validation.

---

## 1. Why a new regression test

The current system has been developed and tested exclusively around one topic: **"token-level hallucination detection using hidden state trajectories."** This was the original research idea that drove development, but it has become a liability for system validation:

- **Overfitting to one domain.** The scoring keyword groups, negative term lists, and relevance thresholds were all tuned against this specific topic. A system that only works for hallucination research is not a general-purpose research automation tool.
- **Paywall risk.** The hallucination trajectory topic mixes CS (NLP/ML) with cognitive science terminology. Many relevant papers are behind IEEE/ACM paywalls, making full-text acquisition unreliable for regression testing.
- **Narrow source coverage.** The topic is niche enough that arXiv coverage is thin compared to broader AI/ML topics. This makes it hard to verify that the multi-source pipeline (arXiv + OpenAlex + Crossref) actually works end-to-end.
- **No independent validation.** If the system produces a bad novelty assessment for hallucination trajectory, we cannot easily tell whether the system is broken or whether the topic genuinely has limited prior work.

A second, independent regression test topic lets us:
1. Verify the pipeline works for arbitrary CS/AI topics, not just the original one.
2. Catch scoring/dedup bugs that are masked by the hallucination topic's specific keyword profile.
3. Validate that full-text acquisition works for papers with open access (arXiv PDFs, OpenReview).
4. Build confidence that the system is ready for real user ideas.

---

## 2. Limitations of the hallucination trajectory test case

| Dimension | Status | Problem |
|-----------|--------|---------|
| arXiv coverage | Moderate | Few papers combine "hidden state trajectories" + "hallucination detection" |
| OpenReview coverage | Low | Very few ICLR/NeurIPS papers on this exact intersection |
| OpenAlex coverage | Moderate | Broader "hallucination" papers exist, but the trajectory angle is niche |
| Full-text availability | Poor | Many relevant papers are IEEE/ACM paywalled |
| Keyword scoring | Overfit | The `_HALLUCINATION_GROUP` and `_INTERNAL_STATE_GROUP` are perfectly tuned for this topic |
| Reproducibility | Low | Hard to verify pipeline correctness when the topic itself is borderline |

---

## 3. Candidate topics

### Candidate A: Retrieval-Augmented Generation for Code Completion

**Topic string:** "Retrieval-Augmented Generation for code completion"

| Dimension | Assessment |
|-----------|-----------|
| arXiv coverage | **Excellent.** RAG + code is a very active area (2023-2026). Dozens of papers on arXiv: CodeRAG, RAGCoder, RepoCoder, etc. |
| OpenReview coverage | **Good.** ICLR/NeurIPS/EMNLP have RAG papers; code-specific ones appear at ICSE/FSE/ASE too. |
| OpenAlex coverage | **Excellent.** Broad coverage of RAG literature across venues. |
| Full-text availability | **High.** Most RAG-for-code papers are on arXiv with open PDFs. |
| Paywall risk | **Low.** Core papers are preprints or open-access venue papers. |
| Quick experiment | **Yes.** Can test with a small codebase + retrieval index. No special hardware needed. |
| CS research automation fit | **Excellent.** Clear problem statement, well-defined baselines, measurable outcomes. |

**Query variants verified:** 12 (PASS at plan generation)
**Must-include terms:** retrieval-augmented, code completion, large language model

### Candidate B: Chain-of-Thought Prompting for Mathematical Reasoning

**Topic string:** "Chain-of-Thought prompting for mathematical reasoning in large language models"

| Dimension | Assessment |
|-----------|-----------|
| arXiv coverage | **Excellent.** CoT + math is one of the most active NLP research areas (2022-2026). |
| OpenReview coverage | **Excellent.** Top venues (ICLR, NeurIPS, ACL) have many CoT papers. |
| OpenAlex coverage | **Excellent.** Broad cross-venue coverage. |
| Full-text availability | **High.** Most CoT papers are on arXiv. |
| Paywall risk | **Low.** Core papers are preprints. |
| Quick experiment | **Yes.** Can test with GSM8K/MATH benchmarks + prompting. |
| CS research automation fit | **Excellent.** Well-defined task, clear metrics, active area. |

**Query variants verified:** 12 (PASS at plan generation)
**Must-include terms:** chain-of-thought, mathematical reasoning, large language model

### Candidate C: Knowledge Distillation for Efficient LLM Inference on Edge Devices

**Topic string:** "Knowledge distillation for efficient large language model inference on edge devices"

| Dimension | Assessment |
|-----------|-----------|
| arXiv coverage | **Good.** Active area but more spread across sub-topics (quantization, pruning, distillation). |
| OpenReview coverage | **Moderate.** Some papers at ICLR/NeurIPS, but fewer than A or B. |
| OpenAlex coverage | **Good.** Broad coverage of KD literature. |
| Full-text availability | **Moderate.** Some papers are arXiv preprints, but edge/MLSys papers may be paywalled. |
| Paywall risk | **Moderate.** MLSys/IEEE papers on edge deployment may be behind paywalls. |
| Quick experiment | **Moderate.** Needs a teacher model + edge device or simulator. |
| CS research automation fit | **Good.** Clear problem, but the "edge device" angle adds hardware complexity. |

**Query variants verified:** 12 (PASS at plan generation)
**Must-include terms:** knowledge distillation, large language model, edge device

---

## 4. Recommendation

**Recommended topic: Candidate B — Chain-of-Thought Prompting for Mathematical Reasoning**

### Why B over A

Both are excellent choices. B is slightly preferred because:
- **Broader source coverage.** CoT + math has even more papers across more venues than RAG + code, giving the pipeline more data to work with.
- **Lower domain specificity.** RAG + code is a sub-niche of code AI; CoT + math is a mainstream NLP topic. A mainstream topic better exercises the general-purpose pipeline.
- **Better full-text availability.** CoT papers are overwhelmingly arXiv preprints. RAG-for-code papers are too, but some important ones (e.g., from ICSE) may be paywalled.

### Why B over C

C is too niche and introduces hardware complexity that is irrelevant to testing the research automation pipeline. The paywall risk is also higher.

### Why this is better than hallucination trajectory

1. **No keyword overfitting.** The scoring groups (`_HALLUCINATION_GROUP`, `_INTERNAL_STATE_GROUP`) were tuned for hallucination trajectory. CoT + math will exercise different keyword paths and expose any scoring weaknesses.
2. **Abundant open-access papers.** The pipeline can actually find and acquire full texts, which is essential for testing the full_text_review stage.
3. **Independent validation.** If the system says a CoT + math idea is novel, we can sanity-check against our own knowledge of the field. The hallucination trajectory topic is too niche for easy sanity-checking.
4. **Reproducible.** Anyone can run the same topic and get comparable results.

---

## 5. How to start the new workflow run

When ready to run the actual regression test (not this session — this session is dry-run only):

```bash
# Step 1: Start a fresh run with the recommended topic
python tools/research_cli.py start \
  --idea "Chain-of-Thought prompting for mathematical reasoning in large language models" \
  --mode novelty_risk \
  --dry-run

# Step 2: If dry-run looks good, run for real
python tools/research_cli.py start \
  --idea "Chain-of-Thought prompting for mathematical reasoning in large language models" \
  --mode novelty_risk

# Step 3: Continue through the pipeline
python tools/research_cli.py continue --stage literature_search
python tools/research_cli.py continue --stage novelty_check
# ... etc.
```

### Success criteria for the new regression test

1. The pipeline finds ≥50 raw records across arXiv + OpenAlex.
2. At least 5 papers have open full text available.
3. The relevance scoring correctly identifies CoT+math papers as high-relevance.
4. The dedup logic merges papers that appear in multiple sources.
5. The novelty check produces a meaningful assessment (not just "no prior work").
6. No paywall-related failures in full-text acquisition.

---

## 6. Important: test topic ≠ product

This document selects a **regression test topic** for validating the system. The test topic is not the product. The product is:

> **One-command trusted research automation for arbitrary research ideas.**

The CoT + math topic is a means to validate that the system works. Once validated, the system should be used for whatever research idea the user actually cares about — which may be hallucination trajectory, or may be something else entirely.

Do not conflate the test case with the system's purpose.
