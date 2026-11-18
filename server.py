#!/usr/bin/env python3
"""AIBaG local web server and OpenAI-compatible API proxy."""

from __future__ import annotations

import gzip
import json
import os
import re
import sys
import time
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
PROBLEMS_PATH = ROOT / "data" / "problems.json"
CATALOG_DIR = ROOT / "data" / "catalog"
VARIANTS_PATH = ROOT / "data" / "variant_templates.json"
MAX_REQUEST_BYTES = 1_000_000
CATALOG_LOAD_LIMIT_SECONDS = 5.0
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
CATALOG_BOOT_STARTED = time.perf_counter()


def enforce_catalog_deadline(stage: str) -> None:
    elapsed = time.perf_counter() - CATALOG_BOOT_STARTED
    if elapsed > CATALOG_LOAD_LIMIT_SECONDS:
        raise TimeoutError(
            f"Catalog loading exceeded {CATALOG_LOAD_LIMIT_SECONDS:.1f}s "
            f"during {stage} ({elapsed:.3f}s)"
        )


def load_problems() -> list[dict[str, Any]]:
    paths = sorted(CATALOG_DIR.glob("part-*.json"))
    if not paths:
        paths = [PROBLEMS_PATH]
    problems: list[dict[str, Any]] = []
    for path in paths:
        shard = json.loads(path.read_bytes())
        enforce_catalog_deadline(f"reading {path.name}")
        if not isinstance(shard, list):
            raise ValueError(f"{path.relative_to(ROOT)} must contain a JSON array")
        problems.extend(shard)
    if VARIANTS_PATH.exists():
        templates = json.loads(VARIANTS_PATH.read_bytes())
        enforce_catalog_deadline("reading variant templates")
        if not isinstance(templates, list):
            raise ValueError("data/variant_templates.json must contain a JSON array")
        base_problems = list(problems)
        next_number = len(base_problems) + 1
        for template in templates:
            key = str(template["key"])
            for base in base_problems:
                # Catalog entries are immutable after startup; a shallow copy is
                # sufficient and avoids cloning large source/license structures.
                derived = dict(base)
                kind = base["kind"]
                title = base["title"]
                description = str(template["descriptions"][kind]).format(
                    title=title,
                    summary=base.get("summary", base["description"]),
                )
                prompts = [
                    str(prompt).format(title=title)
                    for prompt in template["follow_ups"][kind]
                ]
                derived.update(
                    {
                        "id": f"{base['id']}--{key}",
                        "number": next_number,
                        "title": f"{title} · {template['title_suffix']}",
                        "slug": f"{base.get('slug', base['id'])}--{key}",
                        "summary": description[:180],
                        "description": description,
                        "tags": [*base.get("tags", []), str(template["tag"])],
                        "follow_ups": prompts,
                        "hints": prompts[:1],
                        "provenance": {
                            "origin": "aibag-derived",
                            "derived_from": base["id"],
                            "variant": key,
                            "imported_at": base["provenance"]["imported_at"],
                            "base_provenance": base["provenance"],
                        },
                    }
                )
                problems.append(derived)
                next_number += 1
                if next_number % 100 == 0:
                    enforce_catalog_deadline("expanding variants")
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
    for index, problem in enumerate(problems, start=1):
        missing = required - set(problem)
        if missing:
            raise ValueError(f"Problem is missing fields: {sorted(missing)}")
        if problem["id"] in seen:
            raise ValueError(f"Duplicate problem id: {problem['id']}")
        seen.add(problem["id"])
        if index % 100 == 0:
            enforce_catalog_deadline("validating catalog")
    numbers = [problem["number"] for problem in problems]
    if numbers != list(range(1, len(problems) + 1)):
        raise ValueError("Problem numbers must be consecutive and ordered from 1")
    enforce_catalog_deadline("final validation")
    return problems


PROBLEMS = load_problems()
PROBLEM_INDEX = {problem["id"]: problem for problem in PROBLEMS}
ANSWER_CACHE: dict[str, dict[str, str]] = {}


def public_problem(problem: dict[str, Any]) -> dict[str, Any]:
    """Return the problem statement without hidden review points or reference notes."""
    hidden = {"review_points", "review_dimensions", "reference_notes", "hints", "follow_ups"}
    return {key: value for key, value in problem.items() if key not in hidden}


def public_problem_summary(problem: dict[str, Any]) -> dict[str, Any]:
    """Small payload used by catalog pages; detail is fetched on demand."""
    fields = (
        "id",
        "number",
        "kind",
        "title",
        "category",
        "topic",
        "difficulty",
        "tags",
        "summary",
    )
    return {field: problem[field] for field in fields}


PUBLIC_PROBLEM_SUMMARIES = [public_problem_summary(problem) for problem in PROBLEMS]
PUBLIC_CATALOG_JSON = json.dumps(
    PUBLIC_PROBLEM_SUMMARIES, ensure_ascii=False, separators=(",", ":")
).encode("utf-8")
PUBLIC_CATALOG_GZIP = gzip.compress(PUBLIC_CATALOG_JSON, compresslevel=5)
CATALOG_LOAD_SECONDS = time.perf_counter() - CATALOG_BOOT_STARTED
if CATALOG_LOAD_SECONDS > CATALOG_LOAD_LIMIT_SECONDS:
    raise TimeoutError(
        f"Catalog startup exceeded {CATALOG_LOAD_LIMIT_SECONDS:.1f}s "
        f"while building the public index ({CATALOG_LOAD_SECONDS:.3f}s)"
    )


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


def coach_reply(problem: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    is_knowledge = problem["kind"] == "knowledge"
    prompt_name = "coach_knowledge.txt" if is_knowledge else "coach.txt"
    system = (ROOT / "prompts" / prompt_name).read_text(encoding="utf-8")
    action = str(payload.get("action", "chat"))
    if action not in {"hint", "optimize", "counter", "follow_up", "chat"}:
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
        plain_text_key=None if is_knowledge else "reply",
    )
    result: dict[str, Any] = {
        "action": action,
        "reply": str(raw.get("reply", "我们先聚焦一个最关键的知识点。"))[:1_500],
        "focus": str(raw.get("focus", ""))[:500],
    }
    if is_knowledge:
        pe = raw.get("pe", {})
        if not isinstance(pe, dict):
            pe = {}
        state = str(pe.get("state", "exploring"))
        if state not in {"blank", "exploring", "partial", "solid", "misconception", "blocked"}:
            state = "exploring"
        try:
            level = max(0, min(4, int(pe.get("level", 1))))
        except (TypeError, ValueError):
            level = 1
        strategy = str(pe.get("strategy", "probe"))
        if strategy not in {"entry_hint", "clarify", "probe", "challenge", "reframe", "affirm"}:
            strategy = "probe"
        result["pe"] = {
            "state": state,
            "level": level,
            "evidence": str(pe.get("evidence", ""))[:500],
            "core_gap": str(pe.get("core_gap", ""))[:500],
            "strategy": strategy,
        }
    return result


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
        "/completed.html",
        "/completed.js",
        "/problem.html",
        "/problem.js",
        "/style.css",
    }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self) -> None:
        if urlsplit(self.path).path in self.STATIC_PATHS:
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_json(self, data: Any, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        use_gzip = len(body) >= 1_024 and "gzip" in self.headers.get("Accept-Encoding", "")
        if use_gzip:
            body = gzip.compress(body, compresslevel=5)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Vary", "Accept-Encoding")
        if use_gzip:
            self.send_header("Content-Encoding", "gzip")
        self.end_headers()
        self.wfile.write(body)

    def send_catalog(self) -> None:
        use_gzip = "gzip" in self.headers.get("Accept-Encoding", "")
        body = PUBLIC_CATALOG_GZIP if use_gzip else PUBLIC_CATALOG_JSON
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "private, max-age=60")
        self.send_header("Vary", "Accept-Encoding")
        if use_gzip:
            self.send_header("Content-Encoding", "gzip")
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
            self.send_json(
                {
                    "ok": True,
                    "problems": len(PROBLEMS),
                    "catalog_load_ms": round(CATALOG_LOAD_SECONDS * 1_000, 2),
                    "catalog_load_limit_ms": int(CATALOG_LOAD_LIMIT_SECONDS * 1_000),
                    "catalog_within_budget": CATALOG_LOAD_SECONDS <= CATALOG_LOAD_LIMIT_SECONDS,
                    **api_config(),
                }
            )
            return
        if path == "/api/config":
            self.send_json(api_config())
            return
        if path == "/api/problems":
            self.send_catalog()
            return
        if path == "/api/problem":
            problem_id = parse_qs(urlsplit(self.path).query).get("id", [""])[0]
            problem = PROBLEM_INDEX.get(problem_id)
            if problem is None:
                self.send_json({"error": "Unknown problem id"}, HTTPStatus.NOT_FOUND)
                return
            self.send_json(public_problem(problem))
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
