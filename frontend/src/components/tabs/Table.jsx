export default function Table({ columns, rows }) {
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
