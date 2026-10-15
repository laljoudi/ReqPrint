# ReqPrint

**AI-Powered Requirements Engineering — turn a plain-language idea into a structured Software Requirements Specification.**

A personal project by [Layan Aljoudi](https://www.linkedin.com/in/layan-aljoudi/).

Writing software requirements usually means hours of stakeholder interviews and
documentation before a single line of a spec exists. ReqPrint compresses that: describe
your project — or paste the notes you already have — and it asks the adaptive clarifying
questions a business analyst would, then generates a structured requirements document you
can refine, review, and export. The goal isn't to replace analysis — it's to get from a
rough idea to a solid first draft in minutes instead of days.

## Features

- **Describe or paste notes** — a plain description or raw meeting notes both work;
  notes are triaged into clear requirements, implied user stories, and open questions
  before the interview even starts.
- **Category-aware interview** — pick a project category (FinTech, HR Tech, AI Solutions,
  etc.) so clarifying questions probe the angles that actually matter for it.
- **Adaptive clarifying questions** — each question builds on your previous answer,
  deliberately covering different requirement areas, with suggested answers you can pick
  or override, and stops once there's enough context rather than asking a fixed list.
- **Structured specification** — generates functional & non-functional requirements,
  user stories, acceptance criteria, use cases, and assumptions, laid out in clear
  sections as the conversation continues.
- **Refine conversationally** — adjust any section by asking for changes in plain
  language until the requirements match what you actually meant.
- **AI review** — a second pass reads the finished spec from a Business Analyst,
  Developer, and QA perspective, flagging what's ambiguous, missing, or untestable with
  a severity and a suggested fix.
- **One-click Word export** — download the whole spec as a polished `.docx`, ready to
  share.
- **Push to Jira** — one click turns the generated user stories into a real Jira
  project: an epic, dated sprints, and tasks ordered by dependency, created in your
  own Jira through OAuth 2.0.
- **Sub-tasks, derived from the criteria** — optionally breaks each user story into Jira
  sub-tasks derived from its acceptance criteria, each tagged by discipline (backend,
  frontend, qa, design) as a label and parented to its story, so it follows that story
  into its sprint.

## How It Works

1. **Describe your idea, or paste your notes** — pick a category, and either works.
2. **Answer clarifying questions** — a short, adaptive back-and-forth that fills in the gaps.
3. **Watch the document build** — the spec takes shape beside the conversation, not after it.
4. **Review and refine** — run the AI review, or ask for changes conversationally.
5. **Export to Word** — one click produces a shareable `.docx`.

## Built With

- **React 19** — single-page frontend (Vite, Tailwind CSS v4)
- **FastAPI** — REST API backend, rate-limited per visitor with **slowapi**
- **Groq** (`openai/gpt-oss-120b`) — the language model behind the questions,
  generation, review, and notes triage
- **Pydantic** — every AI response is bound to a strict JSON schema at the API level,
  so the shape of a five-section document is guaranteed, not just requested
- **python-docx** — builds the exported `.docx` server-side
- **Docker** — single multi-stage image (Node build stage + Python runtime)

## Engineering Highlights

The interesting parts of this project are less about the tool list and more about a few
deliberate decisions.

**Multi-stage prompting.** Rather than asking the model to turn a raw description
straight into a spec, ReqPrint separates *elicitation* from *generation*. One stage runs
the clarifying-question interview; a distinct stage takes that fuller context and
produces the structured document. Splitting the work this way consistently yields more
complete, less hand-wavy requirements than a single do-everything prompt, because the
model isn't simultaneously interviewing and drafting — it does one job at a time.

**Structured outputs, not parsed prompts.** Every AI call — clarifying questions,
generation, revision, review, and notes triage — is bound to a strict Pydantic JSON
schema enforced by Groq at the API level, rather than asked for in a prompt and hoped
for. The response shape is guaranteed rather than usually correct, which is what makes a
five-section document assemble reliably instead of most of the time.

**Single-image architecture.** The React frontend and the FastAPI backend are built into
one multi-stage Docker image: a Node stage compiles the frontend to static files, and the
final Python stage serves both that build and the API from a single process. This means
the artifact you deploy is byte-for-byte the same thing that runs locally —
there's no separate frontend host, no CORS juggling between environments, and no "works on
my machine" gap between dev and prod.

## Architecture

### The Jira push

Connecting happens in a popup: ReqPrint sends you to Atlassian's own consent screen, and
the callback page tells the app window how it went, so the generated document is never
lost to a page redirect. Once connected, a push runs these steps in order:

1. **Preflight** — the project is created (or looked up), its Scrum board is found, and
   the Epic and Story issue types are resolved (Task if the project has no Story). If any
   of this fails, no epic, story, or sprint is created.
2. **AI ordering** — the model puts the user stories in dependency order, with a one-line
   reason for each position. If its answer is unusable, the document's own order is used.
   If sub-tasks were requested, a second, independent AI call plans them at the same time
   (see step 7); only the ordering is allowed to fail the push.
3. **Sprint math** — plain arithmetic: stories per sprint = weekly capacity × sprint
   length, sprint count = stories ÷ that, rounded up. Sprints run back to back from the
   chosen start date.
4. **Create the epic and stories** — one epic named after the project, with the
   requirements and assumptions in its description; one issue per story, with its role
   and Given/When/Then criteria, parented to the epic.
5. **Create the sprints** — one per block of stories, dated, and left in the future state.
6. **Distribute** — each story is moved into its sprint one at a time, ranked after the
   previous one, so the order in Jira is the dependency order.
7. **Create the sub-tasks (optional)** — last, once the stories and sprints exist. Each
   sub-task is created as a real Jira sub-task under its story, in bulk: one call per 50
   sub-tasks, so a 10-story push with 20 sub-tasks adds a single call. They are never
   moved or ranked themselves; they follow their parent story into its sprint. If any
   sub-task fails, or the AI's plan is unusable or unavailable, the stories and sprints
   are untouched and the dialog says what was left out.

Sprint math is unchanged by sub-tasks: capacity is counted in stories, never sub-tasks, so
a push with sub-tasks has exactly the same sprints as one without.

It spans two Jira API surfaces: the platform REST API (projects, issue types, issues) and
the Agile API (boards, sprints, and moving issues into them). Each needs its own scopes,
which is why the app requests both kinds — see the setup section below.

## Design Decisions

**No AI estimation.** Asking a model for story points produces confident, meaningless
numbers. Sprint count is arithmetic from one real user input: weekly team capacity. The
AI only orders stories by dependency; it never sizes them.

**No database.** The Jira connection is held in an encrypted (Fernet) HttpOnly cookie.
Atlassian rotates refresh tokens on every use, so each request saves the new one back to
the cookie; no token is ever stored server-side.

**OAuth over API tokens.** Users never paste a credential into ReqPrint. They approve
access on Atlassian's own screen, and can revoke it from their Atlassian account.

**Partial failure is surfaced, not rolled back.** Preflight validates the project, board,
and issue types before any epic, story, or sprint is created. If an individual story
fails afterwards, the rest proceed and the failure is reported with Jira's own reason.
(When ReqPrint creates the project itself, that happens during preflight, so a failure
right after it can leave an empty project — the dialog says so.)

**Sub-tasks are derived, not invented.** A model asked to break a story into tasks will
emit the same backend/frontend/QA template for every story, which carries no information.
Instead each sub-task must cite an acceptance criterion from the document, and this is
enforced in code, not just requested in the prompt: a sub-task citing nothing or an
out-of-range criterion is rejected, and a story losing more than half its sub-tasks gets
none. (The story text is used as the source only for a story that has no criteria at all.)
The push response carries an audit trail showing which criterion each sub-task came from.
Checked against the real model: 12 runs across two documents, one of them adversarial
(server-only stories, a story with a single criterion, one with none, one in Arabic),
189 sub-tasks in all, with zero rejected.

## Running Locally

ReqPrint is not currently hosted anywhere: you run it yourself. It ships as a single
Docker image that serves both the API and the built frontend on one port, or you can run
it with uvicorn directly.

```bash
# 1. Clone
git clone https://github.com/laljoudi/ReqPrint.git
cd ReqPrint

# 2. Create a .env with your Groq API key and the Jira settings
#    (variable names + placeholders only - see "Setting Up the Jira Integration" below)
cat > .env <<'EOF'
GROQ_API_KEY=your_key_here
JIRA_CLIENT_ID=your_atlassian_client_id
JIRA_CLIENT_SECRET=your_atlassian_client_secret
JIRA_REDIRECT_URI=http://localhost:8000/api/jira/callback
FRONTEND_ORIGIN=http://localhost:8000
SESSION_SECRET=generate_a_fernet_key
APP_ENV=local
EOF

# 3. Build the image
docker build -t reqprint .

# 4. Run it
docker run --env-file .env -p 8000:8000 reqprint
```

Then open **http://localhost:8000**.

To run without Docker, build the frontend once and start the API with uvicorn (it reads
the same `.env`):

```bash
pip install -r requirements.txt
(cd frontend && npm ci && npm run build)
uvicorn main:app --port 8000
```

> **Hosting.** An earlier version was deployed to AWS. That deployment has been retired,
> and nothing in this README describes a live site. The repository still contains the old
> GitHub Actions workflow for it (`.github/workflows/deploy.yml`); it targets the retired
> deployment and is not part of running ReqPrint.

> You'll need your own [Groq API key](https://console.groq.com/keys). The
> key stays server-side — it's read by the backend and never exposed to the browser.
>
> The Jira settings are required at startup: the server refuses to start if any of the
> six is missing, even if you never click Push to Jira. The next section covers them.

## Setting Up the Jira Integration

ReqPrint pushes to your own Jira Cloud site through OAuth 2.0 (3LO), so you register an
app with Atlassian once and give the server its credentials.

### Environment variables

Names only — put the values in your `.env` (there is a template in `.env.example`), never
in the repository:

- `JIRA_CLIENT_ID` — your Atlassian app's client ID
- `JIRA_CLIENT_SECRET` — its secret; read by the backend only, never sent to the browser
- `JIRA_REDIRECT_URI` — the callback URL, exactly as registered with Atlassian (below)
- `FRONTEND_ORIGIN` — the origin the app is served from: scheme and host, plus the port
  if there is one, and no path. The sign-in popup reports back to exactly this origin
- `SESSION_SECRET` — the key that encrypts the Jira connection cookie (generated below)
- `APP_ENV` — `local` or `prod`

### Registering the Atlassian app

1. Open the [Atlassian developer console](https://developer.atlassian.com/console/myapps/)
   and create an **OAuth 2.0 integration**.
2. Under **Permissions**, add the **Jira API** and enable these 13 scopes.

   Classic scopes:
   - `read:jira-work`
   - `write:jira-work`
   - `read:jira-user`
   - `manage:jira-project`
   - `manage:jira-configuration`

   Granular scopes for the Agile API (boards and sprints):
   - `read:board-scope:jira-software`
   - `write:board-scope:jira-software`
   - `read:sprint:jira-software`
   - `write:sprint:jira-software`
   - `write:issue:jira-software`

   Granular scopes the Agile API also needs from the platform side:
   - `read:project:jira`
   - `read:issue-details:jira`
   - `read:jql:jira`

   The Agile API accepts no classic scopes, which is why both kinds are needed. A third
   scope, `offline_access`, is what makes refresh tokens possible; the app requests it at
   sign-in and there is nothing to enable for it in the console. Sub-tasks need no
   additional scope: the same 13 cover them.
3. Under **Authorization**, add the callback URL for **OAuth 2.0 (3LO)**. Its format is
   your app's origin followed by `/api/jira/callback`:
   - locally: `http://localhost:8000/api/jira/callback`
   - in production: `https://<your-domain>/api/jira/callback`

   It must match `JIRA_REDIRECT_URI` exactly — scheme, host, port, and path.
4. Under **Settings**, copy the client ID and secret into `JIRA_CLIENT_ID` and
   `JIRA_CLIENT_SECRET`.

A scope that is requested but not enabled in the console makes Atlassian's consent screen
fail. Existing connections keep the scopes they were granted, so after changing scopes,
reconnect.

### Generating `SESSION_SECRET`

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Keep it secret and keep it stable: changing it makes every saved Jira connection
unreadable, so everyone has to connect again.

### Production

Set `APP_ENV=prod`. That marks the connection cookies `Secure`, and browsers only keep
and send those over HTTPS — so the app requires HTTPS in production (terminating TLS at a
proxy or load balancer is fine). Over plain HTTP the browser refuses to store the cookie
and connecting will not work. `JIRA_REDIRECT_URI` and `FRONTEND_ORIGIN` should then be
`https://` URLs.

For local development, use the built app on port 8000 rather than the Vite dev server:
the sign-in popup reports back to `FRONTEND_ORIGIN`, which is set to that origin.

## Known Limitations

- **"Use an existing project" is not implemented.** Every push creates a new project.
  (The backend can already push into an existing one; there is just no way yet to list
  your projects in the interface.)
- **If you have several Jira sites, the first one is used.**
- **The duplicate-push warning lives in `localStorage`,** so it is per-browser — pushing
  the same document from another browser or after clearing site data won't be flagged.
- **A push is capped at 100 stories.**
- **Sub-tasks following their parent story into its sprint is not confirmed by the API
  definitions.** It is Jira's documented behavior, but Atlassian's published API
  definitions don't state it, and it hasn't been checked against a live site. That is why
  sub-tasks are never moved into a sprint themselves.
- **After a partial bulk-create failure, returned keys are matched to requests by
  order.** The API doesn't guarantee that. If the number of keys returned disagrees with
  the number of sub-tasks that succeeded, the keys are left unattributed rather than
  guessed.

## Screenshots
