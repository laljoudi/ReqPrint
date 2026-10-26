// DEV ONLY - loaded by main.jsx only when import.meta.env.DEV is true, so it is not part of a
// production build.
//
//   ?preview=document  the document screen, rendered from the fixture, review already filled in
//   ?preview=errors    the same screen three times, each with a different inline error / limit banner
//
// It renders WorkspaceScreen directly instead of App, so none of App's effects (the Jira status
// check on load) run, and every callback WorkspaceScreen could use to reach the backend is replaced
// by one that only shows a "preview mode" notice. As a second line of defence, fetch,
// XMLHttpRequest, sendBeacon and window.open are replaced for as long as this is mounted: anything
// that still tries is refused and counted in the badge at the bottom left (it should stay at 0).
import { useCallback, useEffect, useState } from "react";
import WorkspaceScreen from "../components/WorkspaceScreen";
import { friendlyMessage } from "../lib/api";
import { FIXTURE_MARKER, PREVIEW_DATA, PREVIEW_DESCRIPTION, PREVIEW_QA, PREVIEW_REVIEW } from "./previewFixture";

// The messages are the app's own (api.js), so a change there shows up here.
const ERROR_VARIANTS = [
  { label: "429 usage limit", message: friendlyMessage(429, null) },
  { label: "503 service busy", message: friendlyMessage(503, "quota_exhausted") },
  { label: "generic error", message: friendlyMessage(500, null) },
];

function useNetworkBlock(onBlocked) {
  useEffect(() => {
    const real = {
      fetch: window.fetch,
      open: window.open,
      xhrOpen: XMLHttpRequest.prototype.open,
      beacon: navigator.sendBeacon,
    };
    const refuse = (what) => {
      console.warn(`[preview] blocked ${what}: preview mode makes no network requests`);
      onBlocked();
    };
    window.fetch = (input) => {
      refuse(`fetch ${String(input?.url ?? input)}`);
      return Promise.reject(new TypeError("Network requests are disabled in preview mode"));
    };
    window.open = () => {
      refuse("window.open");
      return null;
    };
    XMLHttpRequest.prototype.open = function blocked() {
      refuse("XMLHttpRequest");
      throw new Error("Network requests are disabled in preview mode");
    };
    navigator.sendBeacon = () => {
      refuse("sendBeacon");
      return false;
    };
    return () => {
      window.fetch = real.fetch;
      window.open = real.open;
      XMLHttpRequest.prototype.open = real.xhrOpen;
      navigator.sendBeacon = real.beacon;
    };
  }, [onBlocked]);
}

export default function Preview({ mode }) {
  const [notice, setNotice] = useState("");
  const [blocked, setBlocked] = useState(0);
  const countBlocked = useCallback(() => setBlocked((n) => n + 1), []);
  useNetworkBlock(countBlocked);

  useEffect(() => {
    if (!notice) return undefined;
    const t = setTimeout(() => setNotice(""), 3200);
    return () => clearTimeout(t);
  }, [notice]);

  const say = (what) => setNotice(`Preview mode: "${what}" is switched off here. Nothing was sent.`);
  const off = (what) => () => say(what);

  // Push to Jira keeps its own dialogs and handlers, so it is stopped at the click, before they run.
  function guardClicks(event) {
    const button = event.target instanceof Element ? event.target.closest("button") : null;
    if (button && /push to jira/i.test(button.textContent || "")) {
      event.preventDefault();
      event.stopPropagation();
      say("Push to Jira");
    }
  }

  const jira = {
    status: "disconnected",
    siteName: "",
    onRefresh: async () => "disconnected",
    onConnect: () => ({ done: new Promise(() => {}), cancel() {} }),
    onDisconnect: async () => {},
    onPush: async () => {
      throw new Error("Preview mode");
    },
  };

  function screen(extra = {}) {
    return (
      <WorkspaceScreen
        description={PREVIEW_DESCRIPTION}
        qaHistory={PREVIEW_QA}
        currentQuestion={null}
        currentSuggestions={[]}
        readyToGenerate={false}
        onStart={off("Start")}
        onAnswer={off("Answer")}
        onGenerate={off("Generate")}
        loading={false}
        error=""
        data={PREVIEW_DATA}
        onDownload={off("Download")}
        downloading={false}
        onStartOver={off("Start over")}
        onRefine={off("Refine")}
        refineHistory={[]}
        refining={false}
        refineError=""
        review={PREVIEW_REVIEW}
        onReview={off("Review")}
        reviewing={false}
        reviewError=""
        jira={jira}
        {...extra}
      />
    );
  }

  return (
    <div onClickCapture={guardClicks}>
      {mode === "errors" ? (
        ERROR_VARIANTS.map((v) => (
          <div key={v.label}>
            <div className="px-5 py-2 text-[12.5px] font-semibold text-ink bg-surface border-b border-border">
              Error variant: {v.label}
            </div>
            {screen({ refineError: v.message, reviewError: v.message, review: null })}
          </div>
        ))
      ) : (
        screen()
      )}

      <div className="fixed left-3 bottom-3 z-50 rounded-lg border border-border bg-panel px-3 py-2 text-[11.5px] leading-snug text-muted">
        Preview: {mode} · fixture {FIXTURE_MARKER} · network calls blocked: {blocked}
      </div>
      {notice && (
        <div
          role="status"
          className="fixed left-1/2 -translate-x-1/2 bottom-14 z-50 max-w-[calc(100%-2rem)] rounded-[14px] border border-border bg-panel px-4 py-3 text-[13.5px] text-ink"
        >
          {notice}
        </div>
      )}
    </div>
  );
}
