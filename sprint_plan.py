"""Sprint math for the Jira push. Pure functions: no AI, no I/O.

Every story counts as one unit; nothing is estimated. A team's weekly capacity,
in stories, times the sprint length gives how many stories fit in one sprint,
and the stories - already in the order the AI put them - fill sprints front to
back.
"""
import math
import re
from datetime import date, datetime, time, timedelta, timezone

SPRINT_LENGTH_WEEKS = 2  # the default length, used when the caller doesn't choose one
MIN_SPRINT_LENGTH_WEEKS = 1
MAX_SPRINT_LENGTH_WEEKS = 4
MIN_CAPACITY_PER_WEEK = 1
MAX_CAPACITY_PER_WEEK = 50
# A start date may be in the past (documenting work already underway), but not
# absurd: a year far outside this would produce dates Jira won't take.
EARLIEST_START_DATE = date(2000, 1, 1)
LATEST_START_DATE = date(2099, 12, 31)


def _check_capacity(capacity_per_week) -> None:
    # bool is an int subclass; True is not a capacity.
    if isinstance(capacity_per_week, bool) or not isinstance(capacity_per_week, int):
        raise ValueError("capacity_per_week must be an integer")
    if not MIN_CAPACITY_PER_WEEK <= capacity_per_week <= MAX_CAPACITY_PER_WEEK:
        raise ValueError(
            f"capacity_per_week must be between {MIN_CAPACITY_PER_WEEK} and {MAX_CAPACITY_PER_WEEK}"
        )


def resolve_sprint_length(sprint_length_weeks: int | None = None) -> int:
    """The sprint length to use: the one given (checked), else the default."""
    if sprint_length_weeks is None:
        return SPRINT_LENGTH_WEEKS
    if isinstance(sprint_length_weeks, bool) or not isinstance(sprint_length_weeks, int):
        raise ValueError("sprint_length_weeks must be an integer")
    if not MIN_SPRINT_LENGTH_WEEKS <= sprint_length_weeks <= MAX_SPRINT_LENGTH_WEEKS:
        raise ValueError(
            f"sprint_length_weeks must be between {MIN_SPRINT_LENGTH_WEEKS} and {MAX_SPRINT_LENGTH_WEEKS}"
        )
    return sprint_length_weeks


def parse_start_date(text: str) -> date:
    """"YYYY-MM-DD" -> a date. Nothing else is accepted: not another layout, not a
    date that doesn't exist (2026-02-30), not a time. Past dates are fine."""
    if not isinstance(text, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", text):
        raise ValueError("start_date must be written YYYY-MM-DD, for example 2026-11-03")
    try:
        day = date.fromisoformat(text)
    except ValueError:
        raise ValueError(f"start_date {text} is not a real calendar date") from None
    if not EARLIEST_START_DATE <= day <= LATEST_START_DATE:
        raise ValueError(f"start_date must be between {EARLIEST_START_DATE} and {LATEST_START_DATE}")
    return day


def stories_per_sprint(capacity_per_week: int, sprint_length_weeks: int | None = None) -> int:
    _check_capacity(capacity_per_week)
    return capacity_per_week * resolve_sprint_length(sprint_length_weeks)


def sprint_count(total_stories: int, capacity_per_week: int, sprint_length_weeks: int | None = None) -> int:
    return math.ceil(total_stories / stories_per_sprint(capacity_per_week, sprint_length_weeks))


def plan_sprints(
    ordered_story_ids: list[str], capacity_per_week: int, sprint_length_weeks: int | None = None
) -> list[list[str]]:
    """Splits the ordered story ids into sprints, filled in the order given.
    Returns one list of ids per sprint - none for no stories - and every id
    lands in exactly one sprint. Only the last sprint can be short."""
    per_sprint = stories_per_sprint(capacity_per_week, sprint_length_weeks)
    return [ordered_story_ids[i : i + per_sprint] for i in range(0, len(ordered_story_ids), per_sprint)]


def sprint_windows(
    count: int, first_day: date, sprint_length_weeks: int | None = None
) -> list[tuple[datetime, datetime]]:
    """The (start, end) of each of `count` back-to-back sprints, as UTC midnights.
    Sprint 1 starts on `first_day`; every sprint lasts `sprint_length_weeks` (the
    default if omitted) and the next one starts at the instant it ends, so there
    are no gaps."""
    length = timedelta(weeks=resolve_sprint_length(sprint_length_weeks))
    first = datetime.combine(first_day, time.min, tzinfo=timezone.utc)
    return [(first + i * length, first + (i + 1) * length) for i in range(count)]


def format_jira_datetime(moment: datetime) -> str:
    """UTC, in the shape of the Jira Software API's own example
    ("2015-04-20T01:22:00.000+10:00"): ISO 8601, milliseconds, numeric offset."""
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000+00:00")
