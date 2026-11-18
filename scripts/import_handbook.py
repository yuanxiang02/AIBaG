#!/usr/bin/env python3
"""Build deterministic AIBaG catalog shards from llm-interview-handbook."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


GROUPS = ("llm-coding", "algorithms", "docs")
HEADING = re.compile(r"^(##|###)\s+Q(\d+)\s*[·.-]\s*(.+?)\s*$")
SKIP_PATTERNS = (
    "multi-head attention",
    "rope (rotary",
    "rmsnorm",
    "cross-entropy loss",
    "top-p",
    "lora linear",
    "swiglu",
    "kv cache",
    "grouped-query attention",
    "causal (masked) attention",
    "bpe 训练",
    "beam search",
    "dpo loss",
    "moe top-k routing",
    "零钱兑换",
    "螺旋矩阵",
)

CATEGORY_NAMES = {
    "01-attention": "Attention",
    "02-position-encoding": "位置编码",
    "03-normalization": "归一化",
    "04-tokenizer": "Tokenizer",
    "05-decoding": "解码策略",
    "06-peft": "参数高效微调",
    "07-loss-rl": "损失与强化学习",
    "08-misc": "LLM 核心组件",
    "01-array": "数组",
    "02-linked-list": "链表",
    "03-hash-table": "哈希表",
    "04-string": "字符串",
    "05-stack-queue": "栈与队列",
    "06-binary-tree": "二叉树",
    "07-backtrack": "回溯",
    "08-monotonic-stack": "单调栈",
    "09-dp": "动态规划",
    "10-hot100": "Hot100",
    "11-interview-real-questions": "面试真题",
    "00-foundations": "基础知识",
    "01-architecture": "模型架构",
    "02-training": "模型训练",
    "03-fine-tuning": "微调方法",
    "04-alignment": "后训练与对齐",
    "05-inference": "推理优化",
    "06-rag": "RAG",
    "07-agent": "Agent",
    "08-multimodal": "多模态",
    "09-evaluation": "模型评测",
    "10-system": "系统与部署",
    "99-frontier": "前沿专题",
}


def clean_markdown(text: str) -> str:
    text = re.sub(r"!\[[^]]*]\([^)]+\)", "", text)
    text = re.sub(r"\[([^]]+)]\([^)]+\)", r"\1", text)
    text = re.sub(r"[`*_>#~]", "", text)
    text = re.sub(r"\$+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def slug_part(text: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return value or "question"


def first_prose(lines: list[str]) -> str:
    in_code = False
    for raw in lines:
        line = raw.strip()
        if line.startswith("```") or line.startswith("~~~"):
            in_code = not in_code
            continue
        if in_code or not line:
            continue
        if line.startswith(("#", "|", "[⬅", "---", "$$")):
            continue
        if line.startswith(("- ", "* ", "> ")):
            line = line[2:]
        value = clean_markdown(line)
        if len(value) >= 8:
            return value[:600]
    return "请说明核心思路、关键步骤、边界条件与主要权衡。"


def extract_notes(lines: list[str]) -> list[str]:
    notes: list[str] = []
    in_code = False
    for raw in lines:
        line = raw.strip()
        if line.startswith("```") or line.startswith("~~~"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if re.match(r"^(?:[-*]|\d+[.)])\s+", line):
            value = clean_markdown(re.sub(r"^(?:[-*]|\d+[.)])\s+", "", line))
            if 12 <= len(value) <= 400 and value not in notes:
                notes.append(value)
        if len(notes) == 3:
            break
    return notes


def starter_from_code(lines: list[str], kind: str) -> str:
    if kind == "knowledge":
        return ""
    code: list[str] = []
    in_python = False
    for raw in lines:
        stripped = raw.strip()
        if not in_python and re.match(r"^(?:```|~~~)python", stripped, re.I):
            in_python = True
            continue
        if in_python and stripped.startswith(("```", "~~~")):
            break
        if in_python:
            code.append(raw.rstrip())
    # Type comments inside multiline signatures otherwise become part of the
    # generated one-line signature and can make the starter invalid Python.
    joined = "\n".join(re.sub(r"\s+#.*$", "", line) for line in code)
    signature = re.search(r"(?m)^def\s+([A-Za-z_]\w*)\s*\((.*?)\)\s*(?:->\s*[^:]+)?\s*:", joined, re.S)
    if signature:
        name = signature.group(1)
        raw_args = re.sub(r"\s+", " ", signature.group(2)).strip()
        if len(raw_args) <= 180:
            return f"def {name}({raw_args}):\n    # TODO: implement the core idea\n    raise NotImplementedError\n"
    class_match = re.search(r"(?m)^class\s+([A-Za-z_]\w*)", joined)
    if class_match:
        return (
            f"class {class_match.group(1)}:\n"
            "    # TODO: define the required state and methods\n"
            "    raise NotImplementedError\n"
        )
    return "# 请写出核心实现；当前是白板模式，不能运行代码。\n"


def review_points(kind: str) -> list[dict[str, Any]]:
    if kind == "knowledge":
        rows = (
            ("核心概念", "准确说明定义与主要机制"),
            ("因果解释", "能解释为什么这样设计，而非只背结论"),
            ("适用边界", "说明成立条件、失败场景或例外"),
            ("权衡比较", "能讨论替代方案、收益与代价"),
        )
    elif kind == "algorithm":
        rows = (
            ("核心算法", "给出正确且可完成的解题路径"),
            ("不变量", "说明循环、递归或数据结构维持的条件"),
            ("边界条件", "覆盖空输入、极值或特殊结构"),
            ("复杂度", "正确分析时间与空间复杂度"),
        )
    else:
        rows = (
            ("核心实现", "实现题目要求的主要计算链路"),
            ("Shape/状态", "静态推导关键 tensor shape 或状态变化"),
            ("边界与数值", "处理 mask、精度、初始化或边界情况"),
            ("复杂度与权衡", "说明计算、内存与工程代价"),
        )
    return [
        {"label": label, "required": True, "description": description}
        for label, description in rows
    ]


def follow_ups(title: str, kind: str) -> list[str]:
    if kind == "knowledge":
        return [
            f"为什么 {title} 要这样设计？",
            "它的适用边界、主要代价和替代方案分别是什么？",
        ]
    if kind == "algorithm":
        return ["你维护的核心不变量是什么？", "时间与空间复杂度分别是多少？"]
    return [
        "你能口头推导一下关键 shape 或状态是怎么变化的吗？",
        "这份实现最容易错在哪个边界？",
    ]


def parse_sections(source_root: Path) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    for group in GROUPS:
        for path in sorted((source_root / group).glob("*.md")):
            if path.name in {"README.md", "_TEMPLATE.md", "99-tips.md"}:
                continue
            lines = path.read_text(encoding="utf-8").splitlines()
            matches = [(index, HEADING.match(line)) for index, line in enumerate(lines)]
            matches = [(index, match) for index, match in matches if match]
            for position, (start, match) in enumerate(matches):
                end = matches[position + 1][0] if position + 1 < len(matches) else len(lines)
                title = clean_markdown(match.group(3))
                lowered = title.lower()
                if any(pattern in lowered for pattern in SKIP_PATTERNS):
                    continue
                sections.append(
                    {
                        "group": group,
                        "path": path,
                        "question_code": f"Q{match.group(2)}",
                        "title": title,
                        "lines": lines[start + 1 : end],
                    }
                )
    return sections


def normalize_base(
    problem: dict[str, Any],
    commit: str,
    updated_at: str,
    imported_at: str,
) -> dict[str, Any]:
    item = dict(problem)
    kind = "coding" if problem["category"] == "AI Infra" else "algorithm"
    item.update(
        {
            "kind": kind,
            "topic": problem["category"],
            "follow_ups": problem.get("follow_ups", follow_ups(problem["title"], kind)),
            "review_dimensions": [point["label"] for point in problem["review_points"]],
            "license": {
                "spdx": problem["sources"][0].get("license", "See source"),
                "notice": "See per-item sources and THIRD_PARTY_NOTICES.md.",
            },
            "provenance": {
                "origin": "aibag-curated",
                "catalog_upstream": "axiaoquan/llm-interview-handbook",
                "catalog_upstream_commit": commit,
                "catalog_upstream_updated_at": updated_at,
                "imported_at": imported_at,
                "source_urls": [source["url"] for source in problem["sources"]],
            },
        }
    )
    return item


def convert_section(
    section: dict[str, Any],
    number: int,
    commit: str,
    updated_at: str,
    imported_at: str,
) -> dict[str, Any]:
    group = section["group"]
    path: Path = section["path"]
    title = section["title"]
    kind = "coding" if group == "llm-coding" else "algorithm" if group == "algorithms" else "knowledge"
    relative = path.relative_to(path.parents[1]).as_posix()
    category = CATEGORY_NAMES.get(path.stem, path.stem)
    source_summary = first_prose(section["lines"])
    if kind == "knowledge":
        description = (
            f"请用面试口述的方式解释「{title}」。重点讲清核心定义或机制、"
            "为什么这样设计，以及一个适用边界或主要权衡；不要求背标准表述。"
        )
    elif kind == "algorithm":
        description = (
            f"请现场实现「{title}」的核心算法。先根据题名说明你理解的输入输出，"
            "再给出可完成的实现，并解释关键不变量、边界条件和复杂度。"
        )
    else:
        description = source_summary
    notes = extract_notes(section["lines"])
    identifier = f"handbook-{slug_part(group)}-{slug_part(path.stem)}-{section['question_code'].lower()}"
    language = "口头回答" if kind == "knowledge" else "Python / PyTorch" if kind == "coding" else "Python 3"
    url = f"https://github.com/axiaoquan/llm-interview-handbook/blob/{commit}/{relative}"
    dimensions = review_points(kind)
    prompts = follow_ups(title, kind)
    return {
        "id": identifier,
        "number": number,
        "kind": kind,
        "title": title,
        "slug": identifier,
        "category": "LLM 手撕" if kind == "coding" else "经典算法" if kind == "algorithm" else "知识问答",
        "topic": category,
        "difficulty": "Medium",
        "language": language,
        "tags": [category, kind],
        "summary": description[:180],
        "description": description,
        "examples": [],
        "constraints": ["白板模式：不能运行代码、print 或使用 debugger。"],
        "starter_code": starter_from_code(section["lines"], kind),
        "review_points": dimensions,
        "review_dimensions": [point["label"] for point in dimensions],
        "follow_ups": prompts,
        "hints": [prompts[0]],
        "reference_notes": notes,
        "sources": [
            {
                "title": f"LLM Interview Handbook · {relative} · {section['question_code']}",
                "url": url,
                "license": "MIT",
                "note": "经 AIBaG 结构化、压缩或重写；保留上游归属。",
                "upstream_updated_at": updated_at,
            }
        ],
        "license": {
            "spdx": "MIT",
            "copyright": "Copyright (c) 2026 axiaoquan",
            "notice_file": "third_party/llm-interview-handbook-LICENSE",
        },
        "provenance": {
            "origin": "axiaoquan/llm-interview-handbook",
            "source_path": relative,
            "source_section": f"{section['question_code']} · {title}",
            "upstream_commit": commit,
            "upstream_updated_at": updated_at,
            "imported_at": imported_at,
        },
    }


def build_catalog(args: argparse.Namespace) -> list[dict[str, Any]]:
    base = json.loads(Path(args.base).read_text(encoding="utf-8"))
    catalog = [
        normalize_base(
            problem,
            args.commit,
            args.updated_at,
            args.imported_at,
        )
        for problem in base
    ]
    sections = parse_sections(Path(args.source))
    needed = args.total - len(catalog)
    if len(sections) < needed:
        raise SystemExit(f"Only {len(sections)} upstream sections available; need {needed}")
    for offset, section in enumerate(sections[:needed], start=len(catalog) + 1):
        catalog.append(
            convert_section(section, offset, args.commit, args.updated_at, args.imported_at)
        )
    if len(catalog) != args.total:
        raise SystemExit(f"Expected {args.total} items, got {len(catalog)}")
    return catalog


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--updated-at", required=True)
    parser.add_argument("--imported-at", required=True)
    parser.add_argument("--total", type=int, default=200)
    parser.add_argument("--shard", type=int, required=True)
    parser.add_argument("--shard-size", type=int, default=50)
    args = parser.parse_args()
    catalog = build_catalog(args)
    start = args.shard * args.shard_size
    end = min(start + args.shard_size, len(catalog))
    if start >= len(catalog):
        raise SystemExit("Shard starts beyond catalog")
    print(json.dumps(catalog[start:end], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
