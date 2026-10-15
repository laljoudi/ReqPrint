"""Everything related to calling Groq. Reusable by any interface."""
import os
import json
import logging
from collections import Counter
from dotenv import load_dotenv
from groq import BadRequestError, Groq
from functools import lru_cache
from typing import Annotated, Literal
from pydantic import BaseModel, Field

from prompts import (
    GENERATE_PROMPT,
    REVISE_PROMPT,
    NEXT_QUESTION_PROMPT,
    REVIEW_PROMPT,
    NOTES_EXTRACTION_PROMPT,
    STORY_ORDER_PROMPT,
    SUBTASKS_PROMPT,
)

load_dotenv()
logger = logging.getLogger(__name__)
API_KEY = os.getenv("GROQ_API_KEY")
MODEL = "openai/gpt-oss-120b"
MAX_REQUIREMENT_TEXT_CHARS = 1_500
MAX_REQUIREMENT_ITEMS = 100
MAX_USER_STORIES = 100
MAX_ACCEPTANCE_CRITERIA = 300
MAX_USE_CASES = 100
MAX_ASSUMPTIONS = 100
RequirementText = Annotated[str, Field(min_length=1, max_length=MAX_REQUIREMENT_TEXT_CHARS)]
OptionalRequirementText = Annotated[str, Field(max_length=MAX_REQUIREMENT_TEXT_CHARS)]

@lru_cache
def _client():
    return Groq(api_key=API_KEY)


class NotesExtraction(BaseModel):
    clear_requirements: list[RequirementText] = Field(max_length=MAX_REQUIREMENT_ITEMS)
    implied_user_stories: list[RequirementText] = Field(max_length=MAX_REQUIREMENT_ITEMS)
    open_questions: list[RequirementText] = Field(max_length=MAX_REQUIREMENT_ITEMS)


class NextQuestionResult(BaseModel):
    done: bool
    question: OptionalRequirementText | None
    suggested_answers: list[RequirementText] = Field(max_length=3)


class Requirements(BaseModel):
    functional: list[RequirementText] = Field(max_length=MAX_REQUIREMENT_ITEMS)
    non_functional: list[RequirementText] = Field(max_length=MAX_REQUIREMENT_ITEMS)


class UserStory(BaseModel):
    id: str = Field(min_length=1, max_length=50)
    role: OptionalRequirementText
    story: RequirementText


class AcceptanceCriterion(BaseModel):
    story_id: str = Field(max_length=50)
    scenario: OptionalRequirementText
    given: OptionalRequirementText
    when: OptionalRequirementText
    then: OptionalRequirementText


class UseCase(BaseModel):
    use_case_id: str = Field(min_length=1, max_length=50)
    actors: OptionalRequirementText
    description: RequirementText
    preconditions: OptionalRequirementText
    trigger: OptionalRequirementText
    main_flow: RequirementText
    alternative_flow: OptionalRequirementText


class GeneratedRequirements(BaseModel):
    """The full requirements document shape - shared by generate_requirements()
    and revise_requirements(), since REVISE_PROMPT returns the same structure
    it was given, just edited."""

    requirements: Requirements
    user_stories: list[UserStory] = Field(max_length=MAX_USER_STORIES)
    acceptance_criteria: list[AcceptanceCriterion] = Field(max_length=MAX_ACCEPTANCE_CRITERIA)
    use_cases: list[UseCase] = Field(max_length=MAX_USE_CASES)
    assumptions: list[RequirementText] = Field(max_length=MAX_ASSUMPTIONS)


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


SUBTASK_DISCIPLINES = ("backend", "frontend", "qa", "design")


class StoryOrderPlan(BaseModel):
    ordered_stories: list[StoryOrderItem]


# Sub-tasks per story. Deliberately no estimate/size/hours field anywhere, and no
# length constraints in the schema (they're checked in code, where a failure can
# be logged and degraded instead of rejected by the API).
class SubtaskItem(BaseModel):
    title: str
    discipline: Literal["backend", "frontend", "qa", "design"]
    criterion_index: int | None


class StorySubtasks(BaseModel):
    story_id: str
    subtasks: list[SubtaskItem]


class SubtaskPlan(BaseModel):
    stories: list[StorySubtasks]


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


MIN_SUBTASKS_PER_STORY = 1
MAX_SUBTASKS_PER_STORY = 5
# Stories per AI call. Keeps each request (the stories plus all their criteria) and
# each answer comfortably small; a document of 10 stories is one call.
SUBTASK_BATCH_SIZE = 25


def _check_subtask_batch(items, batch_ids, criteria_by_story):
    """Validates one answer from the model against the stories it was asked about.

    Whole-answer checks - any failure returns (None, why) and the caller skips every
    sub-task: each returned story id must be one of ours and appear once, each story
    must have 1-5 sub-tasks, and each sub-task a title and an allowed discipline.

    The derivation rule, enforced per sub-task, never silently repaired:
      - a story WITH acceptance criteria: every sub-task must cite a criterion_index
        that exists for that story. One that cites nothing, or an index the story
        doesn't have, is REJECTED - it is not rewritten to quote the story text.
      - a story WITHOUT criteria is the only place the story-text fallback applies:
        its sub-tasks must cite nothing (criterion_index null); one that cites a
        criterion the story doesn't have is rejected too.
      - if MORE THAN HALF of a story's sub-tasks are rejected, that story gets no
        sub-tasks at all rather than a partial set.

    Returns ({"plan", "rejected", "dropped"}, None):
      plan     {story_id: [{title, discipline, criterion_index, criterion}]} - criterion
               is the cited criterion (a dict), or None only for a no-criteria story
      rejected [{story_id, title, reason}] for every sub-task the rule threw out
      dropped  [{story_id, rejected, total, reason}] for each story left with none"""
    expected = set(batch_ids)
    seen = Counter(item.story_id.strip() for item in items)
    unknown = set(seen) - expected
    duplicated = {i for i, n in seen.items() if n > 1}
    if unknown or duplicated:
        return None, f"unknown={len(unknown)} duplicated={len(duplicated)}"
    plan, rejected, dropped = {}, [], []
    for item in items:
        story_id = item.story_id.strip()
        total = len(item.subtasks)
        if not MIN_SUBTASKS_PER_STORY <= total <= MAX_SUBTASKS_PER_STORY:
            return None, f"{story_id} has {total} sub-tasks (allowed {MIN_SUBTASKS_PER_STORY}-{MAX_SUBTASKS_PER_STORY})"
        criteria = criteria_by_story.get(story_id, [])
        kept, bad = [], []
        for sub in item.subtasks:
            title = " ".join(sub.title.split()).rstrip(".")
            if not title:
                return None, f"{story_id} has a sub-task with an empty title"
            if sub.discipline not in SUBTASK_DISCIPLINES:  # the schema already enforces this; belt and braces
                return None, f"{story_id} has a sub-task with discipline {sub.discipline!r}"
            index = sub.criterion_index
            valid_index = isinstance(index, int) and not isinstance(index, bool) and 0 <= index < len(criteria)
            if criteria and valid_index:
                kept.append({"title": title, "discipline": sub.discipline, "criterion_index": index, "criterion": criteria[index]})
            elif not criteria and index is None:
                kept.append({"title": title, "discipline": sub.discipline, "criterion_index": None, "criterion": None})
            else:
                if index is None:
                    reason = "cited no acceptance criterion"
                elif criteria:
                    reason = f"cited criterion {index}, but this story only has criteria 0-{len(criteria) - 1}"
                else:
                    reason = f"cited criterion {index}, but this story has no acceptance criteria"
                bad.append({"story_id": story_id, "title": title, "reason": reason})
        rejected += bad
        if bad and len(bad) * 2 > total:
            reason = f"{len(bad)} of its {total} sub-tasks didn't tie back to a real acceptance criterion, so none were created for this story"
            dropped.append({"story_id": story_id, "rejected": len(bad), "total": total, "reason": reason})
            logger.warning("plan_subtasks: %s: %s", story_id, reason)
        elif kept:
            plan[story_id] = kept
    if not items:
        return None, "no stories returned"
    if rejected:
        logger.warning("plan_subtasks: %s sub-task(s) rejected for not citing a real acceptance criterion", len(rejected))
    return {"plan": plan, "rejected": rejected, "dropped": dropped}, None


def plan_subtasks(user_stories, acceptance_criteria):
    """Break each user story into sub-tasks derived from the story and its own
    acceptance criteria (matched by story_id) - never a fixed template, never an
    estimate. Takes the document's user_stories and acceptance_criteria and returns
    {"plan": {story_id: [{title, discipline, criterion_index, criterion}]},
     "rejected": [...], "dropped": [...]} - see _check_subtask_batch for what the
    derivation rule rejects. `discipline` is one of backend/frontend/qa/design.

    Any unusable answer from the model (malformed output, a rejected request, an id
    that isn't one of ours, a bad count or discipline) is logged and gives None - the
    caller then skips sub-tasks and carries on, because the stories and sprints must
    still be created. Anything else, notably Groq quota and rate-limit errors,
    propagates so the caller can tell "the AI is busy" from "the AI answered badly".
    A story may be missing from the answer (it simply gets no sub-tasks)."""
    if not user_stories:
        return {"plan": {}, "rejected": [], "dropped": []}
    ids = [s["id"] for s in user_stories]
    if len(set(ids)) != len(ids):
        logger.warning("plan_subtasks: duplicate story ids in the input; skipping sub-tasks")
        return None
    criteria_by_story = {}
    for c in acceptance_criteria or []:
        criteria_by_story.setdefault(c.get("story_id", ""), []).append(c)

    merged = {"plan": {}, "rejected": [], "dropped": []}
    for start in range(0, len(user_stories), SUBTASK_BATCH_SIZE):
        batch = user_stories[start : start + SUBTASK_BATCH_SIZE]
        message = json.dumps(
            [
                {
                    "id": s["id"],
                    "role": s.get("role", ""),
                    "story": s.get("story", ""),
                    "criteria": [
                        {"index": i, "scenario": c.get("scenario", ""), "given": c.get("given", ""), "when": c.get("when", ""), "then": c.get("then", "")}
                        for i, c in enumerate(criteria_by_story.get(s["id"], []))
                    ],
                }
                for s in batch
            ]
        )
        try:
            answer = _structured_chat(SUBTASKS_PROMPT, message, SubtaskPlan)
        except (ValueError, BadRequestError) as e:
            logger.warning("plan_subtasks: unusable model output (%s); skipping sub-tasks", type(e).__name__)
            return None
        result, problem = _check_subtask_batch(answer.stories, [s["id"] for s in batch], criteria_by_story)
        if result is None:
            logger.warning("plan_subtasks: model answer rejected (%s); skipping sub-tasks", problem)
            return None
        merged["plan"].update(result["plan"])
        merged["rejected"] += result["rejected"]
        merged["dropped"] += result["dropped"]
    return merged
