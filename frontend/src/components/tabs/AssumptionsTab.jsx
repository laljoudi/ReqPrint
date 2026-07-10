export default function AssumptionsTab({ assumptions }) {
  if (!assumptions.length) {
    return (
      <div className="rounded-lg bg-blue-50 text-sm text-blue-800 px-3.5 py-2.5">
        No additional assumptions were made.
      </div>
    );
  }
  return (
    <div>
      <p className="text-xs text-muted mb-2">
        Information the AI added or inferred (not explicitly stated):
      </p>
      <div className="rounded-lg bg-amber-50 border border-amber-200 text-amber-900 text-sm px-4 py-3">
        <ul className="space-y-1.5 list-disc list-inside">
          {assumptions.map((a, i) => (
            <li key={i}>{a}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
