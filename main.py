"""FastAPI backend for ReqPrint. Wraps the existing ai.py / export.py logic as HTTP
endpoints, and (once built) serves the React app itself, so the whole thing runs as
one process on one port."""
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
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
)
from export import build_docx

load_dotenv()
API_KEY = os.getenv("GROQ_API_KEY")

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="ReqPrint API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Every endpoint below lives under /api/... so it can never collide with a
# React file/route once the frontend is mounted at "/" further down.
api = APIRouter(prefix="/api")


# ---------- Request/response models ----------

class QAItem(BaseModel):
    q: str
    a: str


class NextQuestionRequest(BaseModel):
    description: str
    qa_history: list[QAItem] = []


class GenerateRequest(BaseModel):
    description: str
    qa_history: list[QAItem] = []


class ReviseRequest(BaseModel):
    data: dict
    instruction: str


class ReviewRequest(BaseModel):
    description: str
    qa_history: list[QAItem] = []
    data: dict


class ExtractNotesRequest(BaseModel):
    raw_notes: str


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
    return call_groq(revise_requirements, req.data, req.instruction)


@api.post("/review")
@limiter.limit("4/day")
def review_endpoint(request: Request, req: ReviewRequest):
    """Reviews the generated requirements from BA, developer, and QA perspectives."""
    if not API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not found. Check your .env file.")
    qa_history = [{"q": qa.q, "a": qa.a} for qa in req.qa_history]
    return call_groq(review_requirements, req.description, qa_history, req.data)


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
    buf = build_docx(data)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": "attachment; filename=requirements.docx"},
    )


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
