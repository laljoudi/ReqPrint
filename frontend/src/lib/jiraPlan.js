// Pure helpers for the "Push to Jira" dialog: the live plan preview (the same
// math as sprint_plan.py on the backend), the project-name suggestion, form
// validation, and a short hash used to recognise a document that was already
// pushed. No React, no browser APIs - so it can be tested with plain Node.

export const MAX_STORIES = 100; // the backend rejects more than this per push (jira_push.MAX_STORIES)
export const MIN_CAPACITY = 1;
export const MAX_CAPACITY = 50;
export const DEFAULT_CAPACITY = 3;
export const SPRINT_LENGTHS = [1, 2, 3, 4];
export const DEFAULT_SPRINT_WEEKS = 2;
export const MIN_START_DATE = "2000-01-01"; // the backend's accepted range (sprint_plan.EARLIEST/LATEST_START_DATE)
export const MAX_START_DATE = "2099-12-31";
export const MAX_PROJECT_NAME_LENGTH = 80;

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const DAY_MS = 24 * 60 * 60 * 1000;

// ---------- dates ----------

// Today as the user's own calendar date, "YYYY-MM-DD" (what a date input holds).
export function todayLocalISO(now = new Date()) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

// "YYYY-MM-DD" -> {y, m, d}, or null if it isn't a real date.
export function parseISODate(text) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(typeof text === "string" ? text : "");
  if (!match) return null;
  const [y, m, d] = [Number(match[1]), Number(match[2]), Number(match[3])];
  const check = new Date(Date.UTC(y, m - 1, d));
  const real = check.getUTCFullYear() === y && check.getUTCMonth() === m - 1 && check.getUTCDate() === d;
  return real ? { y, m, d } : null;
}

export function formatDayMonth(date) {
  return `${date.getUTCDate()} ${MONTHS[date.getUTCMonth()]}`;
}

export function formatFullDate(date) {
  return `${formatDayMonth(date)} ${date.getUTCFullYear()}`;
}

// A moment in time as the user's own calendar date, e.g. "10 Oct 2026".
export function formatLocalDate(date) {
  return `${date.getDate()} ${MONTHS[date.getMonth()]} ${date.getFullYear()}`;
}

// ---------- the plan preview ----------

// Same arithmetic as the backend (sprint_plan.py): every story is one unit,
// stories_per_sprint = capacity * sprint length, sprint_count = ceil(stories / that),
// and sprints run back to back from the start date. `end` is the instant the
// last sprint ends - the day after its final day.
export function previewPlan({ totalStories, capacity, weeks, startISO }) {
  const start = parseISODate(startISO);
  if (!start || !Number.isInteger(totalStories) || totalStories < 0) return null;
  if (!Number.isInteger(capacity) || capacity < MIN_CAPACITY || capacity > MAX_CAPACITY) return null;
  if (!SPRINT_LENGTHS.includes(weeks)) return null;
  const perSprint = capacity * weeks;
  const sprints = Math.ceil(totalStories / perSprint);
  const startMs = Date.UTC(start.y, start.m - 1, start.d);
  return {
    totalStories,
    perSprint,
    sprints,
    start: new Date(startMs),
    end: new Date(startMs + sprints * weeks * 7 * DAY_MS),
  };
}

// The preview as separate parts, so the dialog can keep each one on a single line:
// ["8 stories", "4 per sprint", "2 sprints", "7 Nov → 5 Dec"].
// The per-sprint figure is capacity x sprint length (a weekly capacity of 2 over 2-week
// sprints is 4 per sprint) - shown so that product isn't a surprise.
export function previewParts(plan) {
  const stories = `${plan.totalStories} ${plan.totalStories === 1 ? "story" : "stories"}`;
  if (plan.sprints === 0) return [stories];
  return [
    stories,
    `${plan.perSprint} per sprint`,
    `${plan.sprints} ${plan.sprints === 1 ? "sprint" : "sprints"}`,
    `${formatDayMonth(plan.start)} → ${formatDayMonth(plan.end)}`,
  ];
}

// "8 stories · 4 per sprint · 2 sprints · 7 Nov → 5 Dec"
export function previewText(plan) {
  return previewParts(plan).join(" · ");
}

// ---------- the form ----------

// The capacity field is text while typing. A whole number from 1 to 50, or null.
export function parseCapacity(text) {
  if (typeof text !== "string" || !/^\d{1,3}$/.test(text.trim())) return null;
  const n = Number(text.trim());
  return n >= MIN_CAPACITY && n <= MAX_CAPACITY ? n : null;
}

// Messages for whatever is wrong, keyed by field; {} when the form can be sent.
export function validateForm({ name, startISO, capacityText, totalStories }) {
  const errors = {};
  const trimmed = (name || "").trim();
  if (!trimmed) errors.name = "Give the project a name.";
  else if (trimmed.length > MAX_PROJECT_NAME_LENGTH) errors.name = `Keep the name under ${MAX_PROJECT_NAME_LENGTH} characters.`;
  if (!parseISODate(startISO) || startISO < MIN_START_DATE || startISO > MAX_START_DATE) {
    errors.startDate = "Choose a valid start date.";
  }
  if (parseCapacity(capacityText) === null) errors.capacity = `Enter a whole number from ${MIN_CAPACITY} to ${MAX_CAPACITY}.`;
  if (totalStories < 1) errors.stories = "This document has no user stories to push.";
  else if (totalStories > MAX_STORIES) errors.stories = `A push can include up to ${MAX_STORIES} stories; this document has ${totalStories}.`;
  return errors;
}

// ---------- project-name suggestion ----------

const LEADING_FILLER = [
  /^(?:i|we)(?:'d| would)?\s+(?:want|need|like|plan|am planning|are planning|am going|are going)\s+to\s+(?:build|create|make|develop|design|launch|start)\s+/i,
  /^(?:i|we)\s+(?:am|are)\s+(?:building|creating|making|developing|designing)\s+/i,
  /^(?:please\s+)?(?:build|create|make|develop|design)\s+(?:me\s+)?/i,
  /^(?:an?|the|my|our)\s+/i,
];
const CUT_AT = /\s+(?:that|which|where|who|whose|for|to|so|with|using|via|because|in order|allowing|enabling|including|in which)\b|[,.:;!?(\n]/i;
const NAME_WORDS = 6;

// A starting point for the project name, taken from what the user described. It
// only has to be reasonable - the field is editable.
export function suggestProjectName(description) {
  let text = String(description || "")
    .replace(/^\s*project category:[^\n]*\n*/i, "") // the category line ReqPrint adds
    .split(/\n\s*\n\s*open questions identified/i)[0] // and the open questions it appends
    .trim();
  for (let pass = 0; pass < 2; pass += 1) for (const filler of LEADING_FILLER) text = text.replace(filler, "");
  text = text.split(CUT_AT)[0].replace(/[^\p{L}\p{N}\s&'-]/gu, " ").trim();
  const words = text.split(/\s+/).filter(Boolean).slice(0, NAME_WORDS);
  if (!words.length) return "My Project";
  const name = words.map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
  return name.slice(0, MAX_PROJECT_NAME_LENGTH).trim();
}

// ---------- recognising a document that was already pushed ----------

// cyrb53: a small, fast, well-distributed 53-bit string hash. Not for security -
// it only has to tell one requirements document from another.
function cyrb53(str) {
  let h1 = 0xdeadbeef;
  let h2 = 0x41c6ce57;
  for (let i = 0; i < str.length; i += 1) {
    const ch = str.charCodeAt(i);
    h1 = Math.imul(h1 ^ ch, 2654435761);
    h2 = Math.imul(h2 ^ ch, 1597334677);
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909);
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  return 4294967296 * (2097151 & h2) + (h1 >>> 0);
}

export function hashDocument(document) {
  return cyrb53(JSON.stringify(document)).toString(36);
}

// A URL that is safe to put in an href: http(s) only, else null. (Anything read
// back from localStorage is not trusted - "javascript:" must never become a link.)
export function safeHttpUrl(url) {
  try {
    const parsed = new URL(String(url));
    return parsed.protocol === "https:" || parsed.protocol === "http:" ? parsed.href : null;
  } catch {
    return null;
  }
}
