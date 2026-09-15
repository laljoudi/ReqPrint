// Stage 2 (of welcome -> workspace): the interview and the results, as one
// screen. A persistent conversation panel on the left carries the whole
// dialogue - the user's first input (description or notes, no mode to pick),
// clarifying Q&A, and (once requirements exist) refine instructions - while
// the main area on the right shows a placeholder until there's something to
// show, then the generated requirements themselves. Nothing here changes
// what any button calls; App.jsx's handlers and state shape are unchanged,
// only how they're laid out and displayed.
import { useState } from "react";
import {
  RequirementsSection,
  UserStoriesSection,
  AcceptanceCriteriaSection,
  UseCasesSection,
  AssumptionsSection,
  ReviewSection,
} from "./DocumentSections";

const INTRO_REFINE =
  "This document was generated from your conversation. Ask me here to add, remove, or rephrase anything.";

const SUGGESTIONS = ["Add security requirements", "Split stories by role", "Add offline support"];

const CATEGORIES = [
  "Software Systems",
  "AI Solutions",
  "FinTech",
  "HR Tech",
  "Productivity Tools",
  "Other",
];

// First-turn-only step, shown in the same input area before any text is
// typed: pick a category so the interview can ask more relevant questions.
// Rectangular (not pill-shaped, unlike the suggestion chips below) so the two
// don't look interchangeable.
function CategoryChips({ onSelect }) {
  return (
    <div>
      <p className="text-[12.5px] text-muted mb-2.5">What kind of project is this?</p>
      <div className="flex flex-wrap gap-2">
        {CATEGORIES.map((c) => (
          <button
            key={c}
            type="button"
            onClick={() => onSelect(c)}
            className="border border-border bg-surface text-ink text-[13px] font-medium px-3.5 py-2 rounded-lg hover:bg-accent/8 hover:border-accent/30 transition-colors"
          >
            {c}
          </button>
        ))}
      </div>
    </div>
  );
}

// Replaces the chips once one is picked - confirms the choice and offers a
// way back to the chips, without a page transition or layout jump (same
// input area, same spot).
function CategoryPill({ category, onClear }) {
  return (
    <div className="mb-2.5">
      <span className="inline-flex items-center gap-1.5 border border-border bg-surface text-ink text-[12.5px] font-medium px-2.5 py-1 rounded-lg">
        {category}
        <button
          type="button"
          onClick={onClear}
          className="text-hint hover:text-ink transition-colors"
          aria-label="Change category"
        >
          ✕
        </button>
      </span>
    </div>
  );
}

function Thinking() {
  return (
    <div className="flex gap-1.5 items-center py-1">
      {[0, 0.15, 0.3].map((delay) => (
        <span
          key={delay}
          className="w-1.5 h-1.5 rounded-full bg-hint"
          style={{ animation: "rp-dot 1.1s infinite ease-in-out", animationDelay: `${delay}s` }}
        />
      ))}
    </div>
  );
}

// No avatars, no "AI"/"YOU" labels - speakers are told apart by alignment and
// the subtle background on the user's own messages, not by badges. ReqPrint's
// own messages are plain text on the page, not a card; only the user's
// messages get the soft butter-tinted bubble.
function Message({ role, text }) {
  const mine = role === "user";
  if (mine) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] bg-butter px-4 py-3 rounded-2xl text-[14.5px] leading-[1.6] text-ink">
          {text}
        </div>
      </div>
    );
  }
  return <p className="max-w-[92%] text-[14.5px] leading-[1.7] text-ink m-0">{text}</p>;
}

function Placeholder() {
  return (
    <div className="h-full flex items-center justify-center px-10 py-20 text-center">
      <p className="text-muted text-[15px] max-w-xs">
        Your requirements will appear here once there's enough to work with.
      </p>
    </div>
  );
}

// Shared CSS-only hover tooltip (no tooltip primitive exists elsewhere in the
// codebase, so this is the minimal one, reused by every button that needs
// one). Wrap a button in <div className="relative group"> and place this as
// its sibling; `width` sizes the panel for short one-liners vs longer content.
function Tooltip({ children, width = "w-64" }) {
  return (
    <div
      className={`pointer-events-none absolute left-1/2 -translate-x-1/2 top-full mt-2 ${width} rounded-lg border border-border bg-panel px-3.5 py-3 text-left opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-opacity z-10`}
    >
      {children}
    </div>
  );
}

const COMPLIANCE_STANDARDS = [
  "Saudi PDPL (data protection & privacy)",
  "ZATCA (e-invoicing compliance)",
  "INVEST (user story quality)",
  "EARS (requirement clarity standards)",
];

// Placeholder for a future feature - no backend call, just a button, a hover
// tooltip, and a static "coming soon" notice on click.
function ComplianceCheckButton({ onClick }) {
  return (
    <div className="relative group">
      <button
        onClick={onClick}
        className="h-9 px-3.5 rounded-lg border border-border bg-panel text-muted font-semibold text-xs hover:bg-surface transition-colors"
      >
        Compliance Check
      </button>
      <Tooltip>
        <p className="text-[12px] font-semibold text-ink mb-1.5">Checks your requirements against:</p>
        <ul className="text-[11.5px] text-muted leading-relaxed list-disc list-inside space-y-0.5 m-0 p-0">
          {COMPLIANCE_STANDARDS.map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ul>
      </Tooltip>
    </div>
  );
}

function DownloadIcon(props) {
  return (
    <svg
      width="15"
      height="15"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.85"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
      <path d="M7 10l5 5 5-5"></path>
      <path d="M12 15V3"></path>
    </svg>
  );
}

export default function WorkspaceScreen({
  description,
  qaHistory,
  currentQuestion,
  currentSuggestions,
  readyToGenerate,
  onStart,
  onAnswer,
  onGenerate,
  loading,
  error,
  data,
  onDownload,
  downloading,
  onStartOver,
  onRefine,
  refineHistory,
  refining,
  refineError,
  review,
  onReview,
  reviewing,
  reviewError,
}) {
  const [input, setInput] = useState("");
  const [category, setCategory] = useState(null);
  const [showComplianceNotice, setShowComplianceNotice] = useState(false);

  const isFirstTurn = !description;
  const inRefineMode = !!data;

  const messages = [];
  if (description) messages.push({ role: "user", text: description });
  for (const qa of qaHistory) {
    messages.push({ role: "assistant", text: qa.q });
    messages.push({ role: "user", text: qa.a });
  }
  if (currentQuestion && !readyToGenerate && !inRefineMode) {
    messages.push({ role: "assistant", text: currentQuestion });
  }

  const useCases = data?.use_cases || [];
  const assumptions = data?.assumptions || [];
  const reviewIssues = review?.issues || [];

  function submitAnswer(text) {
    if (inRefineMode) onRefine(text);
    else if (!description) onStart(text, category);
    else onAnswer(text);
  }

  function handleSubmit(e) {
    e.preventDefault();
    const text = input.trim();
    if (!text) return;
    setInput("");
    submitAnswer(text);
  }

  function sendSuggestion(label) {
    submitAnswer(label);
  }

  const showAnswerInput = !inRefineMode && !readyToGenerate;
  const showQuestionSuggestions =
    !isFirstTurn && !inRefineMode && !readyToGenerate && currentSuggestions?.length > 0;
  const showSkipLink = description && currentQuestion && !readyToGenerate && !inRefineMode;
  const isBusy = loading || refining;
  const activeError = inRefineMode ? refineError : error;

  return (
    <div className="lg:h-screen flex flex-col lg:flex-row">
      {/* Left: persistent conversation panel - interview, then refine. */}
      <aside className="lg:w-[400px] lg:flex-none flex flex-col border-b lg:border-b-0 lg:border-r border-border bg-panel lg:h-screen">
        <header className="h-14 flex-none flex items-center px-5 border-b border-border">
          <div className="font-display font-extrabold text-base tracking-tight">ReqPrint</div>
          <div className="w-px h-5 bg-border mx-3" />
          <div className="text-[12.5px] text-muted">
            {inRefineMode ? "Refine" : "Scoping conversation"}
          </div>
        </header>

        <div className="flex-1 overflow-y-auto max-h-[55vh] lg:max-h-none px-5 py-7 flex flex-col gap-5">
          {messages.map((m, i) => (
            <Message key={i} role={m.role} text={m.text} />
          ))}

          {inRefineMode && (
            <>
              <div className="text-center text-[11px] font-bold uppercase tracking-wide text-hint py-1">
                Requirements generated
              </div>
              <Message role="assistant" text={INTRO_REFINE} />
              {refineHistory.map((h, i) => (
                <Message key={`refine-${i}`} role="user" text={h} />
              ))}
            </>
          )}

          {isBusy && <Thinking />}
        </div>

        <div className="flex-none border-t border-border px-5 pt-3.5 pb-4">
          {activeError && (
            <div className="mb-3 rounded-lg bg-accent-dark/8 border border-accent-dark/25 text-accent-dark text-sm px-3.5 py-2.5">
              {activeError}
            </div>
          )}

          {readyToGenerate ? (
            <button
              onClick={onGenerate}
              disabled={loading}
              className="w-full h-[46px] rounded-xl bg-accent hover:brightness-105 text-white font-display font-bold text-[14.5px] disabled:opacity-60 transition"
            >
              {loading ? "Generating document..." : "Generate requirements document"}
            </button>
          ) : isFirstTurn && !category ? (
            <CategoryChips onSelect={setCategory} />
          ) : (
            <>
              {isFirstTurn && category && (
                <CategoryPill category={category} onClear={() => setCategory(null)} />
              )}

              {(showQuestionSuggestions || inRefineMode) && (
                <div className="flex flex-wrap gap-1.5 mb-3">
                  {(showQuestionSuggestions ? currentSuggestions : SUGGESTIONS).map((label) => (
                    <button
                      key={label}
                      onClick={() => sendSuggestion(label)}
                      disabled={isBusy}
                      className="border border-border bg-surface text-muted text-xs font-medium px-2.5 py-1.5 rounded-full hover:bg-accent/8 hover:border-accent/30 disabled:opacity-60 transition-colors"
                    >
                      {label}
                    </button>
                  ))}
                </div>
              )}

              {(showAnswerInput || inRefineMode) && (
                <form
                  onSubmit={handleSubmit}
                  className="flex items-end gap-2.5 border border-border rounded-[14px] px-4 py-2.5 bg-panel focus-within:border-accent focus-within:shadow-[0_0_0_4px_rgba(122,31,43,0.12)] transition"
                >
                  <textarea
                    rows={isFirstTurn ? 4 : 1}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        handleSubmit(e);
                      }
                    }}
                    placeholder={
                      inRefineMode
                        ? "Ask ReqPrint to refine..."
                        : isFirstTurn
                          ? "Write a plain description, or paste your notes..."
                          : undefined
                    }
                    className="flex-1 border-none outline-none resize-none text-[14.5px] leading-relaxed bg-transparent py-1.5 max-h-[160px]"
                  />
                  <button
                    type="submit"
                    disabled={isBusy}
                    className="flex-none w-[38px] h-[38px] rounded-[10px] bg-accent hover:brightness-105 text-white flex items-center justify-center disabled:opacity-60 transition"
                  >
                    <svg
                      width="17"
                      height="17"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M12 19V5"></path>
                      <path d="m5 12 7-7 7 7"></path>
                    </svg>
                  </button>
                </form>
              )}

              {showSkipLink && (
                <div className="mt-2 flex justify-end text-[11.5px] text-hint">
                  <button
                    onClick={onGenerate}
                    disabled={loading}
                    className="underline hover:text-ink disabled:opacity-60"
                  >
                    Generate now (skip remaining questions)
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </aside>

      {/* Right: the requirements build here, in place - no separate screen. */}
      <main className="flex-1 lg:h-screen lg:overflow-y-auto">
        {!data ? (
          <Placeholder />
        ) : (
          <div className="max-w-[760px] mx-auto px-6 md:px-10 py-10">
            <div className="flex items-start justify-between flex-wrap gap-4 pb-8 mb-10 border-b border-border">
              <div>
                <div className="text-[11px] font-bold tracking-[0.09em] uppercase text-accent mb-3">
                  Software Requirements Specification
                </div>
                <h1 className="font-display font-extrabold text-[28px] tracking-tight text-ink m-0">
                  Requirements Document
                </h1>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={onReview}
                  disabled={reviewing}
                  className="h-9 px-3.5 rounded-lg border border-border bg-panel text-muted font-semibold text-xs hover:bg-surface disabled:opacity-60 transition-colors"
                >
                  {reviewing
                    ? "Reviewing..."
                    : reviewIssues.length
                      ? "Review Again"
                      : "Review Requirements"}
                </button>
                <ComplianceCheckButton onClick={() => setShowComplianceNotice(true)} />
                <button
                  onClick={onStartOver}
                  className="h-9 px-3.5 rounded-lg border border-border bg-panel text-muted font-semibold text-xs hover:bg-surface transition-colors"
                >
                  Start over
                </button>
                <div className="relative group">
                  <button
                    onClick={onDownload}
                    disabled={downloading}
                    className="inline-flex items-center gap-1.5 h-9 px-3.5 rounded-lg bg-accent hover:brightness-105 text-white font-semibold text-xs disabled:opacity-60 transition"
                  >
                    <DownloadIcon />
                    {downloading && "Preparing..."}
                  </button>
                  <Tooltip width="w-48">
                    <p className="text-[12px] text-ink m-0">Download as Word document</p>
                  </Tooltip>
                </div>
              </div>
            </div>

            {showComplianceNotice && (
              <div className="rounded-[14px] bg-surface border border-border text-sm text-muted px-4 py-3 mb-8">
                This feature is currently in development. We're building automated checks
                against these standards — check back soon.
              </div>
            )}

            <RequirementsSection requirements={data.requirements} />
            <UserStoriesSection userStories={data.user_stories} />
            <AcceptanceCriteriaSection criteria={data.acceptance_criteria} />
            <UseCasesSection useCases={useCases} />
            <AssumptionsSection assumptions={assumptions} />
            <ReviewSection issues={reviewIssues} loading={reviewing} error={reviewError} />
          </div>
        )}
      </main>
    </div>
  );
}
