import { useState } from "react";

export default function DescribeStage({ onStart, loading, error }) {
  const [desc, setDesc] = useState("");

  function handleStart() {
    onStart(desc);
  }

  return (
    <div className="max-w-2xl">
      <h2 className="text-lg font-semibold text-ink mb-3">Describe your project</h2>
      <textarea
        value={desc}
        onChange={(e) => setDesc(e.target.value)}
        rows={6}
        placeholder="e.g. A clinic appointment system where patients book online."
        className="w-full rounded-lg border border-border px-3.5 py-2.5 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent"
      />
      {error && (
        <div className="mt-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm px-3.5 py-2.5">
          {error}
        </div>
      )}
      <button
        onClick={handleStart}
        disabled={loading}
        className="mt-3 rounded-lg bg-accent hover:bg-accent-dark text-white font-medium px-5 py-2.5 text-sm transition-colors disabled:opacity-60"
      >
        {loading ? "Thinking of the first question..." : "Start"}
      </button>
    </div>
  );
}
