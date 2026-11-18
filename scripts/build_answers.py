#!/usr/bin/env python3
"""Build persisted standard answers for the 200 canonical AIBaG questions."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


HEADING = re.compile(r"^(##|###)\s+Q(\d+)\s*[·.-]\s*(.+?)\s*$")
GROUPS = ("llm-coding", "algorithms", "docs")

SOURCE_OVERRIDES = {
    "implement-mha": ("llm-coding/01-attention.md", "Q02"),
    "implement-rope": ("llm-coding/02-position-encoding.md", "Q02"),
    "top-k-frequent": ("algorithms/05-stack-queue.md", "Q07"),
    "implement-rmsnorm": ("llm-coding/03-normalization.md", "Q02"),
    "cross-entropy-from-logits": ("llm-coding/07-loss-rl.md", "Q01"),
    "top-p-sampling-filter": ("llm-coding/05-decoding.md", "Q03"),
    "lora-linear": ("llm-coding/06-peft.md", "Q01"),
    "kv-cache-update": ("llm-coding/01-attention.md", "Q05"),
    "repeat-kv-for-gqa": ("llm-coding/01-attention.md", "Q04"),
    "build-attention-mask": ("llm-coding/01-attention.md", "Q03"),
    "bpe-merge-step": ("llm-coding/04-tokenizer.md", "Q01"),
    "beam-search-step": ("llm-coding/05-decoding.md", "Q05"),
    "dpo-pair-loss": ("llm-coding/07-loss-rl.md", "Q03"),
    "moe-top2-router": ("llm-coding/08-misc.md", "Q01"),
    "coin-change": ("algorithms/11-interview-real-questions.md", "Q01"),
    "spiral-from-center": ("algorithms/11-interview-real-questions.md", "Q06"),
}

MANUAL_ANSWERS = {
    "stable-merge-sort": """核心是归并时遇到相同 key 优先取左侧元素，这样才能保持稳定性。

```python
def stable_merge_sort(items, key=lambda value: value):
    if len(items) <= 1:
        return list(items)
    middle = len(items) // 2
    left = stable_merge_sort(items[:middle], key)
    right = stable_merge_sort(items[middle:], key)
    merged = []
    i = j = 0
    while i < len(left) and j < len(right):
        if key(left[i]) <= key(right[j]):
            merged.append(left[i])
            i += 1
        else:
            merged.append(right[j])
            j += 1
    merged.extend(left[i:])
    merged.extend(right[j:])
    return merged
```

时间复杂度 O(n log n)，额外空间 O(n)。""",
    "three-way-quick-sort": """维护三个区间：`[lo, lt)` 小于 pivot，`[lt, i)` 等于 pivot，`(gt, hi]` 大于 pivot，`[i, gt]` 尚未处理。

```python
def three_way_quick_sort(nums):
    def sort(lo, hi):
        if lo >= hi:
            return
        pivot = nums[lo]
        lt, i, gt = lo, lo + 1, hi
        while i <= gt:
            if nums[i] < pivot:
                nums[lt], nums[i] = nums[i], nums[lt]
                lt += 1
                i += 1
            elif nums[i] > pivot:
                nums[i], nums[gt] = nums[gt], nums[i]
                gt -= 1
            else:
                i += 1
        sort(lo, lt - 1)
        sort(gt + 1, hi)
    sort(0, len(nums) - 1)
    return nums
```

平均时间 O(n log n)，大量重复元素时比二路 partition 更合适；最坏仍为 O(n²)。""",
    "stable-softmax": """先减去每行最大值，避免指数溢出；半精度输入可先转为 float32 计算。

```python
import torch

def stable_softmax(x, dim=-1):
    work = x.float() if x.dtype in (torch.float16, torch.bfloat16) else x
    shifted = work - work.amax(dim=dim, keepdim=True)
    exp = shifted.exp()
    result = exp / exp.sum(dim=dim, keepdim=True)
    return result.to(x.dtype) if result.dtype != x.dtype else result
```

减去常数不改变 softmax；取最大值能保证最大的指数为 1，其余不超过 1。""",
    "implement-swiglu": """SwiGLU 使用两条输入投影，一条经过 SiLU 后与另一条逐元素相乘，再投影回模型维度。

```python
import torch.nn as nn
import torch.nn.functional as F

class SwiGLU(nn.Module):
    def __init__(self, d_model, hidden_dim):
        super().__init__()
        self.gate_proj = nn.Linear(d_model, hidden_dim, bias=False)
        self.up_proj = nn.Linear(d_model, hidden_dim, bias=False)
        self.down_proj = nn.Linear(hidden_dim, d_model, bias=False)

    def forward(self, x):
        gated = F.silu(self.gate_proj(x)) * self.up_proj(x)
        return self.down_proj(gated)
```

输入 `[B,T,d_model]`，两条中间分支都是 `[B,T,hidden_dim]`，输出恢复为 `[B,T,d_model]`。""",
}


def parse_sections(source_root: Path) -> dict[tuple[str, str], dict[str, Any]]:
    sections: dict[tuple[str, str], dict[str, Any]] = {}
    for group in GROUPS:
        for path in sorted((source_root / group).glob("*.md")):
            lines = path.read_text(encoding="utf-8").splitlines()
            matches = [(index, HEADING.match(line)) for index, line in enumerate(lines)]
            matches = [(index, match) for index, match in matches if match]
            for position, (start, match) in enumerate(matches):
                end = matches[position + 1][0] if position + 1 < len(matches) else len(lines)
                relative = path.relative_to(source_root).as_posix()
                code = f"Q{match.group(2)}"
                sections[(relative, code)] = {
                    "title": match.group(3).strip(),
                    "lines": lines[start + 1 : end],
                }
    return sections


def python_blocks(lines: list[str]) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    language = ""
    in_code = False
    for line in lines:
        stripped = line.strip()
        if not in_code and stripped.startswith(("```", "~~~")):
            language = stripped[3:].strip().lower()
            current = []
            in_code = True
            continue
        if in_code and stripped.startswith(("```", "~~~")):
            text = "\n".join(current).strip()
            if language in {"python", "py"} or re.search(r"(?m)^(?:def|class|import|from)\s", text):
                blocks.append(text)
            in_code = False
            continue
        if in_code:
            current.append(line)
    return blocks


def section_answer(problem: dict[str, Any], section: dict[str, Any]) -> str:
    lines = section["lines"]
    if problem["kind"] in {"coding", "algorithm"}:
        blocks = python_blocks(lines)
        if blocks:
            if problem["kind"] == "coding":
                prelude = "import math\nimport torch\nimport torch.nn as nn\nimport torch.nn.functional as F"
                blocks = [prelude, *blocks]
            code_text = "\n\n".join(f"```python\n{block}\n```" for block in blocks)
            notes = problem.get("reference_notes", [])
            note_text = "\n".join(f"- {note}" for note in notes)
            answer = f"参考实现：\n\n{code_text}"
            if note_text:
                answer += f"\n\n关键说明：\n{note_text}"
            return answer[:16_000]
    body = "\n".join(lines).strip()
    body = re.sub(r"\n---\s*$", "", body).strip()
    return body[:16_000]


def load_catalog(catalog_dir: Path) -> list[dict[str, Any]]:
    catalog: list[dict[str, Any]] = []
    for path in sorted(catalog_dir.glob("part-*.json")):
        catalog.extend(json.loads(path.read_text(encoding="utf-8")))
    return catalog


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--catalog", default="data/catalog")
    args = parser.parse_args()
    source_root = Path(args.source)
    sections = parse_sections(source_root)
    catalog = load_catalog(Path(args.catalog))
    answers: dict[str, dict[str, str]] = {}
    for problem in catalog:
        problem_id = problem["id"]
        if problem_id in MANUAL_ANSWERS:
            answer = MANUAL_ANSWERS[problem_id]
            source = "aibag-authored"
        else:
            provenance = problem["provenance"]
            if problem_id in SOURCE_OVERRIDES:
                source_key = SOURCE_OVERRIDES[problem_id]
            else:
                source_key = (
                    provenance["source_path"],
                    provenance["source_section"].split(" · ", 1)[0],
                )
            section = sections.get(source_key)
            if section is None:
                raise SystemExit(f"Missing answer source for {problem_id}: {source_key}")
            answer = section_answer(problem, section)
            source = f"axiaoquan/llm-interview-handbook@8a86e72:{source_key[0]}#{source_key[1]}"
        if len(answer.strip()) < 20:
            raise SystemExit(f"Answer is too short: {problem_id}")
        answers[problem_id] = {"answer": answer.strip(), "source": source}
    if len(answers) != 200:
        raise SystemExit(f"Expected 200 answers, got {len(answers)}")
    print(json.dumps(answers, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
