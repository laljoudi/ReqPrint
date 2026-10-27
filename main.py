"""FastAPI backend for ReqPrint. Wraps the existing ai.py / export.py logic as HTTP
endpoints, and (once built) serves the React app itself, so the whole thing runs as
one process on one port."""
import asyncio
import ipaddress
import logging
import os
from datetime import date
from pathlib import Path
from typing import Annotated, Literal

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from groq import APIError as GroqAPIError, RateLimitError

from ai import (
    next_question,
    generate_requirements,
    revise_requirements,
    review_requirements,
    extract_from_notes,
    plan_story_order,
    plan_subtasks,
    GeneratedRequirements,
)
from export import build_docx, validate_docx_data
from jira_client import TokenRefreshError, refresh_access_token
from jira_push import MAX_STORIES, run_push
from sprint_plan import MAX_SPRINT_LENGTH_WEEKS, MIN_SPRINT_LENGTH_WEEKS, parse_start_date
from jira_oauth import (
    CONNECTION_COOKIE,
    STATE_COOKIE,
    JiraOAuthError,
    build_authorize_url,
    clear_connection_cookie,
    exchange_code,
    finish_popup,
    load_connection,
    new_state,
    provider_error_reason,
    set_connection_cookie,
    set_state_cookie,
    states_match,
)

load_dotenv()
logger = logging.getLogger(__name__)  # TEMPORARY, with the log line in client_ip_key
API_KEY = os.getenv("GROQ_API_KEY")

def client_ip_key(request: Request) -> str:
    """The rate-limit key: the visitor's IP.

    Behind Render the TCP peer is Render's proxy, so request.client.host is the same
    for everyone and a per-IP limit would be shared by all visitors. On a public Render
    web service Cloudflare sets CF-Connecting-IP itself, overwriting anything the caller
    sent, so that header is the real client. X-Forwarded-For is deliberately NOT used:
    proxies append to it, so its leftmost entry is whatever the caller wrote.

    With no (or an unparseable) CF-Connecting-IP - local dev, tests, a direct hit on the
    container - this is exactly what it was before: request.client.host."""
    header = request.headers.get("cf-connecting-ip")
    logger.warning("cf-connecting-ip present: %s", bool(header))  # TEMPORARY
    if header:
        try:
            return str(ipaddress.ip_address(header.strip()))
        except ValueError:
            pass  # not an IP: never let a made-up value become a limiter key
    return get_remote_address(request)


limiter = Limiter(key_func=client_ip_key)

app = FastAPI(title="ReqPrint API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Every endpoint below lives under /api/... so it can never collide with a
# React file/route once the frontend is mounted at "/" further down.
api = APIRouter(prefix="/api")


# ---------- Request/response models ----------

MAX_DESCRIPTION_CHARS = 20_000
MAX_RAW_NOTES_CHARS = 30_000
MAX_INSTRUCTION_CHARS = 4_000
MAX_QA_ITEMS = 8
MAX_QA_QUESTION_CHARS = 600
MAX_QA_ANSWER_CHARS = 4_000
MAX_REQUIREMENT_TEXT_CHARS = 1_500
MAX_REQUIREMENT_ITEMS = 100
MAX_ACCEPTANCE_CRITERIA = 300
MAX_ASSUMPTIONS = 100

RequirementText = Annotated[str, Field(min_length=1, max_length=MAX_REQUIREMENT_TEXT_CHARS)]
OptionalRequirementText = Annotated[str, Field(max_length=MAX_REQUIREMENT_TEXT_CHARS)]


class QAItem(BaseModel):
    q: str = Field(max_length=MAX_QA_QUESTION_CHARS)
    a: str = Field(max_length=MAX_QA_ANSWER_CHARS)


class NextQuestionRequest(BaseModel):
    description: str = Field(min_length=1, max_length=MAX_DESCRIPTION_CHARS)
    qa_history: list[QAItem] = Field(default_factory=list, max_length=MAX_QA_ITEMS)


class GenerateRequest(BaseModel):
    description: str = Field(min_length=1, max_length=MAX_DESCRIPTION_CHARS)
    qa_history: list[QAItem] = Field(default_factory=list, max_length=MAX_QA_ITEMS)


class ReviseRequest(BaseModel):
    data: GeneratedRequirements
    instruction: str = Field(min_length=1, max_length=MAX_INSTRUCTION_CHARS)


class ReviewRequest(BaseModel):
    description: str = Field(min_length=1, max_length=MAX_DESCRIPTION_CHARS)
    qa_history: list[QAItem] = Field(default_factory=list, max_length=MAX_QA_ITEMS)
    data: GeneratedRequirements


class ExtractNotesRequest(BaseModel):
    raw_notes: str = Field(min_length=1, max_length=MAX_RAW_NOTES_CHARS)


class PushStory(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    id: str = Field(min_length=1, max_length=50)
    role: OptionalRequirementText = ""
    story: RequirementText


class PushCriterion(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    story_id: str = Field(default="", max_length=50)
    scenario: OptionalRequirementText = ""
    given: OptionalRequirementText = ""
    when: OptionalRequirementText = ""
    then: OptionalRequirementText = ""


class PushRequirementLists(BaseModel):
    functional: list[RequirementText] = Field(default_factory=list, max_length=MAX_REQUIREMENT_ITEMS)
    non_functional: list[RequirementText] = Field(default_factory=list, max_length=MAX_REQUIREMENT_ITEMS)


class PushDocument(BaseModel):
    """The parts of the generated requirements document a Jira push uses.
    Anything else in the document (e.g. use_cases) is accepted and ignored."""

    requirements: PushRequirementLists = Field(default_factory=PushRequirementLists)
    user_stories: list[PushStory] = Field(min_length=1, max_length=MAX_STORIES)
    acceptance_criteria: list[PushCriterion] = Field(default_factory=list, max_length=MAX_ACCEPTANCE_CRITERIA)
    assumptions: list[RequirementText] = Field(default_factory=list, max_length=MAX_ASSUMPTIONS)

    @model_validator(mode="after")
    def story_ids_are_unique(self):
        ids = [s.id for s in self.user_stories]
        if len(set(ids)) != len(ids):
            raise ValueError("user_stories must have unique ids")
        return self


class JiraPushRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    mode: Literal["create", "existing"]
    project_name: str | None = Field(default=None, max_length=80)
    project_key: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_]{1,50}$")
    capacity_per_week: int = Field(strict=True, ge=1, le=50)
    category: str | None = Field(default=None, max_length=80)
    start_date: date | None = None  # "YYYY-MM-DD"; omitted -> sprint 1 starts today
    sprint_length_weeks: int | None = Field(default=None, strict=True, ge=MIN_SPRINT_LENGTH_WEEKS, le=MAX_SPRINT_LENGTH_WEEKS)
    create_subtasks: bool = Field(default=False, strict=True)  # off unless asked: the push is then exactly what it was
    requirements: PushDocument

    @field_validator("start_date", mode="before")
    @classmethod
    def start_date_is_yyyy_mm_dd(cls, value):
        # Pydantic's own date parsing also takes timestamps and other layouts; only YYYY-MM-DD is allowed here.
        return None if value is None else parse_start_date(value)

    @model_validator(mode="after")
    def mode_has_what_it_needs(self):
        if self.mode == "create" and not self.project_name:
            raise ValueError('mode "create" needs project_name')
        if self.mode == "existing" and not self.project_key:
            raise ValueError('mode "existing" needs project_key')
        return self


def final_input_text(description: str, qa_history: list[QAItem]) -> str:
    """Combine the description with the collected answers, same as the Streamlit app."""
    text = description + "\n\nClarifying questions and answers:\n"
    for qa in qa_history:
        text += f"Q: {qa.q}\nA: {qa.a}\n"
    return text


def call_groq(func, *args):
    """Run a Groq-backed function, translating an exhausted-quota error
    (Groq 429 / rate limit) into a distinct 503 so the frontend
    can tell a quota problem apart from a genuine server error. Any other Groq
    API error becomes a plain 500."""
    try:
        return func(*args)
    except RateLimitError:
        raise HTTPException(status_code=503, detail="quota_exhausted")
    except GroqAPIError as e:
        if getattr(e, "status_code", None) == 429:
            raise HTTPException(status_code=503, detail="quota_exhausted")
        raise HTTPException(status_code=500, detail="Generation failed.")


@api.get("/health")
def health():
    return {"message": "ReqPrint API is running"}


@api.post("/next-question")
@limiter.limit("12/day")
def next_question_endpoint(request: Request, req: NextQuestionRequest):
    """Asks Groq for the next clarifying question based on the description and answers so far."""
    if not API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not found. Check your .env file.")
    qa_history = [{"q": qa.q, "a": qa.a} for qa in req.qa_history]
    return call_groq(next_question, req.description, qa_history)


@api.post("/generate")
@limiter.limit("2/day")
def generate_endpoint(request: Request, req: GenerateRequest):
    """Generates the structured requirements document from the description + answered questions."""
    if not API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not found. Check your .env file.")
    text = final_input_text(req.description, req.qa_history)
    return call_groq(generate_requirements, text)


@api.post("/revise")
@limiter.limit("4/day")
def revise_endpoint(request: Request, req: ReviseRequest):
    """Edits the existing requirements document based on a free-text instruction."""
    if not API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not found. Check your .env file.")
    return call_groq(revise_requirements, req.data.model_dump(), req.instruction)


@api.post("/review")
@limiter.limit("4/day")
def review_endpoint(request: Request, req: ReviewRequest):
    """Reviews the generated requirements from BA, developer, and QA perspectives."""
    if not API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not found. Check your .env file.")
    qa_history = [{"q": qa.q, "a": qa.a} for qa in req.qa_history]
    return call_groq(review_requirements, req.description, qa_history, req.data.model_dump())


@api.post("/extract-notes")
@limiter.limit("10/day")
def extract_notes_endpoint(request: Request, req: ExtractNotesRequest):
    """Extracts clear requirements, implied user stories, and open questions from
    raw pasted notes - an alternative to typing a clean project description."""
    if not API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not found. Check your .env file.")
    return call_groq(extract_from_notes, req.raw_notes)


@api.post("/export")
@limiter.limit("4/day")
def export_endpoint(request: Request, data: dict):
    """Builds a .docx file from the requirements data and returns it for download."""
    try:
        data = validate_docx_data(data)
    except ValueError:
        raise HTTPException(status_code=422, detail="invalid_requirements_document")
    buf = build_docx(data)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": "attachment; filename=requirements.docx"},
    )


# ---------- Jira connection (stage 1: OAuth only) ----------

@api.get("/jira/login")
@limiter.limit("30/day")
def jira_login(request: Request):
    """Starts the Atlassian OAuth flow: remember a random `state` in a short-lived
    cookie, then send the browser to Atlassian's consent screen."""
    state = new_state()
    response = RedirectResponse(build_authorize_url(state), status_code=302)
    set_state_cookie(response, state)
    return response


@api.get("/jira/callback")
@limiter.limit("30/day")
async def jira_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    """Where Atlassian sends the user back. Always answers with the small popup
    page that tells the app window how it went, then closes itself."""
    if error:
        return finish_popup({"type": "jira-error", "reason": provider_error_reason(error)})
    if not code or not states_match(state, request.cookies.get(STATE_COOKIE)):
        return finish_popup({"type": "jira-error", "reason": "state_mismatch"}, status_code=400)
    try:
        connection = await exchange_code(code)
    except JiraOAuthError as e:
        return finish_popup({"type": "jira-error", "reason": e.reason}, status_code=502)
    return finish_popup({"type": "jira-connected"}, connection=connection)


@api.get("/jira/status")
@limiter.limit("300/day")
def jira_status(request: Request):
    """Whether this browser has a Jira connection. Never returns the refresh token."""
    connection = load_connection(request.cookies.get(CONNECTION_COOKIE))
    body = (
        {"connected": True, "site_name": connection["site_name"], "site_url": connection["site_url"]}
        if connection
        else {"connected": False}
    )
    return JSONResponse(body, headers={"Cache-Control": "no-store"})


@api.post("/jira/logout")
@limiter.limit("30/day")
def jira_logout(request: Request):
    """Forgets the Jira connection by deleting the cookie."""
    response = JSONResponse({"connected": False}, headers={"Cache-Control": "no-store"})
    clear_connection_cookie(response)
    return response


# ---------- Jira push ----------

async def order_stories_via_groq(user_stories: list[dict]) -> list[dict]:
    """Runs the (blocking) AI ordering off the event loop, through call_groq so a
    Groq quota/rate-limit error still becomes 503 quota_exhausted."""
    return await asyncio.to_thread(call_groq, plan_story_order, user_stories)


async def plan_subtasks_via_groq(user_stories: list[dict], acceptance_criteria: list[dict]) -> dict | None:
    """Runs the (blocking) sub-task planning off the event loop, through call_groq like
    every other AI call. The push treats any failure here as "skip the sub-tasks"."""
    return await asyncio.to_thread(call_groq, plan_subtasks, user_stories, acceptance_criteria)


@api.post("/jira/push")
@limiter.limit("10/day")
async def jira_push(request: Request, req: JiraPushRequest):
    """Builds a Jira project from the generated requirements: an epic, its stories
    in a meaningful order, and future sprints holding them."""
    if not API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not found. Check your .env file.")
    connection = load_connection(request.cookies.get(CONNECTION_COOKIE))
    if not connection:
        raise HTTPException(status_code=400, detail="not_connected")
    try:
        tokens = await refresh_access_token(connection["refresh_token"])
    except TokenRefreshError as e:
        # No new token exists, so the cookie is left exactly as it was.
        if e.reconnect_required:
            body = {
                "detail": "reconnect_required",
                "message": "Atlassian rejected the saved Jira connection - connect Jira again.",
            }
            return JSONResponse(body, status_code=401, headers={"Cache-Control": "no-store"})
        body = {"detail": "token_refresh_failed", "message": "Could not refresh the Jira token (network problem or Atlassian outage). Try again."}
        return JSONResponse(body, status_code=502, headers={"Cache-Control": "no-store"})

    # Refresh tokens rotate: the one in the cookie is dead now, so the new one
    # goes back on every response from here on, whether or not the rest works.
    connection = {**connection, "refresh_token": tokens["refresh_token"]}
    status, body = await run_push(
        connection,
        tokens["access_token"],
        mode=req.mode,
        project_name=req.project_name,
        project_key=req.project_key,
        capacity_per_week=req.capacity_per_week,
        document=req.requirements.model_dump(),
        order_stories=order_stories_via_groq,
        category=req.category,
        start_date=req.start_date,
        sprint_length_weeks=req.sprint_length_weeks,
        create_subtasks=req.create_subtasks,
        plan_subtasks=plan_subtasks_via_groq,
    )
    response = JSONResponse(body, status_code=status, headers={"Cache-Control": "no-store"})
    set_connection_cookie(response, connection)
    return response


app.include_router(api)

# Serve the built React app (frontend/dist, created by `npm run build`) for every
# route that isn't one of the /api/... routes above. This MUST be added last:
# FastAPI checks routes in the order they were registered, so mounting here first
# would swallow every request before it ever reached /api/*.
# In local dev this directory won't exist yet (the frontend runs on its own Vite
# server instead) - only mount it if a build is actually present.
FRONTEND_DIST = Path(__file__).parent / "frontend" / "dist"
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
