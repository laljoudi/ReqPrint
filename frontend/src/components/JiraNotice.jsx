// A dismissible banner for a Jira push that was cut off - the tab was closed or the
// connection dropped before an answer came back - so Jira may hold a half-built
// project. Shown on whichever screen the app loads into.
export default function JiraNotice({ onDismiss }) {
  return (
    <div
      role="alert"
      className="fixed top-3 left-1/2 -translate-x-1/2 z-40 w-[calc(100%-2rem)] max-w-xl flex items-start gap-3 rounded-[14px] border border-danger/30 bg-panel px-4 py-3 text-[13.5px] leading-relaxed text-ink"
    >
      <p className="flex-1 m-0">Your last push to Jira didn't finish. Check Jira before trying again.</p>
      <button type="button" onClick={onDismiss} className="flex-none text-[12.5px] font-semibold text-muted underline hover:text-ink">
        Dismiss
      </button>
    </div>
  );
}
