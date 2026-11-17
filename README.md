# AIBaG

AIBaG 是一个本地优先的算法与 AI Infra 面试训练场。产品采用两级页面：

1. **题库首页 `/index.html`**：像 LeetCode 一样浏览、筛选题目和查看练习状态。
2. **独立题目页 `/problem.html?id=...`**：点击题目后发生真实页面跳转，左侧题面，右侧代码编辑器和 DeepSeek 面试官对话。

当前 Review 只关注核心实现、tensor shape、算法不变量、边界条件和复杂度，不要求候选人写出唯一标准答案。口语化解释、朴素变量名或不够标准的术语不会单独扣分，只要表达的意思和实现成立即可。

所有题目默认采用白板面试模式：候选人不能运行代码、打印中间结果或使用 debugger；面试官只能引导其静态推导 shape、边界条件、算法不变量和复杂度。

## 当前题库

题目持久化在 [`data/problems.json`](data/problems.json)：

1. 从零实现多头自注意力（MHA）
2. 实现 Rotary Position Embedding（RoPE）
3. 实现稳定归并排序
4. 原地三路快速排序
5. 出现频率最高的 K 个元素

每道题包含题面、示例、约束、starter code、隐藏 review points、分层提示及来源说明。浏览器接口不会返回隐藏评分点和提示。

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
python3 -m json.tool data/problems.json >/dev/null
```

单元测试不会调用外部模型 API。当前“提交”是 AI Review，不执行用户代码；后续如需确定性 Accepted/Rejected，应增加隔离测试执行器。
