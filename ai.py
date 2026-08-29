"""Everything related to calling Groq. Reusable by any interface."""
import os
import json
from dotenv import load_dotenv
from groq import Groq
from functools import lru_cache

from prompts import GENERATE_PROMPT, REVISE_PROMPT, NEXT_QUESTION_PROMPT, REVIEW_PROMPT

load_dotenv()
API_KEY = os.getenv("GROQ_API_KEY")
MODEL = "openai/gpt-oss-120b"

@lru_cache
def _client():
    return Groq(api_key=API_KEY)


def _json_chat(system_prompt, user_message):
    resp = _client().chat.completions.create(
        model=MODEL,
        temperature=0.3,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    return json.loads(resp.choices[0].message.content)


def next_question(description, qa_history):
    """Ask Groq for the next clarifying question, based on the answers so far.
    Returns a dict like {"done": false, "question": "..."} or {"done": true, "question": null}."""
    convo = f"Description: {description}\n\nPrevious questions and answers:\n"
    for qa in qa_history:
        convo += f"Q: {qa['q']}\nA: {qa['a']}\n"
    convo += "\nNow ask the next question, or return done if you have enough."
    return _json_chat(NEXT_QUESTION_PROMPT, convo)


def generate_requirements(user_text):
    """Generate the structured requirements document from text (description + answers)."""
    return _json_chat(GENERATE_PROMPT, user_text)


def revise_requirements(current_data, instruction):
    """Edit the existing document based on a chat instruction."""
    message = f"CURRENT JSON:\n{json.dumps(current_data)}\n\nINSTRUCTION:\n{instruction}"
    return _json_chat(REVISE_PROMPT, message)


def review_requirements(description, qa_history, generated_requirements):
    """Review the generated requirements from BA, developer, and QA perspectives."""
    message = {
        "original_description": description,
        "qa_history": qa_history,
        "generated_requirements": generated_requirements,
    }
    return _json_chat(REVIEW_PROMPT, json.dumps(message))
