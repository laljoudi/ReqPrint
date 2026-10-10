"""Jira Cloud REST client for ReqPrint: token refresh, and everything the push
engine needs - projects, issue types, an epic, stories, sprints.

ROTATING REFRESH TOKENS: every refresh_access_token() call returns a NEW refresh
token and the one you passed in stops working. Whoever calls it must persist the
new one (re-set the jira_conn cookie) on every path afterwards, success or not.

Tokens and the client secret are never logged and never appear in any error
raised from here. Jira's own error text is passed through on purpose - it comes
from the response body, which never contains our credentials.
"""
import logging
import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import quote

import httpx

from jira_oauth import JIRA_CLIENT_ID, JIRA_CLIENT_SECRET, TOKEN_URL

logger = logging.getLogger(__name__)

API_BASE = "https://api.atlassian.com/ex/jira"
_TOKEN_TIMEOUT = httpx.Timeout(10.0)
_JIRA_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

# Which of these is right for current Jira Cloud is uncertain, so they're tried
# in order. (-classic is the company-managed Scrum template, -agility- the
# team-managed one.)
SCRUM_TEMPLATE_KEYS = (
    "com.pyxis.greenhopper.jira:gh-simplified-scrum-classic",
    "com.pyxis.greenhopper.jira:gh-simplified-agility-scrum",
)
MAX_KEY_ATTEMPTS = 5
_MAX_KEY_LENGTH = 10
_FALLBACK_KEY = "PRJ"  # when a name has fewer than 2 A-Z letters (e.g. Arabic)
_KEY_TAKEN_PHRASES = ("uses this project key", "already", "in use", "taken", "exists")


class TokenRefreshError(Exception):
    """The refresh call failed. reconnect_required is True when Atlassian
    definitively rejected the refresh token (the user must connect again) and
    False for a transient problem (network, Atlassian outage)."""

    def __init__(self, reconnect_required: bool, status: int | None = None, provider_error: str | None = None):
        super().__init__("Jira token refresh failed")
        self.reconnect_required = reconnect_required
        self.status = status
        self.provider_error = provider_error


class JiraApiError(Exception):
    """A Jira call failed. `status` is Jira's HTTP status (None if Jira couldn't
    be reached), `message` is Jira's own error text, `fields` its per-field
    errors, and `attempts` (project creation only) every try that was made."""

    def __init__(self, status: int | None, message: str, *, fields: dict | None = None, attempts: list | None = None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.fields = fields or {}
        self.attempts = attempts

    def describe(self) -> str:
        return self.message if self.status is None else f"Jira returned HTTP {self.status}: {self.message}"


class JiraSetupError(Exception):
    """Not a Jira failure but a fact about the project that stops a push - e.g.
    no Scrum board, or no Epic issue type. `code` is a short fixed identifier."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ---------- Token refresh ----------

def _oauth_error_code(resp: httpx.Response) -> str | None:
    """The short OAuth `error` code (e.g. invalid_grant) if the response has one."""
    try:
        code = resp.json().get("error")
    except (ValueError, AttributeError):
        return None
    return code if isinstance(code, str) and re.fullmatch(r"[a-z_]{1,40}", code) else None


async def refresh_access_token(refresh_token: str) -> dict:
    """Returns {"access_token", "refresh_token"}. The returned refresh token is
    the NEW one and must be saved by the caller (see the module docstring)."""
    try:
        async with httpx.AsyncClient(timeout=_TOKEN_TIMEOUT) as client:
            resp = await client.post(
                TOKEN_URL,
                json={
                    "grant_type": "refresh_token",
                    "client_id": JIRA_CLIENT_ID,
                    "client_secret": JIRA_CLIENT_SECRET,
                    "refresh_token": refresh_token,
                },
            )
    except httpx.HTTPError as e:
        logger.warning("Jira token refresh request failed: %s", type(e).__name__)
        raise TokenRefreshError(reconnect_required=False) from None
    if resp.status_code != 200:
        logger.warning("Jira token refresh failed: HTTP %s", resp.status_code)
        raise TokenRefreshError(
            reconnect_required=resp.status_code in (400, 401, 403),
            status=resp.status_code,
            provider_error=_oauth_error_code(resp),
        )
    try:
        tokens = resp.json()
    except ValueError:
        tokens = None
    access_token = tokens.get("access_token") if isinstance(tokens, dict) else None
    if not access_token:
        logger.warning("Jira token refresh response had no access token")
        raise TokenRefreshError(reconnect_required=False)
    # If rotation is ever switched off for the app, no new refresh token comes
    # back and the old one is still the valid one.
    return {"access_token": access_token, "refresh_token": tokens.get("refresh_token") or refresh_token}


# ---------- Authenticated Jira calls ----------

def _parse_jira_error(resp: httpx.Response) -> tuple[str, dict]:
    """Jira's error text and per-field errors. Jira answers in a few shapes:
    {"errorMessages": [...], "errors": {field: msg}} or {"code": 401, "message": ...}."""
    try:
        data = resp.json()
    except ValueError:
        data = None
    parts, fields = [], {}
    if isinstance(data, dict):
        parts += [str(m) for m in (data.get("errorMessages") or []) if m]
        if isinstance(data.get("errors"), dict):
            fields = {str(k): str(v) for k, v in data["errors"].items()}
            parts += [f"{k}: {v}" for k, v in fields.items()]
        if not parts and data.get("message"):
            parts.append(str(data["message"]))
    if not parts:
        parts.append(resp.text.strip()[:300] or resp.reason_phrase or f"HTTP {resp.status_code}")
    return "; ".join(parts)[:1000], fields


async def jira_request(cloud_id: str, access_token: str, method: str, path: str, *, params: dict | None = None, json: dict | None = None):
    """One authenticated call to https://api.atlassian.com/ex/jira/{cloud_id}{path}.
    Returns the parsed JSON body (None for an empty one); raises JiraApiError on
    any HTTP error >= 400 or if Jira can't be reached."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=_JIRA_TIMEOUT) as client:
            resp = await client.request(method, f"{API_BASE}/{cloud_id}{path}", params=params, json=json, headers=headers)
    except httpx.HTTPError as e:
        logger.warning("Jira %s %s failed: %s", method, path, type(e).__name__)
        raise JiraApiError(None, "Could not reach Jira (network error or timeout).") from None
    if resp.status_code >= 400:
        logger.warning("Jira %s %s failed: HTTP %s", method, path, resp.status_code)
        message, fields = _parse_jira_error(resp)
        raise JiraApiError(resp.status_code, message.replace(access_token, "[redacted]"), fields=fields)
    if not resp.content:
        return None
    try:
        return resp.json()
    except ValueError:
        raise JiraApiError(resp.status_code, "Jira returned a response that was not JSON.") from None


async def get_my_account_id(cloud_id: str, access_token: str) -> str:
    data = await jira_request(cloud_id, access_token, "GET", "/rest/api/3/myself")
    account_id = data.get("accountId") if isinstance(data, dict) else None
    if not account_id:
        raise JiraApiError(200, "Jira's /myself response had no accountId.")
    return account_id


# ---------- Create a Scrum project ----------

def derive_project_key(name: str) -> str:
    """A project key: uppercase A-Z only, 2-10 characters.
    Several words -> their initials ("Library Booking System" -> "LBS").
    One word (or too few usable initials) -> the name's own leading letters
    ("Library" -> "LIBRARY"). A name with under 2 such letters gets a fixed key."""
    words = [w for w in re.split(r"[\W\d_]+", name) if w]
    initials = re.sub(r"[^A-Z]", "", "".join(w[0] for w in words).upper())
    if len(words) >= 2 and len(initials) >= 2:
        return initials[:_MAX_KEY_LENGTH]
    letters = re.sub(r"[^A-Z]", "", name.upper())[:_MAX_KEY_LENGTH]
    return letters if len(letters) >= 2 else _FALLBACK_KEY


def _key_for_attempt(base: str, attempt: int) -> str:
    """Attempt 1 is the bare key; attempt n>1 swaps the tail for the digit n
    (KEY, KEY2, KEY3, ...), staying within the 10-character limit."""
    if attempt == 1:
        return base
    suffix = str(attempt)
    return base[: _MAX_KEY_LENGTH - len(suffix)] + suffix


def _is_key_taken(err: JiraApiError) -> bool:
    text = err.message.lower()
    about_key = "projectkey" in text or "project key" in text
    return err.status == 400 and about_key and any(p in text for p in _KEY_TAKEN_PHRASES)


async def create_scrum_project(cloud_id: str, access_token: str, site_url: str, name: str) -> dict:
    """Creates a Scrum project named `name`, led by the connected user.

    Key taken -> retry with KEY2, KEY3, ... (MAX_KEY_ATTEMPTS keys in all).
    Any other failure -> move on to the next template in SCRUM_TEMPLATE_KEYS.
    Returns {key, id, url, template_key}. Raises JiraApiError carrying every
    attempt's Jira message if it can't be done."""
    lead_account_id = await get_my_account_id(cloud_id, access_token)
    base = derive_project_key(name)
    attempts: list[dict] = []
    template_idx = 0
    key_attempt = 1
    while key_attempt <= MAX_KEY_ATTEMPTS:
        key = _key_for_attempt(base, key_attempt)
        template = SCRUM_TEMPLATE_KEYS[template_idx]
        try:
            created = await jira_request(
                cloud_id,
                access_token,
                "POST",
                "/rest/api/3/project",
                json={
                    "key": key,
                    "name": name,
                    "projectTypeKey": "software",
                    "projectTemplateKey": template,
                    "leadAccountId": lead_account_id,
                },
            )
        except JiraApiError as e:
            attempts.append({"key": key, "template": template, "jira_status": e.status, "jira_message": e.message})
            if e.status is None or e.status == 401:
                e.attempts = attempts  # retrying can't help
                raise
            if _is_key_taken(e):
                key_attempt += 1
                continue
            if template_idx + 1 < len(SCRUM_TEMPLATE_KEYS):
                template_idx += 1
                continue
            summary = "; ".join(
                f"{a['template']} (key {a['key']}) -> HTTP {a['jira_status']}: {a['jira_message']}" for a in attempts
            )
            raise JiraApiError(e.status, f"Jira rejected every Scrum template. {summary}", fields=e.fields, attempts=attempts) from None
        if not isinstance(created, dict):
            raise JiraApiError(200, "Jira's create-project response was not the expected object.", attempts=attempts)
        project_key = created.get("key") or key
        return {
            "key": project_key,
            "id": str(created.get("id", "")),
            "url": f"{site_url.rstrip('/')}/browse/{project_key}",
            "template_key": template,
        }
    tried = ", ".join(a["key"] for a in attempts)
    raise JiraApiError(
        400,
        f"No free project key after {MAX_KEY_ATTEMPTS} attempts ({tried}). Last Jira message: {attempts[-1]['jira_message']}",
        attempts=attempts,
    )


# ---------- Find the project's board ----------

async def find_scrum_board(cloud_id: str, access_token: str, project_key: str) -> int | None:
    """The id of the project's first board of type "scrum", or None. Also proves
    whether the granted scopes are enough for the Agile API: if they aren't,
    this raises JiraApiError with Jira's message rather than returning None."""
    data = await jira_request(
        cloud_id, access_token, "GET", "/rest/agile/1.0/board", params={"projectKeyOrId": project_key}
    )
    for board in (data.get("values") if isinstance(data, dict) else None) or []:
        if isinstance(board, dict) and board.get("type") == "scrum":
            return board.get("id")
    return None


# ---------- Atlassian Document Format (ADF) ----------
# API v3 takes rich text - an issue's description - as ADF JSON, never as a
# plain string. These build the few node types the push needs.

def _inline(item) -> list[dict]:
    """Inline nodes for a str, or for a (label, text) pair whose label is bold."""
    label, text = item if isinstance(item, tuple) else (None, item)
    text = " ".join(str(text).split())
    nodes = []
    if label:
        nodes.append({"type": "text", "text": f"{label} " if text else label, "marks": [{"type": "strong"}]})
    if text:
        nodes.append({"type": "text", "text": text})
    return nodes


def adf_paragraph(item="") -> dict:
    return {"type": "paragraph", "content": _inline(item)}


def adf_heading(text: str, level: int = 3) -> dict:
    return {"type": "heading", "attrs": {"level": level}, "content": _inline(text)}


def adf_bullets(items) -> dict:
    """A bullet list; items are str or (label, text). Needs at least one item."""
    return {"type": "bulletList", "content": [{"type": "listItem", "content": [adf_paragraph(i)]} for i in items]}


def adf_document(*blocks) -> dict:
    return {"type": "doc", "version": 1, "content": list(blocks) or [adf_paragraph()]}


def adf_from_text(text: str) -> dict:
    """Plain multi-line text -> a document with one paragraph per non-empty line."""
    return adf_document(*[adf_paragraph(line) for line in text.splitlines() if line.strip()])


# ---------- Projects ----------

_MAX_PAGES = 20


def _project_summary(project: dict) -> dict:
    return {
        "key": project.get("key"),
        "id": project.get("id"),
        "name": project.get("name"),
        "project_type": project.get("projectTypeKey"),
        "style": project.get("style"),
    }


async def list_projects(cloud_id: str, access_token: str) -> list[dict]:
    """Software projects the user may create issues in - the candidates for
    "use an existing project". Returns [{key, id, name, project_type, style}]."""
    projects, start_at = [], 0
    for _ in range(_MAX_PAGES):
        page = await jira_request(
            cloud_id,
            access_token,
            "GET",
            "/rest/api/3/project/search",
            params={"typeKey": "software", "action": "create", "orderBy": "name", "startAt": start_at, "maxResults": 100},
        )
        values = page.get("values") if isinstance(page, dict) else None
        if not values:
            break
        projects += [_project_summary(v) for v in values if isinstance(v, dict)]
        if page.get("isLast", True):
            break
        start_at += len(values)
    return projects


async def get_project(cloud_id: str, access_token: str, project_key: str) -> dict:
    """One project's {key, id, name, project_type, style}. Jira answers 404 for a
    project that doesn't exist *or* that the user can't see."""
    data = await jira_request(cloud_id, access_token, "GET", f"/rest/api/3/project/{quote(project_key, safe='')}")
    if not isinstance(data, dict) or not data.get("key"):
        raise JiraApiError(200, "Jira's project response was not the expected object.")
    return _project_summary(data)


# ---------- Issue types ----------

async def _all_pages(cloud_id: str, access_token: str, path: str, list_key: str) -> list[dict]:
    """Every item of a paged create-metadata response (startAt / maxResults / total)."""
    items, start_at = [], 0
    for _ in range(_MAX_PAGES):
        page = await jira_request(cloud_id, access_token, "GET", path, params={"startAt": start_at, "maxResults": 200})
        chunk = page.get(list_key) if isinstance(page, dict) else None
        if not chunk:
            break
        items += [x for x in chunk if isinstance(x, dict)]
        start_at += len(chunk)
        total = page.get("total")
        if not isinstance(total, int) or start_at >= total:
            break
    return items


async def resolve_issue_types(cloud_id: str, access_token: str, project_key: str) -> dict:
    """The ids to create issues with in this project: {"epic": {id, name},
    "story": {id, name}}. Story falls back to Task when the project has no Story.
    Raises JiraSetupError if there's no Epic, or neither Story nor Task."""
    types = await _all_pages(
        cloud_id, access_token, f"/rest/api/3/issue/createmeta/{quote(project_key, safe='')}/issuetypes", "issueTypes"
    )
    standard = [t for t in types if not t.get("subtask")]

    def by_name(name: str):
        return next((t for t in standard if str(t.get("name", "")).lower() == name), None)

    epic = by_name("epic") or next((t for t in standard if t.get("hierarchyLevel") == 1), None)
    story = by_name("story") or by_name("task")
    available = ", ".join(str(t.get("name")) for t in types) or "none"
    if not epic:
        raise JiraSetupError(
            "no_epic_issue_type",
            f"Project {project_key} has no Epic issue type you can create (available: {available}).",
        )
    if not story:
        raise JiraSetupError(
            "no_story_issue_type",
            f"Project {project_key} has neither a Story nor a Task issue type you can create (available: {available}).",
        )
    return {
        "epic": {"id": str(epic["id"]), "name": epic.get("name")},
        "story": {"id": str(story["id"]), "name": story.get("name")},
    }


async def find_epic_name_field(cloud_id: str, access_token: str, project_key: str, epic_type_id: str) -> str | None:
    """The id of the "Epic Name" custom field if it's on the Epic create screen,
    else None. Some company-managed setups still require it (Atlassian has said
    it will become optional). Jira's rule is that only fields in the create
    metadata may be set, so it is set only when it is listed here. Anything but
    an auth failure counts as "not found" - creating the epic then reports what
    Jira actually needs."""
    path = (
        f"/rest/api/3/issue/createmeta/{quote(project_key, safe='')}/issuetypes/{quote(epic_type_id, safe='')}"
    )
    try:
        fields = await _all_pages(cloud_id, access_token, path, "fields")
    except JiraApiError as e:
        if e.status == 401:
            raise
        logger.warning("Could not read the Epic create fields: %s", e.describe())
        return None
    for field in fields:
        schema = field.get("schema") or {}
        if str(schema.get("custom", "")).endswith(":gh-epic-label") or field.get("name") == "Epic Name":
            return field.get("fieldId")
    return None


# ---------- Issues ----------

# Jira limits the summary field to 255 characters; stay safely under.
_MAX_SUMMARY_LENGTH = 254


def _summary(text: str) -> str:
    """One line, trimmed to fit Jira's summary field."""
    text = " ".join(str(text).split())
    return text if len(text) <= _MAX_SUMMARY_LENGTH else text[: _MAX_SUMMARY_LENGTH - 1].rstrip() + "…"


# ---------- Labels ----------

BASE_LABEL = "reqprint"


def slugify_label(text: str | None) -> str | None:
    """Turns free text into a valid Jira label, or None if nothing usable is left.
    Jira labels cannot contain spaces (Atlassian's documented rule), so this keeps
    only lowercase ASCII letters and digits and joins words with hyphens:
    "HR Tech" -> "hr-tech". Accents are folded ("Café" -> "cafe"); text with no
    Latin letters or digits at all (e.g. Arabic) yields None."""
    folded = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-")
    return slug or None


def build_labels(category: str | None = None) -> list[str]:
    """The labels for every issue a push creates: "reqprint", plus the project
    category if one was given and it slugifies to something."""
    labels = [BASE_LABEL]
    slug = slugify_label(category)
    if slug and slug not in labels:
        labels.append(slug)
    return labels


@dataclass(frozen=True)
class CreatedIssue:
    """A created issue's key, and - only if Jira refused the labels and the issue
    was created without them - Jira's reason."""

    key: str
    labels_dropped: str | None = None


async def _create_issue(cloud_id: str, access_token: str, fields: dict, labels: list[str] | None = None) -> CreatedIssue:
    """Creates the issue with `labels`. Labels never fail an issue: if Jira
    rejects the request over the labels field, it is logged and the issue is
    created again without them. Any other error propagates as usual."""
    dropped = None
    try:
        data = await jira_request(
            cloud_id,
            access_token,
            "POST",
            "/rest/api/3/issue",
            json={"fields": {**fields, "labels": labels} if labels else fields},
        )
    except JiraApiError as e:
        if not (labels and e.status == 400 and ("labels" in e.fields or "label" in e.message.lower())):
            raise
        dropped = e.message
        logger.warning("Jira rejected the labels %s; creating the issue without them: %s", labels, dropped)
        data = await jira_request(cloud_id, access_token, "POST", "/rest/api/3/issue", json={"fields": fields})
    key = data.get("key") if isinstance(data, dict) else None
    if not key:
        raise JiraApiError(201, "Jira's create-issue response had no issue key.")
    return CreatedIssue(key, dropped)


async def create_epic(
    cloud_id: str,
    access_token: str,
    *,
    project_key: str,
    issue_type_id: str,
    name: str,
    functional: list[str],
    non_functional: list[str],
    assumptions: list[str],
    epic_name_field_id: str | None = None,
    labels: list[str] | None = None,
) -> CreatedIssue:
    """One epic, named after the project; its description lists the functional
    requirements, the non-functional requirements and the assumptions."""
    blocks = []
    for title, items in (
        ("Functional requirements", functional),
        ("Non-functional requirements", non_functional),
        ("Assumptions", assumptions),
    ):
        items = [i.strip() for i in items if i and i.strip()]
        if items:
            blocks += [adf_heading(title), adf_bullets(items)]
    fields = {
        "project": {"key": project_key},
        "issuetype": {"id": issue_type_id},
        "summary": _summary(name),
        "description": adf_document(*blocks),
    }
    if epic_name_field_id:
        fields[epic_name_field_id] = _summary(name)
    return await _create_issue(cloud_id, access_token, fields, labels)


async def create_story(
    cloud_id: str,
    access_token: str,
    *,
    project_key: str,
    issue_type_id: str,
    epic_key: str,
    story: dict,
    criteria: list[dict],
    labels: list[str] | None = None,
) -> CreatedIssue:
    """One story under the epic (via `parent`). The summary is the story
    statement; the description carries the role and the story's acceptance
    criteria as Given/When/Then. `story` is {id, role, story}; `criteria` are that
    story's rows of {scenario, given, when, then}."""
    statement = " ".join(str(story.get("story", "")).split()) or str(story.get("id", ""))
    summary = _summary(statement)
    blocks = []
    if summary != statement:
        blocks.append(adf_paragraph(("Story:", statement)))  # too long for the summary: keep it whole here
    if story.get("role"):
        blocks.append(adf_paragraph(("Role:", story["role"])))
    if criteria:
        blocks.append(adf_heading("Acceptance criteria"))
    for c in criteria:
        if c.get("scenario"):
            blocks.append(adf_paragraph(("Scenario:", c["scenario"])))
        steps = [(label, c[key]) for label, key in (("Given", "given"), ("When", "when"), ("Then", "then")) if c.get(key)]
        if steps:
            blocks.append(adf_bullets(steps))
    return await _create_issue(
        cloud_id,
        access_token,
        {
            "project": {"key": project_key},
            "issuetype": {"id": issue_type_id},
            "summary": summary,
            "description": adf_document(*blocks),
            "parent": {"key": epic_key},
        },
        labels,
    )


# ---------- Sprints ----------

# The API accepts up to 50 issues per move, but doesn't say the order of that
# list becomes their rank order - and the order is the point of this feature.
# So each issue is moved on its own and ranked right after the previous one
# (rankAfterIssue), which the API does define. Raising this trades that
# guarantee for fewer calls.
MOVE_GROUP_SIZE = 1


async def create_sprint(
    cloud_id: str,
    access_token: str,
    board_id: int,
    name: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """A new sprint on the board, in the future state. The dates (strings in the
    API's format, see sprint_plan.format_jira_datetime) are optional and are set
    in the same call, which the API supports. Dates never fail a sprint: if Jira
    rejects the request with them, the sprint is created again without. Returns
    {id, name, state, dates_set, dates_error} - dates_set is True only if Jira
    echoed both dates back; dates_error is Jira's reason when they were rejected."""
    body = {"name": name, "originBoardId": board_id}
    wants_dates = bool(start_date and end_date)
    if wants_dates:
        body.update(startDate=start_date, endDate=end_date)
    dates_error = None
    try:
        data = await jira_request(cloud_id, access_token, "POST", "/rest/agile/1.0/sprint", json=body)
    except JiraApiError as e:
        if not wants_dates or e.status != 400:
            raise
        dates_error = e.describe()
        logger.warning("Jira rejected the sprint dates; creating the sprint without them: %s", dates_error)
        wants_dates = False
        data = await jira_request(
            cloud_id, access_token, "POST", "/rest/agile/1.0/sprint", json={"name": name, "originBoardId": board_id}
        )
    if not isinstance(data, dict) or data.get("id") is None:
        raise JiraApiError(201, "Jira's create-sprint response had no sprint id.")
    dates_set = bool(wants_dates and data.get("startDate") and data.get("endDate"))
    if wants_dates and not dates_set:
        dates_error = "Jira created the sprint but did not return its start and end dates."
        logger.warning(dates_error)
    return {
        "id": data["id"],
        "name": data.get("name", name),
        "state": data.get("state"),
        "dates_set": dates_set,
        "dates_error": dates_error,
    }


async def move_issues_to_sprint(cloud_id: str, access_token: str, sprint_id: int, issue_keys: list[str]) -> dict:
    """Moves the issues into the sprint, keeping the order given: each is ranked
    after the last one that moved successfully (see MOVE_GROUP_SIZE). One issue
    failing doesn't stop the rest. A failure that would hit every call (Jira
    unreachable, rejected credentials, rate-limited) stops early and says why.
    Returns {"moved": [keys], "failed": {key: reason}, "stopped": reason | None}."""
    moved: list[str] = []
    failed: dict[str, str] = {}
    previous = None
    for start in range(0, len(issue_keys), MOVE_GROUP_SIZE):
        group = issue_keys[start : start + MOVE_GROUP_SIZE]
        body: dict = {"issues": group}
        if previous:
            body["rankAfterIssue"] = previous
        try:
            await jira_request(cloud_id, access_token, "POST", f"/rest/agile/1.0/sprint/{sprint_id}/issue", json=body)
        except JiraApiError as e:
            if e.status in (None, 401, 403, 429):
                reason = e.describe()
                for key in issue_keys[start:]:
                    failed[key] = reason
                return {"moved": moved, "failed": failed, "stopped": reason}
            for key in group:
                failed[key] = e.describe()
            continue
        moved += group
        previous = group[-1]
    return {"moved": moved, "failed": failed, "stopped": None}
