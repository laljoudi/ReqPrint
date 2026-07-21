// App.jsx is the "brain" of the app: it holds all the state (what stage
// we're on, the data collected so far) and decides which screen to show.
// Each screen component below is "dumb" - it just displays props and calls
// the on... callbacks passed to it; App.jsx is the only place state changes.
import { useState } from "react";
import WelcomeScreen from "./components/WelcomeScreen";
import ChatStage from "./components/ChatStage";
import DocumentStage from "./components/DocumentStage";
import { nextQuestion, generateRequirements, reviseRequirements, exportDocx } from "./lib/api";

const MAX_QUESTIONS = 8;

// The three-stage flow, and everything gathered along the way.
// stage moves welcome -> chat -> document; "Start over" resets to this.
const emptyFlow = {
  stage: "welcome",
  description: "",
  qaHistory: [],
  currentQuestion: null,
  readyToGenerate: false,
  data: null,
  refineHistory: [],
};

function App() {
  const [flow, setFlow] = useState(emptyFlow);

  const [chatLoading, setChatLoading] = useState(false);
  const [chatError, setChatError] = useState("");
  const [downloading, setDownloading] = useState(false);
  const [refining, setRefining] = useState(false);
  const [refineError, setRefineError] = useState("");

  // First message in the chat: the project description. Calls POST /api/next-question.
  async function handleDescribe(desc) {
    setChatError("");
    setChatLoading(true);
    try {
      const result = await nextQuestion(desc, []);
      setFlow((f) => ({
        ...f,
        description: desc,
        qaHistory: [],
        currentQuestion: result.done ? null : result.question,
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
        setFlow((f) => ({ ...f, currentQuestion: null, readyToGenerate: true }));
      } else {
        const result = await nextQuestion(flow.description, newHistory);
        setFlow((f) => ({
          ...f,
          currentQuestion: result.done ? null : result.question,
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
      setFlow((f) => ({ ...f, stage: "document", data, refineHistory: [], readyToGenerate: false }));
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
        refineHistory: [...f.refineHistory, instruction],
      }));
    } catch (err) {
      setRefineError(err.message);
    } finally {
      setRefining(false);
    }
  }

  function handleBackToChat() {
    setFlow((f) => ({ ...f, stage: "chat", readyToGenerate: true }));
  }

  function handleStartOver() {
    setFlow(emptyFlow);
    setChatError("");
    setRefineError("");
  }

  if (flow.stage === "welcome") {
    return <WelcomeScreen onStart={() => setFlow((f) => ({ ...f, stage: "chat" }))} />;
  }

  if (flow.stage === "chat") {
    return (
      <ChatStage
        description={flow.description}
        qaHistory={flow.qaHistory}
        currentQuestion={flow.currentQuestion}
        readyToGenerate={flow.readyToGenerate}
        onDescribe={handleDescribe}
        onAnswer={handleAnswer}
        onGenerate={handleGenerate}
        loading={chatLoading}
        error={chatError}
      />
    );
  }

  if (flow.stage === "document" && flow.data) {
    return (
      <DocumentStage
        data={flow.data}
        onDownload={handleDownload}
        downloading={downloading}
        onStartOver={handleStartOver}
        onBackToChat={handleBackToChat}
        onRefine={handleRefine}
        refineHistory={flow.refineHistory}
        refining={refining}
        refineError={refineError}
      />
    );
  }

  return null;
}

export default App;
