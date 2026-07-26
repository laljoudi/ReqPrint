// The 5 numbered sections shown stacked on the Document stage (see
// DocumentStage.jsx). Each section owns its own numbered heading + anchor id
// so the TOC sidebar can link straight to it.

function SectionHeading({ num, title }) {
  return (
    <div className="flex items-baseline gap-3 mb-3">
      <span className="font-display font-extrabold text-[15px] text-accent">{num}.</span>
      <h2 className="font-display font-bold text-[22px] tracking-tight text-ink m-0">{title}</h2>
    </div>
  );
}

const AC_COLUMNS = [
  { key: "story_id", label: "Story" },
  { key: "scenario", label: "Scenario" },
  { key: "given", label: "Given" },
  { key: "when", label: "When" },
  { key: "then", label: "Then" },
];

const UC_FIELDS = [
  { key: "actors", label: "Actors" },
  { key: "description", label: "Description" },
  { key: "preconditions", label: "Preconditions" },
  { key: "trigger", label: "Trigger" },
  { key: "main_flow", label: "Main flow" },
  { key: "alternative_flow", label: "Alternative flow" },
];

function RequirementList({ items, prefix, chipColor }) {
  return (
    <div className="bg-white border border-border rounded-[14px] px-5 py-1.5">
      {items.map((text, i) => (
        <div
          key={i}
          className={`flex gap-3.5 py-3.5 items-start ${i > 0 ? "border-t border-[#F0EAF5]" : ""}`}
        >
          <span
            className="flex-none font-mono text-[11.5px] font-bold rounded px-2 py-0.5 mt-px"
            style={{ color: chipColor, background: `${chipColor}14` }}
          >
            {`${prefix}-${i + 1}`}
          </span>
          <span className="flex-1 text-sm leading-relaxed text-[#4A4A4A]">{text}</span>
        </div>
      ))}
    </div>
  );
}

export function RequirementsSection({ requirements }) {
  return (
    <section id="sec-1" className="mb-12">
      <SectionHeading num="1" title="Requirements" />
      <h3 className="font-display font-bold text-[15px] text-[#3A3A3A] mb-1 mt-6">
        1.1 &nbsp;Functional
      </h3>
      <RequirementList items={requirements.functional} prefix="FR" chipColor="#BA55D3" />

      <h3 className="font-display font-bold text-[15px] text-[#3A3A3A] mb-1 mt-7">
        1.2 &nbsp;Non-functional
      </h3>
      <RequirementList items={requirements.non_functional} prefix="NF" chipColor="#8E44AD" />
    </section>
  );
}

export function UserStoriesSection({ userStories }) {
  return (
    <section id="sec-2" className="mb-12">
      <SectionHeading num="2" title="User Stories" />
      <p className="text-[13px] text-hint mb-4">
        Feature intent expressed from each user role's perspective.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
        {userStories.map((s, i) => (
          <div
            key={i}
            className="bg-white border border-border rounded-[14px] px-4.5 py-4 flex flex-col gap-2.5"
          >
            <span className="font-mono text-xs font-bold text-accent bg-accent/8 px-2.5 py-0.5 rounded-md w-fit">
              {s.id}
            </span>
            <p className="m-0 text-sm leading-relaxed text-[#3A3A3A]">{s.story}</p>
            <span className="text-[11px] font-bold tracking-wide uppercase text-hint">
              {s.role}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}

function DocTable({ columns, rows }) {
  if (!rows.length) {
    return (
      <div className="rounded-[14px] bg-blue-50 text-sm text-blue-800 px-4 py-3">
        No data available.
      </div>
    );
  }
  return (
    <div className="bg-white border border-border rounded-[14px] overflow-hidden overflow-x-auto">
      <table className="w-full text-left border-collapse min-w-[600px]">
        <thead>
          <tr className="bg-[#F5F1F7]">
            {columns.map((c) => (
              <th
                key={c.key}
                className="text-left px-4 py-3 text-[11px] font-bold tracking-wide uppercase text-muted whitespace-nowrap"
              >
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-t border-[#EDEAF0] align-top">
              {columns.map((c) => (
                <td key={c.key} className="px-4 py-3.5 text-[13px] leading-relaxed text-[#4A4A4A]">
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

export function AcceptanceCriteriaSection({ criteria }) {
  return (
    <section id="sec-3" className="mb-12">
      <SectionHeading num="3" title="Acceptance Criteria" />
      <p className="text-[13px] text-hint mb-4">
        Given / When / Then conditions that define done.
      </p>
      <DocTable columns={AC_COLUMNS} rows={criteria} />
    </section>
  );
}

export function UseCasesSection({ useCases }) {
  return (
    <section id="sec-4" className="mb-12">
      <SectionHeading num="4" title="Use Cases" />
      <p className="text-[13px] text-hint mb-4">
        End-to-end interactions between actors and the system.
      </p>
      {useCases.length ? (
        <div className="flex flex-col gap-4">
          {useCases.map((uc, i) => (
            <div key={i} className="bg-white border border-border rounded-[14px] overflow-hidden">
              <div className="px-4 py-2.5 bg-[#F5F1F7]">
                <span className="font-mono text-xs font-bold text-accent">{uc.use_case_id}</span>
              </div>
              <table className="w-full border-collapse">
                <tbody>
                  {UC_FIELDS.map((f) => (
                    <tr key={f.key} className="border-t border-[#EDEAF0] align-top">
                      <td className="px-4 py-3 text-[11px] font-bold tracking-wide uppercase text-muted w-[140px] whitespace-nowrap">
                        {f.label}
                      </td>
                      <td className="px-4 py-3 text-[13px] leading-relaxed text-[#4A4A4A]">
                        {uc[f.key] ?? ""}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-[14px] bg-blue-50 text-sm text-blue-800 px-4 py-3">
          No data available.
        </div>
      )}
    </section>
  );
}

export function AssumptionsSection({ assumptions }) {
  return (
    <section id="sec-5" className="mb-5">
      <SectionHeading num="5" title="Assumptions" />
      <p className="text-[13px] text-hint mb-4">
        Details not stated in the description that ReqPrint inferred to complete the analysis.
      </p>
      {assumptions.length ? (
        <div
          className="rounded-[14px] px-5 py-1.5"
          style={{
            background: "linear-gradient(180deg, rgba(186,85,211,0.05), rgba(186,85,211,0.015))",
            border: "1px solid rgba(186,85,211,0.20)",
          }}
        >
          {assumptions.map((text, i) => (
            <div
              key={i}
              className={`flex gap-3 py-3.5 ${i > 0 ? "border-t border-accent/12" : ""}`}
            >
              <span className="flex-none font-mono text-[11.5px] font-bold text-accent pt-px">
                {`A-${String(i + 1).padStart(2, "0")}`}
              </span>
              <span className="text-sm leading-relaxed text-[#4A4A4A]">{text}</span>
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-[14px] bg-blue-50 text-sm text-blue-800 px-4 py-3">
          No additional assumptions were made.
        </div>
      )}
    </section>
  );
}
