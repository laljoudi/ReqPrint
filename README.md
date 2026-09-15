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
- **AWS ECS + ECR behind an ALB** — container hosting and registry
- **GitHub Actions** — CI/CD, authenticating to AWS via short-lived OIDC credentials

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
the artifact running in production is byte-for-byte the same thing that runs locally —
there's no separate frontend host, no CORS juggling between environments, and no "works on
my machine" gap between dev and prod.

**Automated deployment with no stored credentials.** Every push to `main` triggers a
GitHub Actions workflow that builds the image, pushes it to a container registry, and
rolls out the new version on AWS ECS. Crucially, the pipeline authenticates to AWS via
OIDC — GitHub exchanges a short-lived token for temporary AWS credentials at run time — so
there are **no long-lived AWS access keys stored** in the repository or CI secrets. Deploys
are hands-off and the credential blast radius stays minimal.

## Running Locally

ReqPrint ships as a single Docker image that serves both the API and the built frontend on
one port.

```bash
# 1. Clone
git clone https://github.com/laljoudi/ReqPrint.git
cd ReqPrint

# 2. Create a .env with your Groq API key (variable names + placeholders only)
cat > .env <<'EOF'
GROQ_API_KEY=your_key_here
EOF

# 3. Build the image
docker build -t reqprint .

# 4. Run it
docker run --env-file .env -p 8000:8000 reqprint
```

Then open **http://localhost:8000**.

> You'll need your own [Groq API key](https://console.groq.com/keys). The
> key stays server-side — it's read by the backend and never exposed to the browser.

## Screenshots
