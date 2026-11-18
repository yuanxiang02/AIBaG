# AIBaG

本地运行的 AI 面试练习工具：1,000 道 AI Infra、简答八股和力扣手撕题，支持 AI Review、多轮追问、标准答案与本机练习记录。

## 一键启动

第一次使用只需配置一次 API：

```bash
cp .env.example .env
```

在 `.env` 填入 `AIBAG_API_KEY`，之后每次直接运行：

```bash
./start.sh
```

脚本会启动本地服务并尝试打开 <http://127.0.0.1:8787>。项目只依赖 Python 3 标准库。

后端对题库启动加载设置了 5 秒硬上限；超过上限会拒绝启动，而不是带着未完成的数据继续运行。实际耗时可在 `/api/health` 查看。

## 题库与来源

- 200 道基础题保存在 [`data/catalog/`](data/catalog/)。
- 4 组训练视角保存在 [`data/variant_templates.json`](data/variant_templates.json)，运行时组合为 1,000 道稳定题目。
- 题库部分改编自 MIT 许可的 [axiaoquan/llm-interview-handbook](https://github.com/axiaoquan/llm-interview-handbook)，上游 commit 为 `8a86e722dcdb77de472daefa9401a859deb96f63`。
- 版权与许可证见 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) 和 [`third_party/llm-interview-handbook-LICENSE`](third_party/llm-interview-handbook-LICENSE)。

API Key 只从本机 `.env` 或私有凭据文件读取，不会通过浏览器接口返回或提交到仓库。

## 测试

```bash
python3 -m unittest discover -s tests -v
```
