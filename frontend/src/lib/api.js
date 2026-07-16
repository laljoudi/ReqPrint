// One function per FastAPI endpoint (main.py). This is the only file that
// talks to the backend - components call these functions, never fetch() directly.
//
// Paths are relative ("/api/...") rather than a full URL: in production FastAPI
// serves this app itself, so "/api/..." is same-origin. In local dev, Vite's
// dev-server proxy (see vite.config.js) forwards "/api/..." to the backend.
const API_BASE = "/api";

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${res.status})`);
  }
  return res;
}

export async function login(username, password) {
  const res = await request("/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  return res.json();
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
