"""Unit tests for ai.plan_story_order - the model is faked, so no network and no
quota. Run from the repo root:
    .venv/bin/python -m unittest discover -s tests -t . -v"""
import json
import unittest
from unittest import mock

import httpx
from groq import BadRequestError, RateLimitError

import ai
from prompts import STORY_ORDER_PROMPT

STORIES = [
    {"id": "US-01", "role": "Member", "story": "As a member, I want to sign in, so that I can reserve books"},
    {"id": "US-02", "role": "Member", "story": "As a member, I want to reserve a book, so that it is held for me"},
    {"id": "US-03", "role": "Librarian", "story": "As a librarian, I want to add books, so that the catalogue is current"},
]
DOC_ORDER = ["US-01", "US-02", "US-03"]


def plan(*items):
    return ai.StoryOrderPlan(ordered_stories=[ai.StoryOrderItem(story_id=i, reason=r, depends_on=d) for i, r, d in items])


def groq_error(cls, status):
    request = httpx.Request("POST", "https://api.groq.com/x")
    return cls("boom", response=httpx.Response(status, request=request), body=None)


def ids_of(result):
    return [r["story_id"] for r in result]


class ValidOrder(unittest.TestCase):
    def test_returns_the_models_order_with_reasons_and_dependencies(self):
        model = plan(("US-03", "Books must exist first.", []), ("US-01", "Sign-in gates everything.", []), ("US-02", "Needs books and a member.", ["US-01", "US-03"]))
        with mock.patch.object(ai, "_structured_chat", return_value=model):
            result = ai.plan_story_order(STORIES)
        self.assertEqual(ids_of(result), ["US-03", "US-01", "US-02"])
        self.assertEqual(result[2], {"story_id": "US-02", "reason": "Needs books and a member.", "depends_on": ["US-01", "US-03"]})

    def test_asks_with_the_ordering_prompt_and_schema_and_only_id_role_story(self):
        with mock.patch.object(ai, "_structured_chat", return_value=plan(*[(i, "r", []) for i in DOC_ORDER])) as chat:
            ai.plan_story_order([{**s, "acceptance_criteria": "SECRET-EXTRA"} for s in STORIES])
        prompt, message, schema = chat.call_args.args
        self.assertIs(prompt, STORY_ORDER_PROMPT)
        self.assertIs(schema, ai.StoryOrderPlan)
        self.assertEqual(json.loads(message), [{"id": s["id"], "role": s["role"], "story": s["story"]} for s in STORIES])

    def test_tidies_whitespace_and_bad_dependencies(self):
        model = plan((" US-02 ", " why ", ["US-02", "NOPE", "US-01", "US-01"]), ("US-01", "r", []), ("US-03", "r", [" US-01"]))
        with mock.patch.object(ai, "_structured_chat", return_value=model):
            result = ai.plan_story_order(STORIES)
        self.assertEqual(ids_of(result), ["US-02", "US-01", "US-03"])
        self.assertEqual(result[0], {"story_id": "US-02", "reason": "why", "depends_on": ["US-01"]})  # self, unknown, duplicate dropped
        self.assertEqual(result[2]["depends_on"], ["US-01"])


class FallsBackToDocumentOrder(unittest.TestCase):
    def assert_fallback(self, result):
        self.assertEqual(ids_of(result), DOC_ORDER)
        self.assertTrue(all(r["reason"] == ai.FALLBACK_ORDER_REASON and r["depends_on"] == [] for r in result))

    def run_with(self, chat_result=None, chat_error=None):
        with mock.patch.object(ai, "_structured_chat", return_value=chat_result, side_effect=chat_error):
            with self.assertLogs(ai.logger, "WARNING") as logs:
                result = ai.plan_story_order(STORIES)
        self.assertEqual(len(logs.records), 1)
        return result

    def test_missing_story(self):
        self.assert_fallback(self.run_with(plan(("US-02", "r", []), ("US-01", "r", []))))

    def test_unknown_story(self):
        self.assert_fallback(self.run_with(plan(("US-01", "r", []), ("US-02", "r", []), ("US-03", "r", []), ("US-99", "r", []))))

    def test_invented_id_in_place_of_a_real_one(self):
        self.assert_fallback(self.run_with(plan(("US-01", "r", []), ("US-02", "r", []), ("US-99", "r", []))))

    def test_duplicated_story(self):
        self.assert_fallback(self.run_with(plan(("US-01", "r", []), ("US-01", "r", []), ("US-02", "r", []), ("US-03", "r", []))))

    def test_empty_answer(self):
        self.assert_fallback(self.run_with(plan()))

    def test_malformed_model_output(self):
        try:
            ai.StoryOrderPlan.model_validate_json("{not json")
        except ValueError as e:
            self.assert_fallback(self.run_with(chat_error=e))

    def test_request_rejected_by_groq_as_invalid(self):
        self.assert_fallback(self.run_with(chat_error=groq_error(BadRequestError, 400)))

    def test_never_raises_for_any_of_the_above(self):
        with mock.patch.object(ai, "_structured_chat", return_value=plan(("nope", "r", []))):
            with self.assertLogs(ai.logger, "WARNING"):
                self.assertEqual(len(ai.plan_story_order(STORIES)), 3)


class ErrorsThatMustReachTheCaller(unittest.TestCase):
    def test_quota_errors_propagate_so_call_groq_can_map_them(self):
        with mock.patch.object(ai, "_structured_chat", side_effect=groq_error(RateLimitError, 429)):
            with self.assertRaises(RateLimitError):
                ai.plan_story_order(STORIES)


class NothingToOrder(unittest.TestCase):
    def test_no_stories_no_call(self):
        with mock.patch.object(ai, "_structured_chat") as chat:
            self.assertEqual(ai.plan_story_order([]), [])
        chat.assert_not_called()

    def test_one_story_no_call(self):
        with mock.patch.object(ai, "_structured_chat") as chat:
            result = ai.plan_story_order(STORIES[:1])
        chat.assert_not_called()
        self.assertEqual(ids_of(result), ["US-01"])

    def test_duplicate_input_ids_keep_document_order_without_a_call(self):
        dupes = [STORIES[0], STORIES[0], STORIES[1]]
        with mock.patch.object(ai, "_structured_chat") as chat:
            with self.assertLogs(ai.logger, "WARNING"):
                result = ai.plan_story_order(dupes)
        chat.assert_not_called()
        self.assertEqual(ids_of(result), ["US-01", "US-01", "US-02"])


class SchemaIsGroqStrictCompatible(unittest.TestCase):
    def test_every_object_forbids_additional_properties(self):
        schema = ai.StoryOrderPlan.model_json_schema()
        ai._forbid_additional_properties(schema)
        objects = [schema] + list(schema.get("$defs", {}).values())
        self.assertTrue(all(o["additionalProperties"] is False for o in objects if o.get("type") == "object"))
        for o in objects:
            if o.get("type") == "object":
                self.assertEqual(set(o["required"]), set(o["properties"]))  # strict mode: all fields required


class PromptStaysInItsLane(unittest.TestCase):
    def test_orders_only_and_forbids_sizing(self):
        text = STORY_ORDER_PROMPT.lower()
        self.assertIn("do not estimate", text)
        self.assertIn("story points", text)  # named only to forbid it
        self.assertIn("every story id appears exactly once", text)


if __name__ == "__main__":
    unittest.main()
