# AIBaG

AIBaG 是一个本地优先的 AI 面试助手。它不要求候选人背出完整标准答案，而是判断回答是否解释了核心思路，并通过短提示、优化建议和追问完成多轮练习。

当前 MVP 包含两条独立链路：

1. **Core Judge**：基于题库中的核心评分点，返回 `pass / partial / retry`、已覆盖内容和少量关键缺口。
2. **Interview Coach**：围绕同一道题提供一层提示、一个优化方向，或者继续追问一个问题。

## 快速开始

项目只依赖 Python 3 标准库。

```bash
git clone https://github.com/yuanxiang02/AIBaG.git
cd AIBaG
cp .env.example .env
```

编辑 `.env`，配置一个 OpenAI-compatible Chat Completions API：

```dotenv
AIBAG_API_KEY=your-api-key
AIBAG_BASE_URL=https://api.openai.com/v1
AIBAG_MODEL=gpt-4o-mini
AIBAG_PORT=8787
```

启动：

```bash
python3 server.py
```

浏览器打开 <http://127.0.0.1:8787>。

也可以连接本地 Ollama 等兼容服务：

```dotenv
AIBAG_API_KEY=ollama
AIBAG_BASE_URL=http://127.0.0.1:11434/v1
AIBAG_MODEL=qwen3:8b
```

> API Key 仅由本地 Python 后端读取，不会发送给浏览器，也不要提交 `.env`。

## 使用流程

1. 从左侧题库选择题目。
2. 用自己的话解释核心思路，点击“提交并判断”。
3. 查看核心点覆盖、关键缺口和下一步建议。
4. 选择“给我一点提示”“哪里还能优化”或“继续追问我”。
5. 在输入框继续回答；需要重新判分时再次点击“提交并判断”。

练习结果仅保存在浏览器 `localStorage`，当前版本没有账号和数据库。

## 题库格式

题库位于 [`data/questions.json`](data/questions.json)。浏览器只能获取公开题面；`core_points` 和 `reference_outline` 只在后端评审时使用。

```json
{
  "id": "rag-evaluation",
  "type": "scenario",
  "topic": "RAG",
  "difficulty": "medium",
  "question": "如何评估一个 RAG 系统？",
  "tags": ["RAG", "Evaluation"],
  "core_points": [
    {
      "label": "分阶段评估",
      "required": true,
      "description": "区分检索、生成和端到端效果"
    }
  ],
  "reference_outline": ["retrieval eval", "generation eval", "人工校准"]
}
```

`required: true` 表示面试中应覆盖的核心点。题库应优先写“判断标准”，而不是堆砌完整答案。

## API

| Endpoint | Method | 用途 |
|---|---|---|
| `/api/questions` | GET | 获取不含评分标准的公开题库 |
| `/api/config` | GET | 获取不含密钥的模型配置摘要 |
| `/api/health` | GET | 本地服务健康检查 |
| `/api/judge` | POST | 对候选人答案进行核心思路判断 |
| `/api/chat` | POST | 提示、优化建议、继续追问或自由对话 |

两套提示词分别位于 [`prompts/judge.txt`](prompts/judge.txt) 和 [`prompts/coach.txt`](prompts/coach.txt)，可以独立迭代。

## 项目结构

```text
AIBaG/
├── index.html
├── app.js
├── style.css
├── server.py
├── data/questions.json
├── prompts/
│   ├── judge.txt
│   └── coach.txt
└── tests/test_server.py
```

## 测试

```bash
python3 -m unittest discover -s tests -v
```

单元测试不会调用外部模型 API。

## MVP 边界

当前版本刻意不包含账号、数据库、语音、RAG、多 Agent 和代码沙箱。后续的 vibe coding 判题需要可重复运行的测试或隔离沙箱；在此之前，LLM 对代码的结论只应标记为 review，而不是确定性的 pass/fail。
