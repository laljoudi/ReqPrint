// The numbered sections shown stacked in the results side of WorkspaceScreen.
// Each section owns its own numbered heading + anchor id (unused now that the
// TOC sidebar is gone, but harmless to keep for in-page anchor links).

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
    <div className="bg-panel border border-border rounded-[14px] px-5 py-1.5">
      {items.map((text, i) => (
        <div
          key={i}
          className={`flex gap-3.5 py-3.5 items-start ${i > 0 ? "border-t border-border" : ""}`}
        >
          <span
            className="flex-none font-mono text-[11.5px] font-bold rounded px-2 py-0.5 mt-px"
            style={{ color: chipColor, background: `${chipColor}14` }}
          >
            {`${prefix}-${i + 1}`}
          </span>
          <span className="flex-1 text-sm leading-relaxed text-ink">{text}</span>
        </div>
      ))}
    </div>
  );
}

export function RequirementsSection({ requirements }) {
  return (
    <section id="sec-1" className="mb-12">
      <SectionHeading num="1" title="Requirements" />
      <h3 className="font-display font-bold text-[15px] text-ink mb-1 mt-6">
        1.1 &nbsp;Functional
      </h3>
      <RequirementList items={requirements.functional} prefix="FR" chipColor="#7A1F2B" />

      <h3 className="font-display font-bold text-[15px] text-ink mb-1 mt-7">
        1.2 &nbsp;Non-functional
      </h3>
      <RequirementList items={requirements.non_functional} prefix="NF" chipColor="#5A1620" />
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
            className="bg-panel border border-border rounded-[14px] px-4.5 py-4 flex flex-col gap-2.5"
          >
            <span className="font-mono text-xs font-bold text-accent bg-accent/8 px-2.5 py-0.5 rounded-md w-fit">
              {s.id}
            </span>
            <p className="m-0 text-sm leading-relaxed text-ink">{s.story}</p>
            <span className="text-[11px] font-bold tracking-wide uppercase text-hint">
              {s.role}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}

function EmptyNotice({ children }) {
  return (
    <div className="rounded-[14px] bg-surface border border-border text-sm text-muted px-4 py-3">
      {children}
    </div>
  );
}

function DocTable({ columns, rows }) {
  if (!rows.length) {
    return <EmptyNotice>No data available.</EmptyNotice>;
  }
  return (
    <div className="bg-panel border border-border rounded-[14px] overflow-hidden overflow-x-auto">
      <table className="w-full text-left border-collapse min-w-[600px]">
        <thead>
          <tr className="bg-surface">
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
            <tr key={i} className="border-t border-border align-top">
              {columns.map((c) => (
                <td key={c.key} className="px-4 py-3.5 text-[13px] leading-relaxed text-ink">
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
            <div key={i} className="bg-panel border border-border rounded-[14px] overflow-hidden">
              <div className="px-4 py-2.5 bg-surface">
                <span className="font-mono text-xs font-bold text-accent">{uc.use_case_id}</span>
              </div>
              <table className="w-full border-collapse">
                <tbody>
                  {UC_FIELDS.map((f) => (
                    <tr key={f.key} className="border-t border-border align-top">
                      <td className="px-4 py-3 text-[11px] font-bold tracking-wide uppercase text-muted w-[140px] whitespace-nowrap">
                        {f.label}
                      </td>
                      <td className="px-4 py-3 text-[13px] leading-relaxed text-ink">
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
        <EmptyNotice>No data available.</EmptyNotice>
      )}
    </section>
  );
}

export function AssumptionsSection({ assumptions }) {
  return (
    <section id="sec-5" className="mb-12">
      <SectionHeading num="5" title="Assumptions" />
      <p className="text-[13px] text-hint mb-4">
        Details not stated in the description that ReqPrint inferred to complete the analysis.
      </p>
      {assumptions.length ? (
        <div
          className="rounded-[14px] px-5 py-1.5"
          style={{
            background: "rgba(122,31,43,0.035)",
            border: "1px solid rgba(122,31,43,0.20)",
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
              <span className="text-sm leading-relaxed text-ink">{text}</span>
            </div>
          ))}
        </div>
      ) : (
        <EmptyNotice>No additional assumptions were made.</EmptyNotice>
      )}
    </section>
  );
}

// Three severity levels, all mapped onto the warm palette instead of the
// conventional red/amber/blue - darker burgundy reads as more severe, and
// Dusty Rose gets its one deliberate, sparing use here for "low".
const SEVERITY_STYLES = {
  high: "bg-accent-dark/10 text-accent-dark border-accent-dark/30",
  medium: "bg-accent/10 text-accent border-accent/30",
  low: "bg-rose/15 text-ink border-rose/40",
};

export function ReviewSection({ issues, loading, error }) {
  return (
    <section id="sec-6" className="mb-5">
      <SectionHeading num="6" title="Review" />
      <p className="text-[13px] text-hint mb-4">
        Feedback from Business Analyst, Developer, and QA perspectives before export.
      </p>

      {error && (
        <div className="mb-4 rounded-lg bg-accent-dark/8 border border-accent-dark/25 text-accent-dark text-sm px-3.5 py-2.5">
          {error}
        </div>
      )}

      {loading && !issues.length && (
        <div className="bg-panel border border-border rounded-[14px] px-5 py-4 text-sm text-ink">
          Reviewing requirements...
        </div>
      )}

      {!loading && !error && !issues.length && (
        <div className="bg-panel border border-border rounded-[14px] px-5 py-4 text-sm text-ink">
          Run a review to check this SRS for ambiguity, gaps, risks, and testability issues.
        </div>
      )}

      {!!issues.length && (
        <div className="flex flex-col gap-3.5">
          {issues.map((item, i) => {
            const severity = String(item.severity || "").toLowerCase();
            const severityClass = SEVERITY_STYLES[severity] || SEVERITY_STYLES.medium;
            return (
              <div key={i} className="bg-panel border border-border rounded-[14px] overflow-hidden">
                <div className="px-4 py-3 bg-surface flex flex-wrap items-center gap-2.5">
                  <span className="font-display font-bold text-[13px] text-ink">
                    {item.role}
                  </span>
                  <span
                    className={`border rounded px-2 py-0.5 text-[11px] font-bold uppercase ${severityClass}`}
                  >
                    {severity || "medium"}
                  </span>
                </div>
                <div className="px-4 py-4">
                  <h3 className="m-0 mb-3 font-display font-bold text-[15px] text-ink">
                    {item.issue}
                  </h3>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                    <div>
                      <div className="text-[11px] font-bold tracking-wide uppercase text-hint mb-1">
                        Why it matters
                      </div>
                      <p className="m-0 text-[13px] leading-relaxed text-ink">
                        {item.why_it_matters}
                      </p>
                    </div>
                    <div>
                      <div className="text-[11px] font-bold tracking-wide uppercase text-hint mb-1">
                        Suggested fix
                      </div>
                      <p className="m-0 text-[13px] leading-relaxed text-ink">
                        {item.suggested_fix}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
