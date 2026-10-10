"""Everything related to calling Groq. Reusable by any interface."""
import os
import json
import logging
from collections import Counter
from dotenv import load_dotenv
from groq import BadRequestError, Groq
from functools import lru_cache
from typing import Literal
from pydantic import BaseModel

from prompts import (
    GENERATE_PROMPT,
    REVISE_PROMPT,
    NEXT_QUESTION_PROMPT,
    REVIEW_PROMPT,
    NOTES_EXTRACTION_PROMPT,
    STORY_ORDER_PROMPT,
)

load_dotenv()
logger = logging.getLogger(__name__)
API_KEY = os.getenv("GROQ_API_KEY")
MODEL = "openai/gpt-oss-120b"

@lru_cache
def _client():
    return Groq(api_key=API_KEY)


class NotesExtraction(BaseModel):
    clear_requirements: list[str]
    implied_user_stories: list[str]
    open_questions: list[str]


class NextQuestionResult(BaseModel):
    done: bool
    question: str | None
    suggested_answers: list[str]


class Requirements(BaseModel):
    functional: list[str]
    non_functional: list[str]


class UserStory(BaseModel):
    id: str
    role: str
    story: str


class AcceptanceCriterion(BaseModel):
    story_id: str
    scenario: str
    given: str
    when: str
    then: str


class UseCase(BaseModel):
    use_case_id: str
    actors: str
    description: str
    preconditions: str
    trigger: str
    main_flow: str
    alternative_flow: str


class GeneratedRequirements(BaseModel):
    """The full requirements document shape - shared by generate_requirements()
    and revise_requirements(), since REVISE_PROMPT returns the same structure
    it was given, just edited."""

    requirements: Requirements
    user_stories: list[UserStory]
    acceptance_criteria: list[AcceptanceCriterion]
    use_cases: list[UseCase]
    assumptions: list[str]


class ReviewIssue(BaseModel):
    role: Literal["Business Analyst", "Developer", "QA Tester"]
    severity: Literal["low", "medium", "high"]
    issue: str
    why_it_matters: str
    suggested_fix: str


class ReviewResult(BaseModel):
    issues: list[ReviewIssue]


class StoryOrderItem(BaseModel):
    story_id: str
    reason: str
    depends_on: list[str]


class StoryOrderPlan(BaseModel):
    ordered_stories: list[StoryOrderItem]


def _forbid_additional_properties(schema):
    """Recursively set "additionalProperties": false on every object schema -
    the top level AND every nested model Pydantic hoists into "$defs" (e.g. a
    list[SomeModel] field). Groq's strict mode requires this on every object
    in the schema, not just the root one; Pydantic doesn't add it anywhere by
    default."""
    if schema.get("type") == "object":
        schema["additionalProperties"] = False
    for def_schema in schema.get("$defs", {}).values():
        _forbid_additional_properties(def_schema)


def _structured_chat(system_prompt, user_message, schema_model):
    """Every Groq call in this file goes through here. Constrains the model at
    the API level using Groq's native JSON Schema structured outputs (strict
    mode) - the response is guaranteed to match schema_model's shape rather
    than merely instructed to via prompt text. Returns a validated instance of
    schema_model.

    Groq's strict mode requires every object in the schema to set
    "additionalProperties": false (Pydantic doesn't add this by default), and
    all fields to be listed as required - which model_json_schema() already
    does for non-Optional fields."""
    schema = schema_model.model_json_schema()
    _forbid_additional_properties(schema)
    resp = _client().chat.completions.create(
        model=MODEL,
        temperature=0.3,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": schema_model.__name__,
                "schema": schema,
                "strict": True,
            },
        },
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    return schema_model.model_validate_json(resp.choices[0].message.content)


def next_question(description, qa_history):
    """Ask Groq for the next clarifying question plus 3 suggested answers, based on
    the answers so far. Returns a dict like
    {"done": false, "question": "...", "suggested_answers": ["...", "...", "..."]}
    or {"done": true, "question": null, "suggested_answers": []}."""
    convo = f"Description: {description}\n\nPrevious questions and answers:\n"
    for qa in qa_history:
        convo += f"Q: {qa['q']}\nA: {qa['a']}\n"
    convo += "\nNow ask the next question, or return done if you have enough."
    result = _structured_chat(NEXT_QUESTION_PROMPT, convo, NextQuestionResult)
    return result.model_dump()


def generate_requirements(user_text):
    """Generate the structured requirements document from text (description + answers).
    Uses structured-output enforcement so the shape is guaranteed rather than merely
    prompted for - a prompt-only JSON mode could (and occasionally did) return
    malformed structure on long or complex conversations."""
    result = _structured_chat(GENERATE_PROMPT, user_text, GeneratedRequirements)
    return result.model_dump()


def revise_requirements(current_data, instruction):
    """Edit the existing document based on a chat instruction. Returns the same
    GeneratedRequirements shape it was given, structurally guaranteed."""
    message = f"CURRENT JSON:\n{json.dumps(current_data)}\n\nINSTRUCTION:\n{instruction}"
    result = _structured_chat(REVISE_PROMPT, message, GeneratedRequirements)
    return result.model_dump()


def review_requirements(description, qa_history, generated_requirements):
    """Review the generated requirements from BA, developer, and QA perspectives.
    "role" and "severity" are constrained to their exact allowed values at the
    schema level (Literal types) rather than by prompt text alone."""
    message = {
        "original_description": description,
        "qa_history": qa_history,
        "generated_requirements": generated_requirements,
    }
    result = _structured_chat(REVIEW_PROMPT, json.dumps(message), ReviewResult)
    return result.model_dump()


def extract_from_notes(raw_notes):
    """Extract clear requirements, implied user stories, and open questions from raw,
    messy pasted notes (meeting notes, scattered thoughts) - an alternative starting
    point to typing a clean description. Uses structured-output enforcement so the
    shape is guaranteed rather than merely prompted for."""
    result = _structured_chat(NOTES_EXTRACTION_PROMPT, raw_notes, NotesExtraction)
    return result.model_dump()


# Stands in for the model's "reason" when we couldn't use its order and kept the
# document's own - so a caller can tell an AI order from a fallback one.
FALLBACK_ORDER_REASON = "Kept in the original document order."


def _document_order(story_ids):
    return [{"story_id": sid, "reason": FALLBACK_ORDER_REASON, "depends_on": []} for sid in story_ids]


def _check_story_order(items, story_ids):
    """Validates the model's ordering against the input. Returns (order, problem):
    the cleaned list if every input id appears exactly once (and nothing else
    does), otherwise (None, a short description of what was wrong)."""
    expected = set(story_ids)
    cleaned = [
        {"story_id": item.story_id.strip(), "reason": item.reason.strip(), "depends_on": item.depends_on}
        for item in items
    ]
    ids = [c["story_id"] for c in cleaned]
    counts = Counter(ids)
    missing = expected - set(ids)
    unknown = set(ids) - expected
    duplicated = {i for i, n in counts.items() if n > 1}
    if missing or unknown or duplicated:
        return None, f"missing={len(missing)} unknown={len(unknown)} duplicated={len(duplicated)}"
    for c in cleaned:
        deps = dict.fromkeys(d.strip() for d in c["depends_on"])
        c["depends_on"] = [d for d in deps if d in expected and d != c["story_id"]]
    return cleaned, None


def plan_story_order(user_stories):
    """Order user stories by logical/dependency order - and nothing else: no
    sizing, no points, no sprints (that's plain code in sprint_plan.py). Takes the
    generated document's user_stories and returns [{story_id, reason, depends_on}],
    every input id exactly once.

    An unusable answer from the model (wrong ids, malformed output, a rejected
    request) never reaches the caller: it is logged and the original document
    order is returned instead. Anything else - notably Groq quota and rate-limit
    errors - propagates, so main.call_groq can turn it into quota_exhausted."""
    story_ids = [s["id"] for s in user_stories]
    if not story_ids:
        return []
    if len(story_ids) == 1:
        return [{"story_id": story_ids[0], "reason": "The only story.", "depends_on": []}]
    if len(set(story_ids)) != len(story_ids):
        logger.warning("plan_story_order: duplicate story ids in the input; keeping document order")
        return _document_order(story_ids)

    message = json.dumps(
        [{"id": s["id"], "role": s.get("role", ""), "story": s.get("story", "")} for s in user_stories]
    )
    try:
        plan = _structured_chat(STORY_ORDER_PROMPT, message, StoryOrderPlan)
    except (ValueError, BadRequestError) as e:
        logger.warning("plan_story_order: unusable model output (%s); keeping document order", type(e).__name__)
        return _document_order(story_ids)
    order, problem = _check_story_order(plan.ordered_stories, story_ids)
    if order is None:
        logger.warning("plan_story_order: model order rejected (%s); keeping document order", problem)
        return _document_order(story_ids)
    return order
