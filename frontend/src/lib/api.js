// One function per FastAPI endpoint (main.py). This is the only file that
// talks to the backend - components call these functions, never fetch() directly.
//
// Paths are relative ("/api/...") rather than a full URL: in production FastAPI
// serves this app itself, so "/api/..." is same-origin. In local dev, Vite's
// dev-server proxy (see vite.config.js) forwards "/api/..." to the backend.
const API_BASE = "/api";

// An HTTP error from the backend. It IS an Error with a friendly message (so
// every existing `catch (err) { err.message }` keeps working), plus the
// backend's machine-readable `detail` code and the parsed body for callers that
// need more (the Jira push does).
export class ApiError extends Error {
  constructor(message, { status = null, code = null, data = null, outcomeUnknown = false } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.data = data;
    // True when the request may have been carried out even though we got no
    // usable answer (connection dropped, gateway timeout).
    this.outcomeUnknown = outcomeUnknown;
  }
}

// Messages for the Jira-specific `detail` codes the backend returns (main.py,
// jira_push.py). A function gets the response body, for the ones that name a project.
const JIRA_MESSAGES = {
  not_connected: "You're not connected to Jira. Connect your account and try again.",
  reconnect_required: "Your Jira connection has expired or was revoked. Reconnect to continue.",
  token_refresh_failed: "Couldn't reach Atlassian to renew your Jira connection. Please try again in a moment.",
  forbidden: "Jira says your account isn't allowed to do that. You may need permission to create projects on this Jira site.",
  project_not_found: "That Jira project couldn't be found, or your account can't see it.",
  no_scrum_board: "Jira didn't give this project a Scrum board, so sprints couldn't be set up.",
  no_epic_issue_type: "This Jira project has no Epic issue type, so the stories couldn't be grouped.",
  no_story_issue_type: "This Jira project has no Story or Task issue type to create.",
  jira_error: "Jira couldn't complete the request.",
  internal_error: "Something unexpected went wrong. Please try again.",
};

// Turns an HTTP error into a friendly, user-facing message. We never surface
// raw status codes or backend error text to the user.
// - 429: our own daily rate limit (slowapi) was hit.
// - 503 with detail "quota_exhausted": the backend distinguishes an exhausted
//   provider quota from a generic failure (see call_groq in main.py).
// - a known Jira `detail` code: its message above.
// - anything else: a generic fallback.
export function friendlyMessage(status, code) {
  if (status === 429) {
    return "You've reached today's usage limit. Please try again tomorrow.";
  }
  if (status === 503 && code === "quota_exhausted") {
    return "The service is busy right now. Please try again later.";
  }
  if (code && Object.hasOwn(JIRA_MESSAGES, code)) {
    return JIRA_MESSAGES[code];
  }
  return "Something went wrong. Please try again.";
}

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const code = typeof body?.detail === "string" ? body.detail : null;
    throw new ApiError(friendlyMessage(res.status, code), { status: res.status, code, data: body });
  }
  return res;
}

export async function nextQuestion(description, qaHistory) {
  const res = await request("/next-question", {
    method: "POST",
    body: JSON.stringify({ description, qa_history: qaHistory }),
  });
  return res.json();
}

export async function generateRequirements(description, qaHistory) {
  const res = await request("/generate", {
    method: "POST",
    body: JSON.stringify({ description, qa_history: qaHistory }),
  });
  return res.json();
}

export async function reviseRequirements(data, instruction) {
  const res = await request("/revise", {
    method: "POST",
    body: JSON.stringify({ data, instruction }),
  });
  return res.json();
}

export async function reviewRequirements(description, qaHistory, data) {
  const res = await request("/review", {
    method: "POST",
    body: JSON.stringify({ description, qa_history: qaHistory, data }),
  });
  return res.json();
}

export async function extractFromNotes(rawNotes) {
  const res = await request("/extract-notes", {
    method: "POST",
    body: JSON.stringify({ raw_notes: rawNotes }),
  });
  return res.json();
}

export async function exportDocx(data) {
  const res = await request("/export", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return res.blob();
}

// ---------- Jira ----------
// Same request() and error mapping as everything above. The extra step: a failure
// that never produced an HTTP answer (offline, connection reset) is turned into an
// ApiError too, instead of surfacing the browser's raw "Failed to fetch".

async function jiraRequest(path, options, { sideEffects = false } = {}) {
  try {
    return await request(path, options);
  } catch (err) {
    if (err instanceof ApiError) {
      // A gateway timeout or crash page has no JSON `detail`: for a call that does
      // things in Jira we can't know whether it got done.
      if (sideEffects && err.code === null && err.status >= 500) err.outcomeUnknown = true;
      throw err;
    }
    throw new ApiError(
      sideEffects
        ? "We lost the connection before the push finished. It may have partly completed - check Jira before trying again."
        : "Couldn't reach ReqPrint. Check your connection and try again.",
      { code: "network_error", outcomeUnknown: sideEffects },
    );
  }
}

// Where the sign-in popup is pointed (see lib/jiraConnect.js). Not fetched.
export const JIRA_LOGIN_URL = `${API_BASE}/jira/login`;

// -> { connected, siteName, siteUrl }. Never includes a token.
export async function getJiraStatus() {
  const res = await jiraRequest("/jira/status");
  const body = await res.json();
  return {
    connected: body.connected === true,
    siteName: typeof body.site_name === "string" ? body.site_name : "",
    siteUrl: typeof body.site_url === "string" ? body.site_url : "",
  };
}

export async function jiraLogout() {
  await jiraRequest("/jira/logout", { method: "POST" });
}

// Creates a Jira project from the generated document: an epic, the stories in
// dependency order, and dated sprints. Takes about 20-40 seconds. On failure the
// ApiError carries `code`, and - when Jira already created the project before
// something went wrong - `project` ({ key, url, created }).
export async function pushToJira({ projectName, capacityPerWeek, sprintLengthWeeks, startDate, category, subtasks, requirements }) {
  const body = {
    mode: "create",
    project_name: projectName,
    capacity_per_week: capacityPerWeek,
    sprint_length_weeks: sprintLengthWeeks,
    start_date: startDate,
    create_subtasks: subtasks === true, // always an explicit true/false; the backend rejects anything else
    requirements,
  };
  if (category) body.category = category;
  try {
    const res = await jiraRequest("/jira/push", { method: "POST", body: JSON.stringify(body) }, { sideEffects: true });
    return await res.json();
  } catch (err) {
    if (!(err instanceof ApiError)) {
      // A 200 whose body wasn't readable: the push ran, we just can't see how it went.
      throw new ApiError("The push finished, but the answer couldn't be read. Check Jira to see what was created.", {
        code: "unreadable_response",
        outcomeUnknown: true,
      });
    }
    const data = err.data;
    if (data && typeof data === "object") {
      if (typeof data.jira_message === "string") err.jiraMessage = data.jira_message.slice(0, 300);
      if (typeof data.project_key === "string") {
        err.project = { key: data.project_key, url: data.project_url || "", created: data.project_created === true };
      }
    }
    throw err;
  }
}
