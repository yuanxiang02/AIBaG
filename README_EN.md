# AIBaG

[简体中文](README.md) | **English**

AIBaG is a local-first AI interview practice app with 1,000 questions across AI infrastructure, short-form ML/LLM knowledge, and coding interviews.

## What it does

- Practice AI Infra, knowledge Q&A, and LeetCode-style coding questions.
- Get adaptive hints and follow-ups after the interviewer evaluates your current understanding.
- Reveal an instant persisted answer for every question.
- Keep practice history locally in your browser.

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

- 200 canonical questions live in [`data/catalog/`](data/catalog/).
- Four structured interview variants expand them into 1,000 stable exercises.
- Persisted answers live in [`data/answers.json`](data/answers.json); revealing an answer does not call the model.
- Part of the catalog is adapted from [axiaoquan/llm-interview-handbook](https://github.com/axiaoquan/llm-interview-handbook) under the MIT License. See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

API keys stay in the local `.env` or private credential file and are never returned to the browser or committed.

## Test

```bash
python3 -m unittest discover -s tests -v
```
