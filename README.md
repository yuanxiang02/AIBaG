# AIBaG

AIBaG 是一个本地优先的算法与 AI Infra 面试训练场。产品采用两级页面：

1. **题库首页 `/index.html`**：像 LeetCode 一样浏览、筛选题目和查看练习状态。
2. **独立题目页 `/problem.html?id=...`**：点击题目后发生真实页面跳转，左侧题面，右侧代码编辑器和 DeepSeek 面试官对话。

当前 Review 只关注核心实现、tensor shape、算法不变量、边界条件和复杂度，不要求候选人写出唯一标准答案。口语化解释、朴素变量名或不够标准的术语不会单独扣分，只要表达的意思和实现成立即可。

所有题目默认采用白板面试模式：候选人不能运行代码、打印中间结果或使用 debugger；面试官只能引导其静态推导 shape、边界条件、算法不变量和复杂度。

## 当前题库

运行时题库持久化在 [`data/catalog/`](data/catalog/)，当前首批共 200 道，按 50 道一个 JSON 分片：

- **LLM / AI Infra 手撕（40 道）**：Attention、位置编码、归一化、Tokenizer、解码、PEFT、Loss / RL 与 MoE 等。
- **经典算法（87 道）**：数组、链表、哈希、字符串、树、回溯、单调栈、动态规划与面试真题等。
- **知识问答（73 道）**：基础、架构、训练、微调、对齐、推理、RAG、Agent、多模态等。

每道题包含 `kind`、题面、分类、starter code、隐藏 review points、追问、来源、许可证与导入版本。浏览器接口不会返回隐藏评分点、参考说明和预设追问。知识题进入独立题目页后会自动切换到口头回答模式。

## 题库来源与致谢

题库扩展部分改编自 MIT 许可的 [axiaoquan/llm-interview-handbook](https://github.com/axiaoquan/llm-interview-handbook)。AIBaG 将其转换为适合本项目的 JSON、白板代码题和多轮 AI 面试格式；具体章节记录在每道题的 `sources` 与 `provenance` 字段中。上游 revision 固定为 `8a86e722dcdb77de472daefa9401a859deb96f63`，完整版权与许可证说明见 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) 和 [`third_party/llm-interview-handbook-LICENSE`](third_party/llm-interview-handbook-LICENSE)。原始 20 道精编种子仍保存在 [`data/problems.json`](data/problems.json)，用于可重复生成完整分片。

导入器位于 [`scripts/import_handbook.py`](scripts/import_handbook.py)。它从固定上游 checkout 解析题目，过滤模板，补齐三类统一 schema，并按指定分片确定性输出 JSON；不会在运行服务时联网抓取。

## 启动

项目只依赖 Python 3 标准库：

```bash
git clone https://github.com/yuanxiang02/AIBaG.git
cd AIBaG
cp .env.example .env
python3 server.py
```

浏览器打开 <http://127.0.0.1:8787>。

## DeepSeek 配置

默认使用 DeepSeek 的 OpenAI-compatible API：

```dotenv
AIBAG_API_KEY=your-private-key
AIBAG_BASE_URL=https://api.deepseek.com
AIBAG_MODEL=deepseek-flash
AIBAG_PORT=8787
```

如果密钥保存在本机私有 Markdown 中，可以不复制密钥，只配置文件路径：

```dotenv
AIBAG_CREDENTIAL_DOC=/absolute/path/to/private-note.md
```

私有文档需要包含单独一行 `key:YOUR_KEY`。后端在运行时读取，`/api/config` 只返回 `has_api_key` 布尔值。`.env`、密钥、文档路径均不应提交。

## 两条 AI 链路

- `POST /api/judge`：输入 `problem_id + code`，内部保留 `pass / partial / retry` 用于进度，但界面展示自然语言面试反馈。
- `POST /api/chat`：像真人面试官一样提供一层提示、一个优化方向、继续追问或自由对话。

提示词位于：

- [`prompts/judge.txt`](prompts/judge.txt)
- [`prompts/coach.txt`](prompts/coach.txt)

## API

| Endpoint | Method | 用途 |
|---|---|---|
| `/api/problems` | GET | 获取公开题面与 starter code |
| `/api/config` | GET | 获取不含密钥的模型配置摘要 |
| `/api/health` | GET | 本地服务健康检查 |
| `/api/judge` | POST | 对代码进行核心实现 Review |
| `/api/chat` | POST | 提示、优化建议与多轮追问 |

## 安全边界

本地 HTTP 服务采用静态文件白名单，只允许访问两个 HTML 页面、各自的 JavaScript 和 `style.css`。以下内容无法通过浏览器静态 URL 读取：

- `.env` 与 API Key
- 私有凭据文档
- 后端源码和提示词
- JSON 中的隐藏 review points、参考说明与提示

## 测试

```bash
python3 -m unittest discover -s tests -v
node --check app.js
node --check problem.js
for file in data/catalog/*.json; do python3 -m json.tool "$file" >/dev/null; done
```

单元测试不会调用外部模型 API。当前“提交”是 AI Review，不执行用户代码；后续如需确定性 Accepted/Rejected，应增加隔离测试执行器。
