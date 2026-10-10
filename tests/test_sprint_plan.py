"""Unit tests for the sprint math. Run from the repo root:
    .venv/bin/python -m unittest discover -s tests -t . -v"""
import math
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest import mock

import sprint_plan
from sprint_plan import (
    format_jira_datetime,
    parse_start_date,
    plan_sprints,
    resolve_sprint_length,
    sprint_count,
    sprint_windows,
    stories_per_sprint,
)


def ids(n):
    return [f"US-{i:02d}" for i in range(1, n + 1)]


class PlanSprintsEdgeCases(unittest.TestCase):
    def test_zero_stories_means_no_sprints(self):
        self.assertEqual(plan_sprints([], 4), [])
        self.assertEqual(sprint_count(0, 4), 0)

    def test_one_story_is_one_sprint_of_one(self):
        self.assertEqual(plan_sprints(["US-01"], 4), [["US-01"]])
        self.assertEqual(sprint_count(1, 4), 1)

    def test_exact_multiples_fill_every_sprint_completely(self):
        # capacity 2/week x 2-week sprints = 4 stories per sprint
        self.assertEqual(plan_sprints(ids(4), 2), [ids(4)])
        self.assertEqual([len(s) for s in plan_sprints(ids(8), 2)], [4, 4])
        self.assertEqual([len(s) for s in plan_sprints(ids(12), 2)], [4, 4, 4])

    def test_one_over_a_multiple_starts_a_new_sprint(self):
        self.assertEqual([len(s) for s in plan_sprints(ids(9), 2)], [4, 4, 1])
        self.assertEqual([len(s) for s in plan_sprints(ids(5), 2)], [4, 1])

    def test_one_short_of_a_multiple_leaves_the_last_sprint_short(self):
        self.assertEqual([len(s) for s in plan_sprints(ids(7), 2)], [4, 3])

    def test_capacity_larger_than_the_story_count_is_a_single_sprint(self):
        self.assertEqual(plan_sprints(ids(3), 50), [ids(3)])  # room for 100
        self.assertEqual(sprint_count(3, 50), 1)


class PlanSprintsBehaviour(unittest.TestCase):
    def test_fills_sprints_in_the_order_given(self):
        order = ["US-05", "US-01", "US-03", "US-02", "US-04"]
        self.assertEqual(plan_sprints(order, 1), [["US-05", "US-01"], ["US-03", "US-02"], ["US-04"]])

    def test_every_story_lands_in_exactly_one_sprint_and_order_is_kept(self):
        for capacity in (1, 3, 7, 50):
            for total in (0, 1, 2, 13, 99, 100, 101, 250):
                flat = [s for sprint in plan_sprints(ids(total), capacity) for s in sprint]
                self.assertEqual(flat, ids(total), (capacity, total))

    def test_sprint_count_is_ceil_of_stories_over_stories_per_sprint(self):
        for capacity in range(1, 51):
            for total in (0, 1, 2, 3, 49, 50, 51, 100, 101, 199, 200, 201):
                expected = math.ceil(total / (capacity * 2))
                self.assertEqual(sprint_count(total, capacity), expected)
                self.assertEqual(len(plan_sprints(ids(total), capacity)), expected)

    def test_sprint_length_is_a_named_constant_that_drives_the_math(self):
        self.assertEqual(sprint_plan.SPRINT_LENGTH_WEEKS, 2)
        self.assertEqual(stories_per_sprint(4), 8)
        with mock.patch.object(sprint_plan, "SPRINT_LENGTH_WEEKS", 3):
            self.assertEqual(stories_per_sprint(4), 12)
            self.assertEqual([len(s) for s in plan_sprints(ids(25), 4)], [12, 12, 1])

    def test_does_not_modify_its_input(self):
        original = ids(9)
        snapshot = list(original)
        plan_sprints(original, 2)
        self.assertEqual(original, snapshot)


class CapacityValidation(unittest.TestCase):
    def test_accepts_the_whole_1_to_50_range(self):
        for capacity in (1, 2, 25, 49, 50):
            plan_sprints(ids(3), capacity)

    def test_rejects_anything_else(self):
        for bad in (0, -1, 51, 100, 2.5, 4.0, "4", None, True, False, [4]):
            with self.assertRaises(ValueError, msg=repr(bad)):
                plan_sprints(ids(3), bad)


class SprintDates(unittest.TestCase):
    TODAY = date(2026, 10, 8)

    def test_sprint_one_starts_today_at_utc_midnight_and_lasts_the_sprint_length(self):
        (start, end), = sprint_windows(1, self.TODAY)
        self.assertEqual(start, datetime(2026, 10, 8, tzinfo=timezone.utc))
        self.assertEqual(end - start, timedelta(weeks=2))
        self.assertEqual(end, datetime(2026, 10, 22, tzinfo=timezone.utc))

    def test_each_sprint_starts_the_instant_the_previous_one_ends(self):
        windows = sprint_windows(6, self.TODAY)
        for (_, previous_end), (next_start, _) in zip(windows, windows[1:]):
            self.assertEqual(previous_end, next_start)
        self.assertTrue(all(end - start == timedelta(weeks=2) for start, end in windows))
        self.assertEqual(windows[-1][1], datetime(2026, 12, 31, tzinfo=timezone.utc))  # 6 sprints x 14 days from Oct 8

    def test_no_sprints_no_windows(self):
        self.assertEqual(sprint_windows(0, self.TODAY), [])

    def test_crosses_month_and_year_boundaries_and_leap_days(self):
        windows = sprint_windows(3, date(2027, 12, 20))
        self.assertEqual([format_jira_datetime(s) for s, _ in windows], ["2027-12-20T00:00:00.000+00:00", "2028-01-03T00:00:00.000+00:00", "2028-01-17T00:00:00.000+00:00"])
        self.assertEqual(format_jira_datetime(sprint_windows(1, date(2028, 2, 20))[0][1]), "2028-03-05T00:00:00.000+00:00")  # 2028 is a leap year

    def test_the_length_is_the_named_constant(self):
        with mock.patch.object(sprint_plan, "SPRINT_LENGTH_WEEKS", 3):
            (start, end), = sprint_windows(1, self.TODAY)
        self.assertEqual(end - start, timedelta(weeks=3))

    def test_format_matches_the_api_example_shape_in_utc(self):
        self.assertEqual(format_jira_datetime(datetime(2026, 10, 8, tzinfo=timezone.utc)), "2026-10-08T00:00:00.000+00:00")
        self.assertRegex(format_jira_datetime(sprint_windows(1, self.TODAY)[0][0]), r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}[+-]\d{2}:\d{2}$")
        # a non-UTC moment is converted, not mislabelled
        plus_three = datetime(2026, 10, 8, 3, 0, tzinfo=timezone(timedelta(hours=3)))
        self.assertEqual(format_jira_datetime(plus_three), "2026-10-08T00:00:00.000+00:00")


class SprintLength(unittest.TestCase):
    def test_default_is_the_named_constant_when_omitted_or_none(self):
        self.assertEqual(resolve_sprint_length(), 2)
        self.assertEqual(resolve_sprint_length(None), sprint_plan.SPRINT_LENGTH_WEEKS)
        self.assertEqual(stories_per_sprint(4), stories_per_sprint(4, None))
        self.assertEqual(plan_sprints(ids(9), 2), plan_sprints(ids(9), 2, None))
        self.assertEqual(sprint_windows(2, date(2026, 10, 8)), sprint_windows(2, date(2026, 10, 8), None))

    def test_allowed_lengths_are_1_to_4(self):
        for weeks in (1, 2, 3, 4):
            self.assertEqual(resolve_sprint_length(weeks), weeks)

    def test_anything_else_is_rejected(self):
        for bad in (0, 5, -1, 10, 2.0, 2.5, "2", [2], True, False):
            with self.assertRaises(ValueError, msg=repr(bad)):
                resolve_sprint_length(bad)

    def test_the_capacity_math_uses_the_chosen_length_not_a_baked_in_2(self):
        for weeks, capacity, expected in ((1, 4, 4), (2, 4, 8), (3, 4, 12), (4, 4, 16), (3, 1, 3), (4, 50, 200)):
            self.assertEqual(stories_per_sprint(capacity, weeks), expected, (weeks, capacity))

    def test_stories_fill_sprints_of_the_chosen_size_in_order(self):
        # capacity 2/week: 1 week -> 2 per sprint, 3 weeks -> 6 per sprint, 4 weeks -> 8 per sprint
        self.assertEqual([len(s) for s in plan_sprints(ids(7), 2, 1)], [2, 2, 2, 1])
        self.assertEqual([len(s) for s in plan_sprints(ids(7), 2, 3)], [6, 1])
        self.assertEqual([len(s) for s in plan_sprints(ids(7), 2, 4)], [7])
        self.assertEqual([x for sprint in plan_sprints(ids(20), 3, 3) for x in sprint], ids(20))

    def test_sprint_count_follows_the_length(self):
        self.assertEqual(sprint_count(7, 2), 2)       # 4 per sprint
        self.assertEqual(sprint_count(7, 2, 1), 4)    # 2 per sprint
        self.assertEqual(sprint_count(7, 2, 3), 2)    # 6 per sprint
        self.assertEqual(sprint_count(12, 2, 3), 2)   # exact multiple
        self.assertEqual(sprint_count(13, 2, 3), 3)
        self.assertEqual(sprint_count(0, 2, 3), 0)

    def test_an_invalid_length_is_rejected_by_every_function_that_takes_it(self):
        for call in (lambda: stories_per_sprint(2, 5), lambda: sprint_count(3, 2, 0), lambda: plan_sprints(ids(3), 2, 9),
                     lambda: sprint_windows(1, date(2026, 10, 8), 5)):
            with self.assertRaises(ValueError):
                call()

    def test_windows_last_the_chosen_length_and_stay_back_to_back(self):
        for weeks in (1, 2, 3, 4):
            windows = sprint_windows(5, date(2026, 11, 8), weeks)
            self.assertTrue(all(end - start == timedelta(weeks=weeks) for start, end in windows), weeks)
            for (_, previous_end), (next_start, _) in zip(windows, windows[1:]):
                self.assertEqual(previous_end, next_start)
            self.assertEqual(windows[0][0], datetime(2026, 11, 8, tzinfo=timezone.utc))

    def test_three_week_sprints_from_a_month_out(self):
        windows = sprint_windows(2, date(2026, 11, 8), 3)
        self.assertEqual([(format_jira_datetime(a), format_jira_datetime(b)) for a, b in windows], [
            ("2026-11-08T00:00:00.000+00:00", "2026-11-29T00:00:00.000+00:00"),
            ("2026-11-29T00:00:00.000+00:00", "2026-12-20T00:00:00.000+00:00"),
        ])

    def test_the_named_default_still_drives_everything_when_no_length_is_given(self):
        with mock.patch.object(sprint_plan, "SPRINT_LENGTH_WEEKS", 4):
            self.assertEqual(stories_per_sprint(2), 8)
            (start, end), = sprint_windows(1, date(2026, 10, 8))
        self.assertEqual(end - start, timedelta(weeks=4))


class StartDate(unittest.TestCase):
    def test_a_yyyy_mm_dd_string_becomes_that_date(self):
        self.assertEqual(parse_start_date("2026-11-03"), date(2026, 11, 3))
        self.assertEqual(parse_start_date("2028-02-29"), date(2028, 2, 29))  # leap day

    def test_past_dates_are_allowed(self):
        self.assertEqual(parse_start_date("2020-01-15"), date(2020, 1, 15))
        self.assertEqual(parse_start_date("2000-01-01"), date(2000, 1, 1))

    def test_malformed_dates_are_rejected_with_a_message_that_names_the_field_and_format(self):
        for bad in ("10/08/2026", "2026-10-8", "2026-1-08", "26-10-08", "20261008", "2026-10-08T00:00:00", "2026-10-08 ", " 2026-10-08",
                    "tomorrow", "", "2026/10/08", "2026-10-08Z", "٢٠٢٦-١٠-٠٨", 20261008, None, 1760000000):
            with self.assertRaises(ValueError, msg=repr(bad)) as ctx:
                parse_start_date(bad)
            self.assertIn("start_date", str(ctx.exception))
            self.assertIn("YYYY-MM-DD", str(ctx.exception))

    def test_dates_that_do_not_exist_are_rejected(self):
        for bad in ("2026-13-01", "2026-00-10", "2026-02-30", "2027-02-29", "2026-04-31", "2026-10-00", "2026-10-32"):
            with self.assertRaises(ValueError, msg=bad) as ctx:
                parse_start_date(bad)
            self.assertIn("not a real calendar date", str(ctx.exception))

    def test_absurd_years_are_rejected_so_the_dates_stay_usable(self):
        for bad in ("1999-12-31", "0001-01-01", "2100-01-01", "9999-12-31"):
            with self.assertRaises(ValueError, msg=bad):
                parse_start_date(bad)

    def test_the_latest_start_with_the_longest_possible_plan_still_makes_valid_dates(self):
        # 100 stories at capacity 1 with 1-week sprints is the longest plan: 100 sprints.
        windows = sprint_windows(100, parse_start_date("2099-12-31"), 1)
        self.assertEqual(format_jira_datetime(windows[-1][1])[:4], "2101")


if __name__ == "__main__":
    unittest.main()
