// The right-hand sidebar on the Document stage. Same behavior as before
// (history of sent instructions, onRefine(text) calls POST /api/revise) -
// only the look changed, to the mockup's chat-thread style. Unlike the
// mockup, this does NOT show a fake assistant reply after each edit - our
// backend doesn't produce one, and inventing text that looks like AI output
// would be misleading.
import { useState } from "react";

const SUGGESTIONS = ["Add security requirements", "Split stories by role", "Add offline support"];

export default function RefinePanel({ history, onRefine, loading, error }) {
  const [instruction, setInstruction] = useState("");

  function send(text) {
    const t = text.trim();
    if (!t) return;
    onRefine(t);
    setInstruction("");
  }

  function handleSubmit(e) {
    e.preventDefault();
    send(instruction);
  }

  return (
    <aside className="w-full lg:w-[320px] flex-none border border-border rounded-[14px] bg-white flex flex-col min-h-0 max-h-[calc(100vh-140px)] lg:sticky lg:top-24">
      <div className="px-5 pt-4.5 pb-4 border-b border-border flex items-center gap-2.5">
        <span className="w-7 h-7 rounded-lg bg-accent/10 text-accent flex items-center justify-center flex-none">
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.85"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M12 20h9"></path>
            <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"></path>
          </svg>
        </span>
        <div>
          <h2 className="font-display font-bold text-[15px] m-0 tracking-tight">Refine</h2>
          <p className="m-0 mt-0.5 text-[11.5px] text-hint">
            Ask for a change and the document updates
          </p>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-4.5 py-4.5 flex flex-col gap-3">
        <div className="max-w-[88%] bg-bubble text-[#4A4A4A] px-3.5 py-2.5 rounded-[14px_14px_14px_4px] text-[13.3px] leading-normal">
          This document was generated from your conversation. Ask me here to add, remove, or
          rephrase anything.
        </div>
        {history.map((h, i) => (
          <div key={i} className="flex justify-end">
            <div className="max-w-[82%] bg-accent text-white px-3.5 py-2.5 rounded-[14px_14px_4px_14px] text-[13.3px] leading-normal">
              {h}
            </div>
          </div>
        ))}
      </div>

      <div className="border-t border-border px-4 pt-3 pb-4">
        {error && (
          <div className="mb-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-xs px-3 py-2">
            {error}
          </div>
        )}
        <div className="flex flex-wrap gap-1.5 mb-3">
          {SUGGESTIONS.map((label) => (
            <button
              key={label}
              onClick={() => send(label)}
              disabled={loading}
              className="border border-border bg-[#F5F2F7] text-[#565656] text-xs font-medium px-2.5 py-1.5 rounded-full hover:bg-accent/8 hover:border-accent/30 disabled:opacity-60 transition-colors"
            >
              {label}
            </button>
          ))}
        </div>
        <form
          onSubmit={handleSubmit}
          className="flex items-end gap-2 border border-border rounded-[13px] px-3.5 py-1.5 bg-white focus-within:border-accent focus-within:shadow-[0_0_0_4px_rgba(186,85,211,0.12)] transition"
        >
          <input
            type="text"
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            placeholder="Ask ReqPrint to refine..."
            className="flex-1 border-none outline-none text-[13.5px] bg-transparent h-8"
          />
          <button
            type="submit"
            disabled={loading}
            className="flex-none w-[34px] h-[34px] rounded-[9px] bg-accent hover:brightness-105 text-white flex items-center justify-center disabled:opacity-60 transition"
          >
            <svg
              width="16"
              height="16"
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
        <div className="mt-1.5 text-[11px] text-hint">
          {loading ? "Updating..." : "Enter to send"}
        </div>
      </div>
    </aside>
  );
}
