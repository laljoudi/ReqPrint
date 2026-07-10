"""FastAPI backend for ReqPrint. Wraps the existing ai.py / export.py logic as HTTP endpoints."""
import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ai import next_question, generate_requirements, revise_requirements
from export import build_docx

load_dotenv()
APP_PASSWORD = os.getenv("APP_PASSWORD")
API_KEY = os.getenv("GEMINI_API_KEY")

app = FastAPI(title="ReqPrint API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:5174", "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


class LoginRequest(BaseModel):
    password: str


def final_input_text(description: str, qa_history: list[QAItem]) -> str:
    """Combine the description with the collected answers, same as the Streamlit app."""
    text = description + "\n\nClarifying questions and answers:\n"
    for qa in qa_history:
        text += f"Q: {qa.q}\nA: {qa.a}\n"
    return text


@app.get("/")
def home():
    return {"message": "ReqPrint API is running"}


@app.post("/login")
def login(req: LoginRequest):
    """Checks the submitted password against APP_PASSWORD from .env."""
    if not APP_PASSWORD:
        raise HTTPException(status_code=500, detail="APP_PASSWORD not set. Check your .env file.")
    if req.password != APP_PASSWORD:
        raise HTTPException(status_code=401, detail="Incorrect password.")
    return {"ok": True}


@app.post("/next-question")
def next_question_endpoint(req: NextQuestionRequest):
    """Asks Gemini for the next clarifying question based on the description and answers so far."""
    if not API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not found. Check your .env file.")
    qa_history = [{"q": qa.q, "a": qa.a} for qa in req.qa_history]
    return next_question(req.description, qa_history)


@app.post("/generate")
def generate_endpoint(req: GenerateRequest):
    """Generates the structured requirements document from the description + answered questions."""
    if not API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not found. Check your .env file.")
    text = final_input_text(req.description, req.qa_history)
    return generate_requirements(text)


@app.post("/revise")
def revise_endpoint(req: ReviseRequest):
    """Edits the existing requirements document based on a free-text instruction."""
    if not API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not found. Check your .env file.")
    try:
        return revise_requirements(req.data, req.instruction)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {e}")


@app.post("/export")
def export_endpoint(data: dict):
    """Builds a .docx file from the requirements data and returns it for download."""
    buf = build_docx(data)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": "attachment; filename=requirements.docx"},
    )
