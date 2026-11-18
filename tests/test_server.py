import json
import unittest
from unittest.mock import patch

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
        self.assertEqual(len(decoded), 1_000)
        self.assertNotIn("starter_code", decoded[0])
        self.assertLess(len(server.PUBLIC_CATALOG_GZIP), len(server.PUBLIC_CATALOG_JSON))

    def test_catalog_has_one_thousand_problems(self):
        self.assertEqual(len(server.PROBLEMS), 1_000)

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
        self.assertEqual(counts, {"coding": 200, "algorithm": 435, "knowledge": 365})

    def test_each_base_problem_has_four_traceable_variants(self):
        derived = [
            problem
            for problem in server.PROBLEMS
            if problem["provenance"].get("origin") == "aibag-derived"
        ]
        self.assertEqual(len(derived), 800)
        counts = {}
        for problem in derived:
            base_id = problem["provenance"]["derived_from"]
            counts[base_id] = counts.get(base_id, 0) + 1
        self.assertEqual(len(counts), 200)
        self.assertEqual(set(counts.values()), {4})

    def test_imported_handbook_items_pin_the_upstream_revision(self):
        imported = [
            problem
            for problem in server.PROBLEMS
            if problem["provenance"].get("origin") == "axiaoquan/llm-interview-handbook"
        ]
        self.assertEqual(len(imported), 180)
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
    def test_reference_answer_is_generated_once_and_cached(self, call_llm):
        problem = server.PROBLEMS[0]
        server.ANSWER_CACHE.pop(problem["id"], None)
        call_llm.return_value = {
            "answer": "参考实现：\n```python\ndef solution():\n    return 1\n```\n关键点是保持 shape 一致。"
        }
        first = server.reference_answer(problem)
        second = server.reference_answer(problem)
        self.assertEqual(first, second)
        self.assertEqual(first["source"], "deepseek-generated")
        self.assertIn("参考实现", first["answer"])
        self.assertEqual(call_llm.call_count, 1)
        context = call_llm.call_args.args[0][1]["content"]
        self.assertIn('"kind": "coding"', context)
        self.assertIn("starter_code", context)


if __name__ == "__main__":
    unittest.main()
