export default function RequirementsTab({ requirements }) {
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
