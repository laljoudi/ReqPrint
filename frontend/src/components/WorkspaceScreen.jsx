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

const INTRO =
  "Write a plain description, or paste whatever notes you already have - ReqPrint will figure out what to do with it.";
const INTRO_REFINE =
  "This document was generated from your conversation. Ask me here to add, remove, or rephrase anything.";

const SUGGESTIONS = ["Add security requirements", "Split stories by role", "Add offline support"];

function ThinkingBubble() {
  return (
    <div className="flex gap-3 items-start">
      <div className="flex-none w-[30px] h-[30px] rounded-[9px] bg-accent text-white flex items-center justify-center font-display font-bold text-[11.5px]">
        AI
      </div>
      <div className="bg-bubble rounded-[14px_14px_14px_4px] px-4 py-3.5 flex gap-1.5 items-center">
        {[0, 0.15, 0.3].map((delay) => (
          <span
            key={delay}
            className="w-1.5 h-1.5 rounded-full bg-hint"
            style={{ animation: "rp-dot 1.1s infinite ease-in-out", animationDelay: `${delay}s` }}
          />
        ))}
      </div>
    </div>
  );
}

function MessageBubble({ role, text }) {
  const mine = role === "user";
  return (
    <div className={`flex gap-3 items-start ${mine ? "flex-row-reverse" : ""}`}>
      <div
        className={`flex-none w-[30px] h-[30px] rounded-[9px] flex items-center justify-center font-display font-bold text-[11.5px] ${
          mine ? "bg-ink text-white" : "bg-accent text-white"
        }`}
      >
        {mine ? "YOU" : "AI"}
      </div>
      <div
        className={`max-w-[78%] px-4 py-3.5 text-[14.5px] leading-[1.55] ${
          mine
            ? "bg-accent text-white rounded-[14px_14px_4px_14px]"
            : "bg-bubble text-ink rounded-[14px_14px_14px_4px]"
        }`}
      >
        {text}
      </div>
    </div>
  );
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

  const isFirstTurn = !description;
  const inRefineMode = !!data;

  const messages = [{ role: "assistant", text: INTRO }];
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
    else if (!description) onStart(text);
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
      <aside className="lg:w-[400px] lg:flex-none flex flex-col border-b lg:border-b-0 lg:border-r border-border bg-white lg:h-screen">
        <header className="h-14 flex-none flex items-center px-5 border-b border-border">
          <div className="font-display font-extrabold text-base tracking-tight">ReqPrint</div>
          <div className="w-px h-5 bg-border mx-3" />
          <div className="text-[12.5px] text-muted">
            {inRefineMode ? "Refine" : "Scoping conversation"}
          </div>
        </header>

        <div className="flex-1 overflow-y-auto max-h-[55vh] lg:max-h-none px-5 py-6 flex flex-col gap-4">
          {messages.map((m, i) => (
            <MessageBubble key={i} role={m.role} text={m.text} />
          ))}

          {inRefineMode && (
            <>
              <div className="text-center text-[11px] font-bold uppercase tracking-wide text-hint py-1">
                Requirements generated
              </div>
              <MessageBubble role="assistant" text={INTRO_REFINE} />
              {refineHistory.map((h, i) => (
                <MessageBubble key={`refine-${i}`} role="user" text={h} />
              ))}
            </>
          )}

          {isBusy && <ThinkingBubble />}
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
          ) : (
            <>
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
                  className="flex items-end gap-2.5 border border-border rounded-[14px] px-4 py-2.5 bg-white focus-within:border-accent focus-within:shadow-[0_0_0_4px_rgba(100,31,42,0.12)] transition"
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
                  className="h-9 px-3.5 rounded-lg border border-border bg-white text-muted font-semibold text-xs hover:bg-surface disabled:opacity-60 transition-colors"
                >
                  {reviewing
                    ? "Reviewing..."
                    : reviewIssues.length
                      ? "Review Again"
                      : "Review Requirements"}
                </button>
                <button
                  onClick={onStartOver}
                  className="h-9 px-3.5 rounded-lg border border-border bg-white text-muted font-semibold text-xs hover:bg-surface transition-colors"
                >
                  Start over
                </button>
                <button
                  onClick={onDownload}
                  disabled={downloading}
                  className="h-9 px-3.5 rounded-lg bg-accent hover:brightness-105 text-white font-semibold text-xs disabled:opacity-60 transition"
                >
                  {downloading ? "Preparing..." : "Word"}
                </button>
              </div>
            </div>

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
