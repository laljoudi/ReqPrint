"""End-to-end tests of POST /api/jira/push against a stateful fake Jira
(httpx.MockTransport) and a fake Groq. No network, no quota. Covers the push
flow, sprint dates, and labels. Run from the repo root:
    .venv/bin/python -m unittest discover -s tests -t . -v"""
import json
import os
import re
import unittest
from datetime import date
from unittest import mock

import httpx
from cryptography.fernet import Fernet

# main/jira_oauth fail fast without these; fake values are fine, and setdefault
# leaves any real ones alone.
for _name, _value in {
    "JIRA_CLIENT_ID": "test-id",
    "JIRA_CLIENT_SECRET": "test-secret",
    "JIRA_REDIRECT_URI": "http://localhost:8000/api/jira/callback",
    "FRONTEND_ORIGIN": "http://localhost:8000",
    "SESSION_SECRET": Fernet.generate_key().decode(),
    "APP_ENV": "local",
    "GROQ_API_KEY": "test-groq-key",
}.items():
    os.environ.setdefault(_name, _value)

import ai  # noqa: E402
import jira_oauth  # noqa: E402
import jira_push  # noqa: E402
import main  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

REAL_ASYNC_CLIENT = httpx.AsyncClient  # captured before any test patches it
CLOUD = "11111111-2222-3333-4444-555555555555"
TODAY = date(2026, 10, 8)
CONN = {"refresh_token": "RT-0", "cloud_id": CLOUD, "site_url": "https://acme.atlassian.net", "site_name": "Acme"}
TYPES = [
    {"id": "10000", "name": "Epic", "subtask": False, "hierarchyLevel": 1},
    {"id": "10001", "name": "Story", "subtask": False, "hierarchyLevel": 0},
    {"id": "10004", "name": "Sub-task", "subtask": True, "hierarchyLevel": -1},
]
LABEL_ERROR = (400, {"errorMessages": [], "errors": {"labels": "Field 'labels' cannot be set. It is not on the appropriate screen, or unknown."}})
DATE_ERROR = (400, {"errorMessages": [], "errors": {"startDate": "Invalid date format"}})


class FakeJira:
    """Atlassian + Jira. Rotates refresh tokens; hooks let a test reject things."""

    def __init__(self):
        self.calls = []        # (kind, ...) in the order they happened
        self.valid_rt = {"RT-0"}
        self.n = 0
        self.issue_n = 0
        self.sprint_n = 100
        self.issues = {}       # key -> fields as sent
        self.sprints = {}      # id -> body as sent
        self.reject_issue = lambda fields: None     # -> (status, body) | None
        self.reject_sprint = lambda body: None
        self.echo_dates = True

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.url.host == "auth.atlassian.com":
            token = json.loads(request.content)["refresh_token"]
            if token not in self.valid_rt:
                return httpx.Response(403, json={"error": "invalid_grant"})
            self.n += 1
            self.valid_rt = {f"RT-{self.n}"}
            return httpx.Response(200, json={"access_token": f"AT-{self.n}", "refresh_token": f"RT-{self.n}"})
        sub = path[len(f"/ex/jira/{CLOUD}"):]
        body = json.loads(request.content) if request.content else None
        if sub == "/rest/api/3/myself":
            return httpx.Response(200, json={"accountId": "acct-1"})
        if sub == "/rest/api/3/project" and request.method == "POST":
            return httpx.Response(201, json={"id": "10500", "key": body["key"]})
        if sub == "/rest/agile/1.0/board":
            return httpx.Response(200, json={"values": [{"id": 7, "type": "scrum"}]})
        if sub.endswith("/issuetypes") and "createmeta" in sub:
            return httpx.Response(200, json={"issueTypes": TYPES, "total": len(TYPES)})
        if "/createmeta/" in sub and "/issuetypes/" in sub:
            return httpx.Response(200, json={"fields": [{"fieldId": "summary", "name": "Summary"}], "total": 1})
        if sub == "/rest/api/3/issue" and request.method == "POST":
            fields = body["fields"]
            self.calls.append(("issue", fields["issuetype"]["id"], "labels" in fields))
            rejection = self.reject_issue(fields)
            if rejection:
                return httpx.Response(rejection[0], json=rejection[1])
            self.issue_n += 1
            key = f"{fields['project']['key']}-{self.issue_n}"
            self.issues[key] = fields
            return httpx.Response(201, json={"id": str(10000 + self.issue_n), "key": key})
        if sub == "/rest/agile/1.0/sprint" and request.method == "POST":
            self.calls.append(("sprint", "startDate" in body))
            rejection = self.reject_sprint(body)
            if rejection:
                return httpx.Response(rejection[0], json=rejection[1])
            self.sprint_n += 1
            self.sprints[self.sprint_n] = body
            echoed = {k: body[k] for k in ("startDate", "endDate") if k in body and self.echo_dates}
            return httpx.Response(201, json={"id": self.sprint_n, "name": body["name"], "state": "future", **echoed})
        if re.fullmatch(r"/rest/agile/1.0/sprint/\d+/issue", sub):
            self.calls.append(("move", body["issues"][0]))
            return httpx.Response(204)
        return httpx.Response(404, json={"message": f"no route {sub}"})


def story(i):
    return {"id": f"US-{i:02d}", "role": "Member", "story": f"As a user {i}, I want thing {i}, so that value {i}"}


def document(n=7):
    return {
        "requirements": {"functional": ["FR"], "non_functional": ["NFR"]},
        "user_stories": [story(i) for i in range(1, n + 1)],
        "acceptance_criteria": [{"story_id": f"US-{i:02d}", "scenario": f"S{i}", "given": "g", "when": "w", "then": "t"} for i in range(1, n + 1)],
        "assumptions": ["A"],
    }


def request_body(n=7, **overrides):
    body = {"mode": "create", "project_name": "Library Booking System", "capacity_per_week": 2, "requirements": document(n)}
    body.update(overrides)
    return body


class PushTestCase(unittest.TestCase):
    def setUp(self):
        self.jira = FakeJira()
        patches = [
            mock.patch.object(httpx, "AsyncClient", lambda **kw: REAL_ASYNC_CLIENT(transport=httpx.MockTransport(self.jira), **kw)),
            mock.patch.object(ai, "_structured_chat", self.fake_groq),
            mock.patch.object(jira_push, "_today_utc", lambda: TODAY),
            mock.patch.object(jira_push, "BOARD_POLL_DELAY", 0),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        main.limiter.reset()

    @staticmethod
    def fake_groq(prompt, message, schema):
        ids = [s["id"] for s in json.loads(message)]
        return ai.StoryOrderPlan(ordered_stories=[ai.StoryOrderItem(story_id=i, reason="r", depends_on=[]) for i in ids])

    def push(self, body):
        client = TestClient(main.app, base_url="http://localhost:8000")
        client.cookies.set("jira_conn", jira_oauth.encrypt_payload(CONN), domain="localhost.local")
        response = client.post("/api/jira/push", json=body)
        self.cookie_after = None
        for header in response.headers.get_list("set-cookie"):
            if header.startswith("jira_conn="):
                self.cookie_after = jira_oauth.decrypt_payload(header.split(";", 1)[0].split("=", 1)[1])
        return response

    def stories(self):
        """The story issues (everything but the epic), by key."""
        return {k: f for k, f in self.jira.issues.items() if f["issuetype"]["id"] == "10001"}


class Labels(PushTestCase):
    def test_every_issue_gets_reqprint_and_the_category_slug(self):
        r = self.push(request_body(category="HR Tech"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(self.jira.issues), 8)  # epic + 7 stories
        for key, fields in self.jira.issues.items():
            self.assertEqual(fields["labels"], ["reqprint", "hr-tech"], key)
        self.assertEqual(r.json()["labels"], ["reqprint", "hr-tech"])
        self.assertEqual(r.json()["labels_failed"], [])

    def test_no_category_means_only_reqprint(self):
        for body in (request_body(), request_body(category=None), request_body(category=""), request_body(category="   ")):
            self.setUp()
            r = self.push(body)
            self.assertEqual(r.status_code, 200)
            self.assertTrue(all(f["labels"] == ["reqprint"] for f in self.jira.issues.values()))
            self.assertEqual(r.json()["labels"], ["reqprint"])

    def test_an_unusable_category_is_dropped_not_sent(self):
        r = self.push(request_body(category="نظام"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(all(f["labels"] == ["reqprint"] for f in self.jira.issues.values()))

    def test_no_label_sent_to_jira_ever_contains_a_space(self):
        for category in ("Software Systems", "  AI   Solutions  ", "Café & Bar", "a b c d"):
            self.setUp()
            self.push(request_body(category=category))
            for fields in self.jira.issues.values():
                self.assertTrue(all(re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", label) for label in fields["labels"]), fields["labels"])

    def test_a_label_jira_refuses_never_fails_a_story(self):
        self.jira.reject_issue = lambda f: LABEL_ERROR if f["issuetype"]["id"] == "10001" and "labels" in f else None
        r = self.push(request_body(category="FinTech"))
        data = r.json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual((data["stories_created"], data["failed"]), (7, []))
        self.assertEqual(data["sprint_count"], 2)
        self.assertEqual(self.jira.issues["LBS-1"]["labels"], ["reqprint", "fintech"])      # the epic kept its labels
        self.assertTrue(all("labels" not in f for f in self.stories().values()))             # the stories were created without
        self.assertEqual(len(data["labels_failed"]), 7)  # every story without labels is reported
        self.assertEqual({x["story_id"] for x in data["labels_failed"]}, {o["story_id"] for o in data["order"]})
        first, rest = data["labels_failed"][0], data["labels_failed"][1:]
        self.assertIn("labels", first["reason"])                              # the one Jira actually refused
        self.assertTrue(all(x["reason"].startswith("Not sent:") and first["reason"] in x["reason"] for x in rest))

    def test_after_one_refusal_that_issue_type_is_not_asked_again(self):
        self.jira.reject_issue = lambda f: LABEL_ERROR if f["issuetype"]["id"] == "10001" and "labels" in f else None
        self.push(request_body())
        story_calls = [c for c in self.jira.calls if c[0] == "issue" and c[1] == "10001"]
        self.assertEqual(len(story_calls), 7 + 1)  # 7 stories + exactly one rejected attempt
        self.assertEqual(sum(1 for c in story_calls if c[2]), 1)

    def test_an_epic_that_refuses_labels_does_not_stop_the_stories_getting_them(self):
        self.jira.reject_issue = lambda f: LABEL_ERROR if f["issuetype"]["id"] == "10000" and "labels" in f else None
        data = self.push(request_body(category="Other")).json()
        self.assertEqual(data["stories_created"], 7)
        self.assertNotIn("labels", self.jira.issues["LBS-1"])
        self.assertTrue(all(f["labels"] == ["reqprint", "other"] for f in self.stories().values()))
        self.assertEqual([x["story_id"] for x in data["labels_failed"]], [None])
        self.assertEqual(data["labels_failed"][0]["issue_key"], "LBS-1")

    def test_other_story_errors_still_fail_that_story(self):
        self.jira.reject_issue = lambda f: (400, {"errors": {"description": "bad"}}) if f["summary"].startswith("As a user 3,") else None
        data = self.push(request_body()).json()
        self.assertEqual((data["stories_created"], [f["story_id"] for f in data["failed"]]), (6, ["US-03"]))
        self.assertEqual(data["labels_failed"], [])  # that failure had nothing to do with labels


class SprintDates(PushTestCase):
    def test_sprints_are_back_to_back_two_week_blocks_starting_today_in_utc(self):
        data = self.push(request_body(n=9, capacity_per_week=2)).json()  # 4 per sprint -> 3 sprints
        self.assertEqual(data["sprint_count"], 3)
        self.assertEqual(
            [(s["start_date"], s["end_date"]) for s in data["sprints"]],
            [
                ("2026-10-08T00:00:00.000+00:00", "2026-10-22T00:00:00.000+00:00"),
                ("2026-10-22T00:00:00.000+00:00", "2026-11-05T00:00:00.000+00:00"),
                ("2026-11-05T00:00:00.000+00:00", "2026-11-19T00:00:00.000+00:00"),
            ],
        )
        self.assertTrue(all(s["dates_set"] and "dates_error" not in s for s in data["sprints"]))
        self.assertTrue(all(c[1] for c in self.jira.calls if c[0] == "sprint"))  # dates went in the create call

    def test_the_dates_in_the_request_are_exactly_the_reported_ones(self):
        data = self.push(request_body()).json()
        for s in data["sprints"]:
            sent = self.jira.sprints[s["id"]]
            self.assertEqual((sent["startDate"], sent["endDate"]), (s["start_date"], s["end_date"]))
            self.assertEqual(set(sent), {"name", "originBoardId", "startDate", "endDate"})

    def test_a_date_jira_refuses_never_fails_the_push(self):
        self.jira.reject_sprint = lambda body: DATE_ERROR if "startDate" in body else None
        r = self.push(request_body())
        data = r.json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual((data["stories_created"], data["failed"], data["sprint_count"]), (7, [], 2))
        self.assertEqual([len(s["story_ids"]) for s in data["sprints"]], [4, 3])        # every story still moved
        self.assertEqual(len([c for c in self.jira.calls if c[0] == "move"]), 7)
        for s in data["sprints"]:
            self.assertFalse(s["dates_set"])
            self.assertIn("startDate: Invalid date format", s["dates_error"])
            self.assertTrue(s["start_date"] and s["end_date"])  # the intended schedule is still reported
        self.assertTrue(all("startDate" not in body for body in self.jira.sprints.values()))

    def test_dates_jira_accepts_but_does_not_return_are_reported_as_not_set(self):
        self.jira.echo_dates = False
        data = self.push(request_body()).json()
        self.assertEqual((data["stories_created"], data["failed"]), (7, []))
        self.assertTrue(all(not s["dates_set"] and "did not return" in s["dates_error"] for s in data["sprints"]))

    def test_dates_follow_the_plan_even_when_an_earlier_sprint_is_never_created(self):
        # 8 stories, 4 per sprint. Make every story of sprint 1 fail: sprint 1 is not created.
        self.jira.reject_issue = lambda f: (400, {"errorMessages": ["nope"]}) if re.match(r"As a user [1-4],", f["summary"]) else None
        data = self.push(request_body(n=8)).json()
        self.assertEqual([s["name"] for s in data["sprints"]], ["ReqPrint Sprint 2"])
        self.assertEqual(data["sprints"][0]["start_date"], "2026-10-22T00:00:00.000+00:00")  # still two weeks in

    def test_a_sprint_error_unrelated_to_dates_is_reported_as_before(self):
        self.jira.reject_sprint = lambda body: (404, {"errorMessages": ["board gone"]})
        data = self.push(request_body()).json()
        self.assertEqual((data["stories_created"], data["sprint_count"]), (7, 0))
        self.assertEqual(len(data["failed"]), 7)
        self.assertTrue(all("could not be created" in f["reason"] for f in data["failed"]))


class ExistingBehaviourIsUnchanged(PushTestCase):
    def test_the_original_response_fields_are_all_still_there_with_the_same_meaning(self):
        r = self.push(request_body())
        data = r.json()
        for field in ("project_key", "project_url", "project_created", "board_id", "epic_key", "sprint_count",
                      "stories_created", "failed", "sprints", "issue_keys", "order"):
            self.assertIn(field, data)
        self.assertEqual((data["project_key"], data["epic_key"], data["board_id"]), ("LBS", "LBS-1", 7))
        self.assertEqual((data["stories_created"], data["sprint_count"], data["failed"]), (7, 2, []))
        for sprint in data["sprints"]:
            self.assertTrue({"id", "name", "story_ids"} <= set(sprint))
        self.assertEqual([s["story_ids"] for s in data["sprints"]], [[f"US-0{i}" for i in range(1, 5)], ["US-05", "US-06", "US-07"]])

    def test_stories_are_ranked_in_order_one_after_the_other(self):
        self.push(request_body(n=3, capacity_per_week=1))
        self.assertEqual([c[1] for c in self.jira.calls if c[0] == "move"], ["LBS-2", "LBS-3", "LBS-4"])

    def test_the_rotated_refresh_token_is_still_set_and_nothing_secret_is_returned(self):
        r = self.push(request_body())
        self.assertEqual(self.cookie_after["refresh_token"], "RT-1")
        self.assertNotRegex(r.text, r"\b[AR]T-\d")

    def test_category_is_validated_without_touching_jira_or_the_ai(self):
        for bad in ("x" * 81, 5, ["a"]):
            self.setUp()
            r = self.push(request_body(category=bad))
            self.assertEqual(r.status_code, 422, repr(bad))
            self.assertEqual(self.jira.calls, [])


class StartDateAndSprintLength(PushTestCase):
    def sprint_dates(self, data):
        return [(x["start_date"], x["end_date"]) for x in data["sprints"]]

    def test_omitted_means_today_and_two_week_sprints_and_both_are_echoed(self):
        data = self.push(request_body()).json()
        self.assertEqual((data["start_date"], data["sprint_length_weeks"]), ("2026-10-08", 2))
        self.assertEqual(self.sprint_dates(data), [
            ("2026-10-08T00:00:00.000+00:00", "2026-10-22T00:00:00.000+00:00"),
            ("2026-10-22T00:00:00.000+00:00", "2026-11-05T00:00:00.000+00:00"),
        ])
        self.assertEqual([len(s["story_ids"]) for s in data["sprints"]], [4, 3])

    def test_explicit_nulls_behave_like_omitted(self):
        a = self.push(request_body()).json()
        self.setUp()
        b = self.push(request_body(start_date=None, sprint_length_weeks=None)).json()
        self.assertEqual((a["start_date"], a["sprint_length_weeks"], self.sprint_dates(a)), (b["start_date"], b["sprint_length_weeks"], self.sprint_dates(b)))

    def test_a_month_out_with_three_week_sprints(self):
        # 7 stories, capacity 2/week x 3 weeks = 6 per sprint -> 2 sprints (6 + 1)
        data = self.push(request_body(start_date="2026-11-08", sprint_length_weeks=3)).json()
        self.assertEqual((data["start_date"], data["sprint_length_weeks"]), ("2026-11-08", 3))
        self.assertEqual(self.sprint_dates(data), [
            ("2026-11-08T00:00:00.000+00:00", "2026-11-29T00:00:00.000+00:00"),
            ("2026-11-29T00:00:00.000+00:00", "2026-12-20T00:00:00.000+00:00"),
        ])
        self.assertEqual([len(s["story_ids"]) for s in data["sprints"]], [6, 1])
        self.assertEqual(data["sprint_count"], 2)

    def test_the_chosen_dates_are_what_jira_receives_in_the_same_format_as_before(self):
        data = self.push(request_body(start_date="2026-11-08", sprint_length_weeks=3)).json()
        for sprint in data["sprints"]:
            sent = self.jira.sprints[sprint["id"]]
            self.assertEqual((sent["startDate"], sent["endDate"]), (sprint["start_date"], sprint["end_date"]))
            self.assertRegex(sent["startDate"], r"^\d{4}-\d{2}-\d{2}T00:00:00\.000\+00:00$")
            self.assertTrue(sprint["dates_set"])

    def test_the_length_changes_the_capacity_math_and_the_dates_together(self):
        expected = {1: [2, 2, 2, 1], 2: [4, 3], 3: [6, 1], 4: [7]}   # 7 stories, capacity 2/week
        for weeks, sizes in expected.items():
            self.setUp()
            data = self.push(request_body(sprint_length_weeks=weeks)).json()
            self.assertEqual([len(s["story_ids"]) for s in data["sprints"]], sizes, weeks)
            first_start, first_end = self.sprint_dates(data)[0]
            self.assertEqual(first_start, "2026-10-08T00:00:00.000+00:00")
            self.assertEqual(first_end, {1: "2026-10-15", 2: "2026-10-22", 3: "2026-10-29", 4: "2026-11-05"}[weeks] + "T00:00:00.000+00:00")

    def test_sprints_run_back_to_back_for_every_length(self):
        for weeks in (1, 2, 3, 4):
            self.setUp()
            dates = self.sprint_dates(self.push(request_body(n=9, capacity_per_week=1, sprint_length_weeks=weeks)).json())
            self.assertTrue(len(dates) >= 2)
            for (_, end), (start, _) in zip(dates, dates[1:]):
                self.assertEqual(end, start, weeks)

    def test_a_start_date_in_the_past_is_allowed(self):
        r = self.push(request_body(start_date="2020-01-15"))
        data = r.json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(data["start_date"], "2020-01-15")
        self.assertEqual(data["sprints"][0]["start_date"], "2020-01-15T00:00:00.000+00:00")
        self.assertEqual((data["stories_created"], data["failed"]), (7, []))

    def test_a_start_date_of_today_equals_leaving_it_out(self):
        a = self.push(request_body(start_date="2026-10-08")).json()
        self.setUp()
        b = self.push(request_body()).json()
        self.assertEqual(self.sprint_dates(a), self.sprint_dates(b))

    def test_malformed_dates_and_lengths_are_rejected_before_anything_is_created(self):
        bad_dates = ["10/08/2026", "2026-10-8", "2026-13-01", "2026-02-30", "2026-10-08T00:00:00", "20261008", "", "tomorrow",
                     20261008, 1760000000, "1999-12-31", "2100-01-01", " 2026-11-08", ["2026-11-08"]]
        bad_lengths = [0, 5, -1, 10, "3", 2.5, 3.0, True, [3]]
        cases = [("start_date", v) for v in bad_dates] + [("sprint_length_weeks", v) for v in bad_lengths]
        for field, value in cases:
            self.setUp()
            r = self.push(request_body(**{field: value}))
            self.assertEqual(r.status_code, 422, (field, value))
            self.assertEqual(self.jira.calls, [], (field, value))           # nothing was created
            self.assertEqual(self.jira.issues, {}, (field, value))
            self.assertIn(field, json.dumps(r.json()), (field, value))        # the error names the field

    def test_the_date_error_says_what_is_expected(self):
        r = self.push(request_body(start_date="10/08/2026"))
        self.assertIn("YYYY-MM-DD", json.dumps(r.json()))
        r = self.push(request_body(start_date="2026-02-30"))
        self.assertIn("not a real calendar date", json.dumps(r.json()))

    def test_a_rejected_request_does_not_touch_the_ai_either(self):
        calls = []
        with mock.patch.object(ai, "_structured_chat", lambda *a: calls.append(a)):
            self.push(request_body(sprint_length_weeks=9))
            self.push(request_body(start_date="nope"))
        self.assertEqual(calls, [])

    def test_the_new_fields_do_not_disturb_the_rest_of_the_response(self):
        data = self.push(request_body(start_date="2026-11-08", sprint_length_weeks=3, category="HR Tech")).json()
        for field in ("project_key", "project_url", "project_created", "board_id", "epic_key", "sprint_count", "stories_created",
                      "failed", "sprints", "issue_keys", "order", "labels", "labels_failed"):
            self.assertIn(field, data)
        self.assertEqual(data["labels"], ["reqprint", "hr-tech"])
        for sprint in data["sprints"]:
            self.assertTrue({"id", "name", "story_ids", "start_date", "end_date", "dates_set"} <= set(sprint))


if __name__ == "__main__":
    unittest.main()
