// The four "content" pieces shown inside the Results tabs (see ResultsStage.jsx).
// Grouped in one file since each is small and they're only ever used together.

export function RequirementsTab({ requirements }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
      <div>
        <span className="inline-block rounded-md bg-func-bg text-func-fg text-sm font-semibold px-3 py-1 mb-3">
          Functional
        </span>
        <ul className="space-y-1.5 text-sm text-ink list-disc list-inside">
          {requirements.functional.map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      </div>
      <div>
        <span className="inline-block rounded-md bg-nonfunc-bg text-nonfunc-fg text-sm font-semibold px-3 py-1 mb-3">
          Non-functional
        </span>
        <ul className="space-y-1.5 text-sm text-ink list-disc list-inside">
          {requirements.non_functional.map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export function UserStoriesTab({ userStories }) {
  return (
    <div className="space-y-3">
      {userStories.map((s, i) => (
        <div key={i} className="rounded-xl bg-story-bg border border-story-border px-4.5 py-3.5">
          <span className="text-story-id font-semibold text-sm">
            {s.id} - {s.role}
          </span>
          <p className="text-sm text-ink mt-1">{s.story}</p>
        </div>
      ))}
    </div>
  );
}

// Generic table used by both the Acceptance Criteria and Use Cases tabs.
export function Table({ columns, rows }) {
  if (!rows.length) {
    return (
      <div className="rounded-lg bg-blue-50 text-sm text-blue-800 px-3.5 py-2.5">
        No data available.
      </div>
    );
  }
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full text-sm text-left">
        <thead className="bg-gray-50 text-ink">
          <tr>
            {columns.map((c) => (
              <th key={c.key} className="px-3.5 py-2.5 font-semibold whitespace-nowrap">
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-t border-border align-top">
              {columns.map((c) => (
                <td key={c.key} className="px-3.5 py-2.5 text-muted">
                  {row[c.key] ?? ""}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function AssumptionsTab({ assumptions }) {
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
