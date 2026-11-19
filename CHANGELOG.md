# Changelog

All notable changes to **AIBaG (Algorithm & AI Interview Lab)** are documented in this file.

## [v2.0.0] - 2026-11-19

### Highlights
- **2,000-Problem Structured Interview Bank**: Expanded the built-in catalog from 1,000 to **2,000** exercises (`250` canonical base problems × `8` interview perspectives), while keeping cold-start catalog compilation under **0.03s** (`< 5.0s` invariant).
- **MIT License & Open-Source Release Standardization**: Added root `LICENSE` (`MIT`) alongside `THIRD_PARTY_NOTICES.md` and per-problem SPDX/provenance metadata so developers can freely fork, customize, and redistribute.

### Added
- **50 New Canonical Base Problems (`data/catalog/part-005.json`) + Persisted Reference Answers (`data/answers.json`)**:
  - **20 New AI Infra Whiteboard Coding Problems (`480` total in track)**: Grouped-Query Attention (GQA), Multi-Query Attention (MQA), DeepSeek MLA Low-Rank KV Projection, Sliding Window Causal Mask, 1-Pass Online Softmax, Cosine Warmup LR Scheduler, Manual Global `clip_grad_norm_`, Decoupled AdamW Step, Per-Channel INT8 Weight Quantization, Dynamic Per-Token INT8 KV Cache Quantization, Speculative Decoding Rejection Sampling, PagedAttention Logical-to-Physical Block Table Mapping, Sequence Packing Block-Diagonal Causal Mask, SFT Masked Causal LM Loss, Reference-Free SimPO Loss, RLHF `k1/k2/k3` KL Estimators, Symmetric InfoNCE Contrastive Loss, 2-Way Tensor Parallel Column+Row MLP, Ring Attention Online Block Merge, and MoE Capacity Factor Token Routing.
  - **13 New LeetCode Hot100 Algorithm Problems (`800` total in track)**: LC 49, 128, 283, 11, 3, 438, 560, 76, 56, 240, 958, 416, 75 with invariant-driven reference solutions.
  - **17 New LLM Evaluation, Systems & Frontier Knowledge Problems (`720` total in track)**: Perplexity & bits-per-byte, MMLU/GSM8K/HumanEval/`pass@k`, LLM-as-Judge bias & calibration, Hallucination taxonomy & NLI detection, Lost in the Middle, Paired Bootstrap & McNemar significance testing, Data decontamination & reproducible eval reports, GPU training/inference KV memory math, vLLM/SGLang/TGI serving comparison, Prefill/Decode (P/D) disaggregation, FLOPs & cost per 1M tokens, Prefix Caching & RadixAttention, Roofline arithmetic intensity & TTFT/TPOT tradeoffs, Diffusion LLMs, State Space Models (Mamba), Inference-time Scaling (`o1` / `DeepSeek-R1`), and Fine-Grained / Shared-Expert MoE (`DeepSeek-V2/V3`).
- **3 New Advanced Interview Training Perspectives (`data/variant_templates.json`)**:
  - `debug` (**故障排查**): Silent bug hunting in PyTorch shapes/masks/precision, minimal 3-element counterexamples for algorithms, and root-cause ablation paths for system anomalies.
  - `tradeoff` (**方案对比**): Arithmetic intensity, memory bandwidth, and engineering complexity comparison with concrete switching thresholds.
  - `scale` (**规模扩展**): 128K+ context & multi-node TP/SP/CP/EP/ZeRO scaling for AI Infra, external/streaming scaling for algorithms, and 100x scale bottleneck shifts for LLM systems.
- **End-to-End User Experience Enhancements**:
  - Filter-aware problem queue navigation (`← 上一题` / `下一题 →` / `随机一题` + `Alt + ←/→` shortcuts) with persisted filter state across pages.
  - In-place editing for user-created custom interview questions (`PUT /api/custom-problems`).
  - 1-click offline self-grading (`✓ 已掌握` / `~ 待巩固` / `↻ 需重试`) and copy-to-clipboard inside the reference answer drawer.
  - Practice history JSON export & import merge on the Completed archive page.
