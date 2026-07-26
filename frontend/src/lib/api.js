// One function per FastAPI endpoint (main.py). This is the only file that
// talks to the backend - components call these functions, never fetch() directly.
//
// Paths are relative ("/api/...") rather than a full URL: in production FastAPI
// serves this app itself, so "/api/..." is same-origin. In local dev, Vite's
// dev-server proxy (see vite.config.js) forwards "/api/..." to the backend.
const API_BASE = "/api";

// Turns an HTTP error into a friendly, user-facing message. We never surface
// raw status codes or backend error text to the user.
// - 429: our own daily rate limit (slowapi) was hit.
// - 503 with detail "quota_exhausted": the backend distinguishes an exhausted
//   Gemini quota from a generic failure (see call_gemini in main.py).
// - anything else: a generic fallback.
async function friendlyMessage(res) {
  if (res.status === 429) {
    return "You've reached today's usage limit. Please try again tomorrow.";
  }
  if (res.status === 503) {
    const body = await res.json().catch(() => ({}));
    if (body.detail === "quota_exhausted") {
      return "The service is busy right now. Please try again later.";
    }
  }
  return "Something went wrong. Please try again.";
}

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    throw new Error(await friendlyMessage(res));
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

export async function exportDocx(data) {
  const res = await request("/export", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return res.blob();
}
