import { useState } from "react";
import { RequirementsTab, UserStoriesTab, Table, AssumptionsTab } from "./ResultTabs";
import RefinePanel from "./RefinePanel";

const AC_COLUMNS = [
  { key: "story_id", label: "Story" },
  { key: "scenario", label: "Scenario" },
  { key: "given", label: "Given" },
  { key: "when", label: "When" },
  { key: "then", label: "Then" },
];

const UC_COLUMNS = [
  { key: "use_case_id", label: "ID" },
  { key: "actors", label: "Actors" },
  { key: "description", label: "Description" },
  { key: "preconditions", label: "Preconditions" },
  { key: "trigger", label: "Trigger" },
  { key: "main_flow", label: "Main flow" },
  { key: "alternative_flow", label: "Alternative flow" },
];

// Stage 3: the final requirements document. Shows 5 tabs (built from ResultTabs.jsx),
// a Word download button, a "start over" button, and the refine sidebar.
export default function ResultsStage({
  data,
  onDownload,
  downloading,
  onStartOver,
  onRefine,
  refineHistory,
  refining,
  refineError,
}) {
  const useCases = data.use_cases || [];
  const assumptions = data.assumptions || [];

  const counts = {
    req: data.requirements.functional.length + data.requirements.non_functional.length,
    us: data.user_stories.length,
    ac: data.acceptance_criteria.length,
    uc: useCases.length,
    as: assumptions.length,
  };

  const tabs = [
    { key: "requirements", label: `Requirements (${counts.req})` },
    { key: "stories", label: `User Stories (${counts.us})` },
    { key: "acceptance", label: `Acceptance Criteria (${counts.ac})` },
    { key: "usecases", label: `Use Cases (${counts.uc})` },
    { key: "assumptions", label: `Assumptions (${counts.as})` },
  ];
  const [activeTab, setActiveTab] = useState("requirements");

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-8">
      <div>
        <div className="flex flex-wrap gap-1 border-b border-border mb-5">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setActiveTab(t.key)}
              className={`px-3.5 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
                activeTab === t.key
                  ? "border-accent text-accent"
                  : "border-transparent text-muted hover:text-ink"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="mb-6">
          {activeTab === "requirements" && <RequirementsTab requirements={data.requirements} />}
          {activeTab === "stories" && <UserStoriesTab userStories={data.user_stories} />}
          {activeTab === "acceptance" && (
            <Table columns={AC_COLUMNS} rows={data.acceptance_criteria} />
          )}
          {activeTab === "usecases" && <Table columns={UC_COLUMNS} rows={useCases} />}
          {activeTab === "assumptions" && <AssumptionsTab assumptions={assumptions} />}
        </div>

        <div className="flex items-center gap-4">
          <button
            onClick={onDownload}
            disabled={downloading}
            className="rounded-lg bg-accent hover:bg-accent-dark text-white font-medium px-5 py-2.5 text-sm transition-colors disabled:opacity-60"
          >
            {downloading ? "Preparing..." : "Download as Word"}
          </button>
          <button
            onClick={onStartOver}
            className="rounded-lg border border-border text-ink hover:bg-gray-50 font-medium px-5 py-2.5 text-sm transition-colors"
          >
            Start over
          </button>
        </div>
      </div>

      <div>
        <RefinePanel
          history={refineHistory}
          onRefine={onRefine}
          loading={refining}
          error={refineError}
        />
      </div>
    </div>
  );
}
