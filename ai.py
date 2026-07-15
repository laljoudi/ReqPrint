"""Everything related to calling Gemini. Reusable by any interface."""
import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types
from functools import lru_cache

from prompts import GENERATE_PROMPT, REVISE_PROMPT, NEXT_QUESTION_PROMPT

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "gemini-2.5-flash"

@lru_cache
def _client():
    return genai.Client(api_key=API_KEY)


def next_question(description, qa_history):
    """Ask Gemini for the next clarifying question, based on the answers so far.
    Returns a dict like {"done": false, "question": "..."} or {"done": true, "question": null}."""
    convo = f"Description: {description}\n\nPrevious questions and answers:\n"
    for qa in qa_history:
        convo += f"Q: {qa['q']}\nA: {qa['a']}\n"
    convo += "\nNow ask the next question, or return done if you have enough."
    resp = _client().models.generate_content(
        model=MODEL, contents=convo,
        config=types.GenerateContentConfig(
            system_instruction=NEXT_QUESTION_PROMPT, temperature=0.3,
            response_mime_type="application/json"),
    )
    return json.loads(resp.text)


def generate_requirements(user_text):
    """Generate the structured requirements document from text (description + answers)."""
    resp = _client().models.generate_content(
        model=MODEL, contents=user_text,
        config=types.GenerateContentConfig(
            system_instruction=GENERATE_PROMPT, temperature=0.3,
            response_mime_type="application/json"),
    )
    return json.loads(resp.text)


def revise_requirements(current_data, instruction):
    """Edit the existing document based on a chat instruction."""
    message = f"CURRENT JSON:\n{json.dumps(current_data)}\n\nINSTRUCTION:\n{instruction}"
    resp = _client().models.generate_content(
        model=MODEL, contents=message,
        config=types.GenerateContentConfig(
            system_instruction=REVISE_PROMPT, temperature=0.3,
            response_mime_type="application/json"),
    )
    return json.loads(resp.text)