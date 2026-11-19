import json
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import server


class ProblemBankTests(unittest.TestCase):
    def test_catalog_startup_is_strictly_under_five_seconds(self):
        self.assertLess(server.CATALOG_LOAD_SECONDS, server.CATALOG_LOAD_LIMIT_SECONDS)
        self.assertEqual(server.CATALOG_LOAD_LIMIT_SECONDS, 5.0)

    def test_catalog_deadline_raises_after_five_seconds(self):
        with patch(
            "server.time.perf_counter",
            return_value=server.CATALOG_BOOT_STARTED + server.CATALOG_LOAD_LIMIT_SECONDS + 0.001,
        ):
            with self.assertRaises(TimeoutError):
                server.enforce_catalog_deadline("test")

    def test_public_catalog_is_preencoded_and_compressed(self):
        decoded = json.loads(server.PUBLIC_CATALOG_JSON)
        self.assertEqual(len(decoded), 2_000)
        self.assertNotIn("starter_code", decoded[0])
        self.assertLess(len(server.PUBLIC_CATALOG_GZIP), len(server.PUBLIC_CATALOG_JSON))

    def test_every_question_has_an_immediate_persisted_answer(self):
        base_ids = {
            problem["id"]
            for problem in server.PROBLEMS
            if problem["provenance"].get("origin") != "aibag-derived"
        }
        self.assertEqual(set(server.STANDARD_ANSWERS), base_ids)
        for problem in server.PROBLEMS:
            result = server.reference_answer(problem)
            self.assertGreaterEqual(len(result["answer"]), 20, problem["id"])
            self.assertNotEqual(result["source"], "deepseek-generated")

    def test_catalog_has_one_thousand_problems(self):
        self.assertEqual(len(server.PROBLEMS), 2_000)

    def test_problem_ids_are_unique(self):
        ids = [problem["id"] for problem in server.PROBLEMS]
        self.assertEqual(len(ids), len(set(ids)))

    def test_problem_numbers_are_consecutive(self):
        numbers = [problem["number"] for problem in server.PROBLEMS]
        self.assertEqual(numbers, list(range(1, len(server.PROBLEMS) + 1)))

    def test_every_problem_records_a_source(self):
        for problem in server.PROBLEMS:
            self.assertTrue(problem["sources"], problem["id"])
            self.assertTrue(problem["sources"][0].get("url"), problem["id"])
            self.assertTrue(problem["license"], problem["id"])
            self.assertTrue(problem["provenance"].get("imported_at"), problem["id"])

    def test_catalog_has_all_three_interview_kinds(self):
        counts = {
            kind: sum(problem["kind"] == kind for problem in server.PROBLEMS)
            for kind in {"coding", "algorithm", "knowledge"}
        }
        self.assertEqual(counts, {"coding": 480, "algorithm": 800, "knowledge": 720})

    def test_each_base_problem_has_four_traceable_variants(self):
        derived = [
            problem
            for problem in server.PROBLEMS
            if problem["provenance"].get("origin") == "aibag-derived"
        ]
        self.assertEqual(len(derived), 1_750)
        counts = {}
        for problem in derived:
            base_id = problem["provenance"]["derived_from"]
            counts[base_id] = counts.get(base_id, 0) + 1
        self.assertEqual(len(counts), 250)
        self.assertEqual(set(counts.values()), {7})

    def test_imported_handbook_items_pin_the_upstream_revision(self):
        imported = [
            problem
            for problem in server.PROBLEMS
            if problem["provenance"].get("origin") == "axiaoquan/llm-interview-handbook"
        ]
        self.assertEqual(len(imported), 210)
        for problem in imported:
            provenance = problem["provenance"]
            self.assertEqual(
                provenance["upstream_commit"],
                "8a86e722dcdb77de472daefa9401a859deb96f63",
            )
            self.assertEqual(provenance["upstream_updated_at"], "2026-11-15T06:00:07Z")
            self.assertTrue(provenance["source_path"])
            self.assertEqual(problem["license"]["spdx"], "MIT")

    def test_all_generated_starters_are_valid_python(self):
        for problem in server.PROBLEMS:
            starter = problem["starter_code"]
            if starter:
                compile(starter, problem["id"], "exec")
            if problem["kind"] == "knowledge":
                self.assertEqual(starter, "")

    def test_public_problems_hide_judging_material(self):
        public = server.public_problem(server.PROBLEMS[0])
        self.assertNotIn("review_points", public)
        self.assertNotIn("reference_notes", public)
        self.assertNotIn("hints", public)
        self.assertNotIn("review_dimensions", public)
        self.assertNotIn("follow_ups", public)
        self.assertIn("starter_code", public)
        self.assertIn("kind", public)

    def test_catalog_summary_is_lightweight(self):
        summary = server.public_problem_summary(server.PROBLEMS[0])
        self.assertIn("title", summary)
        self.assertIn("summary", summary)
        self.assertNotIn("starter_code", summary)
        self.assertNotIn("description", summary)
        self.assertNotIn("sources", summary)
        self.assertNotIn("provenance", summary)


class ReviewNormalizationTests(unittest.TestCase):
    def test_normalize_review_enforces_bounds_and_limits(self):
        review = server.normalize_review(
            {
                "verdict": "unknown",
                "score": 180,
                "interviewer_response": "这个方向没问题，我们再看一个细节。",
                "strengths": ["a", "b", "c"],
                "focus_issue": "shape 不匹配",
                "nudge": "先写一下每一步的 shape。",
                "follow_up": "拆完 head 后 q 是什么形状？",
            }
        )
        self.assertEqual(review["verdict"], "partial")
        self.assertEqual(review["score"], 100)
        self.assertEqual(len(review["strengths"]), 2)
        self.assertIn("方向", review["interviewer_response"])
        self.assertIn("shape", review["focus_issue"])

    def test_json_extraction_accepts_fenced_json(self):
        parsed = server.extract_json_object('```json\n{"verdict":"pass"}\n```')
        self.assertEqual(parsed["verdict"], "pass")

    def test_coach_parser_accepts_plain_language(self):
        parsed = server.parse_model_content(
            "可以，先把 QKV 沿最后一维拆开。", plain_text_key="reply"
        )
        self.assertIn("QKV", parsed["reply"])

    def test_judge_parser_still_requires_json(self):
        with self.assertRaises(ValueError):
            server.parse_model_content("这不是结构化评审")

    @patch("server.urlopen")
    def test_deepseek_json_mode_repairs_one_invalid_response(self, urlopen):
        class Response:
            def __init__(self, content):
                self.body = json.dumps(
                    {"choices": [{"message": {"content": content}}]}
                ).encode()

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return self.body

        urlopen.side_effect = [Response("不是 JSON"), Response('{"verdict":"partial"}')]
        with patch.dict(
            server.os.environ,
            {"AIBAG_BASE_URL": "https://api.deepseek.com", "AIBAG_API_KEY": "test-key"},
        ):
            result = server.call_llm(
                [{"role": "system", "content": "只返回 JSON object"}]
            )
        self.assertEqual(result["verdict"], "partial")
        self.assertEqual(urlopen.call_count, 2)
        for call in urlopen.call_args_list:
            body = json.loads(call.args[0].data.decode())
            self.assertEqual(body["response_format"], {"type": "json_object"})
        retry_body = json.loads(urlopen.call_args_list[1].args[0].data.decode())
        self.assertEqual(retry_body["temperature"], 0)
        self.assertIn("合法 JSON", retry_body["messages"][-1]["content"])


class ModelFlowTests(unittest.TestCase):
    @patch("server.call_llm")
    def test_judge_flow_returns_normalized_review(self, call_llm):
        call_llm.return_value = {
            "verdict": "pass",
            "score": 88,
            "interviewer_response": "整体方向是对的，这段实现已经把核心逻辑接上了。",
            "strengths": ["核心点"],
            "focus_issue": "",
            "nudge": "可以再想想显存开销。",
            "follow_up": "这个方案有什么代价？",
        }
        result = server.judge_code(server.PROBLEMS[0], "def solution():\n    return 1")
        self.assertEqual(result["verdict"], "pass")
        self.assertEqual(result["score"], 88)
        self.assertIn("方向", result["interviewer_response"])
        context = call_llm.call_args.args[0][1]["content"]
        self.assertIn("candidate_submission", context)
        self.assertIn("review_points", context)
        self.assertIn('"kind": "coding"', context)
        self.assertIn('"code_execution": false', context)
        self.assertNotIn("plain_text_key", call_llm.call_args.kwargs)

    @patch("server.call_llm")
    def test_coach_flow_keeps_requested_action(self, call_llm):
        call_llm.return_value = {"reply": "可以先想想数据从哪里来。", "focus": "数据依据"}
        result = server.coach_reply(
            server.PROBLEMS[0],
            {"action": "hint", "code": "# TODO", "history": []},
        )
        self.assertEqual(result["action"], "hint")
        self.assertIn("数据", result["reply"])
        context = call_llm.call_args.args[0][1]["content"]
        self.assertIn('"runtime_prints": false', context)
        self.assertIn("candidate_submission", context)
        self.assertEqual(call_llm.call_args.kwargs["plain_text_key"], "reply")

    @patch("server.call_llm")
    def test_knowledge_coach_runs_pe_before_reply(self, call_llm):
        problem = next(item for item in server.PROBLEMS if item["kind"] == "knowledge")
        call_llm.return_value = {
            "pe": {
                "state": "partial",
                "level": 2,
                "evidence": "已经说到封闭性",
                "core_gap": "还没解释为什么",
                "strategy": "probe",
            },
            "reply": "封闭性这个点是对的，你再想想它为什么能保证线性组合仍在集合里？",
            "focus": "封闭性的原因",
        }
        result = server.coach_reply(
            problem,
            {"action": "follow_up", "code": "我记得要满足加法和数乘封闭。", "history": []},
        )
        self.assertEqual(result["pe"]["state"], "partial")
        self.assertEqual(result["pe"]["level"], 2)
        self.assertEqual(result["pe"]["strategy"], "probe")
        self.assertIn("为什么", result["reply"])
        self.assertIsNone(call_llm.call_args.kwargs["plain_text_key"])
        self.assertIn("Proficiency Evaluation", call_llm.call_args.args[0][0]["content"])

    @patch("server.call_llm")
    def test_reference_answer_does_not_call_the_model(self, call_llm):
        problem = server.PROBLEMS[0]
        result = server.reference_answer(problem)
        self.assertIn("```python", result["answer"])
        call_llm.assert_not_called()

    def test_derived_answer_includes_variant_guidance(self):
        problem = next(
            item
            for item in server.PROBLEMS
            if item["provenance"].get("origin") == "aibag-derived"
        )
        result = server.reference_answer(problem)
        self.assertIn("本题训练视角补充", result["answer"])

    def test_call_llm_raises_friendly_message_when_remote_api_key_is_missing(self):
        with patch.dict(
            server.os.environ,
            {"AIBAG_BASE_URL": "https://api.deepseek.com", "AIBAG_API_KEY": ""},
            clear=False,
        ), patch("server.resolve_api_key", return_value=""):
            with self.assertRaises(RuntimeError) as ctx:
                server.call_llm([{"role": "user", "content": "hello"}])
            self.assertIn("未检测到 API Key", str(ctx.exception))


class CustomProblemBankTests(unittest.TestCase):
    def test_add_load_and_delete_custom_problems(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            custom_path = Path(tmpdir) / "custom_problems.json"
            created = server.add_custom_problems(
                {
                    "title": "DeepSeek MLA 低秩 KV 压缩推导",
                    "kind": "knowledge",
                    "difficulty": "Hard",
                    "category": "大模型推理",
                    "tags": "MLA, KV Cache, DeepSeek",
                    "description": "请推导 MLA 的低秩联合压缩与矩阵吸收机制。",
                    "review_points": "低秩投影\n矩阵吸收\nDecoupled RoPE",
                    "answer": "通过将 KV 压缩到低维潜向量并在注意力计算时吸收解压矩阵，大幅降低显存占用。",
                },
                path=custom_path,
            )
            self.assertEqual(len(created), 1)
            item = created[0]
            self.assertTrue(item["is_custom"])
            self.assertEqual(item["number"], len(server.PROBLEMS) + 1)
            self.assertEqual(item["kind"], "knowledge")
            self.assertIn("自建面经", item["tags"])
            self.assertEqual(len(item["review_points"]), 3)

            loaded = server.load_custom_problems(path=custom_path)
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0]["id"], item["id"])

            found = server.get_problem_by_id(item["id"], path=custom_path)
            self.assertIsNotNone(found)
            ans = server.reference_answer(found)
            self.assertEqual(ans["source"], "user-custom")
            self.assertIn("吸收解压矩阵", ans["answer"])

            all_summaries = server.all_public_problem_summaries(path=custom_path)
            self.assertEqual(len(all_summaries), len(server.PROBLEMS) + 1)
            self.assertTrue(all_summaries[-1]["is_custom"])

            deleted = server.delete_custom_problem(item["id"], path=custom_path)
            self.assertTrue(deleted)
            self.assertEqual(len(server.load_custom_problems(path=custom_path)), 0)

    def test_batch_custom_import_deduplicates_ids_and_generates_fallback_answer(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            custom_path = Path(tmpdir) / "custom_problems.json"
            created = server.add_custom_problems(
                {
                    "problems": [
                        {
                            "id": "my-attn",
                            "title": "手撕 FlashAttention Tiling",
                            "kind": "AI Infra",
                            "description": "用 PyTorch 模拟分块 Online Softmax。",
                        },
                        {
                            "id": "my-attn",
                            "title": "手撕 FlashAttention Tiling 二面变体",
                            "kind": "coding",
                            "description": "加上 causal mask 处理。",
                        },
                    ]
                },
                path=custom_path,
            )
            self.assertEqual(len(created), 2)
            self.assertNotEqual(created[0]["id"], created[1]["id"])
            self.assertEqual(created[0]["kind"], "coding")
            fallback = server.reference_answer(created[0])
            self.assertIn("自建面经参考要点", fallback["answer"])

    def test_update_custom_problem_preserves_id_and_updates_fields(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            custom_path = Path(tmpdir) / "custom_problems.json"
            created = server.add_custom_problems(
                {
                    "title": "初始标题",
                    "kind": "knowledge",
                    "difficulty": "Easy",
                    "category": "一面",
                    "tags": "TagA",
                    "description": "初始描述内容",
                    "review_points": "要点1",
                    "answer": "初始答案",
                },
                path=custom_path,
            )[0]

            updated = server.update_custom_problem(
                {
                    "id": created["id"],
                    "title": "更新后的标题",
                    "kind": "coding",
                    "difficulty": "Hard",
                    "category": "二面算子",
                    "tags": "CUDA, Triton",
                    "description": "更新后的算子实现描述",
                    "starter_code": "def kernel(x):\n    return x\n",
                    "review_points": "要点A\n要点B",
                    "answer": "def kernel(x):\n    return x * 2\n",
                },
                path=custom_path,
            )
            self.assertEqual(updated["id"], created["id"])
            self.assertEqual(updated["title"], "更新后的标题")
            self.assertEqual(updated["kind"], "coding")
            self.assertEqual(updated["difficulty"], "Hard")
            self.assertIn("Triton", updated["tags"])
            self.assertEqual(len(updated["review_points"]), 2)

            reloaded = server.get_problem_by_id(created["id"], path=custom_path)
            self.assertEqual(reloaded["title"], "更新后的标题")
            self.assertEqual(server.reference_answer(reloaded)["answer"], "def kernel(x):\n    return x * 2")


if __name__ == "__main__":
    unittest.main()
