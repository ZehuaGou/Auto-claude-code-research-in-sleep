# Research Idea Report

**Direction**: LLM for anomaly detection — time series, logs, multimodal, LLM output AD
**Generated**: 2026-05-03
**Pipeline**: research-lit → idea-creator (filtered) → [pending: novelty-check → research-review → research-refine-pipeline]
**Hardware**: RTX 4060 8GB + API access
**Background**: DiffAD (KDD 2023), TS anomaly detection, diffusion models

---

## Executive Summary

Generated 10 ideas → filtered to 7 viable → ranked by novelty × feasibility × fit to researcher background.

**Top recommendation**: **MUST-AD** — Multimodal Sensor-Text Anomaly Detection. This fills a clear gap (sensor+text fusion is nearly empty), directly builds on DiffAD expertise, and is feasible on RTX 4060 via frozen LLM + lightweight TS encoder.

**Backup**: TS-Xplain (explanation generation) and Explanation-Guided Refinement (precision improvement).

---

## Landscape Summary (from Phase 1)

The field is in an early but accelerating phase. Key structural findings:

1. **TS+LLM for AD is early-stage**: Only ~5 methods papers exist (NeurIPS 2025, ICML 2025). Fundamental questions remain open (Can LLMs understand TS?).
2. **Log AD is mature but unimodal**: All existing works are pure-text. The gap is combining numerical TS with log text.
3. **Multimodal sensor+text AD is nearly empty**: No paper specifically addresses this intersection — the clearest gap.
4. **TSFM for AD is questionable**: Critical papers show TimesFM/Chronos don't beat simple baselines for AD tasks.
5. **4060 feasibility confirmed**: QLoRA 7B (~5GB) and full fine-tune <500M both viable.

---

## Ranked Ideas

### 🏆 Idea 1: MUST-AD — Multimodal Sensor-Text Anomaly Detection via Cross-Modal Alignment

| Field | Value |
|------|-------|
| **Hypothesis** | Fusing numerical sensor time series with synchronised textual logs in a shared embedding space detects anomalies missed by unimodal methods |
| **Method** | Freeze a light text encoder (DistilRoBERTa 82M) for log snippets; train a lightweight TS encoder (TST-tiny ~0.3M) + projection layer with contrastive loss (InfoNCE) over aligned (window, log) pairs. Anomaly score = 1 − max cosine similarity to nearest normal text embedding |
| **Contribution** | **New method** — first framework to fuse numerical TS with textual logs for anomaly detection |
| **Novelty differentiation** | No existing work combines sensor metrics with auxiliary log text. Closest: multimodal AD uses vision, not text+TS |
| **Risk** | MEDIUM — requires paired dataset (server metrics + system logs). PSM/SMD datasets may have associated logs |
| **4060 feasibility** | ✅ DistilRoBERTa frozen, TS encoder ~0.3M, total <100M trainable params. Easily fits |
| **Reviewer objection** | "Paired sensor-text data is scarce; how do you know the text adds value beyond the sensor data?" |
| **Why this matters** | Real-world systems ALWAYS have both metrics and logs, but no existing AD method uses both jointly |

---

### 🥈 Idea 2: TS-Xplain — Lightweight Explanation Generation for TS Anomalies

| Field | Value |
|------|-------|
| **Hypothesis** | A small LM conditioned on TS patch embeddings via Q-Former can generate faithful explanations for why a window is anomalous |
| **Method** | Pre-train TS patch encoder (PatchTST-tiny) + Q-Former (4 layers) to compress patch embeddings into soft prompts. Fine-tune GPT-2 (124M) with QLoRA to generate explanation sentences. Bootstrap with API-generated rationales as supervision |
| **Contribution** | **New method** — first work to generate natural language explanations for TS anomalies |
| **Novelty differentiation** | Existing TS AD methods output only anomaly scores. LLM-LADE does log explanation, but not for numerical TS |
| **Risk** | MEDIUM — depends on quality of explanation supervision; can bootstrap via API |
| **4060 feasibility** | ✅ GPT-2 full fine-tune (~1.5GB) + Q-Former (~50MB) + encoder (~5MB) |
| **Reviewer objection** | "Explanations might be post-hoc rationalizations; how do you measure explanation faithfulness?" |
| **Why this matters** | AD without explanation has limited real-world value; this adds the missing interpretability layer |

---

### 🥉 Idea 3: Explanation-Guided Refinement of Anomaly Scores

| Field | Value |
|------|-------|
| **Hypothesis** | Initial anomaly scores from a lightweight detector can be refined by having an LLM generate explanations and verifying them against data, reducing false positives |
| **Method** | Classic detector (Isolation Forest) → top-k candidates → prompt 4-bit Phi-3-mini to generate explanation → embed explanation + factual deviation → compute similarity → down-weight candidates with weak explanations |
| **Contribution** | **New method** — LLM-as-filter to improve precision of existing AD methods |
| **Novelty differentiation** | Unlike end-to-end LLM AD methods, this is model-agnostic and adds an interpretable verification step |
| **Risk** | LOW-MEDIUM — the filter step is robust even if LLM explanations are imperfect |
| **4060 feasibility** | ✅ 4-bit Phi-3-mini (~2.5GB) + sentence transformer (~0.1GB) |
| **Reviewer objection** | "Why not just use a better detector? The LLM is a crutch for a weak base detector." |
| **Why this matters** | Practical: any production AD system can add this as a verification layer |

---

### Idea 4: In-Context "Spot the Odd One Out" Anomaly Detection

| Field | Value |
|------|-------|
| **Hypothesis** | A small instruction-tuned LLM can identify anomalies by comparing a test instance against normal in-context examples, mimicking human outlier detection |
| **Method** | For each test point, construct prompt with k normal examples + candidate in JSON lines. Use 4-bit Phi-3-mini (3.8B). Prompt: "Here are 5 sensor readings. One is anomalous. Which one?" Decision based on LLM selection |
| **Contribution** | **Empirical finding** — systematic study of in-context AD with LLMs |
| **Novelty differentiation** | Existing work uses zero-shot prompting; this tests explicit "odd one out" framing |
| **Risk** | HIGH — LLM may fail for subtle anomalies; prompt framing strongly biases results |
| **4060 feasibility** | ✅ 4-bit Phi-3-mini ~2.5GB, batch size ≤4 fits |
| **Reviewer objection** | "This is prompt engineering, not a methodological contribution." |
| **Why this matters** | If it works, enables training-free AD for new domains |
| **Verdict** | **BACKUP — interesting but high risk of weak reviewer reception** |

---

### Idea 5: TS as Text — Fine-Tuning GPT-2 for TS Anomaly Detection

| Field | Value |
|------|-------|
| **Hypothesis** | GPT-2 124M fine-tuned on string-tokenized TS windows can outperform specialized TS models for anomaly detection |
| **Method** | Convert sliding windows to formatted text → fine-tune GPT-2 with classification head → compare against TS baselines |
| **Contribution** | **Empirical finding** — systematic comparison of "TS as text" for AD |
| **Novelty differentiation** | TS-as-text has been tried for forecasting but not systematically for AD |
| **Risk** | LOW — straightforward to implement |
| **4060 feasibility** | ✅ Full fine-tune GPT-2 124M easily fits |
| **Reviewer objection** | "This is a known baseline approach; what's the methodological novelty?" |
| **Why this matters** | Low-risk, may produce a useful benchmark result |
| **Verdict** | **LOWER PRIORITY** — good baseline to include in experiments, but not strong enough as standalone contribution |

---

### Idea 6: Few-Shot AD via Template-Driven LLM Embeddings

| Field | Value |
|------|-------|
| **Hypothesis** | Natural-language summaries of TS windows embedded with sentence transformers create a semantic space where anomalies stand out, enabling few-shot detection |
| **Method** | Convert TS segments to templated sentences → embed with all-MiniLM-L6-v2 → compute centroid of normal → anomaly score = cosine distance |
| **Contribution** | **Empirical finding** — is semantic embedding space useful for TS AD? |
| **Novelty differentiation** | Simple, but nobody has systematically tested this for TS AD |
| **Risk** | MEDIUM — not all anomalies are semantically separable in embedding space |
| **4060 feasibility** | ✅ <100MB model, negligible compute |
| **Reviewer objection** | "This is a bag-of-words approach in disguise; it will miss pattern-level anomalies." |
| **Verdict** | **LOWER PRIORITY** — too simple for top venue |

---

### Idea 7: LLM-Generated Adaptive Anomaly Detectors from NL Specifications

| Field | Value |
|------|-------|
| **Hypothesis** | An LLM can translate high-level user descriptions into executable Python code for bespoke anomaly detectors, reducing prototyping time |
| **Method** | User provides metadata prompt → 4-bit CodeLlama-7B generates PyTorch script → execute in sandbox → self-debug loop |
| **Contribution** | **System/tool** — LLM-as-code-generator for AD |
| **Novelty differentiation** | Novel application of code generation, but more engineering than science |
| **Risk** | MEDIUM — code quality is brittle |
| **4060 feasibility** | ✅ 4-bit CodeLlama-7B ~4-5GB |
| **Reviewer objection** | "This is an engineering demo, not a research contribution." |
| **Verdict** | **ELIMINATED** — does not meet the "methodological contribution" requirement |

---

## Eliminated Ideas

| Idea | Reason Eliminated |
|------|-------------------|
| Zero-shot VLM on Recurrence Plots | Requires CLIP vision pipeline; too far from user's TS background |
| Video Surveillance AD | Requires video processing; not aligned with user's expertise |
| LLM-Enhanced Graph AD | Graph neural networks are a different subfield; text-rich graphs are scarce |
| LLM-Generated Adaptive Detectors (Idea 7) | Engineering demo, not methodological contribution |

---

## Recommended Execution Order

1. **Start with MUST-AD (Idea 1)** — highest novelty, clear gap, directly builds on DiffAD expertise
   - First step: check if PSM/SMD datasets have associated system logs
   - If paired data exists → full implementation
   - If not → consider generating paired data or using alternative datasets (SWaT has documentation)

2. **TS-Xplain (Idea 2) as complementary contribution** — Adds explainability layer
   - Can be combined with MUST-AD for a unified "detection + explanation" framework
   - Bootstrap explanations via API (DeepSeek/Claude)

3. **Explanation-Guided Refinement (Idea 3) as ablation** — Tests whether LLM explanations actually improve detection

4. **TS-as-Text (Idea 5) as baseline** — Should be included in experiments regardless of which idea is pursued

---

## Next Steps

- [x] **Phase 1**: Literature Survey → `idea-stage/LITERATURE_SURVEY.md`
- [ ] **Phase 3**: Deep Novelty Verification — Run `/novelty-check` on top 2 ideas
- [ ] **Phase 4**: External Critical Review — Run `/research-review`
- [ ] **Phase 4.5**: Method Refinement + Experiment Planning — Run `/research-refine-pipeline`
- [ ] **Phase 5**: Final Report
