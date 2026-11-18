#!/usr/bin/env python3
"""AIBaG local web server and OpenAI-compatible API proxy."""

from __future__ import annotations

import json
import os
import re
import sys
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
PROBLEMS_PATH = ROOT / "data" / "problems.json"
CATALOG_DIR = ROOT / "data" / "catalog"
MAX_REQUEST_BYTES = 1_000_000
INTERVIEW_MODE = {
    "code_execution": False,
    "debugger": False,
    "runtime_prints": False,
    "instruction": "Whiteboard interview: reason statically from shapes, invariants, boundaries, and complexity.",
}


def load_dotenv(path: Path) -> None:
    """Load a small KEY=VALUE .env file without overriding real env vars."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"").strip("'")
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            os.environ.setdefault(key, value)


load_dotenv(ROOT / ".env")


def load_problems() -> list[dict[str, Any]]:
    paths = sorted(CATALOG_DIR.glob("part-*.json"))
    if not paths:
        paths = [PROBLEMS_PATH]
    problems: list[dict[str, Any]] = []
    for path in paths:
        shard = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(shard, list):
            raise ValueError(f"{path.relative_to(ROOT)} must contain a JSON array")
        problems.extend(shard)
    required = {
        "id",
        "number",
        "kind",
        "title",
        "category",
        "topic",
        "difficulty",
        "description",
        "starter_code",
        "review_points",
        "review_dimensions",
        "follow_ups",
        "sources",
        "license",
        "provenance",
    }
    seen: set[str] = set()
    for problem in problems:
        missing = required - set(problem)
        if missing:
            raise ValueError(f"Problem is missing fields: {sorted(missing)}")
        if problem["id"] in seen:
            raise ValueError(f"Duplicate problem id: {problem['id']}")
        seen.add(problem["id"])
    numbers = [problem["number"] for problem in problems]
    if numbers != list(range(1, len(problems) + 1)):
        raise ValueError("Problem numbers must be consecutive and ordered from 1")
    return problems


PROBLEMS = load_problems()
PROBLEM_INDEX = {problem["id"]: problem for problem in PROBLEMS}
ANSWER_CACHE: dict[str, dict[str, str]] = {}


def public_problem(problem: dict[str, Any]) -> dict[str, Any]:
    """Return the problem statement without hidden review points or reference notes."""
    hidden = {"review_points", "review_dimensions", "reference_notes", "hints", "follow_ups"}
    return {key: value for key, value in problem.items() if key not in hidden}


def resolve_api_key() -> str:
    """Resolve a key from the environment or a private local credential note."""
    direct = os.getenv("AIBAG_API_KEY", "").strip()
    if direct:
        return direct
    credential_doc = os.getenv("AIBAG_CREDENTIAL_DOC", "").strip()
    if not credential_doc:
        return ""
    doc_path = Path(credential_doc).expanduser()
    if not doc_path.is_file():
        return ""
    content = doc_path.read_text(encoding="utf-8")
    match = re.search(r"(?im)^\s*key\s*:\s*([^\s`]+)\s*$", content)
    return match.group(1).strip() if match else ""


def api_config() -> dict[str, Any]:
    return {
        "model": os.getenv("AIBAG_MODEL", "deepseek-flash"),
        "base_url": os.getenv("AIBAG_BASE_URL", "https://api.deepseek.com"),
        "has_api_key": bool(resolve_api_key()),
    }


def extract_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, count=1)
        text = re.sub(r"\s*```$", "", text, count=1)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("Model did not return a JSON object") from None
        parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("Model response must be a JSON object")
    return parsed


def parse_model_content(content: str, plain_text_key: str | None = None) -> dict[str, Any]:
    """Parse structured output, optionally accepting natural-language text."""
    try:
        return extract_json_object(content)
    except (ValueError, json.JSONDecodeError):
        text = content.strip()
        if plain_text_key and text:
            text = re.sub(r"^```(?:text|markdown)?\s*", "", text, count=1)
            text = re.sub(r"\s*```$", "", text, count=1)
            return {plain_text_key: text.strip()}
        raise


def call_llm(
    messages: list[dict[str, str]], plain_text_key: str | None = None
) -> dict[str, Any]:
    base_url = os.getenv("AIBAG_BASE_URL", "https://api.deepseek.com").rstrip("/")
    is_deepseek = urlsplit(base_url).hostname in {"api.deepseek.com", "api.deepseek.com.cn"}
    model = os.getenv("AIBAG_MODEL", "deepseek-flash")
    api_key = resolve_api_key()
    endpoint = f"{base_url}/chat/completions"
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }

    def make_request(body: dict[str, Any]) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        request = Request(
            endpoint,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urlopen(request, timeout=90) as response:
            return json.loads(response.read().decode("utf-8"))

    def request_with_json_mode(body: dict[str, Any]) -> dict[str, Any]:
        try:
            return make_request(body)
        except HTTPError as error:
            # DeepSeek supports json_object mode, so never silently downgrade it.
            # A custom OpenAI-compatible endpoint may still need the old fallback.
            if error.code != HTTPStatus.BAD_REQUEST or is_deepseek:
                raise
            fallback = dict(body)
            fallback.pop("response_format", None)
            return make_request(fallback)

    try:
        response = request_with_json_mode(payload)
    except HTTPError as error:
        detail = error.read(2_000).decode("utf-8", errors="replace")
        raise RuntimeError(f"Model API returned HTTP {error.code}: {detail}") from None
    except URLError as error:
        raise RuntimeError(f"Cannot reach model API: {error.reason}") from None

    def response_content(response_data: dict[str, Any]) -> str:
        try:
            return str(response_data["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError):
            raise RuntimeError(
                "Model API response does not contain choices[0].message.content"
            ) from None

    content = response_content(response)
    try:
        return parse_model_content(content, plain_text_key=plain_text_key)
    except (ValueError, json.JSONDecodeError):
        # Structured judge/answer calls get one strict repair attempt. Chat still
        # accepts plain text so a conversational reply never breaks the UI.
        retry = dict(payload)
        retry["temperature"] = 0
        retry["messages"] = [
            *messages,
            {
                "role": "user",
                "content": "上一条输出不是合法 JSON。请重新回答，只输出一个可被 json.loads 解析的 JSON object，不要 Markdown。",
            },
        ]
        try:
            repaired = request_with_json_mode(retry)
        except HTTPError as error:
            detail = error.read(2_000).decode("utf-8", errors="replace")
            raise RuntimeError(f"Model API returned HTTP {error.code}: {detail}") from None
        except URLError as error:
            raise RuntimeError(f"Cannot reach model API: {error.reason}") from None
        repaired_content = response_content(repaired)
        try:
            return parse_model_content(repaired_content, plain_text_key=plain_text_key)
        except (ValueError, json.JSONDecodeError):
            raise RuntimeError("Model returned invalid JSON twice; please try again") from None


def as_short_list(value: Any, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value[:limit]:
        if isinstance(item, str) and item.strip():
            result.append(item.strip()[:500])
    return result


def normalize_review(raw: dict[str, Any]) -> dict[str, Any]:
    verdict = raw.get("verdict", "partial")
    if verdict not in {"pass", "partial", "retry"}:
        verdict = "partial"
    try:
        score = max(0, min(100, int(raw.get("score", 0))))
    except (TypeError, ValueError):
        score = 0
    return {
        "verdict": verdict,
        "score": score,
        "interviewer_response": str(
            raw.get("interviewer_response", raw.get("summary", "我看过你的实现了，我们接着聊最关键的一点。"))
        )[:1_000],
        "strengths": as_short_list(raw.get("strengths", raw.get("covered")), 2),
        "focus_issue": str(raw.get("focus_issue", ""))[:500],
        "nudge": str(raw.get("nudge", raw.get("next_focus", "")))[:500],
        "follow_up": str(raw.get("follow_up", raw.get("interviewer_follow_up", "")))[:500],
    }


def judge_code(problem: dict[str, Any], code: str) -> dict[str, Any]:
    system = (ROOT / "prompts" / "judge.txt").read_text(encoding="utf-8")
    context = {
        "interview_mode": INTERVIEW_MODE,
        "kind": problem["kind"],
        "title": problem["title"],
        "description": problem["description"],
        "constraints": problem.get("constraints", []),
        "review_points": problem["review_points"],
        "reference_notes": problem.get("reference_notes", []),
        "candidate_submission": code,
    }
    raw = call_llm(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
        ]
    )
    return normalize_review(raw)


def coach_reply(problem: dict[str, Any], payload: dict[str, Any]) -> dict[str, str]:
    system = (ROOT / "prompts" / "coach.txt").read_text(encoding="utf-8")
    action = str(payload.get("action", "chat"))
    if action not in {"hint", "optimize", "follow_up", "chat"}:
        action = "chat"
    history = payload.get("history", [])
    if not isinstance(history, list):
        history = []
    safe_history = []
    for turn in history[-8:]:
        if isinstance(turn, dict) and turn.get("role") in {"user", "assistant"}:
            safe_history.append(
                {"role": turn["role"], "content": str(turn.get("content", ""))[:2_000]}
            )
    context = {
        "interview_mode": INTERVIEW_MODE,
        "kind": problem["kind"],
        "action": action,
        "title": problem["title"],
        "description": problem["description"],
        "review_points": problem["review_points"],
        "hints": problem.get("hints", []),
        "candidate_submission": str(payload.get("code", ""))[:16_000],
        "latest_review": payload.get("review", {}),
        "candidate_message": str(payload.get("message", ""))[:2_000],
        "conversation": safe_history,
    }
    raw = call_llm(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
        ],
        plain_text_key="reply",
    )
    return {
        "action": action,
        "reply": str(raw.get("reply", "我们先聚焦一个最关键的知识点。"))[:1_500],
        "focus": str(raw.get("focus", ""))[:500],
    }


def reference_answer(problem: dict[str, Any]) -> dict[str, str]:
    """Generate and cache an explicitly revealed reference answer."""
    cached = ANSWER_CACHE.get(problem["id"])
    if cached is not None:
        return cached
    system = (ROOT / "prompts" / "answer.txt").read_text(encoding="utf-8")
    context = {
        "interview_mode": INTERVIEW_MODE,
        "kind": problem["kind"],
        "title": problem["title"],
        "description": problem["description"],
        "constraints": problem.get("constraints", []),
        "starter_code": problem.get("starter_code", ""),
        "review_points": problem["review_points"],
        "reference_notes": problem.get("reference_notes", []),
    }
    raw = call_llm(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
        ]
    )
    answer = str(raw.get("answer", "")).strip()
    if len(answer) < 20:
        raise RuntimeError("Model did not return a usable reference answer")
    result = {"answer": answer[:16_000], "source": "deepseek-generated"}
    ANSWER_CACHE[problem["id"]] = result
    return result


class AIBaGHandler(SimpleHTTPRequestHandler):
    server_version = "AIBaG/0.1"
    STATIC_PATHS = {
        "/",
        "/index.html",
        "/app.js",
        "/problem.html",
        "/problem.js",
        "/style.css",
    }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def send_json(self, data: Any, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValueError("Invalid Content-Length") from None
        if length <= 0 or length > MAX_REQUEST_BYTES:
            raise ValueError("Request body is empty or too large")
        data = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Request body must be a JSON object")
        return data

    def do_GET(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        if path == "/api/health":
            self.send_json({"ok": True, "problems": len(PROBLEMS), **api_config()})
            return
        if path == "/api/config":
            self.send_json(api_config())
            return
        if path == "/api/problems":
            self.send_json([public_problem(problem) for problem in PROBLEMS])
            return
        if path not in self.STATIC_PATHS:
            self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return
        super().do_GET()

    def do_HEAD(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        if path not in self.STATIC_PATHS:
            self.send_response(HTTPStatus.NOT_FOUND)
            self.end_headers()
            return
        super().do_HEAD()

    def do_POST(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        if path not in {"/api/judge", "/api/chat", "/api/answer"}:
            self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            payload = self.read_json()
            problem_id = str(payload.get("problem_id", ""))
            problem = PROBLEM_INDEX.get(problem_id)
            if problem is None:
                self.send_json({"error": "Unknown problem_id"}, HTTPStatus.NOT_FOUND)
                return
            if path == "/api/judge":
                code = str(payload.get("code", "")).strip()
                if len(code) < 8:
                    raise ValueError("Please provide an answer before submitting")
                result = judge_code(problem, code[:16_000])
            elif path == "/api/answer":
                result = reference_answer(problem)
            else:
                result = coach_reply(problem, payload)
            self.send_json(result)
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
        except RuntimeError as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_GATEWAY)
        except Exception as error:  # Keep the local server alive on unexpected provider output.
            print(f"Unexpected error: {error}", file=sys.stderr)
            self.send_json({"error": "Unexpected server error"}, HTTPStatus.INTERNAL_SERVER_ERROR)


def main() -> None:
    port = int(os.getenv("AIBAG_PORT", "8787"))
    server = ThreadingHTTPServer(("127.0.0.1", port), AIBaGHandler)
    print(f"AIBaG is running at http://127.0.0.1:{port}")
    print(f"Loaded {len(PROBLEMS)} problems; model: {api_config()['model']}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping AIBaG.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
