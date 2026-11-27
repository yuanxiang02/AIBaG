#!/usr/bin/env python3
"""AIBaG local web server and OpenAI-compatible API proxy."""

from __future__ import annotations

import gzip
import json
import os
import re
import sys
import threading
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
ANSWERS_PATH = ROOT / "data" / "answers.json"
CUSTOM_PROBLEMS_PATH = Path(
    os.getenv("AIBAG_CUSTOM_PROBLEMS_PATH", str(ROOT / "data" / "custom_problems.json"))
)
CUSTOM_LOCK = threading.RLock()
CUSTOM_LOAD_FAILURE: dict[str, str] | None = None
MAX_REQUEST_BYTES = 1_000_000
MAX_CUSTOM_IMPORT_ITEMS = 200
CATALOG_LOAD_LIMIT_SECONDS = 5.0
VALID_KINDS = {"coding", "knowledge", "algorithm"}
VALID_DIFFICULTIES = {"Easy", "Medium", "Hard"}
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
                notes = "；".join(base.get("reference_notes", [])) or "题面中的边界与评分点"
                answer_addendum = str(template["answer_guidance"][kind]).format(
                    title=title,
                    notes=notes,
                )
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
                        "answer_addendum": answer_addendum,
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
STANDARD_ANSWERS: dict[str, dict[str, str]] = json.loads(ANSWERS_PATH.read_bytes())
enforce_catalog_deadline("reading standard answers")
BASE_PROBLEM_IDS = {
    problem["id"]
    for problem in PROBLEMS
    if problem["provenance"].get("origin") != "aibag-derived"
}
if set(STANDARD_ANSWERS) != BASE_PROBLEM_IDS:
    missing = sorted(BASE_PROBLEM_IDS - set(STANDARD_ANSWERS))
    extra = sorted(set(STANDARD_ANSWERS) - BASE_PROBLEM_IDS)
    raise ValueError(f"Standard answer index mismatch; missing={missing}, extra={extra}")


def public_problem(problem: dict[str, Any]) -> dict[str, Any]:
    """Return the problem statement without hidden review points or reference notes."""
    hidden = {
        "review_points",
        "review_dimensions",
        "reference_notes",
        "hints",
        "follow_ups",
        "answer_addendum",
        "answer",
    }
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
    summary = {field: problem[field] for field in fields}
    summary["is_custom"] = bool(
        problem.get("is_custom") or problem.get("provenance", {}).get("origin") == "user-custom"
    )
    return summary


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


def slugify_custom_id(text: str, index: int) -> str:
    ascii_slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if ascii_slug:
        return f"custom-{ascii_slug[:48]}"
    return f"custom-item-{int(time.time() * 1000)}-{index}"


def default_review_points_for_kind(kind: str, raw_points: Any) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    if isinstance(raw_points, str):
        raw_points = [item.strip() for item in re.split(r"[\n;；]+", raw_points) if item.strip()]
    if isinstance(raw_points, list):
        for item in raw_points[:8]:
            if isinstance(item, str) and item.strip():
                text = item.strip()[:240]
                points.append({"label": text[:40], "required": True, "description": text})
            elif isinstance(item, dict):
                label = str(item.get("label") or item.get("description") or "").strip()[:60]
                desc = str(item.get("description") or label).strip()[:240]
                if label:
                    points.append({"label": label, "required": bool(item.get("required", True)), "description": desc})
    if points:
        return points
    if kind == "knowledge":
        return [
            {"label": "核心概念与机制", "required": True, "description": "准确讲清核心定义与底层工作原理"},
            {"label": "设计原因与因果逻辑", "required": True, "description": "解释为什么这样设计，解决什么痛点"},
            {"label": "适用边界与工程权衡", "required": True, "description": "说明开销、局限性或替代方案对比"},
        ]
    if kind == "coding":
        return [
            {"label": "核心算子与模块实现", "required": True, "description": "主干计算逻辑与关键步骤完整"},
            {"label": "Tensor Shape 与维度变换", "required": True, "description": "各步维度对齐、广播与返回形状正确"},
            {"label": "数值稳定与边界处理", "required": True, "description": "处理缩放、mask、精度或极端输入"},
        ]
    return [
        {"label": "核心算法思路", "required": True, "description": "数据结构选择与主循环/递归不变量正确"},
        {"label": "边界条件覆盖", "required": True, "description": "空输入、单元素、重复值或越界处理稳健"},
        {"label": "时间与空间复杂度", "required": True, "description": "复杂度满足面试要求并能清晰推导"},
    ]


def normalize_custom_problem(
    raw: dict[str, Any], number: int, existing_ids: set[str] | None = None
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("每道自定义题目必须是 JSON 对象")
    title = str(raw.get("title", "")).strip()[:120]
    if not title:
        raise ValueError("题目标题（title）不能为空")
    kind = str(raw.get("kind", "knowledge")).strip().lower()
    if kind not in VALID_KINDS:
        kind_map = {
            "ai infra": "coding",
            "infra": "coding",
            "简答八股": "knowledge",
            "八股": "knowledge",
            "面经": "knowledge",
            "力扣手撕": "algorithm",
            "手撕": "algorithm",
            "算法": "algorithm",
        }
        kind = kind_map.get(kind, "knowledge")
    description = str(raw.get("description") or raw.get("prompt") or "").strip()[:8_000]
    if not description:
        raise ValueError(f"题目「{title}」缺少题面描述（description）")
    difficulty_raw = str(raw.get("difficulty", "Medium")).strip().capitalize()
    difficulty = difficulty_raw if difficulty_raw in VALID_DIFFICULTIES else "Medium"
    default_category = {
        "coding": "AI Infra",
        "knowledge": "自建面经",
        "algorithm": "算法手撕",
    }[kind]
    category = str(raw.get("category") or default_category).strip()[:40] or default_category
    topic = str(raw.get("topic") or category).strip()[:40] or category
    default_language = "口头回答" if kind == "knowledge" else "Python / PyTorch" if kind == "coding" else "Python"
    language = str(raw.get("language") or default_language).strip()[:40] or default_language

    raw_tags = raw.get("tags", [])
    if isinstance(raw_tags, str):
        tags = [t.strip()[:30] for t in re.split(r"[,，;；\s]+", raw_tags) if t.strip()]
    elif isinstance(raw_tags, list):
        tags = [str(t).strip()[:30] for t in raw_tags if str(t).strip()]
    else:
        tags = []
    if "自建面经" not in tags:
        tags.append("自建面经")
    tags = tags[:8]

    starter_code = str(raw.get("starter_code", ""))[:8_000]
    if kind == "knowledge":
        starter_code = ""
    elif not starter_code.strip():
        starter_code = "def solution(*args, **kwargs):\n    # 在此编写核心实现\n    pass\n"

    answer = str(raw.get("answer") or raw.get("reference_answer") or "").strip()[:16_000]
    review_points = default_review_points_for_kind(kind, raw.get("review_points"))
    review_dimensions = [point["label"] for point in review_points]

    raw_notes = raw.get("reference_notes", [])
    if isinstance(raw_notes, str):
        reference_notes = [n.strip()[:240] for n in re.split(r"[\n;；]+", raw_notes) if n.strip()]
    elif isinstance(raw_notes, list):
        reference_notes = [str(n).strip()[:240] for n in raw_notes if str(n).strip()]
    else:
        reference_notes = []
    if not reference_notes and answer:
        reference_notes = [line.strip()[:200] for line in answer.splitlines() if line.strip()][:4]

    raw_constraints = raw.get("constraints", [])
    if isinstance(raw_constraints, str):
        constraints = [c.strip()[:200] for c in re.split(r"[\n;；]+", raw_constraints) if c.strip()]
    elif isinstance(raw_constraints, list):
        constraints = [str(c).strip()[:200] for c in raw_constraints if str(c).strip()]
    else:
        constraints = []
    if not constraints:
        constraints = [
            "面试口述模式：用自己的话讲清核心机制、原因与工程权衡。"
            if kind == "knowledge"
            else "白板模式：静态推导关键数据结构、维度变化与边界条件。"
        ]

    raw_examples = raw.get("examples", [])
    examples: list[dict[str, str]] = []
    if isinstance(raw_examples, list):
        for ex in raw_examples[:4]:
            if isinstance(ex, dict) and (ex.get("input") or ex.get("output")):
                examples.append(
                    {
                        "input": str(ex.get("input", "")).strip()[:400],
                        "output": str(ex.get("output", "")).strip()[:400],
                        "explanation": str(ex.get("explanation", "")).strip()[:400],
                    }
                )

    raw_id = str(raw.get("id", "")).strip()
    if raw_id and re.fullmatch(r"[A-Za-z0-9_-]{3,80}", raw_id):
        candidate_id = raw_id if raw_id.startswith("custom-") else f"custom-{raw_id}"
    else:
        candidate_id = slugify_custom_id(title, number)
    if existing_ids is not None:
        base_candidate = candidate_id
        suffix = 2
        while candidate_id in existing_ids:
            candidate_id = f"{base_candidate}-{suffix}"
            suffix += 1
        existing_ids.add(candidate_id)

    summary = str(raw.get("summary") or description.splitlines()[0]).strip()[:160]
    imported_at = str(raw.get("imported_at") or time.strftime("%Y-%m-%d"))
    follow_ups = [
        f"围绕「{title}」，最关键的设计权衡或边界条件是什么？",
        f"如果在生产环境中落地「{title}」，最容易踩的坑在哪里？",
    ]
    return {
        "id": candidate_id,
        "number": number,
        "kind": kind,
        "title": title,
        "slug": candidate_id,
        "category": category,
        "topic": topic,
        "difficulty": difficulty,
        "language": language,
        "tags": tags,
        "summary": summary,
        "description": description,
        "examples": examples,
        "constraints": constraints,
        "starter_code": starter_code,
        "review_points": review_points,
        "review_dimensions": review_dimensions,
        "follow_ups": follow_ups,
        "hints": [follow_ups[0]],
        "reference_notes": reference_notes,
        "answer": answer,
        "is_custom": True,
        "sources": [
            {
                "title": str(raw.get("source_title") or "用户自建 AI 面经题库").strip()[:120],
                "url": "local://custom-problem-bank",
                "license": "User-Custom",
                "note": "保存在本机 data/custom_problems.json，可随时查看或删除。",
            }
        ],
        "license": {"spdx": "LicenseRef-User-Custom", "notice": "User-submitted local problem."},
        "provenance": {
            "origin": "user-custom",
            "imported_at": imported_at,
        },
    }


def load_custom_problems(path: Path | None = None) -> list[dict[str, Any]]:
    global CUSTOM_LOAD_FAILURE
    target = path or CUSTOM_PROBLEMS_PATH
    CUSTOM_LOAD_FAILURE = None
    if not target.exists():
        return []
    try:
        raw_list = json.loads(target.read_bytes())
    except (ValueError, OSError) as error:
        # An unreadable bank must not look like an empty bank: the next save
        # would otherwise replace the user's data with a single new entry.
        CUSTOM_LOAD_FAILURE = {
            "path": str(target),
            "error": f"{type(error).__name__}: {error}",
        }
        print(
            f"Custom problem bank is unreadable and must not be overwritten: "
            f"{target} ({error})",
            file=sys.stderr,
        )
        return []
    if not isinstance(raw_list, list):
        return []
    seen_ids = set(PROBLEM_INDEX)
    result: list[dict[str, Any]] = []
    base_count = len(PROBLEMS)
    for offset, item in enumerate(raw_list, start=1):
        if not isinstance(item, dict):
            continue
        try:
            normalized = normalize_custom_problem(item, base_count + len(result) + 1, seen_ids)
            result.append(normalized)
        except ValueError:
            continue
    return result


def custom_bank_status(path: Path | None = None) -> dict[str, Any]:
    """Report whether the custom bank on disk is readable, without mutating it."""
    target = path or CUSTOM_PROBLEMS_PATH
    if not target.exists():
        return {"path": str(target), "exists": False, "ok": True, "error": None}
    try:
        json.loads(target.read_bytes())
    except (ValueError, OSError) as error:
        return {
            "path": str(target),
            "exists": True,
            "ok": False,
            "error": f"{type(error).__name__}: {error}",
        }
    return {"path": str(target), "exists": True, "ok": True, "error": None}


def quarantine_unreadable_bank(target: Path) -> Path | None:
    """Move a corrupt bank aside so a later save cannot destroy it."""
    if not target.exists():
        return None
    try:
        json.loads(target.read_bytes())
        return None
    except (ValueError, OSError) as error:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup = target.with_name(f"{target.stem}.corrupt-{stamp}{target.suffix}")
        target.replace(backup)
        print(f"Preserved unreadable custom bank as {backup}: {error}", file=sys.stderr)
        return backup


def save_custom_problems(items: list[dict[str, Any]], path: Path | None = None) -> None:
    target = path or CUSTOM_PROBLEMS_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    quarantine_unreadable_bank(target)
    base_count = len(PROBLEMS)
    for idx, item in enumerate(items, start=1):
        item["number"] = base_count + idx
    serialized = json.dumps(items, ensure_ascii=False, indent=2).encode("utf-8")
    tmp_path = target.with_suffix(".json.tmp")
    tmp_path.write_bytes(serialized)
    tmp_path.replace(target)


def add_custom_problems(payload: dict[str, Any], path: Path | None = None) -> list[dict[str, Any]]:
    with CUSTOM_LOCK:
        existing = load_custom_problems(path)
        seen_ids = set(PROBLEM_INDEX) | {item["id"] for item in existing}
        raw_items = payload.get("problems") if isinstance(payload.get("problems"), list) else [payload]
        if not raw_items:
            raise ValueError("请提供至少一道题目")
        if len(raw_items) > MAX_CUSTOM_IMPORT_ITEMS:
            raise ValueError(f"单次最多导入 {MAX_CUSTOM_IMPORT_ITEMS} 道题目")
        created: list[dict[str, Any]] = []
        base_number = len(PROBLEMS) + len(existing)
        for offset, raw_item in enumerate(raw_items, start=1):
            normalized = normalize_custom_problem(raw_item, base_number + offset, seen_ids)
            existing.append(normalized)
            created.append(normalized)
        save_custom_problems(existing, path)
        return created


def update_custom_problem(payload: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    target_id = str(payload.get("id") or payload.get("problem_id") or "").strip()
    if not target_id:
        raise ValueError("缺少要编辑的自建题目 ID")
    with CUSTOM_LOCK:
        existing = load_custom_problems(path)
        target_idx = next((idx for idx, item in enumerate(existing) if item["id"] == target_id), -1)
        if target_idx < 0:
            raise KeyError(f"未找到自建题目：{target_id}")
        other_ids = set(PROBLEM_INDEX) | {
            item["id"] for idx, item in enumerate(existing) if idx != target_idx
        }
        merged_raw = {
            **existing[target_idx],
            **payload,
            "id": target_id,
            "imported_at": existing[target_idx].get("provenance", {}).get("imported_at"),
        }
        updated = normalize_custom_problem(merged_raw, existing[target_idx]["number"], other_ids)
        existing[target_idx] = updated
        save_custom_problems(existing, path)
        return updated


def delete_custom_problem(problem_id: str, path: Path | None = None) -> bool:
    with CUSTOM_LOCK:
        existing = load_custom_problems(path)
        kept = [item for item in existing if item["id"] != problem_id]
        if len(kept) == len(existing):
            return False
        save_custom_problems(kept, path)
        return True


def get_problem_by_id(problem_id: str, path: Path | None = None) -> dict[str, Any] | None:
    built_in = PROBLEM_INDEX.get(problem_id)
    if built_in is not None:
        return built_in
    for item in load_custom_problems(path):
        if item["id"] == problem_id:
            return item
    return None


def all_public_problem_summaries(path: Path | None = None) -> list[dict[str, Any]]:
    custom = load_custom_problems(path)
    if not custom:
        return PUBLIC_PROBLEM_SUMMARIES
    return [*PUBLIC_PROBLEM_SUMMARIES, *(public_problem_summary(item) for item in custom)]


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


def ai_is_available() -> bool:
    """Return whether the configured provider can serve AI review requests."""
    base_url = os.getenv("AIBAG_BASE_URL", "https://api.deepseek.com").rstrip("/")
    hostname = urlsplit(base_url).hostname or ""
    is_local_provider = hostname in {"127.0.0.1", "localhost", "::1"}
    return bool(resolve_api_key()) or is_local_provider


def api_config() -> dict[str, Any]:
    return {
        "model": os.getenv("AIBAG_MODEL", "deepseek-flash"),
        "base_url": os.getenv("AIBAG_BASE_URL", "https://api.deepseek.com"),
        "has_api_key": bool(resolve_api_key()),
        "ai_available": ai_is_available(),
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
    hostname = urlsplit(base_url).hostname or ""
    is_deepseek = hostname in {"api.deepseek.com", "api.deepseek.com.cn"}
    is_local_provider = hostname in {"127.0.0.1", "localhost", "::1"}
    model = os.getenv("AIBAG_MODEL", "deepseek-flash")
    api_key = resolve_api_key()
    if not api_key and not is_local_provider:
        raise RuntimeError(
            "未检测到 API Key。请在项目根目录 .env 文件中设置 AIBAG_API_KEY，"
            "或先使用左侧「查看标准答案」与自评掌握度按钮进行离线训练。"
        )
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
    """Return a persisted answer immediately; derived items reuse their base answer."""
    if problem.get("is_custom") or problem.get("provenance", {}).get("origin") == "user-custom":
        custom_ans = str(problem.get("answer", "")).strip()
        if not custom_ans:
            points = "\n".join(
                f"- {pt['label']}：{pt.get('description', '')}"
                for pt in problem.get("review_points", [])
            )
            custom_ans = (
                f"【自建面经参考要点】\n{points}\n\n"
                "提示：你可以在创建题目时填入专属参考答案，或直接与右侧 AI 面试官进行多轮追问演练。"
            )
        return {"answer": custom_ans, "source": "user-custom"}
    provenance = problem.get("provenance", {})
    base_id = str(provenance.get("derived_from", problem["id"]))
    stored = STANDARD_ANSWERS.get(base_id)
    if stored is None:
        raise RuntimeError(f"No persisted standard answer for {base_id}")
    answer = str(stored["answer"]).strip()
    addendum = str(problem.get("answer_addendum", "")).strip()
    if addendum:
        answer = f"{answer}\n\n本题训练视角补充：\n{addendum}"
    return {
        "answer": answer,
        "source": str(stored.get("source", "aibag-persisted")),
    }


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
        custom = load_custom_problems()
        use_gzip = "gzip" in self.headers.get("Accept-Encoding", "")
        if not custom:
            body = PUBLIC_CATALOG_GZIP if use_gzip else PUBLIC_CATALOG_JSON
        else:
            combined = [*PUBLIC_PROBLEM_SUMMARIES, *(public_problem_summary(item) for item in custom)]
            raw_bytes = json.dumps(combined, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            body = gzip.compress(raw_bytes, compresslevel=5) if use_gzip else raw_bytes
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
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
            custom_count = len(load_custom_problems())
            self.send_json(
                {
                    "ok": True,
                    "problems": len(PROBLEMS) + custom_count,
                    "custom_problems": custom_count,
                    "catalog_load_ms": round(CATALOG_LOAD_SECONDS * 1_000, 2),
                    "catalog_load_limit_ms": int(CATALOG_LOAD_LIMIT_SECONDS * 1_000),
                    "catalog_within_budget": CATALOG_LOAD_SECONDS <= CATALOG_LOAD_LIMIT_SECONDS,
                    "custom_bank": custom_bank_status(),
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
        if path == "/api/custom-problems":
            self.send_json({"problems": load_custom_problems()})
            return
        if path == "/api/problem":
            problem_id = parse_qs(urlsplit(self.path).query).get("id", [""])[0]
            problem = get_problem_by_id(problem_id)
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
        if path not in {
            "/api/judge",
            "/api/chat",
            "/api/answer",
            "/api/custom-problems",
            "/api/custom-problems/update",
            "/api/custom-problems/delete",
        }:
            self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            payload = self.read_json()
            if path == "/api/custom-problems":
                created = add_custom_problems(payload)
                self.send_json(
                    {
                        "created": [public_problem_summary(item) for item in created],
                        "count": len(created),
                    },
                    HTTPStatus.CREATED,
                )
                return
            if path == "/api/custom-problems/update":
                try:
                    updated = update_custom_problem(payload)
                except KeyError as error:
                    self.send_json({"error": str(error)}, HTTPStatus.NOT_FOUND)
                    return
                self.send_json(
                    {"updated": public_problem_summary(updated), "problem": updated},
                    HTTPStatus.OK,
                )
                return
            if path == "/api/custom-problems/delete":
                target_id = str(payload.get("id") or payload.get("problem_id") or "").strip()
                if not target_id:
                    raise ValueError("Missing problem id")
                deleted = delete_custom_problem(target_id)
                if not deleted:
                    self.send_json({"error": "Custom problem not found"}, HTTPStatus.NOT_FOUND)
                    return
                self.send_json({"deleted": target_id})
                return
            problem_id = str(payload.get("problem_id", ""))
            problem = get_problem_by_id(problem_id)
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
