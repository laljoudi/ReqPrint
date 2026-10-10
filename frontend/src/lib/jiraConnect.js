// Connecting to Jira happens in a POPUP, never in this tab: the generated
// document lives in page state and a full-page redirect to Atlassian would lose
// it. The backend's callback page (jira_oauth.finish_popup) tells this window how
// it went with window.opener.postMessage({type: "jira-connected"} or
// {type: "jira-error", reason}), then closes itself.

export class JiraConnectError extends Error {
  constructor(code) {
    super(connectErrorMessage(code));
    this.name = "JiraConnectError";
    this.code = code;
  }
}

// Messages for the reasons the backend can send back (jira_oauth.py), plus the
// three that happen on this side of the popup.
const MESSAGES = {
  popup_blocked: "Your browser blocked the sign-in window. Allow pop-ups for this site, then click Connect Jira again.",
  popup_closed: "The sign-in window was closed before it finished. Click Connect Jira to try again.",
  access_denied: "Access wasn't granted, so ReqPrint couldn't connect to Jira. Click Connect Jira to try again.",
  state_mismatch: "That sign-in session expired or didn't match. Please try again.",
  token_exchange_failed: "Atlassian wouldn't complete the sign-in. Please try again.",
  site_lookup_failed: "Atlassian signed you in, but ReqPrint couldn't read your Jira sites. Please try again.",
  no_jira_site: "That Atlassian account has no Jira site ReqPrint can use.",
  network_error: "Couldn't reach Atlassian. Check your connection and try again.",
  invalid_scope: "Atlassian rejected the permissions ReqPrint asked for. This is a setup problem on ReqPrint's side.",
  unauthorized_client: "Atlassian doesn't recognise this ReqPrint app. This is a setup problem on ReqPrint's side.",
};

export function connectErrorMessage(code) {
  return MESSAGES[code] || "Couldn't connect to Jira. Please try again.";
}

// Opens the sign-in popup. Returns { promise, cancel }: the promise resolves when
// the callback reports success and rejects with a JiraConnectError for everything
// else - a blocked popup, a window closed early, an error from Atlassian, or
// cancel(). It settles at most once and always removes its listeners.
export function startJiraConnect(loginUrl) {
  let settle = () => {};
  let popup = null;
  const promise = new Promise((resolve, reject) => {
    const width = 560;
    const height = 760;
    const left = Math.max(0, Math.round(window.screenX + (window.outerWidth - width) / 2));
    const top = Math.max(0, Math.round(window.screenY + (window.outerHeight - height) / 2));
    popup = window.open(loginUrl, "reqprint-jira", `popup=yes,width=${width},height=${height},left=${left},top=${top}`);
    if (!popup) {
      reject(new JiraConnectError("popup_blocked"));
      return;
    }

    let done = false;
    let timer = null;
    const cleanup = () => {
      window.removeEventListener("message", onMessage);
      clearInterval(timer);
    };
    settle = (error) => {
      if (done) return;
      done = true;
      cleanup();
      if (error) reject(error);
      else resolve();
    };

    // Trust only messages from the window we opened: its origin can differ from
    // this page's (dev server vs. backend), but no other window is our popup.
    function onMessage(event) {
      if (event.source !== popup) return;
      const message = event.data;
      if (!message || typeof message !== "object") return;
      if (message.type === "jira-connected") settle();
      else if (message.type === "jira-error") {
        settle(new JiraConnectError(typeof message.reason === "string" ? message.reason : "unknown_error"));
      }
    }
    window.addEventListener("message", onMessage);

    // The popup closing is the only sign of "user gave up" - but a successful
    // popup closes itself too, right after posting its message. So give a late
    // message a moment before calling it an early close.
    timer = setInterval(() => {
      if (!popup.closed) return;
      clearInterval(timer);
      setTimeout(() => settle(new JiraConnectError("popup_closed")), 700);
    }, 400);
  });

  return {
    promise,
    cancel() {
      settle(new JiraConnectError("cancelled"));
      try {
        popup?.close();
      } catch {
        /* already gone */
      }
    },
  };
}
