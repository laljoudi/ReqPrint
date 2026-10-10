"""The push engine: turns a generated requirements document into a real Jira
project - an epic, its stories in a meaningful order, and future sprints holding
them.

Order of work: preflight (resolve or create the project, find its Scrum board,
resolve the issue types) -> order the stories -> compute sprints -> create the
epic -> the stories -> the sprints -> distribute. Nothing is created before
preflight passes (for a new project, creating the project *is* part of
preflight). Once the epic exists, one story failing never stops the rest and
nothing is ever rolled back: the result lists exactly what worked and what didn't.

run_push never raises: the caller must always get the chance to re-set the
rotated refresh-token cookie. Tokens are never logged or returned.
"""
import asyncio
import logging
from datetime import date, datetime, timezone

from fastapi import HTTPException

from jira_client import (
    JiraApiError,
    JiraSetupError,
    build_labels,
    create_epic,
    create_scrum_project,
    create_sprint,
    create_story,
    find_epic_name_field,
    find_scrum_board,
    get_project,
    move_issues_to_sprint,
    resolve_issue_types,
)
from sprint_plan import format_jira_datetime, plan_sprints, resolve_sprint_length, sprint_windows

logger = logging.getLogger(__name__)

# Sequential calls, ~0.3-0.5s each: this bounds how long one push can take.
MAX_STORIES = 100
BOARD_POLLS = 3  # a new project's board may take a moment to show up
BOARD_POLL_DELAY = 1.0
SPRINT_NAME_PREFIX = "ReqPrint Sprint"


def _today_utc():
    return datetime.now(timezone.utc).date()


def _is_systemic(e: JiraApiError) -> bool:
    """A failure that would hit every following call too: Jira unreachable,
    credentials rejected, no permission, or rate-limited."""
    return e.status in (None, 401, 403, 429)


def jira_failure(e: JiraApiError) -> tuple[int, dict]:
    body = {"jira_status": e.status, "jira_message": e.message}
    if e.attempts:
        body["attempts"] = e.attempts
    if e.status == 401:
        body["detail"] = "reconnect_required"
        body["message"] = "Jira rejected the access token (401) - reconnect Jira."
        return 401, body
    if e.status == 403:
        body["detail"] = "forbidden"
        body["message"] = (
            "Jira returned 403: a scope or permission is likely missing - check the app's scopes in the "
            f"Atlassian developer console, and that this account may do this. Jira said: {e.message}"
        )
        return 403, body
    body["detail"] = "jira_error"
    body["message"] = e.describe()
    return 502, body


async def run_push(
    connection: dict,
    access_token: str,
    *,
    mode: str,
    project_name: str | None,
    project_key: str | None,
    capacity_per_week: int,
    document: dict,
    order_stories,
    category: str | None = None,
    start_date: date | None = None,
    sprint_length_weeks: int | None = None,
) -> tuple[int, dict]:
    """Returns (http_status, body). `order_stories` is an async callable taking the
    document's user_stories and returning plan_story_order's result; it may raise
    HTTPException (from main.call_groq) for an AI/quota failure."""
    cloud_id, site_url = connection["cloud_id"], connection["site_url"].rstrip("/")
    labels = build_labels(category)
    labels_failed: list[dict] = []
    labels_blocked: dict[str, str] = {}  # issue type id -> why Jira refused labels there; we stop asking
    state = {"step": "project", "project_key": None, "project_url": None, "created": False}
    try:
        # ---- 1. preflight: project, board, issue types
        if mode == "create":
            project = await create_scrum_project(cloud_id, access_token, site_url, project_name)
            key, epic_name = project["key"], project_name
            state.update(project_key=key, project_url=project["url"], created=True)
            state["step"] = "board"
            board_id = None
            for poll in range(BOARD_POLLS):
                board_id = await find_scrum_board(cloud_id, access_token, key)
                if board_id is not None:
                    break
                if poll < BOARD_POLLS - 1:
                    await asyncio.sleep(BOARD_POLL_DELAY)
        else:
            project = await get_project(cloud_id, access_token, project_key)
            key, epic_name = project["key"], project["name"]
            state.update(project_key=key, project_url=f"{site_url}/browse/{key}")
            state["step"] = "board"
            board_id = await find_scrum_board(cloud_id, access_token, key)
        if board_id is None:
            raise JiraSetupError(
                "no_scrum_board",
                f"Project {key} has no Scrum board, so it can't have sprints (Kanban and business projects don't).",
            )
        state["step"] = "issue_types"
        types = await resolve_issue_types(cloud_id, access_token, key)
        epic_name_field = await find_epic_name_field(cloud_id, access_token, key, types["epic"]["id"])

        # ---- 2. order the stories, then compute the sprints
        state["step"] = "ordering"
        stories = document["user_stories"]
        order = await order_stories(stories)
        ordered_ids = [item["story_id"] for item in order]
        weeks = resolve_sprint_length(sprint_length_weeks)
        first_day = start_date or _today_utc()
        sprint_plan = plan_sprints(ordered_ids, capacity_per_week, weeks)

        # ---- 3. the epic (fatal if it fails: the stories hang off it)
        state["step"] = "epic"
        requirements = document["requirements"]
        epic = await create_epic(
            cloud_id,
            access_token,
            project_key=key,
            issue_type_id=types["epic"]["id"],
            name=epic_name,
            functional=requirements["functional"],
            non_functional=requirements["non_functional"],
            assumptions=document["assumptions"],
            epic_name_field_id=epic_name_field,
            labels=labels,
        )
        epic_key = epic.key
        if epic.labels_dropped:
            labels_blocked[types["epic"]["id"]] = epic.labels_dropped
            labels_failed.append({"issue_key": epic_key, "story_id": None, "reason": epic.labels_dropped})
    except JiraApiError as e:
        if e.status == 404 and state["step"] == "project" and mode == "existing":
            status, body = 404, {
                "detail": "project_not_found",
                "message": f"No project with key {project_key} was found, or this account can't see it.",
                "jira_status": e.status,
                "jira_message": e.message,
            }
        else:
            status, body = jira_failure(e)
        return _preflight_failure(status, body, state)
    except JiraSetupError as e:
        return _preflight_failure(422, {"detail": e.code, "message": e.message}, state)
    except HTTPException as e:
        return _preflight_failure(e.status_code, {"detail": e.detail}, state)
    except Exception as e:  # noqa: BLE001 - run_push must never raise; only the type is logged/returned
        logger.warning("Unexpected error during Jira push preflight: %s", type(e).__name__)
        return _preflight_failure(
            500, {"detail": "internal_error", "message": f"Unexpected {type(e).__name__} - see the server log."}, state
        )

    # ---- 4. the stories, one by one, in order. From here on nothing is fatal.
    by_id = {s["id"]: s for s in stories}
    criteria: dict[str, list[dict]] = {}
    for c in document["acceptance_criteria"]:
        criteria.setdefault(c["story_id"], []).append(c)
    created: dict[str, str] = {}
    failed: list[dict] = []
    stopped = None
    for story_id in ordered_ids:
        if stopped:
            failed.append({"story_id": story_id, "reason": f"Not attempted: {stopped}"})
            continue
        try:
            issue = await create_story(
                cloud_id,
                access_token,
                project_key=key,
                issue_type_id=types["story"]["id"],
                epic_key=epic_key,
                story=by_id[story_id],
                criteria=criteria.get(story_id, []),
                labels=None if types["story"]["id"] in labels_blocked else labels,
            )
            created[story_id] = issue.key
            if issue.labels_dropped:
                labels_blocked[types["story"]["id"]] = issue.labels_dropped
                labels_failed.append({"issue_key": issue.key, "story_id": story_id, "reason": issue.labels_dropped})
            elif types["story"]["id"] in labels_blocked:
                # Not even tried: Jira already refused labels for this issue type. Still reported.
                reason = f"Not sent: Jira refused labels for this issue type earlier in this push ({labels_blocked[types['story']['id']]})"
                labels_failed.append({"issue_key": issue.key, "story_id": story_id, "reason": reason})
        except JiraApiError as e:
            failed.append({"story_id": story_id, "reason": e.describe()})
            if _is_systemic(e):
                stopped = e.describe()
        except Exception as e:  # noqa: BLE001 - keep going; report only the type
            logger.warning("Unexpected error creating a story: %s", type(e).__name__)
            failed.append({"story_id": story_id, "reason": f"Unexpected error ({type(e).__name__})"})

    # ---- 5. the sprints, and putting the stories in them
    sprints: list[dict] = []
    # Dates follow the plan, not what got created: sprint N always starts when N-1 ends.
    windows = sprint_windows(len(sprint_plan), first_day, weeks)
    for index, chunk in enumerate(sprint_plan, start=1):
        members = [(sid, created[sid]) for sid in chunk if sid in created]
        if not members:
            continue
        name = f"{SPRINT_NAME_PREFIX} {index}"
        start_date, end_date = (format_jira_datetime(d) for d in windows[index - 1])
        if stopped:
            failed += [
                {"story_id": sid, "reason": f"Created as {k}, but not moved to a sprint. Not attempted: {stopped}"}
                for sid, k in members
            ]
            continue
        try:
            sprint = await create_sprint(cloud_id, access_token, board_id, name, start_date, end_date)
            outcome = await move_issues_to_sprint(cloud_id, access_token, sprint["id"], [k for _, k in members])
        except JiraApiError as e:  # only create_sprint raises this; the moves report their own failures
            failed += [
                {"story_id": sid, "reason": f"Created as {k}, but sprint '{name}' could not be created: {e.describe()}"}
                for sid, k in members
            ]
            if _is_systemic(e):
                stopped = e.describe()
            continue
        except Exception as e:  # noqa: BLE001
            logger.warning("Unexpected error creating a sprint: %s", type(e).__name__)
            failed += [
                {"story_id": sid, "reason": f"Created as {k}, but sprint '{name}' failed unexpectedly ({type(e).__name__})"}
                for sid, k in members
            ]
            continue
        moved = set(outcome["moved"])
        failed += [
            {"story_id": sid, "reason": f"Created as {k}, but could not be moved to '{name}': {outcome['failed'][k]}"}
            for sid, k in members
            if k in outcome["failed"]
        ]
        entry = {
            "id": sprint["id"],
            "name": name,
            "story_ids": [sid for sid, k in members if k in moved],
            "start_date": start_date,
            "end_date": end_date,
            "dates_set": sprint["dates_set"],
        }
        if sprint["dates_error"]:
            entry["dates_error"] = sprint["dates_error"]
        sprints.append(entry)
        if outcome["stopped"]:
            stopped = outcome["stopped"]

    return 200, {
        "project_key": key,
        "project_url": state["project_url"],
        "project_created": state["created"],
        "board_id": board_id,
        "epic_key": epic_key,
        "sprint_count": len(sprints),
        "stories_created": len(created),
        "failed": failed,
        "sprints": sprints,
        "issue_keys": created,
        "order": order,
        "labels": labels,
        "labels_failed": labels_failed,
        "start_date": first_day.isoformat(),
        "sprint_length_weeks": weeks,
    }


def _preflight_failure(status: int, body: dict, state: dict) -> tuple[int, dict]:
    """An error before any story exists. Says which step failed and exactly what
    (if anything) was already created."""
    body["step"] = state["step"]
    if state["project_key"]:
        body.update(project_key=state["project_key"], project_url=state["project_url"], project_created=state["created"])
    body["note"] = (
        "The project was created, but no epic, stories or sprints were."
        if state["created"]
        else "Nothing was created in Jira."
    )
    return status, body
