# AIBaG 社区分享与多平台推广文案

以下文案专为不同技术社区与社交平台量身定制，可直接复制发布以扩大项目影响力。

---

## 1. 小红书 / 即刻（视觉痛点向 · 适合配 README 三张截图）

**标题备选：**
1. 肝了几个通宵，我把 2000 道大模型与 AI Infra 手撕八股做成了本地面试训练场！
2. 别再死背静态八股 PDF 了！开源一个零依赖的大模型白板面试神器 AIBaG 🔥
3. 秋招/社招大模型算法岗突击：480 道 AI Infra 手撕 + 720 道系统八股 + 800 道力扣

**正文：**
准备大模型算法 / AI Infra / 推理系统面试时，你是不是也有这几个痛点：
❌ 静态八股文背了一遍又一遍，面试官追问一句“为什么这样设计？边界在哪？”当场卡壳
❌ 刷了力扣，但面试官让你白板手撕 GQA、RoPE、DeepSeek MLA、FlashAttention Online Softmax、KV Cache INT8 量化、投机采样、SimPO Loss 时无从下手
❌ 每次面完复盘的面经散落在备忘录里，下次面试前根本找不到

所以我开源了 **AIBaG (Algorithm & AI Interview Lab)** v2.0 —— 一个零第三方依赖、本地优先的 AI 面试与算法训练工作台！

✨ **核心亮点：**
1️⃣ **2,000 道结构化题库，覆盖三大核心赛道**
- **AI Infra 手撕算子（480 题）**：MHA / GQA / MQA / MLA、RoPE、RMSNorm、KV Cache 量化、PagedAttention、投机采样、Ring Attention、TP 切分、MoE Top-2 / Capacity 路由、DPO / GRPO / SimPO Loss 全覆盖
- **大模型全栈八股（720 题）**：从架构、ZeRO/TP/PP/EP 分布式训练、vLLM/SGLang/P-D 分离推理、显存与 Roofline 手算，到评测去污染、Mamba、Diffusion LLM、DeepSeek-R1 测试时扩展
- **力扣高频手撕（800 题）**：聚焦 Hot100 与大厂面试变体，死磕循环不变量与边界分析

2️⃣ **8 大真实面试追问视角**
每道母题不仅有基础标准题，还支持从「边界诊断、复杂度优化、原理证明、场景迁移、静默 Bug 故障排查、方案对比、分布式规模扩展」8 个维度训练，彻底告别死记硬背。

3️⃣ **毫秒级持久化标准答案 + AI 面试官多轮追问**
- 不配 API Key 也能完全离线使用：2,000 道题全部内置即时标准答案与代码实现，支持一键自评掌握度（已掌握 / 待巩固 / 需重试）
- 配置 DeepSeek / OpenAI 兼容 Key 后，即可开启 AI 面试官结构化诊断（Pass / Partial / Retry）与苏格拉底式追问

4️⃣ **个人自建面经闭环**
面试遇到新题？一键录入或 JSON 批量导入本地题库，随时在线编辑复盘，数据完全保存在本机！

🚀 **30 秒极速启动（仅需 Python 3 标准库，无需装任何 pip/npm 包）：**
`git clone https://github.com/yuanxiang02/AIBaG.git && cd AIBaG && ./start.sh`

项目采用 MIT 协议完全开源，求一个 Star ⭐ 支持！
🔗 GitHub：`https://github.com/yuanxiang02/AIBaG`

#大模型面试 #AIInfra #算法岗秋招 #深度学习手撕代码 #LLM面试 #开源项目 #PyTorch #DeepSeek

---

## 2. 知乎 / 微信公众号（深度技术复盘向）

**标题：**
开源 AIBaG v2.0：内置 2,000 道 AI Infra 算子手撕、LLM 系统八股与算法题的本地白板面试训练场（零依赖 / MIT 协议）

**正文摘要：**
在大模型与 AI Infra 岗位面试中，“能看懂论文公式”和“能在 15 分钟白板上手撕出数值稳定、维度对齐的 PyTorch 核心代码并顶住三轮追问”之间存在巨大鸿沟。

为此，我开发并开源了 **AIBaG (Algorithm & AI Interview Lab)**，并在今天发布了 **v2.0.0**：
- **题库扩充至 2,000 题**：涵盖 **480 道 AI Infra 核心算子手撕**（MHA/GQA/MLA、Online Softmax、PagedAttention、投机采样、Ring Attention、TP/MoE、DPO/GRPO/SimPO）、**720 道大模型系统与前沿问答**（显存精确手算、P/D 分离、Roofline 算术强度、Paired Bootstrap 置信区间、DeepSeek-R1/V3 架构）以及 **800 道经典算法手撕**。
- **八维追问训练矩阵**：除基础实现外，每道题均覆盖边界诊断、复杂度优化、原理证明、场景迁移、故障排查、方案对比、规模扩展 7 大进阶追问视角。
- **零依赖 + 本地优先**：纯 Python 3 标准库 + 原生前端实现，冷启动加载 2,000 题仅需 20ms；所有题目内置持久化标准答案，支持无 API Key 离线自习，也支持接入 DeepSeek 等模型进行 PE（掌握度状态机）多轮追问。

仓库地址：https://github.com/yuanxiang02/AIBaG （MIT License）

---

## 3. V2EX（简洁极客向 · 适合发 `/go/create` 或 `/go/python`）

**标题：**
[开源] AIBaG v2.0：零依赖、本地优先的 AI Infra / LLM 算法面试白板训练工作台（内置 2,000 题与即时答案）

**正文：**
大家好，分享一个我做的开源本地工具 **AIBaG**（MIT License）：
https://github.com/yuanxiang02/AIBaG

### 解决什么问题？
现在面大模型 / AI Infra / 算法岗，除了常规 LeetCode，面试官越来越喜欢考察：
1. **PyTorch 核心算子手撕**：比如不调库写 GQA/MQA、DeepSeek MLA 低秩投影、FlashAttention Online Softmax、KV Cache INT8 量化、Speculative Decoding 拒绝采样、DPO/GRPO/SimPO Loss、Megatron TP 切分等。
2. **系统算账与深度追问**：给定 7B/70B 模型手算训练/推理 KV 显存、Roofline 算术强度、P/D 分离代价、评测配对置信区间等。

只看静态 Markdown 很容易“以为自己会了，一上手写 shape 就错”。AIBaG 把这些高频考点做成了本地交互式白板工作台：
- **内置 2,000 道结构化练习题**：250 道精选母题（60 AI Infra + 90 LLM/系统问答 + 100 经典算法）× 8 个面试考察视角（基础 / 边界 / 优化 / 证明 / 迁移 / 排障 / 对比 / 扩展）。
- **零依赖，开箱即用**：后端仅用 Python 3 标准库（`http.server`），前端原生 ES Module，无需 `pip install` 或 `npm install`，`./start.sh` 秒开。
- **离线可用 + AI 面试官可选**：2,000 道题全部内置持久化参考答案（点开即看，零 Token 消耗），支持离线标记掌握度；配好 DeepSeek / OpenAI API Key 后可做白板静态评审与多轮追问。
- **支持私有面经管理**：随时在页面录入、编辑或通过 JSON 导入自己的面经，保存在本地 `data/custom_problems.json`。

欢迎正在准备 AI / 算法面试的朋友试用、提 Issue 或 PR！

---

## 4. X (Twitter) / English Community

**Post:**
Just released **AIBaG v2.0** — a zero-dependency, local-first AI Infra & LLM interview workbench! 🚀

🧠 **2,000 structured exercises** across 3 tracks:
• 480 AI Infra whiteboard coding (MHA/GQA/MLA, Online Softmax, KV INT8 quant, PagedAttention, Speculative Decoding, RingAttn, TP/MoE, DPO/GRPO/SimPO)
• 720 LLM systems, eval & frontier Q&A (VRAM math, P/D disaggregation, Roofline, Mamba, DeepSeek-R1/V3)
• 800 Algorithmic coding exercises

⚡ **Why AIBaG?**
• Pure Python 3 stdlib — zero `pip` or `npm` dependencies, starts in <30ms
• Instant persisted reference answers for all 2,000 questions (works 100% offline!)
• Optional AI Interviewer (OpenAI/DeepSeek compatible) for whiteboard diagnostics & multi-turn probing
• Built-in Custom Interview Bank with JSON import/export
• MIT Licensed

Try it in 30s:
🔗 https://github.com/yuanxiang02/AIBaG
