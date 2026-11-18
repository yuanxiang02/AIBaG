import unittest
from unittest.mock import patch

import server


class ProblemBankTests(unittest.TestCase):
    def test_catalog_has_two_hundred_problems(self):
        self.assertEqual(len(server.PROBLEMS), 200)

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
        self.assertEqual(counts, {"coding": 40, "algorithm": 87, "knowledge": 73})

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


if __name__ == "__main__":
    unittest.main()
