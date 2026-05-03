# Literature Survey: LLM for Anomaly Detection

**Date**: 2026-05-03
**Direction**: LLM for anomaly detection — time series, logs, multimodal, LLM output AD
**Hardware Constraint**: RTX 4060 8GB
**Sources**: arXiv API, WebSearch, Google Scholar, Semantic Scholar

---

## Executive Summary

LLM for anomaly detection is an emerging cross-direction. NAACL 2025 published the first systematic survey (Xu & Ding), categorizing LLM roles as *feature extractors* or *reasoning agents*. 2024–2025 has seen rapid growth across four sub-areas with different maturity levels.

Key findings:
- **TS + LLM for AD is early-stage, high-upside**: few methods papers, active debate on LLM's fundamental ability to understand time series
- **Log AD is crowded**: many works, but all are pure-text — combining with numerical TS is a gap
- **Multimodal AD (sensor+text) is almost empty**: the intersection of your DiffAD background and LLM
- **TS foundation models for AD have questionable value**: recent studies show they don't beat simple baselines

---

## 1. Time Series Anomaly Detection with LLM

### 1.1 Foundational / Benchmarking Studies

| Paper | Venue | Key Finding | Relevance |
|-------|-------|-------------|-----------|
| **Can LLMs Understand Time Series Anomalies?** (Zhou & Yu, 2024) | arXiv 2410.05440 | LLMs understand TS better as images than text; CoT does NOT help TSAD; performance varies significantly across models | ⭐⭐⭐ Challenges the "LLM can natively understand TS" assumption |
| **Anomaly Detection of Tabular Data Using LLMs** (Li et al., 2024) | arXiv 2406.16308 | Pre-trained LLMs are zero-shot batch-level anomaly detectors for tabular data | ⭐⭐⭐ LLM's ability to identify low-density regions without training |
| **Time Series Foundational Models: Their Role in Anomaly Detection** (Shyalika et al., 2024) | arXiv 2412.19286 | TSFMs underperform specialized models; black-box nature limits applicability | ⚠️ TSFM-for-AD is questionable |
| **When Foundation Models are One-Liners** (OpenReview 2025) | OpenReview | TimesFM/Chronos/MOMENT don't beat moving-window variance baselines for AD | ⚠️ Critical negative result |

### 1.2 Method Papers (LLM + TS AD)

| Paper | Venue | Method | Compute | Relevance |
|-------|-------|--------|---------|-----------|
| **Delving into LLMs for Effective TSAD** (Park et al.) | **NeurIPS 2025** | Statistical decomposition + index-aware prompting; 66.6% F1 ↑ | API-based | ⭐⭐⭐⭐⭐ State-of-the-art LLM+TSAD |
| **SPEAR: Soft Prompt Enhanced Anomaly Recognition** (Wei et al., 2025) | arXiv 2510.03962 | Soft prompts + quantization for small LLMs, no full fine-tuning | 4060 ✅ 4-bit QLoRA | ⭐⭐⭐⭐ Efficient small-model approach |
| **LEAD Framework** (ICML 2025) | **ICML 2025** | Two-stage: statistical screening + batched LLM; precision 27%→72%, 14× latency ↓ | 4060 ✅ Statistical + API | ⭐⭐⭐⭐ Efficient hybrid |
| **LAST SToP** (ICML 2025) | **ICML 2025** | Stochastic soft prompting for asynchronous TS; outperforms QLoRA fine-tuning | 4060 ✅ | ⭐⭐⭐ Novel prompt method |
| **CALM: Continuous Adaptive LLM-Mediated AD** (2025) | arXiv | TimesFM + LLM-as-Judge; closed-loop continuous fine-tuning for concept drift | API + TSFM | ⭐⭐⭐ TS foundation + LLM |

### 1.3 Domain-specific LLM+TS AD

| Paper | Method | Gap it Addresses |
|-------|--------|------------------|
| **Metabolic Info + LLM for Clinical TS AD** (Rahman et al., 2024) | Metabolism Pathway-driven Prompting (MPP) | Domain knowledge injection into LLM for clinical TS AD |
| **LLM-Mixer** (Kowsher et al., 2024) | Multiscale mixing in LLMs for TS | LLM architecture for TS, but for forecasting, not AD |
| **Production TS Monitoring using VLMs** (SPE 2025) | VLM with TS-as-images | Industry application of visual+TS AD |

---

## 2. Log Anomaly Detection with LLM

Most mature sub-area. Many papers use LoRA fine-tuned LLaMA-7B/8B.

| Paper | Venue | Method | Compute | Differentiation |
|-------|-------|--------|---------|-----------------|
| **LLM-LADE** (2025) | **KBS** | LLaMA3-8B + LoRA; 3-stage: augmentation → PEFT → incremental KB | ✅ ~5GB | Detection + explanation jointly |
| **LogLLaMA** (2025) | arXiv 2503.14849 | LLaMA2 + REINFORCE RL + Top-K selection | ✅ ~5GB | Generative next-log-key prediction |
| **LogLLM** (2024) | arXiv 2411.08561 | BERT + Llama hybrid + projector; no parser needed | ✅ ~3GB | Parser-free |
| **FlexLog** (2025) | arXiv 2406.07467 | ML + Mistral + RAG; 62.87% less labeled data | ✅ Lightweight | Data efficiency |
| **LogRules** (2025) | **NAACL 2025 Findings** | Rule induction via GPT-4o-mini + CPO alignment | API | Anti-hallucination via rules |
| **EnrichLog** (2025) | arXiv | Training-free RAG; corpus-specific knowledge | ✅ Training-free | Zero training cost |
| **LLM-Enhanced Log AD Benchmark** (Patel, 2026) | arXiv 2604.12218 | Systematic benchmark of LLM vs traditional methods | N/A | Provides standardized evaluation |

### Gap: 
Pure log AD is crowded. **The clear gap is combining numerical TS (your DiffAD) + log text** — no existing work in this intersection.

---

## 3. Multimodal Anomaly Detection

Two largely separate sub-directions: **Industrial Visual AD** (crowded) and **Multimodal Sensor+Text** (open).

### 3.1 Visual Industrial AD (crowded — many papers on MVTec/VisA)

| Paper | Venue | Method | Notes |
|-------|-------|--------|-------|
| MALM-CLIP (2025) | SciDir | Multi-agent LLM + CLIP | Requires visual backbone |
| MoXpert (2025) | PR | MoE wrapper for frozen MLLM, +7.4% | Lightweight adapter |
| OmniAD (2025) | arXiv | Multimodal reasoning + RL (GRPO) | Heavy training |
| Unlocking VLMs for Video AD (2025) | arXiv 2510.02155 | VLM + fine-grained prompting | Video-focused |

### 3.2 Sensor + Text Multimodal AD (GAP — nearly empty)

Combining numerical time series sensor readings with auxiliary text (sensor metadata, maintenance logs, operational context). This is:
- **Natural for you**: DiffAD already works on server metrics (PSM, SMD) which often have logs
- **Not explored**: no paper specifically addresses this intersection

---

## 4. LLM Output Anomaly / Hallucination Detection

A mature standalone field. Not directly connected to DiffAD background but transferable OOD methodology.

| Paper | Venue | Method |
|-------|-------|--------|
| **Hallucination Detection with Small LMs** (Cheung, 2025) | arXiv 2506.22486 | Detection using small models |
| **THaMES** (Liang et al., 2024) | arXiv 2409.11353 | End-to-end hallucination mitigation & evaluation |
| **Probabilistic Distances Hallucination Detection** (Oblovatny, 2025) | arXiv 2506.09886 | RAG + probabilistic distances |

---

## 5. Comprehensive Surveys

| Survey | Venue | Coverage |
|--------|-------|----------|
| **Xu & Ding — LLMs for Anomaly and OOD Detection** | **NAACL 2025 Findings** | First systematic survey; taxonomy of LLM roles |
| AIOps for Log AD in the Era of LLMs | Array 2025 | RAG + LLM for AIOps diagnostics |
| Time Series LLMs: A Systematic Review | IEEE Access 2025 | 700+ studies; anomaly detection still underexplored |
| Generative Models for TSAD: A Survey | IEEE TAI 2025 | GANs, Transformers, diffusion for TSAD (includes your DiffAD context) |
| A Survey of AIOps in the Era of LLMs (Zhang et al., 2025) | arXiv 2507.12472 | Comprehensive AIOps + LLM review |
| Deep AD of Temporal Heterogeneous Data in AIOps | FITEE 2025 | Four methodological groups; LLM for network AD |

---

## 6. Hardware Feasibility: RTX 4060 8GB

| Scale | What's Possible | VRAM |
|-------|----------------|------|
| 7B-8B model | 4-bit QLoRA fine-tune (LLaMA3, Qwen2.5, DeepSeek) | ~5-6GB |
| 1.5B-3B model | Full fine-tune or LoRA (Phi-3 mini, Qwen2.5-1.5B) | ~3-5GB |
| <500M model | Full training from scratch | <3GB |
| Statistical + API hybrid | Preprocessing locally, LLM via API | Negligible |

**Evidence**: "Profiling LoRA/QLoRA Fine-Tuning on RTX 4060 8GB" (2025) — Qwen2.5-1.5B feasible at seq_len 2048, PagedAdamW +25% throughput, fp16 > bf16.

---

## 7. 🚩 Key Gaps & Opportunities

Ranked by potential + fit to your background:

| Gap | Opportunity | Your Advantage | Feasibility |
|-----|------------|----------------|-------------|
| **1. Multimodal TS + Text AD** | Combine numerical TS (your DiffAD) with auxiliary log/text for joint anomaly detection | Deep TSAD expertise + access to benchmark data | ✅ 4060 |
| **2. Efficient Statistical + LLM AD** | LEAD-style two-stage on 4060; statistical screening + small LLM verification | Know TSAD benchmarks intimately | ✅ 4060 |
| **3. Explainable TS AD via LLM** | Add LLM-generated anomaly explanations on top of detection | DiffAD lacks explainability — natural extension | ✅ API-based |
| **4. Small LLM via Knowledge Distillation** | Distill from API strong LLM (GPT-4/Claude) → small on-device model | 4060 perfect for inference | ✅ 4060 |
| **5. Online / Streaming LLM AD** | Concept drift adaptation with LLM + TS foundation model | Real-world deployment relevance | ⚠️ More complex |

### Most recommended direction:

**"Multimodal Time Series + Text Anomaly Detection via Efficient LLM Fusion"**
- Use DiffAD/TS backbone for numerical features
- Use small LLM (Phi-3/Qwen2.5-1.5B) for text log understanding  
- Fuse both modalities for anomaly detection + explanation
- 4060 feasible ~5GB with QLoRA
- Novel: no existing work combines TS sensor AD with textual log understanding
