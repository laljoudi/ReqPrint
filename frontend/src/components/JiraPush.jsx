// "Push to Jira": the button beside the other document actions, and the dialogs
// it opens. Flow:
//   click -> not connected -> "Connect your Jira account" (sign-in in a popup)
//                  |                          | on success, straight to...
//   connected  ----+-> already pushed? -> "Already pushed to Jira" -> ...
//                  +-> the push dialog (form + live plan preview)
//                        -> staged progress -> result (or an error, in place)
// The network calls and everything stored in localStorage live in App.jsx and
// come in through `jira`; this component only holds what the dialogs show.
import { useEffect, useRef, useState } from "react";
import { ConnectView, DuplicateView, FormView, ResultView } from "./JiraDialogs";
import Modal from "./Modal";
import { connectErrorMessage } from "../lib/jiraConnect";
import { getPushRecord } from "../lib/jiraStorage";
import {
  DEFAULT_CAPACITY,
  DEFAULT_SPRINT_WEEKS,
  hashDocument,
  parseCapacity,
  suggestProjectName,
  todayLocalISO,
  validateForm,
} from "../lib/jiraPlan";

// The push is one request with no progress events, so the stages are an honest
// estimate by time: they advance while we wait, and the last one holds until the
// answer arrives.
const STAGE_DELAYS_MS = [5000, 5000, 6000];

const TITLES = {
  connect: "Connect your Jira account",
  duplicate: "Already pushed to Jira",
  form: "Push to Jira",
};

export default function JiraPush({ data, description, category, jira, buttonClassName }) {
  const [step, setStep] = useState("closed"); // closed | connect | duplicate | form | result
  const [checking, setChecking] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [connectError, setConnectError] = useState("");
  const [previous, setPrevious] = useState(null);
  const [form, setForm] = useState({ name: "", startDate: "", weeks: DEFAULT_SPRINT_WEEKS, capacity: String(DEFAULT_CAPACITY), subtasks: true });
  const [submitting, setSubmitting] = useState(false);
  const [stage, setStage] = useState(0);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [disconnectError, setDisconnectError] = useState("");
  const connectAttempt = useRef(null);
  const reconnecting = useRef(false); // signing in again from the form: come back to it afterwards

  const stories = data.user_stories || [];

  // Staged progress while a push is in flight.
  useEffect(() => {
    if (!submitting) return undefined;
    let elapsed = 0;
    const timers = STAGE_DELAYS_MS.map((delay, i) => {
      elapsed += delay;
      return setTimeout(() => setStage(i + 1), elapsed);
    });
    return () => timers.forEach(clearTimeout);
  }, [submitting]);

  // Leaving while the sign-in popup is open closes it.
  useEffect(() => () => connectAttempt.current?.cancel(), []);

  function openFreshForm() {
    setForm({
      name: suggestProjectName(description),
      startDate: todayLocalISO(),
      weeks: DEFAULT_SPRINT_WEEKS,
      capacity: String(DEFAULT_CAPACITY),
      subtasks: true,
    });
    setError(null);
    setResult(null);
    setDisconnectError("");
    const record = getPushRecord(hashDocument(data));
    setPrevious(record);
    setStep(record ? "duplicate" : "form");
  }

  async function handleOpen() {
    if (checking) return;
    let status = jira.status;
    if (status === "unknown") {
      // The check on page load didn't give an answer; ask again before bothering the user.
      setChecking(true);
      status = await jira.onRefresh();
      setChecking(false);
    }
    if (status === "connected") {
      openFreshForm();
    } else {
      reconnecting.current = false;
      setConnectError("");
      setConnecting(false);
      setStep("connect");
    }
  }

  async function handleConnect() {
    if (connecting) return;
    setConnecting(true);
    setConnectError("");
    const attempt = jira.onConnect();
    connectAttempt.current = attempt;
    try {
      await attempt.done;
    } catch (err) {
      connectAttempt.current = null;
      setConnecting(false);
      if (err?.code !== "cancelled") setConnectError(err?.message || connectErrorMessage(err?.code));
      return;
    }
    connectAttempt.current = null;
    setConnecting(false);
    if (reconnecting.current) {
      reconnecting.current = false;
      setError(null);
      setStep("form");
    } else {
      openFreshForm(); // connected: straight to the push dialog (or the duplicate warning)
    }
  }

  function handleCancelConnect() {
    connectAttempt.current?.cancel();
    setConnecting(false);
    setStep(reconnecting.current ? "form" : "closed");
    reconnecting.current = false;
  }

  function handleReconnect() {
    reconnecting.current = true;
    setConnectError("");
    setStep("connect");
  }

  async function handleDisconnect() {
    setDisconnectError("");
    try {
      await jira.onDisconnect();
      setStep("closed");
    } catch {
      setDisconnectError("Couldn't disconnect. Please try again.");
    }
  }

  async function handleSubmit() {
    if (submitting) return;
    const problems = validateForm({
      name: form.name,
      startISO: form.startDate,
      capacityText: form.capacity,
      totalStories: stories.length,
    });
    if (Object.keys(problems).length) return;
    setError(null);
    setStage(0);
    setSubmitting(true);
    try {
      const pushed = await jira.onPush({
        projectName: form.name.trim(),
        capacityPerWeek: parseCapacity(form.capacity),
        sprintLengthWeeks: form.weeks,
        startDate: form.startDate,
        category,
        subtasks: form.subtasks,
        requirements: data,
      });
      setResult(pushed);
      setStep("result");
    } catch (err) {
      setError(err);
    } finally {
      setSubmitting(false);
    }
  }

  const close = () => setStep("closed");

  return (
    <>
      <button type="button" onClick={handleOpen} disabled={checking} className={buttonClassName}>
        Push to Jira
      </button>

      {step === "connect" && (
        <Modal title={TITLES.connect} onClose={handleCancelConnect}>
          <ConnectView connecting={connecting} error={connectError} onCancel={handleCancelConnect} onConnect={handleConnect} />
        </Modal>
      )}

      {step === "duplicate" && previous && (
        <Modal title={TITLES.duplicate} onClose={close}>
          <DuplicateView record={previous} onCancel={close} onProceed={() => setStep("form")} />
        </Modal>
      )}

      {step === "form" && (
        <Modal title={TITLES.form} onClose={close} closable={!submitting} wide>
          <FormView
            connected={jira.status === "connected"}
            siteName={jira.siteName}
            values={form}
            onChange={(field, value) => setForm((f) => ({ ...f, [field]: value }))}
            totalStories={stories.length}
            submitting={submitting}
            stage={stage}
            error={error}
            disconnectError={disconnectError}
            onDisconnect={handleDisconnect}
            onReconnect={handleReconnect}
            onCancel={close}
            onSubmit={handleSubmit}
          />
        </Modal>
      )}

      {step === "result" && result && (
        <Modal title={result.failed?.length || result.subtasks_failed?.length ? "Pushed to Jira, with some problems" : "Pushed to Jira"} onClose={close}>
          <ResultView result={result} stories={stories} onClose={close} />
        </Modal>
      )}
    </>
  );
}
