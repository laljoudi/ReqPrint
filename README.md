# ReqPrint

**AI-Powered Requirements Engineering — turn a plain-language idea into a structured Software Requirements Specification.**

[Live demo](LINK)

Writing software requirements usually means hours of stakeholder interviews and
documentation before a single line of a spec exists. ReqPrint compresses that: you
describe your project in plain language, it asks the adaptive clarifying questions a
business analyst would, and then it generates a structured requirements document you can
refine and export. The goal isn't to replace analysis — it's to get from a rough idea to
a solid first draft in minutes instead of days.

## Features

- **Adaptive clarifying questions** — each question builds on your previous answer,
  deliberately covering different requirement areas, and stops once there's enough
  context rather than asking a fixed list.
- **Structured specification** — generates functional & non-functional requirements,
  user stories, acceptance criteria, and use cases, laid out in clear sections.
- **Refine panel** — adjust any section conversationally until the requirements match
  what you actually meant.
- **One-click Word export** — download the whole spec as a polished `.docx`, ready to
  share.

## How It Works

1. **Describe your idea** — a sentence or two in plain language is enough.
2. **Answer clarifying questions** — a short, adaptive back-and-forth that fills in the gaps.
3. **Requirements generated in sections** — a structured spec, organized the way a real one is.
4. **Export to Word** — one click produces a shareable `.docx`.

## Built With

- **React** — single-page frontend
- **FastAPI** — REST API backend
- **Google Gemini API** — the language model behind the questions and generation
- **Docker** — single multi-stage image
- **AWS ECS + ECR** — container hosting and registry
- **GitHub Actions** — CI/CD

## Engineering Highlights

The interesting parts of this project are less about the tool list and more about a few
deliberate decisions.

**Multi-stage prompting.** Rather than asking the model to turn a raw description
straight into a spec, ReqPrint separates *elicitation* from *generation*. One stage runs
the clarifying-question interview; a distinct stage takes that fuller context and
produces the structured document. Splitting the work this way consistently yields more
complete, less hand-wavy requirements than a single do-everything prompt, because the
model isn't simultaneously interviewing and drafting — it does one job at a time.

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
git clone https://github.com/<your-username>/ReqPrint.git
cd ReqPrint

# 2. Create a .env with your Gemini API key (variable names + placeholders only)
cat > .env <<'EOF'
GEMINI_API_KEY=your_key_here
EOF

# 3. Build the image
docker build -t reqprint .

# 4. Run it
docker run --env-file .env -p 8000:8000 reqprint
```

Then open **http://localhost:8000**.

> You'll need your own [Google Gemini API key](https://aistudio.google.com/app/apikey). The
> key stays server-side — it's read by the backend and never exposed to the browser.

## Screenshots
