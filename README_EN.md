# AIBaG · Local-First AI Infra & LLM Interview Lab

<p align="left">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-0f766e.svg" alt="MIT License"></a>
  <a href="https://github.com/yuanxiang02/AIBaG/releases"><img src="https://img.shields.io/badge/Release-v2.0.0-1d4ed8.svg" alt="Release v2.0.0"></a>
  <img src="https://img.shields.io/badge/Problems-2%2C000-b45309.svg" alt="2,000 Problems">
  <img src="https://img.shields.io/badge/Python-3.10%2B%20Stdlib-374151.svg" alt="Python 3 Stdlib Only">
  <img src="https://img.shields.io/badge/Dependencies-Zero-059669.svg" alt="Zero Dependencies">
</p>

[简体中文](README.md) | **English** · [Changelog](CHANGELOG.md)

**AIBaG (Algorithm & AI Interview Lab)** is a zero-dependency, local-first AI interview workbench with **2,000 structured exercises** across **AI Infrastructure (`480`)**, **LLM/ML System & Theory Q&A (`720`)**, and **Algorithmic Coding (`800`)**.

## What it does

- **3 Core Tracks (`2,000` Problems)**:
  - **AI Infra (`480`)**: MHA, GQA, MQA, DeepSeek MLA, FlashAttention Online Softmax, RoPE, KV Cache INT8 quantization, PagedAttention, Speculative Decoding, Ring Attention, TP/MoE routing, DPO/GRPO/SimPO losses.
  - **LLM & System Knowledge (`720`)**: Pre-training, distributed systems (ZeRO/TP/PP/EP/P-D disaggregation), Roofline arithmetic intensity, alignment, RAG/Agent, evaluation de-contamination, and frontier architectures (Mamba, Diffusion LLM, Inference-time Scaling).
  - **Algorithmic Coding (`800`)**: Data structures, LeetCode Hot100, and real-world whiteboard variants.
- **8 Interview Perspectives**: 250 canonical base problems expand into 2,000 traceable exercises across *Base Implementation, Boundary Diagnosis, Complexity & Optimization, Proof & Invariants, Scenario Migration, Silent Bug Debugging, Tradeoff Comparison,* and *Distributed Scaling*.
- **Adaptive AI Interviewer + Offline Self-Grading**: Get structured evaluation (`Pass` / `Partial` / `Retry`) and multi-turn follow-ups with an OpenAI-compatible API key, or practice completely offline using instant persisted reference answers and 1-click self-grading.
- **Custom Interview Bank**: Add, edit, import, and export your own interview questions locally (`data/custom_problems.json`).

## Quick start

Configure the API once:

```bash
cp .env.example .env
```

Add `AIBAG_API_KEY` to `.env`, then run:

```bash
./start.sh
```

The script starts the service and opens <http://127.0.0.1:8787>. Only Python 3 is required.

## Data and attribution

- Released under the **[MIT License](LICENSE)**.
- 250 canonical questions live in [`data/catalog/`](data/catalog/) (`part-001.json` – `part-005.json`).
- Seven structured interview variant templates in [`data/variant_templates.json`](data/variant_templates.json) expand them into 2,000 stable exercises in under 50ms at startup.
- Persisted answers live in [`data/answers.json`](data/answers.json); revealing an answer does not call the model.
- Part of the catalog is adapted from [axiaoquan/llm-interview-handbook](https://github.com/axiaoquan/llm-interview-handbook) under the MIT License. See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

API keys stay in the local `.env` or private credential file and are never returned to the browser or committed.

## Test

```bash
python3 -m unittest discover -s tests -v
```
