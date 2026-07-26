// Stage 2 of welcome -> chat -> document: describing the project and
// answering clarifying questions, both shown as one chat thread (the mockup
// treats them as a single conversation rather than two separate screens).
//
// This component is purely presentational - it derives the message list from
// props every render. App.jsx still owns all the real state (description,
// qaHistory, currentQuestion) and calls the exact same backend endpoints as
// before; only the UI changed.
import { useState } from "react";

const INTRO = "Tell me about the project you're building.";

const STEP_DEFS = [
  { n: "1", label: "Describe" },
  { n: "2", label: "Converse" },
  { n: "3", label: "Publish" },
];

function StepDots() {
  return (
    <div className="flex items-center gap-4">
      {STEP_DEFS.map((s, i) => (
        <div key={s.n} className="flex items-center gap-1.5">
          <span
            className={`w-[18px] h-[18px] rounded-full flex items-center justify-center font-mono text-[10px] font-bold ${
              i <= 1 ? "bg-accent text-white" : "bg-border text-hint"
            }`}
          >
            {s.n}
          </span>
          <span className={`text-xs font-semibold ${i === 1 ? "text-ink" : "text-[#B0AAB4]"}`}>
            {s.label}
          </span>
        </div>
      ))}
    </div>
  );
}

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
            : "bg-bubble text-[#3A3A3A] rounded-[14px_14px_14px_4px]"
        }`}
      >
        {text}
      </div>
    </div>
  );
}

export default function ChatStage({
  description,
  qaHistory,
  currentQuestion,
  readyToGenerate,
  onDescribe,
  onAnswer,
  onGenerate,
  loading,
  error,
}) {
  const [input, setInput] = useState("");

  const messages = [{ role: "assistant", text: INTRO }];
  if (description) messages.push({ role: "user", text: description });
  for (const qa of qaHistory) {
    messages.push({ role: "assistant", text: qa.q });
    messages.push({ role: "user", text: qa.a });
  }
  if (currentQuestion && !readyToGenerate) {
    messages.push({ role: "assistant", text: currentQuestion });
  }

  function handleSubmit(e) {
    e.preventDefault();
    const text = input.trim();
    if (!text) return;
    setInput("");
    if (!description) onDescribe(text);
    else onAnswer(text);
  }

  const showInput = !readyToGenerate;
  const showSkipLink = description && currentQuestion && !readyToGenerate;

  return (
    <div className="h-screen flex flex-col">
      <header className="h-16 flex-none flex items-center justify-between px-6 bg-white border-b border-border">
        <div className="flex items-center gap-3.5">
          <div className="font-display font-extrabold text-lg tracking-tight">ReqPrint</div>
          <div className="w-px h-5.5 bg-border" />
          <div className="text-[13px] text-muted">Scoping conversation</div>
        </div>
        <StepDots />
      </header>

      <div className="flex-1 overflow-y-auto flex justify-center px-6 pt-9 pb-6">
        <div className="w-full max-w-[720px] flex flex-col gap-4.5">
          {messages.map((m, i) => (
            <MessageBubble key={i} role={m.role} text={m.text} />
          ))}
          {loading && <ThinkingBubble />}
        </div>
      </div>

      <div className="flex-none border-t border-border bg-white px-6 pt-4 pb-5 flex justify-center">
        <div className="w-full max-w-[720px]">
          {error && (
            <div className="mb-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm px-3.5 py-2.5">
              {error}
            </div>
          )}

          {readyToGenerate ? (
            <button
              onClick={onGenerate}
              disabled={loading}
              className="w-full h-[50px] rounded-xl bg-accent hover:brightness-105 text-white font-display font-bold text-[15px] shadow-[0_10px_24px_rgba(186,85,211,0.30)] disabled:opacity-60 transition"
            >
              {loading ? "Generating document..." : "Generate requirements document"}
            </button>
          ) : (
            showInput && (
              <>
                <form
                  onSubmit={handleSubmit}
                  className="flex items-end gap-2.5 border border-border rounded-[14px] px-4 py-2.5 bg-white focus-within:border-accent focus-within:shadow-[0_0_0_4px_rgba(186,85,211,0.12)] transition"
                >
                  <textarea
                    rows={1}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        handleSubmit(e);
                      }
                    }}
                    className="flex-1 border-none outline-none resize-none text-[14.5px] leading-relaxed bg-transparent py-1.5 max-h-[120px]"
                  />
                  <button
                    type="submit"
                    disabled={loading}
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
            )
          )}
        </div>
      </div>
    </div>
  );
}

