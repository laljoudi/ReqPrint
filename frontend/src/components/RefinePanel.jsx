import { useState } from "react";

export default function RefinePanel({ history, onRefine, loading, error }) {
  const [instruction, setInstruction] = useState("");

  function handleSubmit(e) {
    e.preventDefault();
    if (!instruction.trim()) return;
    onRefine(instruction);
    setInstruction("");
  }

  return (
    <div className="rounded-xl border border-border bg-gray-50 p-4">
      <h3 className="font-semibold text-ink text-sm mb-1">Refine</h3>
      <p className="text-xs text-muted mb-3">Ask for a change and the output updates.</p>

      {history.length > 0 && (
        <ul className="space-y-1 mb-3 text-xs text-muted list-disc list-inside">
          {history.map((h, i) => (
            <li key={i}>{h}</li>
          ))}
        </ul>
      )}

      <form onSubmit={handleSubmit} className="flex flex-col gap-2">
        <input
          type="text"
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          placeholder="e.g. Add a user story for admins"
          className="w-full rounded-lg border border-border px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent"
        />
        {error && (
          <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 text-xs px-3 py-2">
            {error}
          </div>
        )}
        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-accent hover:bg-accent-dark text-white font-medium py-2 text-sm transition-colors disabled:opacity-60"
        >
          {loading ? "Updating..." : "Send"}
        </button>
      </form>
    </div>
  );
}
