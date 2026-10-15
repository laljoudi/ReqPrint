"""Unit tests for ai.plan_subtasks - the model is faked, so no network and no quota.
Run from the repo root:  .venv/bin/python -m unittest discover -s tests -t . -v"""
import json
import unittest
from unittest import mock

import httpx
from groq import BadRequestError, RateLimitError
from pydantic import ValidationError

import ai
from prompts import SUBTASKS_PROMPT

STORIES = [
    {"id": "US-01", "role": "Member", "story": "As a member, I want an overdue email, so that I return books."},
    {"id": "US-02", "role": "Librarian", "story": "As a librarian, I want to add books, so that members can find them."},
    {"id": "US-03", "role": "Member", "story": "As a member, I want to see my name in the header, so that I know I'm signed in."},
]
CRITERIA = [
    {"story_id": "US-01", "scenario": "Reminder", "given": "a loan is due", "when": "the job runs", "then": "an email is sent"},
    {"story_id": "US-01", "scenario": "Returned", "given": "it was returned", "when": "the job runs", "then": "no email"},
    {"story_id": "US-02", "scenario": "Add", "given": "the form", "when": "submitted", "then": "the book exists"},
]


def sub(title="Do the thing", discipline="backend", index=None):
    return ai.SubtaskItem(title=title, discipline=discipline, criterion_index=index)


def answer(**per_story):
    """answer(**{"US-01": [sub(), sub()], ...}) -> a SubtaskPlan (ids with underscores: US_01)."""
    return ai.SubtaskPlan(stories=[ai.StorySubtasks(story_id=k.replace("_", "-"), subtasks=v) for k, v in per_story.items()])


def groq_error(cls, status):
    return cls("boom", response=httpx.Response(status, request=httpx.Request("POST", "https://api.groq.com/x")), body=None)


def plan(chat_result=None, chat_error=None, stories=STORIES, criteria=CRITERIA):
    with mock.patch.object(ai, "_structured_chat", return_value=chat_result, side_effect=chat_error) as chat:
        result = ai.plan_subtasks(stories, criteria)
    return result, chat


GOOD = dict(US_01=[sub("Send overdue reminder email", "backend", 0), sub("Skip returned loans", "backend", 1)],
            US_02=[sub("Add book form", "frontend", 0)], US_03=[sub("Show the name in the header", "frontend", None)])


class ValidAnswers(unittest.TestCase):
    def test_returns_each_story_with_its_subtasks_and_the_criterion_each_came_from(self):
        result, _ = plan(answer(**GOOD))
        self.assertEqual(list(result["plan"]), ["US-01", "US-02", "US-03"])
        self.assertEqual(result["plan"]["US-01"][0], {"title": "Send overdue reminder email", "discipline": "backend",
                                                       "criterion_index": 0, "criterion": CRITERIA[0]})
        self.assertEqual(result["plan"]["US-01"][1]["criterion"], CRITERIA[1])
        self.assertEqual(result["plan"]["US-01"][1]["criterion_index"], 1)
        self.assertEqual(result["plan"]["US-02"][0]["criterion"], CRITERIA[2])
        self.assertEqual(result["plan"]["US-02"][0]["criterion_index"], 0)   # per story, not across the document
        self.assertIsNone(result["plan"]["US-03"][0]["criterion"])            # no criteria: the story text is the source
        self.assertIsNone(result["plan"]["US-03"][0]["criterion_index"])
        self.assertEqual((result["rejected"], result["dropped"]), ([], []))

    def test_asks_with_its_own_prompt_and_schema_and_sends_each_story_only_its_own_criteria(self):
        _, chat = plan(answer(**GOOD))
        prompt, message, schema = chat.call_args.args
        self.assertIs(prompt, SUBTASKS_PROMPT)
        self.assertIs(schema, ai.SubtaskPlan)
        sent = json.loads(message)
        self.assertEqual([s["id"] for s in sent], ["US-01", "US-02", "US-03"])
        self.assertEqual([[c["index"] for c in s["criteria"]] for s in sent], [[0, 1], [0], []])
        self.assertEqual(sent[0]["criteria"][0], {"index": 0, "scenario": "Reminder", "given": "a loan is due", "when": "the job runs", "then": "an email is sent"})
        self.assertNotIn("story_id", message)                          # criteria are nested under their story, not matched by the model

    def test_titles_are_tidied(self):
        result, _ = plan(answer(US_01=[sub("  Send   the\nemail.  ", index=0)], US_02=[sub("Add it", index=0)], US_03=[sub("Show it")]))
        self.assertEqual(result["plan"]["US-01"][0]["title"], "Send the email")

    def test_a_story_left_out_of_the_answer_simply_gets_no_subtasks(self):
        result, _ = plan(answer(US_01=[sub(index=0)], US_03=[sub()]))
        self.assertEqual(sorted(result["plan"]), ["US-01", "US-03"])

    def test_nothing_to_plan_makes_no_call(self):
        result, chat = plan(stories=[], criteria=[])
        self.assertEqual(result, {"plan": {}, "rejected": [], "dropped": []})
        chat.assert_not_called()

    def test_no_criteria_at_all_is_fine_and_falls_back_to_the_story_text(self):
        result, _ = plan(answer(US_01=[sub()], US_02=[sub()], US_03=[sub()]), criteria=[])
        self.assertTrue(all(v[0]["criterion"] is None and v[0]["criterion_index"] is None for v in result["plan"].values()))
        self.assertEqual((result["rejected"], result["dropped"]), ([], []))


class TheCriterionRule(unittest.TestCase):
    """A story WITH criteria: every sub-task must cite one of its own criteria, or it is rejected - never
    rewritten to quote the story. The story-text fallback is for stories with no criteria only."""

    def run_plan(self, **per_story):
        with self.assertLogs(ai.logger, "WARNING"):
            result, _ = plan(answer(**per_story))
        return result

    def test_citing_nothing_is_rejected_not_rewritten_to_the_story_text(self):
        # three sub-tasks, one of them uncited: 1 of 3 rejected is NOT more than half, so the other two stay
        result = self.run_plan(US_01=[sub("A", index=0), sub("B", index=1), sub("Invented", index=None)],
                               US_02=[sub("C", index=0)], US_03=[sub("D")])
        self.assertEqual([t["title"] for t in result["plan"]["US-01"]], ["A", "B"])
        self.assertEqual(result["rejected"], [{"story_id": "US-01", "title": "Invented", "reason": "cited no acceptance criterion"}])
        self.assertEqual(result["dropped"], [])
        self.assertTrue(all(t["criterion"] is not None for t in result["plan"]["US-01"]))  # nothing was quietly turned into a story quote

    def test_an_out_of_range_index_is_rejected(self):
        result = self.run_plan(US_01=[sub("A", index=0), sub("B", index=1), sub("Too high", index=2)],
                               US_02=[sub("C", index=0)], US_03=[sub("D")])
        self.assertEqual(result["rejected"][0]["title"], "Too high")
        self.assertIn("cited criterion 2, but this story only has criteria 0-1", result["rejected"][0]["reason"])
        self.assertEqual([t["title"] for t in result["plan"]["US-01"]], ["A", "B"])

    def test_a_negative_index_is_rejected(self):
        result = self.run_plan(US_01=[sub("A", index=0), sub("B", index=1), sub("Neg", index=-1)], US_02=[sub("C", index=0)], US_03=[sub("D")])
        self.assertEqual([r["title"] for r in result["rejected"]], ["Neg"])

    def test_another_stories_criterion_index_is_judged_against_its_own_story(self):
        # US-02 has one criterion (index 0). Index 1 exists for US-01 but not for US-02.
        result = self.run_plan(US_01=[sub("A", index=0)], US_02=[sub("Borrowed index", index=1)], US_03=[sub("D")])
        self.assertEqual([r["story_id"] for r in result["rejected"]], ["US-02"])
        self.assertEqual(result["dropped"][0]["story_id"], "US-02")   # its only sub-task was rejected: more than half

    def test_a_criterionless_story_may_not_cite_one(self):
        result = self.run_plan(US_01=[sub("A", index=0)], US_02=[sub("C", index=0)], US_03=[sub("Phantom", index=0)])
        self.assertIn("this story has no acceptance criteria", result["rejected"][0]["reason"])
        self.assertNotIn("US-03", result["plan"])

    def test_exactly_half_rejected_keeps_the_rest_more_than_half_drops_the_story(self):
        half = self.run_plan(US_01=[sub("A", index=0), sub("Bad", index=None)], US_02=[sub("C", index=0)], US_03=[sub("D")])
        self.assertEqual([t["title"] for t in half["plan"]["US-01"]], ["A"])   # 1 of 2 is not MORE than half
        self.assertEqual(half["dropped"], [])
        more = self.run_plan(US_01=[sub("A", index=0), sub("Bad1", index=None), sub("Bad2", index=9)], US_02=[sub("C", index=0)], US_03=[sub("D")])
        self.assertNotIn("US-01", more["plan"])                                 # no partial set - not even the good one
        self.assertEqual(len(more["rejected"]), 2)                              # the individual rejections are still listed
        drop = more["dropped"][0]
        self.assertEqual((drop["story_id"], drop["rejected"], drop["total"]), ("US-01", 2, 3))
        self.assertIn("2 of its 3 sub-tasks", drop["reason"])

    def test_dropping_one_story_does_not_touch_the_others(self):
        result = self.run_plan(US_01=[sub("Bad", index=None)], US_02=[sub("C", index=0)], US_03=[sub("D")])
        self.assertEqual(sorted(result["plan"]), ["US-02", "US-03"])

    def test_the_drop_is_logged_with_the_story_and_the_counts(self):
        with self.assertLogs(ai.logger, "WARNING") as logs:
            plan(answer(US_01=[sub("Bad", index=None)], US_02=[sub("C", index=0)], US_03=[sub("D")]))
        text = " ".join(r.getMessage() for r in logs.records)
        self.assertIn("US-01", text)
        self.assertIn("1 of its 1", text)

    def test_every_valid_answer_logs_nothing(self):
        with self.assertNoLogs(ai.logger, "WARNING"):
            plan(answer(**GOOD))

    def test_a_boolean_is_not_a_criterion_index(self):
        raw = ai.SubtaskItem.model_construct(title="x", discipline="qa", criterion_index=True)
        result = self.run_plan(US_01=[raw, sub("A", index=0), sub("B", index=1)], US_02=[sub("C", index=0)], US_03=[sub("D")])
        self.assertEqual([r["title"] for r in result["rejected"]], ["x"])


class RejectedAnswers(unittest.TestCase):
    """Any of these must give None (the push then skips sub-tasks) and a logged warning - never an exception."""

    def assert_rejected(self, chat_result=None, chat_error=None, **kw):
        with self.assertLogs(ai.logger, "WARNING") as logs:
            result, _ = plan(chat_result, chat_error, **kw)
        self.assertIsNone(result)
        self.assertEqual(len(logs.records), 1)

    def test_a_story_id_that_is_not_ours(self):
        self.assert_rejected(answer(US_01=[sub()], US_99=[sub()]))

    def test_the_same_story_twice(self):
        self.assert_rejected(ai.SubtaskPlan(stories=[ai.StorySubtasks(story_id="US-01", subtasks=[sub()]), ai.StorySubtasks(story_id="US-01", subtasks=[sub()])]))

    def test_a_story_with_no_subtasks(self):
        self.assert_rejected(answer(US_01=[], US_02=[sub()], US_03=[sub()]))

    def test_a_story_with_more_than_five(self):
        self.assert_rejected(answer(US_01=[sub(f"T{i}") for i in range(6)], US_02=[sub()], US_03=[sub()]))

    def test_exactly_five_is_allowed(self):
        result, _ = plan(answer(US_01=[sub(f"T{i}", index=0) for i in range(5)], US_02=[sub(index=0)], US_03=[sub()]))
        self.assertEqual(len(result["plan"]["US-01"]), 5)

    def test_an_empty_title(self):
        self.assert_rejected(answer(US_01=[sub("   ")], US_02=[sub()], US_03=[sub()]))
        self.assert_rejected(answer(US_01=[sub("...")], US_02=[sub()], US_03=[sub()]))

    def test_an_empty_answer(self):
        self.assert_rejected(answer())

    def test_malformed_model_output(self):
        try:
            ai.SubtaskPlan.model_validate_json("{not json")
        except ValueError as e:
            self.assert_rejected(chat_error=e)

    def test_a_request_groq_rejected_as_invalid(self):
        self.assert_rejected(chat_error=groq_error(BadRequestError, 400))

    def test_duplicate_ids_in_the_input(self):
        with self.assertLogs(ai.logger, "WARNING"):
            result, chat = plan(stories=[STORIES[0], STORIES[0]])
        self.assertIsNone(result)
        chat.assert_not_called()


class Disciplines(unittest.TestCase):
    def test_only_the_four_allowed_values_exist_at_the_schema_level(self):
        for good in ("backend", "frontend", "qa", "design"):
            self.assertEqual(ai.SubtaskItem(title="x", discipline=good, criterion_index=None).discipline, good)
        for bad in ("devops", "Backend", "", "mobile", "ux", None):
            with self.assertRaises(ValidationError, msg=repr(bad)):
                ai.SubtaskItem(title="x", discipline=bad, criterion_index=None)
        self.assertEqual(ai.SUBTASK_DISCIPLINES, ("backend", "frontend", "qa", "design"))

    def test_the_schema_offers_the_model_exactly_those_four(self):
        schema = ai.SubtaskPlan.model_json_schema()
        self.assertEqual(schema["$defs"]["SubtaskItem"]["properties"]["discipline"]["enum"], ["backend", "frontend", "qa", "design"])

    def test_an_invalid_discipline_in_a_raw_answer_is_a_rejected_answer(self):
        raw = json.dumps({"stories": [{"story_id": "US-01", "subtasks": [{"title": "x", "discipline": "devops", "criterion_index": None}]}]})
        try:
            ai.SubtaskPlan.model_validate_json(raw)
        except ValueError as e:
            with self.assertLogs(ai.logger, "WARNING"):
                result, _ = plan(chat_error=e)
            self.assertIsNone(result)
        else:
            self.fail("should not validate")


class ErrorsThatMustReachTheCaller(unittest.TestCase):
    def test_quota_errors_propagate_so_the_caller_can_tell_busy_from_bad(self):
        with self.assertRaises(RateLimitError):
            plan(chat_error=groq_error(RateLimitError, 429))


class Batching(unittest.TestCase):
    def stories(self, n):
        return [{"id": f"S-{i}", "role": "R", "story": f"story {i}"} for i in range(n)]

    def chat(self, prompt, message, schema):
        ids = [s["id"] for s in json.loads(message)]
        return ai.SubtaskPlan(stories=[ai.StorySubtasks(story_id=i, subtasks=[sub(f"Do {i}")]) for i in ids])

    def test_a_big_document_is_planned_in_batches_and_merged(self):
        stories = self.stories(60)
        with mock.patch.object(ai, "_structured_chat", side_effect=self.chat) as chat:
            result = ai.plan_subtasks(stories, [])
        self.assertEqual([len(json.loads(c.args[1])) for c in chat.call_args_list], [25, 25, 10])
        self.assertEqual(list(result["plan"]), [s["id"] for s in stories])

    def test_a_small_document_is_one_call(self):
        with mock.patch.object(ai, "_structured_chat", side_effect=self.chat) as chat:
            ai.plan_subtasks(self.stories(10), [])
        self.assertEqual(chat.call_count, 1)

    def test_one_bad_batch_skips_everything(self):
        calls = []
        def flaky(prompt, message, schema):
            calls.append(1)
            return ai.SubtaskPlan(stories=[]) if len(calls) == 2 else self.chat(prompt, message, schema)
        with mock.patch.object(ai, "_structured_chat", side_effect=flaky):
            with self.assertLogs(ai.logger, "WARNING"):
                result = ai.plan_subtasks(self.stories(60), [])
        self.assertIsNone(result)
        self.assertEqual(len(calls), 2)                                # and it stopped asking

    def test_an_id_from_another_batch_is_not_ours_to_accept(self):
        def wrong(prompt, message, schema):
            return ai.SubtaskPlan(stories=[ai.StorySubtasks(story_id="S-59", subtasks=[sub()])])
        with mock.patch.object(ai, "_structured_chat", side_effect=wrong):
            with self.assertLogs(ai.logger, "WARNING"):
                self.assertIsNone(ai.plan_subtasks(self.stories(30), []))


class ThePromptKeepsItsHardRules(unittest.TestCase):
    """The behaviour itself is checked against the live model by hand; these pin the wording that asks for it."""

    def test_derive_do_not_invent(self):
        self.assertIn("DERIVE, DON'T INVENT", SUBTASKS_PROMPT)
        self.assertIn("REQUIRED for every sub-task of a story that has criteria", SUBTASKS_PROMPT)
        self.assertIn("is thrown away", SUBTASKS_PROMPT)               # the model is told the rule is enforced
        self.assertIn("deployment", SUBTASKS_PROMPT)               # named only to forbid it

    def test_no_fixed_template(self):
        self.assertIn("NO FIXED TEMPLATE", SUBTASKS_PROMPT)
        self.assertIn("A story whose criteria are all server-side gets no frontend or design sub-task", SUBTASKS_PROMPT)
        self.assertIn("one or two sub-tasks", SUBTASKS_PROMPT)
        self.assertIn("SELF-CHECK", SUBTASKS_PROMPT)               # qa is not a default step

    def test_one_to_five_per_story(self):
        self.assertIn("1 to 5 sub-tasks per story", SUBTASKS_PROMPT)
        self.assertEqual((ai.MIN_SUBTASKS_PER_STORY, ai.MAX_SUBTASKS_PER_STORY), (1, 5))

    def test_no_estimates_and_no_estimate_field_anywhere(self):
        self.assertIn("NO ESTIMATES", SUBTASKS_PROMPT)
        for model in (ai.SubtaskItem, ai.StorySubtasks, ai.SubtaskPlan):
            fields = set(model.model_fields)
            self.assertFalse(fields & {"estimate", "hours", "points", "size", "effort", "priority", "days"}, model.__name__)
        self.assertEqual(set(ai.SubtaskItem.model_fields), {"title", "discipline", "criterion_index"})

    def test_the_schema_suits_groqs_strict_mode(self):
        schema = ai.SubtaskPlan.model_json_schema()
        ai._forbid_additional_properties(schema)
        objects = [schema] + list(schema.get("$defs", {}).values())
        for o in (o for o in objects if o.get("type") == "object"):
            self.assertIs(o["additionalProperties"], False)
            self.assertEqual(set(o["required"]), set(o["properties"]))
        self.assertFalse(any(k in json.dumps(schema) for k in ("maxLength", "minLength", "maxItems", "minItems")))


if __name__ == "__main__":
    unittest.main()
