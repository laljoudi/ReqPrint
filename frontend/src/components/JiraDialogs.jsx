// The views inside the Push-to-Jira dialogs. Purely presentational: JiraPush.jsx
// owns the state and the flow, these just render what they're given.
import { useId } from "react";
import {
  DEFAULT_SPRINT_WEEKS,
  MAX_CAPACITY,
  MAX_START_DATE,
  MIN_CAPACITY,
  MIN_START_DATE,
  SPRINT_LENGTHS,
  formatFullDate,
  formatLocalDate,
  parseCapacity,
  parseISODate,
  previewParts,
  previewPlan,
  safeHttpUrl,
  validateForm,
} from "../lib/jiraPlan";

const button = "h-10 px-4 rounded-lg text-[13.5px] font-semibold transition-colors";
const secondaryButton = `${button} border border-border bg-panel text-muted hover:bg-surface disabled:opacity-60`;
const primaryButton = `${button} bg-accent text-on-accent hover:bg-accent-hover disabled:opacity-60 disabled:hover:bg-accent`;
const fieldInput =
  "w-full h-10 rounded-lg border border-border bg-input px-3 text-[14px] text-ink outline-none focus:border-accent focus:ring-1 focus:ring-accent disabled:opacity-60 transition";

// The four stages shown while a push runs.
const PUSH_STAGES = ["Creating project", "Ordering stories", "Creating sprints", "Adding stories"];

function Field({ id, label, hint, error, children }) {
  return (
    <div className="mb-4">
      <label htmlFor={id} className="block text-[13px] font-semibold text-ink mb-1.5">
        {label}
      </label>
      {children}
      {error ? (
        <p id={`${id}-note`} className="text-[12px] text-danger mt-1.5 m-0">
          {error}
        </p>
      ) : hint ? (
        <p id={`${id}-note`} className="text-[12px] text-muted mt-1.5 m-0">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

function Notice({ children, tone = "error" }) {
  const styles =
    tone === "error"
      ? "bg-danger-tint border-danger/30 text-danger"
      : "bg-surface border-border text-muted";
  return (
    <div role={tone === "error" ? "alert" : "note"} className={`rounded-lg border px-3.5 py-2.5 text-[13px] leading-relaxed ${styles}`}>
      {children}
    </div>
  );
}

// ---------- 1. not connected ----------

export function ConnectView({ connecting, error, onCancel, onConnect }) {
  return (
    <>
      <p className="text-[14px] leading-[1.6] text-muted m-0 mb-5">
        To push your user stories into Jira as sprints and tasks, ReqPrint needs access to your Jira account. You'll sign in
        with Atlassian and choose which site to use.
      </p>
      {connecting && (
        <p className="text-[13px] text-muted mt-0 mb-4">
          Finish signing in in the window that just opened. If you don't see it, check your browser's pop-up blocker.
        </p>
      )}
      {error && (
        <div className="mb-4">
          <Notice>{error}</Notice>
        </div>
      )}
      <div className="flex justify-end gap-2">
        <button type="button" onClick={onCancel} className={secondaryButton}>
          Cancel
        </button>
        <button type="button" onClick={onConnect} disabled={connecting} data-autofocus className={primaryButton}>
          {connecting ? "Waiting for sign-in..." : "Connect Jira"}
        </button>
      </div>
    </>
  );
}

// ---------- 2. the same document was pushed before ----------

export function DuplicateView({ record, onCancel, onProceed }) {
  const url = safeHttpUrl(record.project_url);
  return (
    <>
      <p className="text-[14px] leading-[1.6] text-muted m-0 mb-5">
        These requirements were pushed to project <strong className="text-ink">{record.project_key}</strong> on{" "}
        {formatLocalDate(new Date(record.pushed_at))}. Pushing again will create a new project with duplicate tasks.
      </p>
      <div className="flex flex-wrap justify-end gap-2">
        {url && (
          <a href={url} target="_blank" rel="noopener noreferrer" className={`${secondaryButton} inline-flex items-center`}>
            View previous project
          </a>
        )}
        <button type="button" onClick={onCancel} data-autofocus className={secondaryButton}>
          Cancel
        </button>
        <button type="button" onClick={onProceed} className={primaryButton}>
          Create new project anyway
        </button>
      </div>
    </>
  );
}

// ---------- 3. the push form (and progress, while it runs) ----------

function Progress({ stage }) {
  return (
    <div className="mb-4 rounded-lg border border-border bg-surface px-4 py-3" aria-live="polite">
      <ol className="list-none m-0 p-0 flex flex-col gap-1.5">
        {PUSH_STAGES.map((label, i) => (
          <li key={label} className={`flex items-center gap-2.5 text-[13.5px] ${i > stage ? "text-hint opacity-80" : i < stage ? "text-muted" : "text-ink font-semibold"}`}>
            <span className="w-4 flex-none flex justify-center">
              {i < stage ? (
                <span className="text-accent">✓</span>
              ) : i === stage ? (
                <span className="flex gap-0.5">
                  {[0, 0.15, 0.3].map((delay) => (
                    <span
                      key={delay}
                      className="w-1 h-1 rounded-full bg-accent"
                      style={{ animation: "rp-dot 1.1s infinite ease-in-out", animationDelay: `${delay}s` }}
                    />
                  ))}
                </span>
              ) : (
                <span>·</span>
              )}
            </span>
            {label}
          </li>
        ))}
      </ol>
      <p className="text-[12px] text-muted m-0 mt-2.5">This usually takes 20-40 seconds. Keep this window open.</p>
    </div>
  );
}

function PushError({ error, onReconnect }) {
  const needsReconnect = error.code === "reconnect_required" || error.code === "not_connected";
  const answered = error.code !== "network_error" && error.code !== "unreadable_response";
  const url = error.project?.created ? safeHttpUrl(error.project.url) : null;
  return (
    <div className="mb-4">
      <Notice>
        <p className="m-0 font-semibold">{error.message}</p>
        {error.jiraMessage && <p className="m-0 mt-1 text-[12.5px]">Jira said: {error.jiraMessage}</p>}
        {error.outcomeUnknown && answered && (
          <p className="m-0 mt-1 text-[12.5px]">The push may have partly finished. Check Jira before trying again.</p>
        )}
        {error.project?.created && (
          <p className="m-0 mt-1 text-[12.5px]">
            Jira had already created project <strong>{error.project.key}</strong> when this happened
            {url && (
              <>
                {" "}
                (
                <a href={url} target="_blank" rel="noopener noreferrer" className="underline">
                  open it
                </a>
                )
              </>
            )}
            . Change the project name, or delete that project in Jira, before trying again.
          </p>
        )}
        {needsReconnect && (
          <p className="m-0 mt-2">
            <button type="button" onClick={onReconnect} className="underline font-semibold">
              Reconnect Jira
            </button>
          </p>
        )}
      </Notice>
    </div>
  );
}

export function FormView({
  connected,
  siteName,
  values,
  onChange,
  totalStories,
  submitting,
  stage,
  error,
  disconnectError,
  onDisconnect,
  onReconnect,
  onCancel,
  onSubmit,
}) {
  const id = useId();
  const errors = validateForm({ name: values.name, startISO: values.startDate, capacityText: values.capacity, totalStories });
  const plan = previewPlan({
    totalStories,
    capacity: parseCapacity(values.capacity) ?? NaN,
    weeks: values.weeks,
    startISO: values.startDate,
  });

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
      noValidate
    >
      {connected ? (
        <p className="text-[12.5px] text-muted m-0 mb-4">
          Connected to <strong className="text-ink">{siteName || "your Jira site"}</strong>
          {" · "}
          <button type="button" onClick={onDisconnect} disabled={submitting} className="underline hover:text-ink disabled:opacity-60">
            Disconnect
          </button>
          {disconnectError && <span className="text-danger"> {disconnectError}</span>}
        </p>
      ) : (
        <p className="text-[12.5px] text-muted m-0 mb-4">Not connected to Jira.</p>
      )}

      <Field id={`${id}-name`} label="Project name" error={errors.name}>
        <input
          id={`${id}-name`}
          type="text"
          value={values.name}
          maxLength={80}
          disabled={submitting}
          data-autofocus
          aria-invalid={!!errors.name}
          aria-describedby={errors.name ? `${id}-name-note` : undefined}
          onChange={(event) => onChange("name", event.target.value)}
          className={fieldInput}
        />
      </Field>

      <div className="grid grid-cols-2 gap-3">
        <Field id={`${id}-start`} label="Start date" error={errors.startDate}>
          <input
            id={`${id}-start`}
            type="date"
            value={values.startDate}
            min={MIN_START_DATE}
            max={MAX_START_DATE}
            disabled={submitting}
            aria-invalid={!!errors.startDate}
            aria-describedby={errors.startDate ? `${id}-start-note` : undefined}
            onChange={(event) => onChange("startDate", event.target.value)}
            className={fieldInput}
          />
        </Field>
        <Field id={`${id}-weeks`} label="Sprint length">
          <select
            id={`${id}-weeks`}
            value={values.weeks}
            disabled={submitting}
            onChange={(event) => onChange("weeks", Number(event.target.value))}
            className={fieldInput}
          >
            {SPRINT_LENGTHS.map((weeks) => (
              <option key={weeks} value={weeks}>
                {weeks} {weeks === 1 ? "week" : "weeks"}
                {weeks === DEFAULT_SPRINT_WEEKS ? " (default)" : ""}
              </option>
            ))}
          </select>
        </Field>
      </div>

      <Field id={`${id}-capacity`} label="How many user stories can your team finish in a week?" error={errors.capacity}>
        <input
          id={`${id}-capacity`}
          type="number"
          inputMode="numeric"
          min={MIN_CAPACITY}
          max={MAX_CAPACITY}
          step={1}
          value={values.capacity}
          disabled={submitting}
          aria-invalid={!!errors.capacity}
          aria-describedby={errors.capacity ? `${id}-capacity-note` : undefined}
          onChange={(event) => onChange("capacity", event.target.value)}
          className={fieldInput}
        />
      </Field>

      <div className="mb-4">
        <label htmlFor={`${id}-subtasks`} className="flex items-center gap-2.5 text-[13px] font-semibold text-ink cursor-pointer">
          <input
            id={`${id}-subtasks`}
            type="checkbox"
            checked={values.subtasks}
            disabled={submitting}
            onChange={(event) => onChange("subtasks", event.target.checked)}
            className="h-4 w-4 flex-none accent-accent"
          />
          Break stories into sub-tasks
        </label>
        <p className="text-[12px] text-muted mt-1.5 ml-[26px] m-0">
          Each story gets a few sub-tasks drawn from its acceptance criteria. They follow the story into its sprint, so capacity still counts stories.
        </p>
      </div>

      <div className="mb-4 rounded-lg border border-border bg-surface px-4 py-2.5 text-[13.5px] font-semibold text-ink" aria-live="polite">
        {errors.stories ? (
          <span className="font-normal text-danger">{errors.stories}</span>
        ) : plan ? (
          // Each part stays on one line, so a narrow screen breaks between them ("... 2 sprints ·" / "7 Nov → 5 Dec"), never inside a date.
          previewParts(plan).map((part, i, all) => (
            <span key={part}>
              <span className="whitespace-nowrap">{i < all.length - 1 ? `${part} ·` : part}</span>
              {i < all.length - 1 && " "}
            </span>
          ))
        ) : (
          "Fill in the fields above to see the plan."
        )}
      </div>

      {submitting && <Progress stage={stage} />}
      {error && !submitting && <PushError error={error} onReconnect={onReconnect} />}

      <div className="flex justify-end gap-2">
        <button type="button" onClick={onCancel} disabled={submitting} className={secondaryButton}>
          Cancel
        </button>
        <button type="submit" disabled={submitting || Object.keys(errors).length > 0} className={primaryButton}>
          {submitting ? "Pushing..." : "Push to Jira"}
        </button>
      </div>
    </form>
  );
}

// ---------- 4. the result ----------

// Why sub-tasks were left out of a push that otherwise went through. result.subtasks_skipped is a
// list: one entry with story_id null and one of these reasons when ALL sub-tasks were skipped, and one
// "criterion_citation" entry per story whose sub-tasks were dropped for not tying back to a criterion.
const SUBTASKS_SKIPPED = {
  no_subtask_type: "This Jira project has no sub-task issue type, so the stories were created without sub-tasks.",
  ai_unavailable: "The AI service wasn't available to plan sub-tasks, so the stories were created without them.",
  invalid_ai_output: "The AI's sub-task plan didn't pass validation, so the stories were created without sub-tasks.",
};

// How one sub-task's source reads in the audit list.
function sourceText(row) {
  if (row.source === "criterion") {
    const scenario = row.criterion_scenario ? `: ${truncate(String(row.criterion_scenario), 70)}` : "";
    return `criterion ${row.criterion_index}${scenario}`;
  }
  return "the story text (this story has no acceptance criteria)";
}

const truncate = (text, n) => (text.length > n ? `${text.slice(0, n - 1).trimEnd()}…` : text);

export function ResultView({ result, stories, onClose }) {
  const url = safeHttpUrl(result.project_url);
  const failed = Array.isArray(result.failed) ? result.failed : [];
  const labelsFailed = Array.isArray(result.labels_failed) ? result.labels_failed : [];
  const datesFailed = (Array.isArray(result.sprints) ? result.sprints : []).filter((s) => s.dates_error);
  const storyText = (id) => stories.find((s) => s.id === id)?.story;
  const start = parseISODate(result.start_date);
  const when = start ? formatFullDate(new Date(Date.UTC(start.y, start.m - 1, start.d))) : null;
  const created = result.stories_created ?? 0;
  const sprints = result.sprint_count ?? 0;
  const subtasksCreated = result.subtasks_created ?? 0;
  const subtasksFailed = Array.isArray(result.subtasks_failed) ? result.subtasks_failed : [];
  const skipped = Array.isArray(result.subtasks_skipped) ? result.subtasks_skipped : [];
  const subtasksSkipped = SUBTASKS_SKIPPED[skipped.find((x) => x && !x.story_id)?.reason] || null;
  const droppedStories = skipped.filter((x) => x && x.story_id && x.reason === "criterion_citation");
  const subtaskRows = Array.isArray(result.subtask_details) ? result.subtask_details.filter((r) => r.created) : [];

  return (
    <>
      <p className="text-[14px] leading-[1.6] text-ink m-0 mb-1">
        Your tasks are in project <strong>{result.project_key}</strong>.
      </p>
      <p className="text-[13.5px] leading-[1.6] text-muted m-0 mb-4">
        {created} {created === 1 ? "story" : "stories"} created
        {result.subtasks_requested && subtasksCreated > 0 ? ` · ${subtasksCreated} ${subtasksCreated === 1 ? "sub-task" : "sub-tasks"}` : ""}
        {" · "}{sprints} {sprints === 1 ? "sprint" : "sprints"}
        {when && result.sprint_length_weeks ? ` of ${result.sprint_length_weeks} ${result.sprint_length_weeks === 1 ? "week" : "weeks"}, starting ${when}` : ""}
      </p>

      {failed.length > 0 && (
        <div className="mb-4">
          <Notice>
            <p className="m-0 font-semibold">
              {failed.length} {failed.length === 1 ? "story" : "stories"} had a problem:
            </p>
            <ul className="m-0 mt-1.5 pl-4 max-h-40 overflow-y-auto text-[12.5px] leading-relaxed">
              {failed.map((f, i) => (
                <li key={`${f.story_id}-${i}`}>
                  <strong>{f.story_id}</strong>
                  {storyText(f.story_id) ? ` - ${truncate(storyText(f.story_id), 90)}` : ""}
                  <br />
                  <span>{truncate(String(f.reason || "No reason given."), 220)}</span>
                </li>
              ))}
            </ul>
          </Notice>
        </div>
      )}

      {subtasksFailed.length > 0 && (
        <div className="mb-4">
          <Notice>
            <p className="m-0 font-semibold">
              {subtasksFailed.length} {subtasksFailed.length === 1 ? "sub-task" : "sub-tasks"} couldn't be created. The stories are fine.
            </p>
            <ul className="m-0 mt-1.5 pl-4 max-h-40 overflow-y-auto text-[12.5px] leading-relaxed">
              {subtasksFailed.map((f, i) => (
                <li key={`${f.story_id}-${i}`}>
                  <strong>{f.story_id}</strong> - {truncate(String(f.title || ""), 90)}
                  <br />
                  <span>{truncate(String(f.reason || "No reason given."), 220)}</span>
                </li>
              ))}
            </ul>
          </Notice>
        </div>
      )}
      {subtasksSkipped && (
        <div className="mb-3">
          <Notice tone="note">{subtasksSkipped}</Notice>
        </div>
      )}
      {droppedStories.length > 0 && (
        <div className="mb-3">
          <Notice tone="note">
            No sub-tasks were created for {droppedStories.map((x) => x.story_id).join(", ")}: most of what the AI proposed there
            didn't match any of the story's acceptance criteria, so it was thrown away rather than made up. The{" "}
            {droppedStories.length === 1 ? "story itself is" : "stories themselves are"} fine.
          </Notice>
        </div>
      )}
      {subtaskRows.length > 0 && (
        <details className="mb-4 text-[12.5px] text-muted">
          <summary className="cursor-pointer">Where each sub-task came from</summary>
          <ul className="m-0 mt-1.5 pl-4 max-h-40 overflow-y-auto leading-relaxed">
            {subtaskRows.map((r, i) => (
              <li key={`${r.key || r.story_id}-${i}`}>
                <strong>{r.key || r.story_id}</strong> - {truncate(String(r.title || ""), 80)}
                <br />
                <span className="opacity-80">from {sourceText(r)}</span>
              </li>
            ))}
          </ul>
        </details>
      )}

      {labelsFailed.length > 0 && (
        <div className="mb-3">
          <Notice tone="note">
            Labels couldn't be added to {labelsFailed.length} {labelsFailed.length === 1 ? "issue" : "issues"} - Jira wouldn't accept
            them there. Everything else was created normally.
          </Notice>
        </div>
      )}
      {datesFailed.length > 0 && (
        <div className="mb-3">
          <Notice tone="note">
            Dates couldn't be set on {datesFailed.length} {datesFailed.length === 1 ? "sprint" : "sprints"} (
            {datesFailed.map((s) => s.name).join(", ")}). They were created without dates, with their stories in them. You can set
            the dates in Jira.
          </Notice>
        </div>
      )}

      <p className="text-[12.5px] text-muted m-0 mb-5">Invite your team from Jira → Project settings → People.</p>

      <div className="flex justify-end gap-2">
        <button type="button" onClick={onClose} className={secondaryButton}>
          Close
        </button>
        {url && (
          <a href={url} target="_blank" rel="noopener noreferrer" className={`${primaryButton} inline-flex items-center`}>
            Open in Jira
          </a>
        )}
      </div>
    </>
  );
}
