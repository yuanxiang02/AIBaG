import unittest
from unittest.mock import patch

import server


class QuestionBankTests(unittest.TestCase):
    def test_question_ids_are_unique(self):
        ids = [question["id"] for question in server.QUESTIONS]
        self.assertEqual(len(ids), len(set(ids)))

    def test_public_questions_hide_judging_material(self):
        public = server.public_question(server.QUESTIONS[0])
        self.assertNotIn("core_points", public)
        self.assertNotIn("reference_outline", public)
        self.assertIn("question", public)


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
        result = server.judge_answer(server.QUESTIONS[0], "候选人的回答")
        self.assertEqual(result["verdict"], "pass")
        self.assertEqual(result["score"], 88)
        context = call_llm.call_args.args[0][1]["content"]
        self.assertIn("candidate_answer", context)
        self.assertIn("core_points", context)

    @patch("server.call_llm")
    def test_coach_flow_keeps_requested_action(self, call_llm):
        call_llm.return_value = {"reply": "可以先想想数据从哪里来。", "focus": "数据依据"}
        result = server.coach_reply(
            server.QUESTIONS[0],
            {"action": "hint", "answer": "回答", "history": []},
        )
        self.assertEqual(result["action"], "hint")
        self.assertIn("数据", result["reply"])


if __name__ == "__main__":
    unittest.main()
