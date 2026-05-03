# Research Brief

> 基于扩散模型时序异常检测的工作背景，结合大模型寻找新的 research direction，目标申请 2027 年 PhD。

## Problem Statement

异常检测是数据挖掘领域的核心问题之一，在工业系统监控、运维、欺诈检测等场景有广泛应用。我在 KDD 2023 发表的 DiffAD 工作中，证明了扩散模型在时序异常检测上的有效性——通过条件 weight-incremental 扩散做 imputation，以重建误差判异常。

但从 2023 年到现在，领域格局发生了几个关键变化：

1. **LLM 展示了强大的序列建模和表示学习能力**，在时序任务上（如 TimesFM、Lag-Llama、PatchTST）证明了 transformer/LLM 架构在时序建模中的优越性。但 LLM 在异常检测这个特定任务上的潜力还没有被充分挖掘。
2. **扩散模型的热度在下降**，LLM 和 foundation model 成为主流范式。继续纯粹沿着扩散模型做 TS anomaly detection，在 novelty 和投稿竞争力上可能面临挑战。
3. **工业级异常检测正从"检测"走向"诊断"**——仅给出异常分数已经不够，需要可解释性、根因分析、多模态融合。

同时，异常检测的范畴也在扩展：
- 传统时序异常检测（服务器指标、传感器）
- 日志异常检测（半结构化文本，LLM 天然适配）
- LLM 自身的异常（幻觉、毒性、越狱检测）——一个新的交叉方向
- 多模态异常检测（数值 + 文本 + 图像）

这些方向之间的共性问题是：**如何有效利用 LLM 的泛化能力和语义理解能力来做异常检测，同时保持计算开销可控（RTX 4060 8G 级别）？**

## Background

- **Field**: Data Mining / Anomaly Detection / Time Series
- **Sub-area**: Diffusion models for time series anomaly detection → LLM for anomaly detection
- **Key publication**: C. Xiao, Z. Gou, et al. "Imputation-based Time-Series Anomaly Detection with Conditional Weight-Incremental Diffusion Models" — KDD 2023
- **Prior work I know well**:
  - DiffAD (my work): 扩散模型做时序 imputation 异常检测，weight-incremental condition
  - USAD、MSCRED、GDN、MTAD_GAT、AnomalyTransformer 等 TS 异常检测基线
  - TimesFM、Lag-Llama、MOIRAI、PatchTST 等时序 foundation model
  - LogAnomaly、DeepLog、BERTLog 等日志异常检测
- **What I already tried**: 扩散模型的条件生成范式在时序异常检测上的应用，对 PSM、SMAP、MSL、SMD、SWaT 等 benchmark 有深入理解和实践经验
- **What didn't work / limitations of prior work**:
  - 扩散模型采样慢，实时检测场景受限
  - 纯数值时序方法缺少语义理解能力，无法解释异常"为什么"发生
  - 现有工作对多模态信号（日志 + 数值）融合不充分
  - 跨域迁移能力有限——在一个场景训练的模型很难迁移到另一个场景

## Constraints

- **Compute**: 单张 RTX 4060 8GB VRAM。可接受 4-bit QLoRA fine-tune 7B 模型（~5-6GB），或者全参训练 <500M 参数模型。也可调用 LLM API（GPT-4、Claude、DeepSeek 等）做推理/蒸馏。
- **Storage**: 本地存储充足，可下载公开数据集
- **Timeline**: ~12 个月的 research 周期，目标 2027 年 PhD 申请前有 publication
- **Target venue**: KDD、NeurIPS、ICML、ICLR、CIKM、AAAI 均可

## What I'm Looking For

- [x] New research direction from scratch（不一定要延续扩散模型）
- [x] Improvement on existing method
- [ ] Diagnostic study / analysis paper
- [x] LLM + anomaly detection 的交叉方向
- [ ] 也可以不局限于时间序列

**核心诉求**：找到一个有新意、4060 8G 能做、能支撑 strong publication 的方向，提升 2027 年 PhD 申请的竞争力。

## Domain Knowledge

- 异常检测的本质是分布外检测 + 可解释性——不仅要找出异常，还要说明为什么异常
- LLM 的优势在于语义理解和泛化，劣势在于计算成本高和幻觉
- 关键直觉：LLM 在异常检测中的角色可以是多层次的——
  - **表示层**：LLM 作为特征提取器，提供语义 rich 的表示
  - **推理层**：LLM 作为推理引擎，做多步诊断和根因分析
  - **生成层**：LLM 生成异常解释、修复建议
- RTX 4060 8G 的限制意味着需要精打细算——小模型 + 量化 + API 混合策略
- 时序异常检测 benchmark（PSM、SMAP、MSL、SMD、SWaT）已经比较成熟，但大多数方法缺乏可解释性

## Non-Goals

- 不做纯扩散模型方法（除非有非常强的理由）
- 不做需要大规模分布式训练的方向（4+ GPU、100GB+ VRAM）
- 不做纯理论/证明类的工作（更适合有数学背景的申请者）
- 不做纯 NLP 任务（希望保留异常检测的底色）
- 避免"LLM 套壳"类工作——需要方法论贡献，不只是调用 API

## Existing Results (if any)

- DiffAD 在 PSM/SMAP/MSL/SMD/SWaT 五个 benchmark 上取得了 SOTA 或接近 SOTA 的结果
- 对 TS anomaly detection 的核心挑战（点异常 vs 模式异常、时序依赖建模、可解释性）有深入理解
- 代码框架（PyTorch + Python）已经完善，可快速在新方向上搭建实验
- 熟悉 multi-source 数据集的特性：PSM（eBay 服务器指标）、SMAP/MSL（NASA 航天器）、SMD（阿里服务器）、SWaT（水处理系统）
