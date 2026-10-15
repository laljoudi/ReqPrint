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
from groq import RateLimitError

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
        self.types = TYPES
        self.requests = []     # every call that reached Jira's API (not the token endpoint), in order
        self.reject_bulk_element = lambda fields: None   # -> (status, {field: message}) | None
        self.bulk_failure = None                          # (status, body) answering a whole bulk call
        self.bulk_issues_override = None                  # replaces the "issues" list in a bulk answer

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
        self.requests.append((request.method, re.sub(r"/\d{2,}(?=/|$)", "/{id}", sub)))   # ids, not the API version
        if sub == "/rest/api/3/myself":
            return httpx.Response(200, json={"accountId": "acct-1"})
        if sub == "/rest/api/3/project" and request.method == "POST":
            return httpx.Response(201, json={"id": "10500", "key": body["key"]})
        if sub == "/rest/agile/1.0/board":
            return httpx.Response(200, json={"values": [{"id": 7, "type": "scrum"}]})
        if sub.endswith("/issuetypes") and "createmeta" in sub:
            return httpx.Response(200, json={"issueTypes": self.types, "total": len(self.types)})
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
        if sub == "/rest/api/3/issue/bulk" and request.method == "POST":
            elements = body["issueUpdates"]
            assert len(elements) <= 50, "Atlassian's limit is 50 per bulk call"
            self.calls.append(("bulk", len(elements)))
            if self.bulk_failure:
                return httpx.Response(self.bulk_failure[0], json=self.bulk_failure[1])
            issues, errors = [], []
            for index, element in enumerate(elements):
                fields = element["fields"]
                rejection = self.reject_bulk_element(fields)
                if rejection:
                    errors.append({"status": rejection[0], "elementErrors": {"errorMessages": [], "errors": rejection[1]}, "failedElementNumber": index})
                    continue
                self.issue_n += 1
                key = f"{fields['project']['key']}-{self.issue_n}"
                self.issues[key] = fields
                issues.append({"id": str(10000 + self.issue_n), "key": key, "self": "x"})
            if self.bulk_issues_override is not None:
                issues = self.bulk_issues_override
            # Atlassian: 201 if any element was created, 400 (same body shape) if all were invalid.
            return httpx.Response(201 if issues else 400, json={"issues": issues, "errors": errors})
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

    sub_mode = "ok"   # "ok" | "unknown_story" | "too_many" | "quota" | "half_uncited" | "uncited" | "out_of_range"
    ai_calls = None

    def fake_groq(self, prompt, message, schema):
        self.ai_calls = (self.ai_calls or []) + [schema.__name__]
        if schema is ai.SubtaskPlan:
            return self.fake_subtasks(json.loads(message))
        ids = [s["id"] for s in json.loads(message)]
        return ai.StoryOrderPlan(ordered_stories=[ai.StoryOrderItem(story_id=i, reason="r", depends_on=[]) for i in ids])

    def fake_subtasks(self, stories):
        """Two sub-tasks per story, both from the story's first criterion (a story with no criteria cites none).
        The modes break the rule on purpose: "half_uncited" makes the second cite nothing, "uncited" both,
        "out_of_range" both cite a criterion the story doesn't have."""
        if self.sub_mode == "quota":
            raise RateLimitError("slow down", response=httpx.Response(429, request=httpx.Request("POST", "https://api.groq.com/x")), body=None)
        out = []
        for st in stories:
            n = 6 if self.sub_mode == "too_many" else 2
            cite = 0 if st["criteria"] else None
            first = {"uncited": None, "out_of_range": 5}.get(self.sub_mode, cite)
            rest = {"uncited": None, "half_uncited": None, "out_of_range": 5}.get(self.sub_mode, cite)
            items = [ai.SubtaskItem(title=f"Backend work for {st['id']}", discipline="backend", criterion_index=first)]
            items += [ai.SubtaskItem(title=f"Frontend work {k} for {st['id']}", discipline="frontend", criterion_index=rest) for k in range(n - 1)]
            out.append(ai.StorySubtasks(story_id="NOPE" if self.sub_mode == "unknown_story" else st["id"], subtasks=items))
        return ai.SubtaskPlan(stories=out)

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


SUBTASK_TYPE_ID = "10004"   # the "Sub-task" entry in TYPES


class SubTasks(PushTestCase):
    """Stage 5: each story broken into real sub-tasks, parented to it. Off unless asked."""

    def subtasks(self):
        return {k: f for k, f in self.jira.issues.items() if f["issuetype"]["id"] == SUBTASK_TYPE_ID}

    def go(self, n=7, **extra):
        return self.push(request_body(n=n, create_subtasks=True, **extra))

    # ---- off by default: exactly the push that existed before
    def test_off_by_default_nothing_changes(self):
        data = self.push(request_body()).json()
        self.assertEqual(self.subtasks(), {})
        self.assertNotIn(("POST", "/rest/api/3/issue/bulk"), self.jira.requests)
        self.assertNotIn("SubtaskPlan", self.ai_calls or [])
        self.assertEqual((data["subtasks_requested"], data["subtasks_created"], data["subtasks_failed"], data["subtask_keys"], data["subtasks_skipped"]), (False, 0, [], {}, []))
        self.assertEqual((data["subtask_details"], data["subtasks_rejected"]), ([], []))
        self.assertEqual((data["stories_created"], data["sprint_count"], data["failed"]), (7, 2, []))

    def test_explicit_false_is_the_same_as_off(self):
        a = self.push(request_body()).json()
        self.setUp()
        b = self.push(request_body(create_subtasks=False)).json()
        self.assertEqual({k: v for k, v in a.items()}, {k: v for k, v in b.items()})

    def test_the_flag_must_be_a_real_boolean(self):
        for bad in ("yes", "true", 1, 0, None, []):
            self.setUp()
            r = self.push(request_body(create_subtasks=bad))
            self.assertEqual(r.status_code, 422, repr(bad))
            self.assertEqual(self.jira.calls, [])

    # ---- on: real sub-tasks under their stories
    def test_creates_real_subtasks_parented_to_their_stories_in_one_bulk_call(self):
        r = self.go()
        data = r.json()
        self.assertEqual(r.status_code, 200)
        subs = self.subtasks()
        self.assertEqual(len(subs), 14)  # 2 per story
        self.assertEqual(data["subtasks_created"], 14)
        self.assertEqual(data["subtasks_failed"], [])
        self.assertEqual([c for c in self.jira.calls if c[0] == "bulk"], [("bulk", 14)])
        for key, fields in subs.items():
            self.assertEqual(fields["issuetype"], {"id": SUBTASK_TYPE_ID})
            self.assertIn(fields["parent"]["key"], data["issue_keys"].values())   # a story, never the epic
            self.assertNotEqual(fields["parent"]["key"], data["epic_key"])
        self.assertEqual(set(data["subtask_keys"]), set(data["issue_keys"]))      # every story has some, keyed by story id
        for story_id, keys in data["subtask_keys"].items():
            self.assertEqual(len(keys), 2)
            self.assertTrue(all(subs[k]["parent"]["key"] == data["issue_keys"][story_id] for k in keys))
        self.assertEqual(data["subtasks_requested"], True)
        self.assertEqual((data["subtasks_skipped"], data["subtasks_rejected"]), ([], []))

    def test_each_subtask_has_its_title_labels_and_a_quote_of_its_criterion(self):
        data = self.go(category="HR Tech").json()
        story_key = data["issue_keys"]["US-02"]
        mine = {k: f for k, f in self.subtasks().items() if f["parent"]["key"] == story_key}
        backend = next(f for f in mine.values() if f["summary"].startswith("Backend work"))
        frontend = next(f for f in mine.values() if f["summary"].startswith("Frontend work"))
        self.assertEqual(backend["labels"], ["reqprint", "hr-tech", "backend"])
        self.assertEqual(frontend["labels"], ["reqprint", "hr-tech", "frontend"])
        quote = json.dumps(backend["description"])        # came from criterion 0 of US-02
        self.assertIn("Acceptance criterion:", quote)
        self.assertIn("S2", quote)                                         # the criterion's own scenario name
        self.assertTrue(all(label in quote for label in ("Given", "When", "Then")))
        self.assertIn("Acceptance criterion:", json.dumps(frontend["description"]))   # it cites a criterion too: never the story text
        self.assertNotIn("From the story:", json.dumps(frontend["description"]))

    def test_a_story_with_no_criteria_quotes_the_story_text(self):
        body = request_body(n=3, create_subtasks=True)
        body["requirements"]["acceptance_criteria"] = [c for c in body["requirements"]["acceptance_criteria"] if c["story_id"] != "US-02"]
        data = self.push(body).json()
        story_key = data["issue_keys"]["US-02"]
        mine = [f for f in self.subtasks().values() if f["parent"]["key"] == story_key]
        self.assertEqual(len(mine), 2)
        for f in mine:
            self.assertIn("From the story:", json.dumps(f["description"]))
            self.assertIn(story(2)["story"], json.dumps(f["description"]))
        self.assertEqual(data["subtasks_rejected"], [])
        rows = [r for r in data["subtask_details"] if r["story_id"] == "US-02"]
        self.assertEqual([(r["source"], r["criterion_index"], r["criterion_scenario"]) for r in rows], [("story", None, None)] * 2)

    def test_without_a_category_the_labels_are_reqprint_plus_the_discipline(self):
        self.go()
        self.assertTrue(all(f["labels"] in (["reqprint", "backend"], ["reqprint", "frontend"]) for f in self.subtasks().values()))

    def test_capacity_and_the_sprint_math_still_count_stories_only(self):
        without = self.push(request_body(n=10)).json()
        self.setUp()
        with_sub = self.push(request_body(n=10, create_subtasks=True)).json()
        for field in ("sprint_count", "stories_created", "order", "start_date", "sprint_length_weeks"):
            self.assertEqual(without[field], with_sub[field], field)
        self.assertEqual([s["story_ids"] for s in without["sprints"]], [s["story_ids"] for s in with_sub["sprints"]])
        self.assertEqual([(s["start_date"], s["end_date"]) for s in without["sprints"]], [(s["start_date"], s["end_date"]) for s in with_sub["sprints"]])
        self.assertEqual(with_sub["subtasks_created"], 20)    # 20 sub-tasks did not change the sprint size:
        self.assertEqual([len(s["story_ids"]) for s in with_sub["sprints"]], [4, 4, 2])   # capacity 2/week x 2 weeks = 4 stories each

    def test_subtasks_are_never_moved_into_a_sprint_or_ranked(self):
        data = self.go().json()
        moved = [c[1] for c in self.jira.calls if c[0] == "move"]
        self.assertEqual(sorted(moved), sorted(data["issue_keys"].values()))     # stories only
        self.assertTrue(set(moved).isdisjoint(self.subtasks()))
        self.assertEqual(sum(1 for m, p in self.jira.requests if "/rank" in p), 0)

    def test_subtasks_come_last_after_the_stories_and_sprints(self):
        self.go()
        kinds = [c[0] for c in self.jira.calls]
        self.assertEqual(kinds[-1], "bulk")
        self.assertLess(max(i for i, k in enumerate(kinds) if k == "move"), kinds.index("bulk"))
        self.assertLess(max(i for i, k in enumerate(kinds) if k == "issue"), kinds.index("bulk"))

    def test_one_ai_call_for_ordering_and_one_for_subtasks(self):
        self.go()
        self.assertEqual(sorted(self.ai_calls), ["StoryOrderPlan", "SubtaskPlan"])

    def test_the_ai_is_sent_each_story_with_only_its_own_criteria(self):
        sent = []
        def spy(prompt, message, schema):
            if schema is ai.SubtaskPlan:
                sent.append(json.loads(message))
            return self.fake_groq(prompt, message, schema)
        with mock.patch.object(ai, "_structured_chat", spy):
            self.go(n=3)
        self.assertEqual([s["id"] for s in sent[0]], ["US-01", "US-02", "US-03"])
        self.assertEqual([[c["scenario"] for c in s["criteria"]] for s in sent[0]], [["S1"], ["S2"], ["S3"]])

    # ---- the project can't have sub-tasks
    def test_no_subtask_type_skips_them_and_everything_else_is_created(self):
        self.jira.types = [t for t in TYPES if not t["subtask"]]
        r = self.go()
        data = r.json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(data["subtasks_skipped"], [{"story_id": None, "reason": "no_subtask_type", "detail": None}])
        self.assertEqual((data["subtasks_created"], data["subtasks_failed"], data["subtask_keys"]), (0, [], {}))
        self.assertEqual((data["stories_created"], data["sprint_count"], data["failed"]), (7, 2, []))
        self.assertNotIn("SubtaskPlan", self.ai_calls or [])      # no AI call wasted on work that can't be created
        self.assertNotIn(("POST", "/rest/api/3/issue/bulk"), self.jira.requests)

    # ---- the derivation rule, enforced in code
    def test_every_created_subtask_is_listed_with_the_criterion_it_came_from(self):
        data = self.go(n=3).json()
        rows = data["subtask_details"]
        self.assertEqual(len(rows), 6)
        all_keys = {k for ks in data["subtask_keys"].values() for k in ks}
        self.assertEqual({r["key"] for r in rows}, all_keys)
        for r in rows:
            n = int(r["story_id"][-2:])
            self.assertEqual((r["source"], r["criterion_index"], r["criterion_scenario"]), ("criterion", 0, f"S{n}"))
            self.assertEqual((r["created"], r["error"], r["story_key"]), (True, None, data["issue_keys"][r["story_id"]]))
            self.assertIn(r["discipline"], ("backend", "frontend"))

    def test_the_audit_row_of_a_failed_subtask_says_so(self):
        self.jira.reject_bulk_element = lambda f: (400, {"summary": "Nope."}) if f["summary"].startswith("Frontend") and "US-03" in f["summary"] else None
        rows = self.go().json()["subtask_details"]
        bad = [r for r in rows if not r["created"]]
        self.assertEqual(len(bad), 1)
        self.assertEqual((bad[0]["story_id"], bad[0]["key"], bad[0]["criterion_index"]), ("US-03", None, 0))
        self.assertIn("Nope.", bad[0]["error"])
        self.assertEqual(len(rows), 14)

    def test_a_subtask_that_cites_nothing_is_rejected_and_never_reaches_jira(self):
        self.sub_mode = "half_uncited"      # per story: one cites criterion 0, one cites nothing
        with self.assertLogs(ai.logger, "WARNING"):
            data = self.go(n=3).json()
        self.assertEqual(data["subtasks_created"], 3)                      # one per story survives; 1 of 2 is not "more than half"
        self.assertEqual(sorted(r["story_id"] for r in data["subtasks_rejected"]), ["US-01", "US-02", "US-03"])
        self.assertTrue(all(r["reason"] == "cited no acceptance criterion" and r["title"].startswith("Frontend") for r in data["subtasks_rejected"]))
        self.assertEqual(data["subtasks_skipped"], [])
        self.assertTrue(all(f["summary"].startswith("Backend") for f in self.subtasks().values()))   # nothing invented in Jira
        self.assertNotIn("From the story:", json.dumps([f["description"] for f in self.subtasks().values()]))
        self.assertEqual((data["stories_created"], data["failed"]), (3, []))

    def test_more_than_half_rejected_drops_the_whole_story_and_reports_it(self):
        self.sub_mode = "uncited"
        with self.assertLogs(ai.logger, "WARNING"):
            data = self.go(n=3).json()
        self.assertEqual((data["subtasks_created"], self.subtasks()), (0, {}))
        self.assertEqual([(d["story_id"], d["reason"]) for d in data["subtasks_skipped"]], [(f"US-0{i}", "criterion_citation") for i in (1, 2, 3)])
        self.assertIn("2 of its 2 sub-tasks", data["subtasks_skipped"][0]["detail"])
        self.assertEqual(len(data["subtasks_rejected"]), 6)
        self.assertEqual(data["subtask_details"], [])
        self.assertEqual((data["stories_created"], data["sprint_count"], data["failed"]), (3, 1, []))
        self.assertNotIn(("POST", "/rest/api/3/issue/bulk"), self.jira.requests)     # nothing to send

    def test_an_out_of_range_index_is_rejected_the_same_way(self):
        self.sub_mode = "out_of_range"
        with self.assertLogs(ai.logger, "WARNING"):
            data = self.go(n=2).json()
        self.assertEqual(data["subtasks_created"], 0)
        self.assertIn("cited criterion 5, but this story only has criteria 0-0", data["subtasks_rejected"][0]["reason"])
        self.assertEqual({d["reason"] for d in data["subtasks_skipped"]}, {"criterion_citation"})

    # ---- the AI part can fail without touching the push
    def test_an_invalid_ai_answer_skips_subtasks_and_the_push_succeeds(self):
        self.sub_mode = "unknown_story"
        with self.assertLogs(ai.logger, "WARNING"):
            data = self.go().json()
        self.assertEqual(data["subtasks_skipped"], [{"story_id": None, "reason": "invalid_ai_output", "detail": None}])
        self.assertEqual((data["stories_created"], data["sprint_count"], data["failed"]), (7, 2, []))
        self.assertEqual(self.subtasks(), {})

    def test_too_many_subtasks_for_a_story_is_a_validation_failure(self):
        self.sub_mode = "too_many"
        with self.assertLogs(ai.logger, "WARNING"):
            data = self.go().json()
        self.assertEqual(data["subtasks_skipped"][0]["reason"], "invalid_ai_output")
        self.assertEqual(data["stories_created"], 7)

    def test_the_ai_being_unavailable_skips_subtasks_but_not_the_push(self):
        self.sub_mode = "quota"
        with self.assertLogs(jira_push.logger, "WARNING"):
            r = self.go()
        data = r.json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(data["subtasks_skipped"], [{"story_id": None, "reason": "ai_unavailable", "detail": None}])
        self.assertEqual((data["stories_created"], data["sprint_count"], data["failed"]), (7, 2, []))

    def test_a_failure_of_the_story_ordering_still_fails_the_push_as_before(self):
        def only_ordering_fails(prompt, message, schema):
            if schema is ai.StoryOrderPlan:
                raise RateLimitError("slow down", response=httpx.Response(429, request=httpx.Request("POST", "https://api.groq.com/x")), body=None)
            return self.fake_groq(prompt, message, schema)
        with mock.patch.object(ai, "_structured_chat", only_ordering_fails):
            r = self.go()
        self.assertEqual((r.status_code, r.json()["detail"]), (503, "quota_exhausted"))
        self.assertEqual([c for c in self.jira.calls if c[0] in ("issue", "sprint", "move", "bulk")], [])

    # ---- Jira rejecting some or all sub-tasks never touches stories
    def test_some_subtasks_rejected_the_rest_created_and_stories_untouched(self):
        self.jira.reject_bulk_element = lambda f: (400, {"summary": "Summary is too long."}) if f["summary"].startswith("Frontend") and "US-03" in f["summary"] else None
        data = self.go().json()
        self.assertEqual((data["subtasks_created"], len(data["subtasks_failed"])), (13, 1))
        failure = data["subtasks_failed"][0]
        self.assertEqual(failure["story_id"], "US-03")
        self.assertIn("Summary is too long.", failure["reason"])
        self.assertTrue(failure["title"].startswith("Frontend work"))
        self.assertEqual(len(data["subtask_keys"]["US-03"]), 1)          # its other sub-task made it
        self.assertEqual((data["stories_created"], data["sprint_count"], data["failed"]), (7, 2, []))
        self.assertEqual(len(self.subtasks()), 13)
        for story_id, keys in data["subtask_keys"].items():          # the keys reported really belong to that story
            self.assertTrue(all(self.jira.issues[k]["parent"]["key"] == data["issue_keys"][story_id] for k in keys), story_id)

    def test_every_subtask_rejected_is_reported_per_subtask_and_the_push_still_succeeds(self):
        self.jira.reject_bulk_element = lambda f: (400, {"parent": "The parent issue can't have sub-tasks."})
        r = self.go()
        data = r.json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual((data["subtasks_created"], len(data["subtasks_failed"]), data["subtask_keys"]), (0, 14, {}))
        self.assertTrue(all("The parent issue can't have sub-tasks." in f["reason"] and f["title"] and f["story_id"] for f in data["subtasks_failed"]))
        self.assertEqual((data["stories_created"], data["sprint_count"], data["failed"]), (7, 2, []))

    def test_labels_jira_refuses_never_fail_a_subtask(self):
        self.jira.reject_bulk_element = lambda f: (400, {"labels": "Field 'labels' cannot be set."}) if "labels" in f else None
        data = self.go().json()
        self.assertEqual((data["subtasks_created"], data["subtasks_failed"]), (14, []))
        self.assertTrue(all("labels" not in f for f in self.subtasks().values()))
        entries = [e for e in data["labels_failed"] if e.get("kind") == "subtask"]
        self.assertEqual(len(entries), 14)
        self.assertTrue(all(e["issue_key"] in self.subtasks() and e["story_id"] for e in entries))
        self.assertEqual([c for c in self.jira.calls if c[0] == "bulk"], [("bulk", 14), ("bulk", 14)])   # one retry, not one per sub-task

    def test_more_than_fifty_subtasks_use_more_than_one_call_never_over_fifty(self):
        data = self.push(request_body(n=30, create_subtasks=True)).json()        # 60 sub-tasks
        self.assertEqual(data["subtasks_created"], 60)
        self.assertEqual([c[1] for c in self.jira.calls if c[0] == "bulk"], [50, 10])

    def test_the_subtasks_of_a_story_that_was_not_created_are_reported_not_attempted(self):
        self.jira.reject_issue = lambda f: (400, {"description": "bad"}) if f["summary"].startswith("As a user 3,") else None
        data = self.go().json()
        self.assertEqual([f["story_id"] for f in data["failed"]], ["US-03"])
        missing = [f for f in data["subtasks_failed"] if f["story_id"] == "US-03"]
        self.assertEqual(len(missing), 2)
        self.assertTrue(all(f["reason"] == "Its story wasn't created." for f in missing))
        self.assertEqual(data["subtasks_created"], 12)
        self.assertNotIn("US-03", data["subtask_keys"])

    def test_a_failure_that_would_hit_every_call_is_reported_and_the_push_still_succeeds(self):
        for status in (401, 429):
            self.setUp()
            self.jira.bulk_failure = (status, {"message": "nope"})
            r = self.go()
            data = r.json()
            self.assertEqual(r.status_code, 200, status)
            self.assertEqual((data["subtasks_created"], len(data["subtasks_failed"])), (0, 14), status)
            self.assertEqual((data["stories_created"], data["failed"]), (7, []), status)
            self.assertEqual(self.cookie_after["refresh_token"], "RT-1")

    def test_an_earlier_systemic_failure_means_no_subtask_calls_at_all(self):
        self.jira.reject_sprint = lambda b: (429, {"message": "slow down"})
        data = self.go().json()
        self.assertNotIn(("POST", "/rest/api/3/issue/bulk"), self.jira.requests)
        self.assertTrue(data["subtasks_failed"] and all(f["reason"].startswith("Not attempted") for f in data["subtasks_failed"]))

    def test_keys_are_not_guessed_when_jira_answers_with_a_different_number_of_issues(self):
        self.jira.bulk_issues_override = [{"id": "1", "key": "LBS-900", "self": "x"}]
        with self.assertLogs("jira_client", "WARNING"):
            data = self.go().json()
        self.assertEqual(data["subtask_keys"], {})                # no key is attributed to the wrong story
        self.assertEqual(data["subtasks_failed"], [])

    def test_a_dropped_connection_while_creating_subtasks_does_not_fail_the_push(self):
        handler = self.jira

        def drop_the_bulk_call(request):
            if request.url.path.endswith("/issue/bulk"):
                raise httpx.ConnectError("boom")
            return handler(request)

        with mock.patch.object(httpx, "AsyncClient", lambda **kw: REAL_ASYNC_CLIENT(transport=httpx.MockTransport(drop_the_bulk_call), **kw)):
            r = self.go()
        data = r.json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual((data["subtasks_created"], len(data["subtasks_failed"])), (0, 14))
        self.assertEqual((data["stories_created"], data["failed"]), (7, []))

    # ---- how many calls does it cost?
    def test_sub_tasks_cost_one_extra_jira_call_for_up_to_fifty_of_them(self):
        self.push(request_body(n=10))
        before = len(self.jira.requests)
        self.setUp()
        self.push(request_body(n=10, create_subtasks=True))
        after = len(self.jira.requests)
        self.assertEqual(after - before, 1)
        self.assertEqual(self.jira.requests[-1], ("POST", "/rest/api/3/issue/bulk"))


if __name__ == "__main__":
    unittest.main()
