"""Unit tests for jira_client's own logic - key derivation, ADF, the request
bodies for epics/stories/sprints, and the ordered sprint move. The HTTP layer
(jira_request) is faked, so no network. Run from the repo root:
    .venv/bin/python -m unittest discover -s tests -t . -v"""
import asyncio
import os
import unittest
from unittest import mock

from cryptography.fernet import Fernet

# jira_oauth (imported by jira_client) fails fast without these; fake values are
# fine for tests, and setdefault leaves any real ones alone.
for _name, _value in {
    "JIRA_CLIENT_ID": "test-id",
    "JIRA_CLIENT_SECRET": "test-secret",
    "JIRA_REDIRECT_URI": "http://localhost:8000/api/jira/callback",
    "FRONTEND_ORIGIN": "http://localhost:8000",
    "SESSION_SECRET": Fernet.generate_key().decode(),
    "APP_ENV": "local",
}.items():
    os.environ.setdefault(_name, _value)

import jira_client as jc  # noqa: E402


def run(coro):
    return asyncio.run(coro)


class Recorder:
    """Stands in for jira_client.jira_request: records calls, answers from a script."""

    def __init__(self, *responses):
        self.calls = []
        self._responses = list(responses)

    async def __call__(self, cloud_id, token, method, path, *, params=None, json=None):
        self.calls.append({"method": method, "path": path, "params": params, "json": json})
        response = self._responses.pop(0) if self._responses else {"id": "1", "key": "K-1"}
        if isinstance(response, Exception):
            raise response
        return response


class ProjectKey(unittest.TestCase):
    def test_several_words_use_their_initials(self):
        self.assertEqual(jc.derive_project_key("Library Booking System"), "LBS")
        self.assertEqual(jc.derive_project_key("e-commerce site"), "ECS")
        self.assertEqual(jc.derive_project_key("a b"), "AB")

    def test_initials_are_capped_at_ten(self):
        self.assertEqual(jc.derive_project_key("Point of Sale System for Cafes and Restaurants Online"), "POSSFCARO")
        self.assertEqual(len(jc.derive_project_key(" ".join("word" for _ in range(30)))), 10)

    def test_a_single_word_keeps_the_old_behaviour(self):
        self.assertEqual(jc.derive_project_key("Library"), "LIBRARY")
        self.assertEqual(jc.derive_project_key("ReqPrint"), "REQPRINT")
        self.assertEqual(jc.derive_project_key("Supercalifragilistic"), "SUPERCALIF")

    def test_digits_and_punctuation_are_dropped(self):
        self.assertEqual(jc.derive_project_key("3D Printer!"), "DP")
        self.assertEqual(jc.derive_project_key("Project 2024 Plan"), "PP")

    def test_unusable_initials_fall_back_to_the_leading_letters(self):
        self.assertEqual(jc.derive_project_key("Élan Vital"), "LANVITAL")  # É is not A-Z
        self.assertEqual(jc.derive_project_key("Booking نظام"), "BOOKING")

    def test_names_with_no_latin_letters_get_a_fixed_key(self):
        for name in ("نظام الحجز", "x", "", "١٢٣", "!!"):
            self.assertEqual(jc.derive_project_key(name), "PRJ", name)

    def test_always_valid_for_jira(self):
        for name in ("Library Booking System", "x", "Élan", "a b c d e f g h i j k l", "ﬁnance ﬁrst"):
            key = jc.derive_project_key(name)
            self.assertRegex(key, r"^[A-Z]{2,10}$", name)

    def test_collision_retry_still_appends_a_number_within_ten_characters(self):
        self.assertEqual([jc._key_for_attempt("LBS", n) for n in range(1, 6)], ["LBS", "LBS2", "LBS3", "LBS4", "LBS5"])
        self.assertEqual(jc._key_for_attempt("LIBRARYBOO", 5), "LIBRARYBO5")


class Adf(unittest.TestCase):
    def test_paragraph_with_bold_label(self):
        node = jc.adf_paragraph(("Role:", "Librarian"))
        self.assertEqual(node["content"][0], {"type": "text", "text": "Role: ", "marks": [{"type": "strong"}]})
        self.assertEqual(node["content"][1], {"type": "text", "text": "Librarian"})

    def test_bullet_list_shape(self):
        node = jc.adf_bullets(["one", ("Given", "two")])
        self.assertEqual(node["type"], "bulletList")
        self.assertEqual([i["type"] for i in node["content"]], ["listItem", "listItem"])
        self.assertEqual(node["content"][0]["content"][0], {"type": "paragraph", "content": [{"type": "text", "text": "one"}]})

    def test_document_wrapper_and_never_empty(self):
        doc = jc.adf_document(jc.adf_paragraph("hi"))
        self.assertEqual((doc["type"], doc["version"]), ("doc", 1))
        self.assertEqual(jc.adf_document()["content"], [{"type": "paragraph", "content": []}])  # ADF forbids an empty doc

    def test_no_text_node_is_ever_empty(self):
        for node in (jc.adf_paragraph(""), jc.adf_paragraph("   "), jc.adf_paragraph(("Label", "")), jc.adf_paragraph(("", "x"))):
            self.assertTrue(all(t["text"] for t in node["content"]))

    def test_plain_text_becomes_one_paragraph_per_line(self):
        doc = jc.adf_from_text("first line\n\n  second   line  \n")
        self.assertEqual([p["content"][0]["text"] for p in doc["content"]], ["first line", "second line"])

    def test_whitespace_and_newlines_inside_text_are_collapsed(self):
        self.assertEqual(jc.adf_paragraph("a\n  b\tc")["content"][0]["text"], "a b c")

    def test_heading(self):
        self.assertEqual(jc.adf_heading("Assumptions"), {"type": "heading", "attrs": {"level": 3}, "content": [{"type": "text", "text": "Assumptions"}]})


class Summary(unittest.TestCase):
    def test_short_text_is_unchanged_and_one_line(self):
        self.assertEqual(jc._summary("As a member,\n I want   x"), "As a member, I want x")

    def test_long_text_is_cut_under_jiras_limit_with_an_ellipsis(self):
        out = jc._summary("word " * 200)
        self.assertLessEqual(len(out), 254)
        self.assertTrue(out.endswith("…"))


class ErrorText(unittest.TestCase):
    def test_describe_includes_status_only_when_there_is_one(self):
        self.assertEqual(jc.JiraApiError(400, "bad field").describe(), "Jira returned HTTP 400: bad field")
        self.assertEqual(jc.JiraApiError(None, "Could not reach Jira").describe(), "Could not reach Jira")


class ResolveIssueTypes(unittest.TestCase):
    def types(self, *names, **levels):
        return {"issueTypes": [{"id": str(i), "name": n, "subtask": n == "Sub-task", "hierarchyLevel": levels.get(n, -1 if n == "Sub-task" else 0)} for i, n in enumerate(names, 10)], "total": len(names)}

    def test_finds_epic_and_story(self):
        with mock.patch.object(jc, "jira_request", Recorder(self.types("Task", "Story", "Epic", "Bug", "Sub-task", Epic=1))):
            result = run(jc.resolve_issue_types("c", "t", "KEY"))
        self.assertEqual(result, {"epic": {"id": "12", "name": "Epic"}, "story": {"id": "11", "name": "Story"}})

    def test_falls_back_to_task_when_there_is_no_story(self):
        with mock.patch.object(jc, "jira_request", Recorder(self.types("Epic", "Task", "Bug", Epic=1))):
            self.assertEqual(run(jc.resolve_issue_types("c", "t", "KEY"))["story"], {"id": "11", "name": "Task"})

    def test_finds_the_epic_by_hierarchy_level_when_it_is_renamed(self):
        with mock.patch.object(jc, "jira_request", Recorder(self.types("Feature", "Story", Feature=1))):
            self.assertEqual(run(jc.resolve_issue_types("c", "t", "KEY"))["epic"]["name"], "Feature")

    def test_subtasks_are_never_chosen(self):
        with mock.patch.object(jc, "jira_request", Recorder({"issueTypes": [{"id": "1", "name": "Epic", "subtask": False, "hierarchyLevel": 1}, {"id": "2", "name": "Task", "subtask": True}], "total": 2})):
            with self.assertRaises(jc.JiraSetupError) as ctx:
                run(jc.resolve_issue_types("c", "t", "KEY"))
        self.assertEqual(ctx.exception.code, "no_story_issue_type")

    def test_no_epic_type(self):
        with mock.patch.object(jc, "jira_request", Recorder(self.types("Story", "Task"))):
            with self.assertRaises(jc.JiraSetupError) as ctx:
                run(jc.resolve_issue_types("c", "t", "KEY"))
        self.assertEqual(ctx.exception.code, "no_epic_issue_type")
        self.assertIn("Story, Task", ctx.exception.message)

    def test_reads_every_page(self):
        p1 = {"issueTypes": [{"id": "1", "name": "Bug"}], "total": 3}
        p2 = {"issueTypes": [{"id": "2", "name": "Epic", "hierarchyLevel": 1}, {"id": "3", "name": "Story"}], "total": 3}
        rec = Recorder(p1, p2)
        with mock.patch.object(jc, "jira_request", rec):
            result = run(jc.resolve_issue_types("c", "t", "KEY"))
        self.assertEqual((result["epic"]["id"], result["story"]["id"]), ("2", "3"))
        self.assertEqual([c["params"]["startAt"] for c in rec.calls], [0, 1])
        self.assertEqual(rec.calls[0]["path"], "/rest/api/3/issue/createmeta/KEY/issuetypes")


class EpicNameField(unittest.TestCase):
    def find(self, response):
        with mock.patch.object(jc, "jira_request", Recorder(response)):
            return run(jc.find_epic_name_field("c", "t", "KEY", "10000"))

    def test_found_by_name(self):
        self.assertEqual(self.find({"fields": [{"fieldId": "summary", "name": "Summary"}, {"fieldId": "customfield_10011", "name": "Epic Name", "schema": {"type": "string"}}], "total": 2}), "customfield_10011")

    def test_found_by_field_type(self):
        self.assertEqual(self.find({"fields": [{"fieldId": "customfield_10005", "name": "Titel", "schema": {"custom": "com.pyxis.greenhopper.jira:gh-epic-label"}}], "total": 1}), "customfield_10005")

    def test_absent_means_none(self):
        self.assertIsNone(self.find({"fields": [{"fieldId": "summary", "name": "Summary"}], "total": 1}))

    def test_a_non_auth_failure_means_none(self):
        with mock.patch.object(jc, "jira_request", Recorder(jc.JiraApiError(500, "boom"))):
            with self.assertLogs(jc.logger, "WARNING"):
                self.assertIsNone(run(jc.find_epic_name_field("c", "t", "KEY", "10000")))

    def test_an_auth_failure_is_not_swallowed(self):
        with mock.patch.object(jc, "jira_request", Recorder(jc.JiraApiError(401, "no"))):
            with self.assertRaises(jc.JiraApiError):
                run(jc.find_epic_name_field("c", "t", "KEY", "10000"))


class CreateEpic(unittest.TestCase):
    def create(self, **overrides):
        rec = Recorder({"id": "1", "key": "LBS-1"})
        kwargs = dict(project_key="LBS", issue_type_id="10000", name="Library Booking System", functional=["F1", "F2"], non_functional=["N1"], assumptions=["A1"])
        with mock.patch.object(jc, "jira_request", rec):
            key = run(jc.create_epic("c", "t", **{**kwargs, **overrides}))
        return key, rec.calls[0]

    def test_posts_the_epic_and_returns_its_key(self):
        issue, call = self.create()
        self.assertEqual((issue.key, issue.labels_dropped), ("LBS-1", None))
        self.assertEqual((call["method"], call["path"]), ("POST", "/rest/api/3/issue"))
        fields = call["json"]["fields"]
        self.assertEqual(fields["project"], {"key": "LBS"})
        self.assertEqual(fields["issuetype"], {"id": "10000"})
        self.assertEqual(fields["summary"], "Library Booking System")
        self.assertNotIn("parent", fields)

    def test_description_has_the_three_sections_as_headed_bullet_lists(self):
        content = self.create()[1]["json"]["fields"]["description"]["content"]
        self.assertEqual([n["type"] for n in content], ["heading", "bulletList"] * 3)
        titles = [n["content"][0]["text"] for n in content if n["type"] == "heading"]
        self.assertEqual(titles, ["Functional requirements", "Non-functional requirements", "Assumptions"])
        bullets = [[i["content"][0]["content"][0]["text"] for i in n["content"]] for n in content if n["type"] == "bulletList"]
        self.assertEqual(bullets, [["F1", "F2"], ["N1"], ["A1"]])

    def test_empty_sections_are_left_out(self):
        content = self.create(non_functional=[" ", ""], assumptions=[])[1]["json"]["fields"]["description"]["content"]
        self.assertEqual([n["content"][0]["text"] for n in content if n["type"] == "heading"], ["Functional requirements"])

    def test_sets_epic_name_only_when_the_field_is_known(self):
        self.assertNotIn("customfield_10011", self.create()[1]["json"]["fields"])
        self.assertEqual(self.create(epic_name_field_id="customfield_10011")[1]["json"]["fields"]["customfield_10011"], "Library Booking System")


class CreateStory(unittest.TestCase):
    STORY = {"id": "US-01", "role": "Member", "story": "As a member, I want to reserve a book, so that it is held for me"}
    CRITERIA = [
        {"scenario": "Book is available", "given": "a book is on the shelf", "when": "I reserve it", "then": "it is held for 3 days"},
        {"scenario": "Book is out", "given": "all copies are lent", "when": "I reserve it", "then": ""},
    ]

    def create(self, story=None, criteria=None):
        rec = Recorder({"id": "2", "key": "LBS-2"})
        with mock.patch.object(jc, "jira_request", rec):
            key = run(jc.create_story("c", "t", project_key="LBS", issue_type_id="10001", epic_key="LBS-1", story=story or self.STORY, criteria=self.CRITERIA if criteria is None else criteria))
        return key, rec.calls[0]["json"]["fields"]

    def test_parents_to_the_epic_and_uses_the_statement_as_summary(self):
        issue, fields = self.create()
        self.assertEqual(issue.key, "LBS-2")
        self.assertEqual(fields["parent"], {"key": "LBS-1"})
        self.assertEqual(fields["issuetype"], {"id": "10001"})
        self.assertEqual(fields["summary"], self.STORY["story"])

    def test_description_has_role_then_given_when_then_per_scenario(self):
        content = self.create()[1]["description"]["content"]
        self.assertEqual([n["type"] for n in content], ["paragraph", "heading", "paragraph", "bulletList", "paragraph", "bulletList"])
        self.assertEqual([t["text"] for t in content[0]["content"]], ["Role: ", "Member"])
        first = [[t["text"] for t in i["content"][0]["content"]] for i in content[3]["content"]]
        self.assertEqual(first, [["Given ", "a book is on the shelf"], ["When ", "I reserve it"], ["Then ", "it is held for 3 days"]])
        self.assertEqual(len(content[5]["content"]), 2)  # the empty "then" is left out

    def test_a_story_without_criteria_or_role_still_gets_a_valid_description(self):
        content = self.create(story={"id": "US-9", "role": "", "story": "Do a thing"}, criteria=[])[1]["description"]["content"]
        self.assertEqual(content, [{"type": "paragraph", "content": []}])

    def test_a_statement_too_long_for_the_summary_is_kept_whole_in_the_description(self):
        long = "As a member " + "x " * 200
        fields = self.create(story={"id": "US-9", "role": "R", "story": long})[1]
        self.assertLessEqual(len(fields["summary"]), 254)
        first = fields["description"]["content"][0]["content"]
        self.assertEqual((first[0]["text"], first[1]["text"]), ("Story: ", " ".join(long.split())))


class Sprints(unittest.TestCase):
    def test_create_sprint_sends_only_a_name_and_the_board_so_it_stays_in_the_future(self):
        rec = Recorder({"id": 37, "name": "S1", "state": "future", "originBoardId": 5})
        with mock.patch.object(jc, "jira_request", rec):
            result = run(jc.create_sprint("c", "t", 5, "S1"))
        self.assertEqual(result, {"id": 37, "name": "S1", "state": "future", "dates_set": False, "dates_error": None})
        call = rec.calls[0]
        self.assertEqual((call["method"], call["path"], call["json"]), ("POST", "/rest/agile/1.0/sprint", {"name": "S1", "originBoardId": 5}))

    def move(self, keys, *responses):
        rec = Recorder(*responses)
        with mock.patch.object(jc, "jira_request", rec):
            return run(jc.move_issues_to_sprint("c", "t", 37, keys)), rec.calls

    def test_moves_each_issue_ranked_after_the_previous_one(self):
        result, calls = self.move(["K-1", "K-2", "K-3"], None, None, None)
        self.assertEqual(result, {"moved": ["K-1", "K-2", "K-3"], "failed": {}, "stopped": None})
        self.assertEqual([c["path"] for c in calls], ["/rest/agile/1.0/sprint/37/issue"] * 3)
        self.assertEqual([c["json"] for c in calls], [
            {"issues": ["K-1"]},
            {"issues": ["K-2"], "rankAfterIssue": "K-1"},
            {"issues": ["K-3"], "rankAfterIssue": "K-2"},
        ])

    def test_a_failed_issue_is_skipped_and_the_next_ranks_after_the_last_success(self):
        result, calls = self.move(["K-1", "K-2", "K-3"], None, jc.JiraApiError(400, "nope"), None)
        self.assertEqual(result["moved"], ["K-1", "K-3"])
        self.assertEqual(result["failed"], {"K-2": "Jira returned HTTP 400: nope"})
        self.assertIsNone(result["stopped"])
        self.assertEqual(calls[2]["json"], {"issues": ["K-3"], "rankAfterIssue": "K-1"})

    def test_no_rank_reference_is_sent_until_something_has_moved(self):
        result, calls = self.move(["K-1", "K-2"], jc.JiraApiError(400, "nope"), None)
        self.assertEqual(calls[1]["json"], {"issues": ["K-2"]})

    def test_a_failure_that_would_hit_every_call_stops_early_and_fails_the_rest(self):
        for status in (401, 403, 429, None):
            result, calls = self.move(["K-1", "K-2", "K-3", "K-4"], None, jc.JiraApiError(status, "systemic"))
            self.assertEqual(result["moved"], ["K-1"], status)
            self.assertEqual(sorted(result["failed"]), ["K-2", "K-3", "K-4"], status)
            self.assertTrue(result["stopped"])
            self.assertEqual(len(calls), 2)  # no more calls after that

    def test_group_size_can_be_raised_and_batches_are_chained(self):
        with mock.patch.object(jc, "MOVE_GROUP_SIZE", 2):
            result, calls = self.move(["K-1", "K-2", "K-3"], None, None)
        self.assertEqual([c["json"] for c in calls], [{"issues": ["K-1", "K-2"]}, {"issues": ["K-3"], "rankAfterIssue": "K-2"}])

    def test_no_issues_no_calls(self):
        result, calls = self.move([])
        self.assertEqual((result, calls), ({"moved": [], "failed": {}, "stopped": None}, []))


class Projects(unittest.TestCase):
    def test_list_projects_asks_for_software_projects_the_user_can_create_in_and_pages(self):
        rec = Recorder(
            {"values": [{"key": "A", "id": "1", "name": "Alpha", "projectTypeKey": "software", "style": "classic"}], "isLast": False},
            {"values": [{"key": "B", "id": "2", "name": "Beta", "projectTypeKey": "software", "style": "next-gen"}], "isLast": True},
        )
        with mock.patch.object(jc, "jira_request", rec):
            projects = run(jc.list_projects("c", "t"))
        self.assertEqual([p["key"] for p in projects], ["A", "B"])
        self.assertEqual(projects[0], {"key": "A", "id": "1", "name": "Alpha", "project_type": "software", "style": "classic"})
        self.assertEqual(rec.calls[0]["path"], "/rest/api/3/project/search")
        self.assertEqual({k: rec.calls[0]["params"][k] for k in ("typeKey", "action")}, {"typeKey": "software", "action": "create"})
        self.assertEqual([c["params"]["startAt"] for c in rec.calls], [0, 1])

    def test_get_project_quotes_the_key_into_the_path(self):
        rec = Recorder({"key": "LBS", "id": "9", "name": "Library", "projectTypeKey": "software", "style": "classic"})
        with mock.patch.object(jc, "jira_request", rec):
            self.assertEqual(run(jc.get_project("c", "t", "LBS"))["name"], "Library")
        self.assertEqual(rec.calls[0]["path"], "/rest/api/3/project/LBS")
        rec = Recorder({"key": "X"})
        with mock.patch.object(jc, "jira_request", rec):
            run(jc.get_project("c", "t", "../etc"))
        self.assertEqual(rec.calls[0]["path"], "/rest/api/3/project/..%2Fetc")


class LabelSlugs(unittest.TestCase):
    def test_the_categories_the_app_offers(self):
        for category, slug in {
            "Software Systems": "software-systems", "AI Solutions": "ai-solutions", "FinTech": "fintech",
            "HR Tech": "hr-tech", "Productivity Tools": "productivity-tools", "Other": "other",
        }.items():
            self.assertEqual(jc.slugify_label(category), slug)
            self.assertEqual(jc.build_labels(category), ["reqprint", slug])

    def test_never_contains_a_space_or_anything_but_lowercase_letters_digits_hyphens(self):
        for text in ("a b", "  x   y  ", "A&B/C", "tabs\tand\nnewlines", "100% Done!", "snake_case name", "Under_Score"):
            self.assertRegex(jc.slugify_label(text), r"^[a-z0-9]+(-[a-z0-9]+)*$", text)

    def test_folds_accents_and_collapses_separators(self):
        self.assertEqual(jc.slugify_label("  Café  &  Bar! "), "cafe-bar")
        self.assertEqual(jc.slugify_label("3D / AR"), "3d-ar")

    def test_nothing_usable_gives_none(self):
        for text in ("", "   ", "!!!", "نظام", None):
            self.assertIsNone(jc.slugify_label(text), repr(text))

    def test_reqprint_is_always_first_and_never_repeated(self):
        self.assertEqual(jc.build_labels(None), ["reqprint"])
        self.assertEqual(jc.build_labels(""), ["reqprint"])
        self.assertEqual(jc.build_labels("نظام"), ["reqprint"])  # unusable category -> only the base label
        self.assertEqual(jc.build_labels("ReqPrint"), ["reqprint"])


LABEL_REJECTION = lambda: jc.JiraApiError(400, "labels: The label 'a b' contains spaces which is invalid (labels)", fields={"labels": "The label 'a b' contains spaces which is invalid (labels)"})


class IssueLabels(unittest.TestCase):
    def epic(self, rec, labels=("reqprint", "fintech")):
        with mock.patch.object(jc, "jira_request", rec):
            return run(jc.create_epic("c", "t", project_key="K", issue_type_id="1", name="N", functional=["f"], non_functional=[], assumptions=[], labels=list(labels) if labels is not None else None))

    def story(self, rec, labels=("reqprint",)):
        with mock.patch.object(jc, "jira_request", rec):
            return run(jc.create_story("c", "t", project_key="K", issue_type_id="2", epic_key="K-1", story={"id": "US-01", "role": "R", "story": "S"}, criteria=[], labels=list(labels) if labels is not None else None))

    def test_labels_are_sent_as_an_array_of_strings_in_fields(self):
        rec = Recorder({"key": "K-1"}, {"key": "K-2"})
        self.epic(rec)
        self.story(rec, ["reqprint", "ai-solutions"])
        self.assertEqual(rec.calls[0]["json"]["fields"]["labels"], ["reqprint", "fintech"])
        self.assertEqual(rec.calls[1]["json"]["fields"]["labels"], ["reqprint", "ai-solutions"])
        self.assertEqual(len(rec.calls), 2)  # one request each

    def test_no_labels_means_no_labels_field(self):
        rec = Recorder({"key": "K-1"}, {"key": "K-2"})
        self.epic(rec, None)
        self.story(rec, None)
        self.assertTrue(all("labels" not in c["json"]["fields"] for c in rec.calls))

    def test_labels_do_not_disturb_the_rest_of_the_fields(self):
        with_labels, without = Recorder({"key": "K-1"}), Recorder({"key": "K-1"})
        self.story(with_labels)
        self.story(without, None)
        a, b = with_labels.calls[0]["json"]["fields"], without.calls[0]["json"]["fields"]
        self.assertEqual({k: v for k, v in a.items() if k != "labels"}, b)

    def test_a_label_rejection_creates_the_issue_again_without_labels(self):
        rec = Recorder(LABEL_REJECTION(), {"key": "K-7"})
        with self.assertLogs(jc.logger, "WARNING") as logs:
            issue = self.story(rec)
        self.assertEqual(issue.key, "K-7")
        self.assertIn("contains spaces", issue.labels_dropped)
        self.assertIn("labels", rec.calls[0]["json"]["fields"])
        self.assertNotIn("labels", rec.calls[1]["json"]["fields"])
        self.assertEqual({k: v for k, v in rec.calls[0]["json"]["fields"].items() if k != "labels"}, rec.calls[1]["json"]["fields"])
        self.assertEqual(len(logs.records), 1)

    def test_the_field_not_being_on_the_create_screen_is_handled_the_same_way(self):
        screen = jc.JiraApiError(400, "labels: Field 'labels' cannot be set. It is not on the appropriate screen, or unknown.", fields={"labels": "Field 'labels' cannot be set."})
        with self.assertLogs(jc.logger, "WARNING"):
            issue = self.epic(Recorder(screen, {"key": "K-1"}))
        self.assertEqual(issue.key, "K-1")
        self.assertTrue(issue.labels_dropped)

    def test_a_clean_create_reports_no_dropped_labels(self):
        self.assertIsNone(self.story(Recorder({"key": "K-2"})).labels_dropped)

    def test_other_errors_are_not_swallowed_or_retried(self):
        for error in (jc.JiraApiError(400, "parent: bad parent", fields={"parent": "bad parent"}), jc.JiraApiError(401, "Unauthorized"),
                      jc.JiraApiError(403, "Forbidden"), jc.JiraApiError(500, "boom"), jc.JiraApiError(None, "Could not reach Jira")):
            rec = Recorder(error)
            with self.assertRaises(jc.JiraApiError) as ctx:
                self.story(rec)
            self.assertIs(ctx.exception, error)
            self.assertEqual(len(rec.calls), 1, error.message)

    def test_if_the_retry_also_fails_that_error_is_raised(self):
        second = jc.JiraApiError(400, "summary: required", fields={"summary": "required"})
        rec = Recorder(LABEL_REJECTION(), second)
        with self.assertLogs(jc.logger, "WARNING"):
            with self.assertRaises(jc.JiraApiError) as ctx:
                self.story(rec)
        self.assertIs(ctx.exception, second)

    def test_nothing_to_retry_when_no_labels_were_sent(self):
        rec = Recorder(LABEL_REJECTION())
        with self.assertRaises(jc.JiraApiError):
            self.story(rec, None)
        self.assertEqual(len(rec.calls), 1)


class SprintDates(unittest.TestCase):
    START, END = "2026-10-08T00:00:00.000+00:00", "2026-10-22T00:00:00.000+00:00"

    def create(self, *responses, dates=True):
        rec = Recorder(*responses)
        with mock.patch.object(jc, "jira_request", rec):
            result = run(jc.create_sprint("c", "t", 5, "S1", self.START, self.END) if dates else jc.create_sprint("c", "t", 5, "S1"))
        return result, rec.calls

    ECHO = {"id": 37, "name": "S1", "state": "future", "startDate": START, "endDate": END}

    def test_dates_are_set_in_the_create_call_itself(self):
        result, calls = self.create(self.ECHO)
        self.assertEqual(len(calls), 1)
        self.assertEqual((calls[0]["method"], calls[0]["path"]), ("POST", "/rest/agile/1.0/sprint"))
        self.assertEqual(calls[0]["json"], {"name": "S1", "originBoardId": 5, "startDate": self.START, "endDate": self.END})
        self.assertEqual(result, {"id": 37, "name": "S1", "state": "future", "dates_set": True, "dates_error": None})

    def test_no_dates_given_means_the_old_request(self):
        result, calls = self.create({"id": 37, "name": "S1", "state": "future"}, dates=False)
        self.assertEqual(calls[0]["json"], {"name": "S1", "originBoardId": 5})
        self.assertFalse(result["dates_set"])
        self.assertIsNone(result["dates_error"])

    def test_only_one_of_two_dates_is_treated_as_none(self):
        rec = Recorder({"id": 1})
        with mock.patch.object(jc, "jira_request", rec):
            run(jc.create_sprint("c", "t", 5, "S1", self.START, None))
        self.assertEqual(rec.calls[0]["json"], {"name": "S1", "originBoardId": 5})

    def test_rejected_dates_still_create_the_sprint_and_say_why(self):
        rejection = jc.JiraApiError(400, "startDate: Invalid date format")
        with self.assertLogs(jc.logger, "WARNING"):
            result, calls = self.create(rejection, {"id": 38, "name": "S1", "state": "future"})
        self.assertEqual(len(calls), 2)
        self.assertIn("startDate", calls[0]["json"])
        self.assertEqual(calls[1]["json"], {"name": "S1", "originBoardId": 5})  # same sprint, no dates
        self.assertEqual(result["id"], 38)
        self.assertFalse(result["dates_set"])
        self.assertEqual(result["dates_error"], "Jira returned HTTP 400: startDate: Invalid date format")

    def test_a_response_without_the_dates_is_reported_not_assumed(self):
        with self.assertLogs(jc.logger, "WARNING"):
            result, calls = self.create({"id": 37, "name": "S1", "state": "future"})
        self.assertEqual(len(calls), 1)
        self.assertFalse(result["dates_set"])
        self.assertIn("did not return", result["dates_error"])

    def test_failures_that_are_not_about_the_dates_are_raised_not_retried(self):
        for error in (jc.JiraApiError(401, "no"), jc.JiraApiError(403, "no"), jc.JiraApiError(404, "no board"),
                      jc.JiraApiError(429, "slow down"), jc.JiraApiError(500, "boom"), jc.JiraApiError(None, "unreachable")):
            rec = Recorder(error)
            with mock.patch.object(jc, "jira_request", rec):
                with self.assertRaises(jc.JiraApiError) as ctx:
                    run(jc.create_sprint("c", "t", 5, "S1", self.START, self.END))
            self.assertIs(ctx.exception, error)
            self.assertEqual(len(rec.calls), 1, error.message)

    def test_a_400_that_was_not_about_dates_surfaces_after_the_retry_also_fails(self):
        second = jc.JiraApiError(400, "name: bad")
        with self.assertLogs(jc.logger, "WARNING"):
            with self.assertRaises(jc.JiraApiError) as ctx:
                self.create(jc.JiraApiError(400, "name: bad"), second)
        self.assertIs(ctx.exception, second)


if __name__ == "__main__":
    unittest.main()
