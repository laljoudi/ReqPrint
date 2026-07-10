# ReqPrint

An AI Business Analysis assistant. You describe a project in plain language, answer a
few clarifying questions, and it produces structured software requirements
(functional/non-functional requirements, user stories, acceptance criteria, use cases,
assumptions) — exportable as a Word document.

## How the project is laid out

```
ReqPrint/
├── ai.py              # Talks to Gemini: next_question(), generate_requirements(), revise_requirements()
├── prompts.py         # All prompt text used by ai.py
├── export.py          # Builds the .docx file from the requirements data
├── main.py            # FastAPI backend - turns the functions above into web endpoints
├── requirements.txt   # Python dependencies
├── .env                # GEMINI_API_KEY and APP_PASSWORD (never committed)
│
└── frontend/           # The React app (what you see in the browser)
    ├── index.html
    ├── vite.config.js  # Dev server + build config
    └── src/
        ├── main.jsx           # Boots React into the page
        ├── App.jsx            # The "brain": holds all state, decides which screen to show
        ├── index.css          # Tailwind + the app's color palette
        ├── lib/api.js         # Every call to the backend lives here (one function per endpoint)
        └── components/
            ├── Header.jsx       # Top bar (logo + title)
            ├── LoginScreen.jsx  # Password screen
            ├── Stages.jsx       # "Describe" and "Questions" screens
            ├── ResultsStage.jsx # The results page: tabs, download, start over
            ├── ResultTabs.jsx   # The 5 tab contents shown inside ResultsStage
            └── RefinePanel.jsx  # The "ask for a change" sidebar
```

**ai.py, prompts.py, and export.py are unchanged from the original Streamlit app.**
The migration only changed how those functions are *called* — first from a Streamlit
script, now from a web server (`main.py`) and a browser app (`frontend/`).

## How a request flows, end to end

1. You type something in the browser (React, running on `localhost:5174`).
2. React calls a function in `frontend/src/lib/api.js`, e.g. `generateRequirements(...)`.
3. That function sends an HTTP request to the FastAPI backend (`main.py`, running on
   `localhost:8000`), e.g. `POST /generate`.
4. `main.py` calls the matching function in `ai.py`, which calls Gemini.
5. The result comes back through the same chain and React displays it.

Your Gemini API key and app password only ever live on the backend (`main.py` /
`ai.py`) — the browser never sees them.

## Running it locally

Two servers, in two terminals, from the project root:

```bash
# Terminal 1 — backend (http://localhost:8000)
.venv/bin/uvicorn main:app --reload --port 8000

# Terminal 2 — frontend (http://localhost:5173, or next free port)
cd frontend && npm run dev
```

Then open whatever URL the frontend terminal prints.

## Files you generally won't need to touch

- `frontend/.oxlintrc.json` — linter config, used by `npm run lint`.
- `frontend/public/favicon.svg` — the browser tab icon.
- `test_api.py` — a standalone CLI script for manually trying `next_question()`
  outside of any web server; not part of the app itself.
