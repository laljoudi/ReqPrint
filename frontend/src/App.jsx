// App.jsx is the "brain" of the app: it holds all the state (what stage
// we're on, the data collected so far) and decides which screen to show.
// Each screen component below is "dumb" - it just displays props and calls
// the on... callbacks passed to it; App.jsx is the only place state changes.
import { useEffect, useRef, useState } from "react";
import JiraNotice from "./components/JiraNotice";
import WelcomeScreen from "./components/WelcomeScreen";
import WorkspaceScreen from "./components/WorkspaceScreen";
import {
  nextQuestion,
  generateRequirements,
  reviseRequirements,
  reviewRequirements,
  extractFromNotes,
  exportDocx,
  getJiraStatus,
  jiraLogout,
  pushToJira,
  JIRA_LOGIN_URL,
} from "./lib/api";
import { startJiraConnect } from "./lib/jiraConnect";
import { hashDocument } from "./lib/jiraPlan";
import { clearPushStarted, hasUnfinishedPush, markPushStarted, savePushRecord } from "./lib/jiraStorage";

const MAX_QUESTIONS = 8;

// The two-stage flow, and everything gathered along the way.
// stage moves welcome -> workspace; "Start over" resets to this. Within
// "workspace", the interview and results share one screen - "data" existing
// (not a stage change) is what switches the main content area from
// placeholder to results and the conversation panel from Q&A to refine.
const emptyFlow = {
  stage: "welcome",
  description: "",
  qaHistory: [],
  currentQuestion: null,
  currentSuggestions: [],
  readyToGenerate: false,
  data: null,
  review: null,
  refineHistory: [],
};

// Turns raw input + its extracted open_questions into one description string
// for the interview (next_question / NEXT_QUESTION_PROMPT are untouched - this
// just gives them richer context to start from instead of a blank slate, so
// the interview naturally asks about these gaps first). For a clean
// description, extraction naturally yields no open_questions, so this is a
// no-op and the description passes through unchanged.
function seedDescriptionFromNotes(rawInput, openQuestions) {
  if (!openQuestions.length) return rawInput;
  const list = openQuestions.map((q) => `- ${q}`).join("\n");
  return `${rawInput}\n\nOpen questions identified from this input - please prioritize asking about these:\n${list}`;
}

// Folds the category the user picked into the input text itself, rather than
// threading it as a separate parameter through /api/extract-notes and every
// /api/next-question call - this way it's just part of `description`, which
// is already reused for the whole conversation (every question) and the
// final generation, with zero backend/schema changes needed.
function prependCategory(rawInput, category) {
  return `Project category: ${category}\n\n${rawInput}`;
}

// Whether this browser has a Jira connection. "unknown" until the check on load
// answers (or if it couldn't). The refresh token itself lives in an HttpOnly
// cookie this page can't read - only the site's name and URL come back.
const jiraUnknown = { status: "unknown", siteName: "", siteUrl: "" };
const jiraDisconnected = { status: "disconnected", siteName: "", siteUrl: "" };

function App() {
  const [flow, setFlow] = useState(emptyFlow);

  const [chatLoading, setChatLoading] = useState(false);
  const [chatError, setChatError] = useState("");
  const [downloading, setDownloading] = useState(false);
  const [refining, setRefining] = useState(false);
  const [refineError, setRefineError] = useState("");
  const [reviewing, setReviewing] = useState(false);
  const [reviewError, setReviewError] = useState("");
  const [jiraConn, setJiraConn] = useState(jiraUnknown);
  // A push that started in an earlier visit and never reported back (read once, on load).
  const [unfinishedPush, setUnfinishedPush] = useState(() => hasUnfinishedPush());

  // Ask the backend once, on load, whether Jira is connected. (The ref keeps React's
  // development double-run of effects from asking twice.)
  const askedJiraStatus = useRef(false);
  useEffect(() => {
    if (askedJiraStatus.current) return;
    askedJiraStatus.current = true;
    handleJiraRefresh();
  }, []);

  // The single first-turn entry point, for whatever the user typed or pasted -
  // a clean description or messy notes, it doesn't matter which. Always runs
  // it through POST /api/extract-notes first, then feeds the (possibly
  // seeded) result into the same POST /api/next-question call every
  // subsequent turn uses - the interview itself doesn't know or care how the
  // description was arrived at.
  async function handleStart(rawInput, category) {
    setChatError("");
    setChatLoading(true);
    try {
      const categorizedInput = prependCategory(rawInput, category);
      const extraction = await extractFromNotes(categorizedInput);
      const seeded = seedDescriptionFromNotes(categorizedInput, extraction.open_questions);
      const result = await nextQuestion(seeded, []);
      setFlow((f) => ({
        ...f,
        description: seeded,
        qaHistory: [],
        currentQuestion: result.done ? null : result.question,
        currentSuggestions: result.suggested_answers || [],
        readyToGenerate: !!result.done,
      }));
    } catch (err) {
      setChatError(err.message);
    } finally {
      setChatLoading(false);
    }
  }

  // Answering the current question. Calls POST /api/next-question with the updated history.
  async function handleAnswer(answer) {
    const newHistory = [...flow.qaHistory, { q: flow.currentQuestion, a: answer }];
    setFlow((f) => ({ ...f, qaHistory: newHistory }));
    setChatError("");
    setChatLoading(true);
    try {
      if (newHistory.length >= MAX_QUESTIONS) {
        setFlow((f) => ({ ...f, currentQuestion: null, currentSuggestions: [], readyToGenerate: true }));
      } else {
        const result = await nextQuestion(flow.description, newHistory);
        setFlow((f) => ({
          ...f,
          currentQuestion: result.done ? null : result.question,
          currentSuggestions: result.suggested_answers || [],
          readyToGenerate: !!result.done,
        }));
      }
    } catch (err) {
      setChatError(err.message);
    } finally {
      setChatLoading(false);
    }
  }

  // "Generate requirements document" / "skip remaining questions". Calls POST /api/generate.
  async function handleGenerate() {
    setChatError("");
    setChatLoading(true);
    try {
      const data = await generateRequirements(flow.description, flow.qaHistory);
      setFlow((f) => ({
        ...f,
        data,
        review: null,
        refineHistory: [],
        readyToGenerate: false,
      }));
    } catch (err) {
      setChatError(err.message);
    } finally {
      setChatLoading(false);
    }
  }

  async function handleDownload() {
    setDownloading(true);
    try {
      const blob = await exportDocx(flow.data);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "requirements.docx";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setRefineError(err.message);
    } finally {
      setDownloading(false);
    }
  }

  async function handleRefine(instruction) {
    setRefineError("");
    setRefining(true);
    try {
      const data = await reviseRequirements(flow.data, instruction);
      setFlow((f) => ({
        ...f,
        data,
        review: null,
        refineHistory: [...f.refineHistory, instruction],
      }));
    } catch (err) {
      setRefineError(err.message);
    } finally {
      setRefining(false);
    }
  }

  async function handleReview() {
    setReviewError("");
    setReviewing(true);
    try {
      const review = await reviewRequirements(flow.description, flow.qaHistory, flow.data);
      setFlow((f) => ({ ...f, review }));
    } catch (err) {
      setReviewError(err.message);
    } finally {
      setReviewing(false);
    }
  }

  // Calls GET /api/jira/status. Returns "connected", "disconnected" or "unknown".
  async function handleJiraRefresh() {
    try {
      const s = await getJiraStatus();
      setJiraConn(s.connected ? { status: "connected", siteName: s.siteName, siteUrl: s.siteUrl } : jiraDisconnected);
      return s.connected ? "connected" : "disconnected";
    } catch {
      return "unknown";
    }
  }

  // Opens the Atlassian sign-in popup. Returns { done, cancel }: `done` settles when the
  // user has finished (or failed, or given up), `cancel` closes the popup.
  function handleJiraConnect() {
    const attempt = startJiraConnect(JIRA_LOGIN_URL);
    const done = attempt.promise
      .catch(async (err) => {
        // A popup closed with no message may still have connected (the message can be lost).
        if (err?.code === "popup_closed" && (await handleJiraRefresh()) === "connected") return;
        throw err;
      })
      .then(handleJiraRefresh);
    return { done, cancel: attempt.cancel };
  }

  // Calls POST /api/jira/logout.
  async function handleJiraDisconnect() {
    await jiraLogout();
    setJiraConn(jiraDisconnected);
  }

  // Calls POST /api/jira/push - 20-40 seconds. A "push started" marker is kept in
  // localStorage until we know how it went, so a push cut off by closing the tab is
  // flagged on the next load. If the answer never came back readable (connection lost,
  // gateway timeout) the push may have partly run, so the marker stays.
  async function handleJiraPush(params) {
    markPushStarted();
    try {
      const result = await pushToJira(params);
      clearPushStarted();
      savePushRecord(hashDocument(params.requirements), {
        projectKey: result.project_key,
        projectUrl: result.project_url,
        storyCount: result.stories_created,
      });
      return result;
    } catch (err) {
      if (!err.outcomeUnknown) clearPushStarted();
      if (err.code === "reconnect_required" || err.code === "not_connected") setJiraConn(jiraDisconnected);
      throw err;
    }
  }

  function handleStartOver() {
    setFlow(emptyFlow);
    setChatError("");
    setRefineError("");
    setReviewError("");
  }

  const notice = unfinishedPush && (
    <JiraNotice
      onDismiss={() => {
        clearPushStarted();
        setUnfinishedPush(false);
      }}
    />
  );

  if (flow.stage === "welcome") {
    return (
      <>
        {notice}
        <WelcomeScreen onStart={() => setFlow((f) => ({ ...f, stage: "workspace" }))} />
      </>
    );
  }

  if (flow.stage === "workspace") {
    return (
      <>
        {notice}
        <WorkspaceScreen
          description={flow.description}
          qaHistory={flow.qaHistory}
          currentQuestion={flow.currentQuestion}
          currentSuggestions={flow.currentSuggestions}
          readyToGenerate={flow.readyToGenerate}
          onStart={handleStart}
          onAnswer={handleAnswer}
          onGenerate={handleGenerate}
          loading={chatLoading}
          error={chatError}
          data={flow.data}
          onDownload={handleDownload}
          downloading={downloading}
          onStartOver={handleStartOver}
          onRefine={handleRefine}
          refineHistory={flow.refineHistory}
          refining={refining}
          refineError={refineError}
          review={flow.review}
          onReview={handleReview}
          reviewing={reviewing}
          reviewError={reviewError}
          jira={{
            status: jiraConn.status,
            siteName: jiraConn.siteName,
            onRefresh: handleJiraRefresh,
            onConnect: handleJiraConnect,
            onDisconnect: handleJiraDisconnect,
            onPush: handleJiraPush,
          }}
        />
      </>
    );
  }

  return null;
}

export default App;
