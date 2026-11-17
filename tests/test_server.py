import unittest
from unittest.mock import patch

import server


class ProblemBankTests(unittest.TestCase):
    def test_problem_ids_are_unique(self):
        ids = [problem["id"] for problem in server.PROBLEMS]
        self.assertEqual(len(ids), len(set(ids)))

    def test_public_problems_hide_judging_material(self):
        public = server.public_problem(server.PROBLEMS[0])
        self.assertNotIn("review_points", public)
        self.assertNotIn("reference_notes", public)
        self.assertNotIn("hints", public)
        self.assertIn("starter_code", public)


class ReviewNormalizationTests(unittest.TestCase):
    def test_normalize_review_enforces_bounds_and_limits(self):
        review = server.normalize_review(
            {
                "verdict": "unknown",
                "score": 180,
                "summary": "summary",
                "covered": ["a", "b", "c", "d", "e"],
                "key_gaps": ["1", "2", "3", "4"],
                "incorrect_points": ["x", "y", "z"],
            }
        )
        self.assertEqual(review["verdict"], "partial")
        self.assertEqual(review["score"], 100)
        self.assertEqual(len(review["covered"]), 4)
        self.assertEqual(len(review["key_gaps"]), 3)
        self.assertEqual(len(review["incorrect_points"]), 2)

    def test_json_extraction_accepts_fenced_json(self):
        parsed = server.extract_json_object('```json\n{"verdict":"pass"}\n```')
        self.assertEqual(parsed["verdict"], "pass")


class ModelFlowTests(unittest.TestCase):
    @patch("server.call_llm")
    def test_judge_flow_returns_normalized_review(self, call_llm):
        call_llm.return_value = {
            "verdict": "pass",
            "score": 88,
            "summary": "核心思路正确",
            "covered": ["核心点"],
            "key_gaps": [],
            "incorrect_points": [],
            "next_focus": "补充一个权衡",
            "interviewer_follow_up": "这个方案有什么代价？",
        }
        result = server.judge_code(server.PROBLEMS[0], "def solution():\n    return 1")
        self.assertEqual(result["verdict"], "pass")
        self.assertEqual(result["score"], 88)
        context = call_llm.call_args.args[0][1]["content"]
        self.assertIn("candidate_code", context)
        self.assertIn("review_points", context)

    @patch("server.call_llm")
    def test_coach_flow_keeps_requested_action(self, call_llm):
        call_llm.return_value = {"reply": "可以先想想数据从哪里来。", "focus": "数据依据"}
        result = server.coach_reply(
            server.PROBLEMS[0],
            {"action": "hint", "code": "# TODO", "history": []},
        )
        self.assertEqual(result["action"], "hint")
        self.assertIn("数据", result["reply"])


if __name__ == "__main__":
    unittest.main()
