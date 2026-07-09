import os
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

from ai import next_question, generate_requirements, revise_requirements
from export import build_docx

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
APP_PASSWORD = os.getenv("APP_PASSWORD")

ACCENT = "#2563EB"
MAX_QUESTIONS = 5


def inject_css():
    st.markdown(f"""
    <style>
    .top-bar {{display:flex; align-items:center; gap:12px;
              border-bottom:1px solid #eceae6; padding-bottom:14px; margin-bottom:8px;}}
    .logo {{width:34px; height:34px; background:{ACCENT}; border-radius:8px;
           display:flex; align-items:center; justify-content:center;
           color:#fff; font-weight:700; font-size:18px;}}
    .brand {{font-weight:600; font-size:20px; color:#1a1a19;}}
    .tagline {{color:#8a8780; font-size:13px; border-left:1px solid #e0ded9; padding-left:12px;}}
    .story-card {{background:#F1EEFB; border:0.5px solid #E0D9F5; border-radius:12px;
                 padding:14px 18px; margin-bottom:10px;}}
    .story-id {{color:#57459B; font-weight:600; font-size:13px;}}
    .badge {{display:inline-block; padding:4px 12px; border-radius:6px;
            font-size:13px; font-weight:600; margin-bottom:10px;}}
    .b-func {{background:#EEF4FB; color:#2C5988;}}
    .b-nonfunc {{background:#ECF6EE; color:#3A6B45;}}
    </style>
    """, unsafe_allow_html=True)


def login_screen():
    st.markdown('<div class="logo">R</div>', unsafe_allow_html=True)
    st.title("Sign in to your workspace")
    st.caption("Turn plain-language descriptions into structured software requirements.")
    password = st.text_input("Password", type="password")
    if st.button("Sign in", type="primary"):
        if not APP_PASSWORD:
            st.error("APP_PASSWORD not set. Check your .env file.")
        elif password == APP_PASSWORD:
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("Incorrect password. Try again.")
    st.caption("Demo access - enter the password from your .env file.")


def header():
    st.markdown(
        '<div class="top-bar"><div class="logo">R</div>'
        '<span class="brand">ReqPrint</span>'
        '<span class="tagline">AI business analysis assistant</span></div>',
        unsafe_allow_html=True,
    )


def reset_to_describe():
    st.session_state.stage = "describe"
    st.session_state.description = ""
    st.session_state.qa_history = []
    st.session_state.current_question = None
    st.session_state.data = None
    st.session_state.history = []


def final_input_text(description, qa_history):
    """Combine the description with the collected answers for the final generation."""
    text = description + "\n\nClarifying questions and answers:\n"
    for qa in qa_history:
        text += f"Q: {qa['q']}\nA: {qa['a']}\n"
    return text


def render_output(data):
    counts = {
        "req": len(data["requirements"]["functional"]) + len(data["requirements"]["non_functional"]),
        "us": len(data["user_stories"]),
        "ac": len(data["acceptance_criteria"]),
        "uc": len(data.get("use_cases", [])),
        "as": len(data.get("assumptions", [])),
    }
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        f"Requirements ({counts['req']})",
        f"User Stories ({counts['us']})",
        f"Acceptance Criteria ({counts['ac']})",
        f"Use Cases ({counts['uc']})",
        f"Assumptions ({counts['as']})",
    ])
    with tab1:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown('<span class="badge b-func">Functional</span>', unsafe_allow_html=True)
            for r in data["requirements"]["functional"]:
                st.markdown(f"- {r}")
        with c2:
            st.markdown('<span class="badge b-nonfunc">Non-functional</span>', unsafe_allow_html=True)
            for r in data["requirements"]["non_functional"]:
                st.markdown(f"- {r}")
    with tab2:
        for s in data["user_stories"]:
            st.markdown(
                f'<div class="story-card"><span class="story-id">{s["id"]} - {s["role"]}</span>'
                f'<br>{s["story"]}</div>', unsafe_allow_html=True)
    with tab3:
        df = pd.DataFrame(data["acceptance_criteria"]).rename(columns={
            "story_id": "Story", "scenario": "Scenario",
            "given": "Given", "when": "When", "then": "Then"})
        st.dataframe(df, use_container_width=True, hide_index=True)
    with tab4:
        use_cases = data.get("use_cases", [])
        if use_cases:
            df = pd.DataFrame(use_cases).rename(columns={
                "use_case_id": "ID", "actors": "Actors",
                "description": "Description", "preconditions": "Preconditions",
                "trigger": "Trigger", "main_flow": "Main flow",
                "alternative_flow": "Alternative flow"})
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No use cases were generated.")
    with tab5:
        assumptions = data.get("assumptions", [])
        if assumptions:
            st.caption("Information the AI added or inferred (not explicitly stated):")
            st.warning("\n".join(f"- {a}" for a in assumptions))
        else:
            st.info("No additional assumptions were made.")


def run_generation():
    """Generate requirements from description + answers, then move to results."""
    with st.spinner("Generating requirements..."):
        text = final_input_text(st.session_state.description, st.session_state.qa_history)
        st.session_state.data = generate_requirements(text)
        st.session_state.history = []
    st.session_state.stage = "results"
    st.rerun()


# ---------- App ----------
st.set_page_config(page_title="ReqPrint", page_icon="📋", layout="wide")
inject_css()

# session_state defaults
defaults = {
    "logged_in": False,
    "stage": "describe",
    "description": "",
    "qa_history": [],
    "current_question": None,
    "data": None,
    "history": [],
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# Login gate
if not st.session_state.logged_in:
    login_screen()
    st.stop()

header()

# ---------- Stage 1: describe ----------
if st.session_state.stage == "describe":
    st.subheader("Describe your project")
    desc = st.text_area("Enter a project or feature description:", height=140,
                        placeholder="e.g. A clinic appointment system where patients book online.")
    if st.button("Start", type="primary"):
        if not API_KEY:
            st.error("GEMINI_API_KEY not found. Check your .env file.")
        elif not desc.strip():
            st.warning("Please enter a description first.")
        else:
            st.session_state.description = desc
            st.session_state.qa_history = []
            with st.spinner("Thinking of the first question..."):
                result = next_question(desc, [])
            if result.get("done"):
                run_generation()
            else:
                st.session_state.current_question = result["question"]
                st.session_state.stage = "questions"
                st.rerun()

# ---------- Stage 2: questions (one at a time) ----------
elif st.session_state.stage == "questions":
    st.subheader("A few clarifying questions")
    st.caption(f"Project: {st.session_state.description}")

    # Show what's been answered so far
    for qa in st.session_state.qa_history:
        st.markdown(f"**Q:** {qa['q']}")
        st.markdown(f"**A:** {qa['a']}")

    st.info(f"**Question {len(st.session_state.qa_history) + 1}:** "
            f"{st.session_state.current_question}")

    with st.form("answer_form", clear_on_submit=True):
        answer = st.text_input("Your answer:")
        submitted = st.form_submit_button("Next", type="primary")
    if submitted:
        if not answer.strip():
            st.warning("Please write an answer, or click 'Generate now' to skip.")
        else:
            st.session_state.qa_history.append(
                {"q": st.session_state.current_question, "a": answer})
            if len(st.session_state.qa_history) >= MAX_QUESTIONS:
                run_generation()
            else:
                with st.spinner("Thinking of the next question..."):
                    result = next_question(st.session_state.description,
                                           st.session_state.qa_history)
                if result.get("done"):
                    run_generation()
                else:
                    st.session_state.current_question = result["question"]
                    st.rerun()

    if st.button("Generate now (skip remaining questions)"):
        run_generation()

# ---------- Stage 3: results ----------
elif st.session_state.stage == "results":
    if st.session_state.data:
        render_output(st.session_state.data)

        col1, col2 = st.columns([1, 4])
        with col1:
            st.download_button(
                "Download as Word",
                data=build_docx(st.session_state.data),
                file_name="requirements.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        with col2:
            if st.button("Start over"):
                reset_to_describe()
                st.rerun()

        with st.sidebar:
            st.header("Refine")
            st.caption("Ask for a change and the output updates.")
            for h in st.session_state.history:
                st.markdown(f"- {h}")
            with st.form("refine_form", clear_on_submit=True):
                instruction = st.text_input("Your request:",
                                            placeholder="e.g. Add a user story for admins")
                submitted = st.form_submit_button("Send")
            if submitted and instruction.strip():
                with st.spinner("Updating..."):
                    try:
                        st.session_state.data = revise_requirements(
                            st.session_state.data, instruction)
                        st.session_state.history.append(instruction)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Update failed: {e}")