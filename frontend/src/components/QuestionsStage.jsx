import { useState } from "react";

const MAX_QUESTIONS = 5;

export default function QuestionsStage({
  description,
  qaHistory,
  currentQuestion,
  onAnswer,
  onSkip,
  loading,
  error,
}) {
  const [answer, setAnswer] = useState("");

  function handleSubmit(e) {
    e.preventDefault();
    if (!answer.trim()) return;
    onAnswer(answer);
    setAnswer("");
  }

  return (
    <div className="max-w-2xl">
      <h2 className="text-lg font-semibold text-ink mb-1">A few clarifying questions</h2>
      <p className="text-sm text-muted mb-4">Project: {description}</p>

      {qaHistory.map((qa, i) => (
        <div key={i} className="mb-3 text-sm">
          <p className="font-semibold text-ink">Q: {qa.q}</p>
          <p className="text-muted">A: {qa.a}</p>
        </div>
      ))}

      <div className="rounded-lg bg-func-bg text-func-fg text-sm px-3.5 py-2.5 mb-4">
        <span className="font-semibold">Question {qaHistory.length + 1}:</span> {currentQuestion}
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <input
          type="text"
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          placeholder="Your answer:"
          className="w-full rounded-lg border border-border px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent"
        />
        {error && (
          <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm px-3.5 py-2.5">
            {error}
          </div>
        )}
        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={loading}
            className="rounded-lg bg-accent hover:bg-accent-dark text-white font-medium px-5 py-2.5 text-sm transition-colors disabled:opacity-60"
          >
            {loading ? "Thinking..." : "Next"}
          </button>
          <button
            type="button"
            onClick={onSkip}
            disabled={loading}
            className="text-sm text-muted hover:text-ink underline disabled:opacity-60"
          >
            Generate now (skip remaining questions)
          </button>
        </div>
      </form>
      <p className="text-xs text-muted mt-3">
        {qaHistory.length + 1} of up to {MAX_QUESTIONS} questions
      </p>
    </div>
  );
}
