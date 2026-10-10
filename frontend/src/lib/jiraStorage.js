// What the Jira push keeps in localStorage, and nothing more:
//  - a record per pushed document (project key, link, date, story count) so
//    pushing the same document again can be flagged;
//  - a marker that a push is in flight, so a push that was cut off (tab closed,
//    connection lost) can be flagged on the next load.
// Never a token, a cookie, or any credential: those live in an HttpOnly cookie the
// page cannot read. Every access is wrapped because storage can be unavailable
// (private windows, blocked site data) - the feature then simply has no memory.
import { safeHttpUrl } from "./jiraPlan";

const PUSH_PREFIX = "reqprint.jira.push.";
const IN_PROGRESS_KEY = "reqprint.jira.pushInProgress";

function read(key) {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* storage unavailable or full: carry on without it */
  }
}

function remove(key) {
  try {
    window.localStorage.removeItem(key);
  } catch {
    /* see above */
  }
}

function readJson(key) {
  const raw = read(key);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

// ---------- pushed documents ----------

// { project_key, project_url, pushed_at, story_count } for a document hash, or
// null. Whatever is in storage is validated: it is only trusted as far as it looks right.
export function getPushRecord(hash) {
  const rec = readJson(PUSH_PREFIX + hash);
  if (!rec || typeof rec !== "object") return null;
  const date = new Date(rec.pushed_at);
  if (typeof rec.project_key !== "string" || !rec.project_key || Number.isNaN(date.getTime())) return null;
  return {
    project_key: rec.project_key.slice(0, 50),
    project_url: safeHttpUrl(rec.project_url) || "",
    pushed_at: date.toISOString(),
    story_count: Number.isInteger(rec.story_count) ? rec.story_count : 0,
  };
}

export function savePushRecord(hash, { projectKey, projectUrl, storyCount }) {
  write(
    PUSH_PREFIX + hash,
    JSON.stringify({
      project_key: projectKey,
      project_url: projectUrl,
      pushed_at: new Date().toISOString(),
      story_count: storyCount,
    }),
  );
}

// ---------- a push that may not have finished ----------

export function markPushStarted() {
  write(IN_PROGRESS_KEY, JSON.stringify({ started_at: new Date().toISOString() }));
}

export function clearPushStarted() {
  remove(IN_PROGRESS_KEY);
}

export function hasUnfinishedPush() {
  return read(IN_PROGRESS_KEY) !== null;
}
