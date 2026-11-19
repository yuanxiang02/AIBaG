# Third-party notices

## LLM Interview Handbook

部分题目、易错点与追问思路改编自：

- Project: [axiaoquan/llm-interview-handbook](https://github.com/axiaoquan/llm-interview-handbook)
- Description: 大模型算法面试手册（八股 + 手撕）
- Copyright: Copyright (c) 2026 axiaoquan
- License: MIT
- Local license copy: [`third_party/llm-interview-handbook-LICENSE`](third_party/llm-interview-handbook-LICENSE)

AIBaG 将相关内容转换为 JSON 题库、白板面试 starter code、隐藏 review points 与多轮提示。题面可能经过压缩、重写或拆分；每道直接改编的题目会在 `data/catalog/*.json` 的 `sources` 与 `provenance` 字段中记录具体上游章节、commit、更新时间和导入日期。

运行时的 2,000 道题由 250 道基础题（210 道整理自上游手册 + 40 道 AIBaG 自编精选）与 7 组 AIBaG 自有训练视角（边界诊断、复杂度优化、原理证明、场景迁移、故障排查、方案对比、规模扩展）组合而成。派生题会保留基础题来源，并通过 `provenance.origin = aibag-derived`、`derived_from` 和 `variant` 明确标识，不表示上游仓库原生包含 2,000 道独立题目。

`data/answers.json` 中直接抽取或整理自上游章节的标准答案继续适用同一 MIT 许可与归属说明；AIBaG 自行编写的补充实现会标记为 `aibag-authored`。

本说明不表示上游作者认可、维护或参与 AIBaG。
