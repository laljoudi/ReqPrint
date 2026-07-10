// App.jsx is the "brain" of the app: it holds all the state (what stage we're
// on, the data collected so far) and decides which screen to show. Each
// screen component below is "dumb" - it just displays props and calls the
// on... callbacks passed to it; App.jsx is the only place state changes.
import { useState } from "react";
import Header from "./components/Header";
import LoginScreen from "./components/LoginScreen";
import { DescribeStage, QuestionsStage } from "./components/Stages";
import ResultsStage from "./components/ResultsStage";
import { nextQuestion, generateRequirements, reviseRequirements, exportDocx } from "./lib/api";

const MAX_QUESTIONS = 5;

// The three-stage flow, and everything gathered along the way.
// stage moves describe -> questions -> results; "Start over" resets to this.
const emptyFlow = {
  stage: "describe",
  description: "",
  qaHistory: [],
  currentQuestion: null,
  data: null,
  refineHistory: [],
};

function App() {
  const [loggedIn, setLoggedIn] = useState(false);
  const [flow, setFlow] = useState(emptyFlow);

  const [describeLoading, setDescribeLoading] = useState(false);
  const [describeError, setDescribeError] = useState("");
  const [questionLoading, setQuestionLoading] = useState(false);
  const [questionError, setQuestionError] = useState("");
  const [downloading, setDownloading] = useState(false);
  const [refining, setRefining] = useState(false);
  const [refineError, setRefineError] = useState("");

  // Calls POST /generate and moves to the results stage.
  async function runGeneration(description, qaHistory) {
    const data = await generateRequirements(description, qaHistory);
    setFlow((f) => ({ ...f, stage: "results", data, refineHistory: [] }));
  }

  async function handleStart(desc) {
    if (!desc.trim()) {
      setDescribeError("Please enter a description first.");
      return;
    }
    setDescribeError("");
    setDescribeLoading(true);
    try {
      const result = await nextQuestion(desc, []);
      if (result.done) {
        await runGeneration(desc, []);
      } else {
        setFlow((f) => ({
          ...f,
          description: desc,
          qaHistory: [],
          currentQuestion: result.question,
          stage: "questions",
        }));
      }
    } catch (err) {
      setDescribeError(err.message);
    } finally {
      setDescribeLoading(false);
    }
  }

  async function handleAnswer(answer) {
    const newHistory = [...flow.qaHistory, { q: flow.currentQuestion, a: answer }];
    setFlow((f) => ({ ...f, qaHistory: newHistory }));
    setQuestionError("");
    setQuestionLoading(true);
    try {
      if (newHistory.length >= MAX_QUESTIONS) {
        await runGeneration(flow.description, newHistory);
      } else {
        const result = await nextQuestion(flow.description, newHistory);
        if (result.done) {
          await runGeneration(flow.description, newHistory);
        } else {
          setFlow((f) => ({ ...f, currentQuestion: result.question }));
        }
      }
    } catch (err) {
      setQuestionError(err.message);
    } finally {
      setQuestionLoading(false);
    }
  }

  async function handleSkip() {
    setQuestionError("");
    setQuestionLoading(true);
    try {
      await runGeneration(flow.description, flow.qaHistory);
    } catch (err) {
      setQuestionError(err.message);
    } finally {
      setQuestionLoading(false);
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
        refineHistory: [...f.refineHistory, instruction],
      }));
    } catch (err) {
      setRefineError(err.message);
    } finally {
      setRefining(false);
    }
  }

  function handleStartOver() {
    setFlow(emptyFlow);
    setDescribeError("");
    setQuestionError("");
    setRefineError("");
  }

  if (!loggedIn) {
    return <LoginScreen onLoggedIn={() => setLoggedIn(true)} />;
  }

  return (
    <div className="min-h-screen bg-white">
      <div className="max-w-5xl mx-auto px-6 py-8">
        <Header />

        {flow.stage === "describe" && (
          <DescribeStage onStart={handleStart} loading={describeLoading} error={describeError} />
        )}

        {flow.stage === "questions" && (
          <QuestionsStage
            description={flow.description}
            qaHistory={flow.qaHistory}
            currentQuestion={flow.currentQuestion}
            onAnswer={handleAnswer}
            onSkip={handleSkip}
            loading={questionLoading}
            error={questionError}
          />
        )}

        {flow.stage === "results" && flow.data && (
          <ResultsStage
            data={flow.data}
            onDownload={handleDownload}
            downloading={downloading}
            onStartOver={handleStartOver}
            onRefine={handleRefine}
            refineHistory={flow.refineHistory}
            refining={refining}
            refineError={refineError}
          />
        )}
      </div>
    </div>
  );
}

export default App;
