import { useEffect, useMemo, useState } from "react";

import { AgentEvent, EvidenceItem, HighlightedRange, RunStatus, SourceFile } from "./api/events";
import { readSourceFile, searchProjectFiles, startRun, subscribeRunEvents } from "./api/client";
import { AnswerPanel } from "./components/answer/AnswerPanel";
import { ChatPanel } from "./components/chat/ChatPanel";
import { CodeEditor } from "./components/code/CodeEditor";
import { EvidencePanel } from "./components/evidence/EvidencePanel";
import { FileExplorer } from "./components/files/FileExplorer";
import { WorkbenchShell } from "./components/layout/WorkbenchShell";
import { StatusBar } from "./components/status/StatusBar";
import { AgentTimeline } from "./components/timeline/AgentTimeline";
import { CallGraph } from "./components/CallGraph";

export function App() {
  const [question, setQuestion] = useState("Explain this project");
  const [answer, setAnswer] = useState("");
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [status, setStatus] = useState<RunStatus>("idle");
  const [runId, setRunId] = useState("");
  const [history, setHistory] = useState<string[]>([]);
  const [files, setFiles] = useState<string[]>([]);
  const [fileQuery, setFileQuery] = useState("");
  const [openFilePaths, setOpenFilePaths] = useState<string[]>([]);
  const [activeFile, setActiveFile] = useState<SourceFile | null>(null);
  const [highlightedRange, setHighlightedRange] = useState<HighlightedRange | undefined>();

  const visibleFiles = useMemo(() => files.slice(0, 200), [files]);

  useEffect(() => {
    refreshFiles("");
  }, []);

  async function openFile(path: string, range?: HighlightedRange) {
    const lineOffset = range?.startLine && range.startLine > 900 ? Math.max(1, range.startLine - 50) : 1;
    const file = await readSourceFile(path, lineOffset);
    setActiveFile(file);
    setOpenFilePaths((current) => (current.includes(path) ? current : [...current, path]));
    if (range) {
      setHighlightedRange(range);
    }
  }

  async function run() {
    setEvents([]);
    setAnswer("");
    setStatus("running");
    setHistory((current) => [question, ...current.filter((item) => item !== question)].slice(0, 8));
    const nextRunId = await startRun(question);
    setRunId(nextRunId);
    subscribeRunEvents(
      nextRunId,
      (parsed) => {
      setEvents((current) => [...current, parsed]);
      if (parsed.type === "answer_final") {
        setAnswer(String(parsed.payload.answer || ""));
      }
      if (parsed.type === "file_opened") {
        openFile(String(parsed.payload.path));
      }
        if (parsed.type === "line_range_read") {
          const range = {
            path: String(parsed.payload.path ?? ""),
            startLine: Number(parsed.payload.start_line ?? 1),
            endLine: Number(parsed.payload.end_line ?? parsed.payload.start_line ?? 1),
          };
          setHighlightedRange(range);
          if (range.path) openFile(range.path, range);
        }
        if (parsed.type === "run_error") {
          setStatus("failed");
        }
      },
      () => setStatus((current) => (current === "failed" ? "failed" : "finished")),
      () => setStatus("failed"),
    );
  }

  async function refreshFiles(query = fileQuery) {
    setFiles(await searchProjectFiles(query));
  }

  async function updateFileQuery(query: string) {
    setFileQuery(query);
    await refreshFiles(query);
  }

  function openEvidence(evidence: EvidenceItem) {
        openFile(evidence.path, evidence.startLine ? {
      path: evidence.path,
      startLine: evidence.startLine,
      endLine: evidence.endLine ?? evidence.startLine,
    } : undefined);
  }

  return (
    <WorkbenchShell
      title="agentCli"
      repoLabel="source-reading workbench"
      modelLabel="deepseek-v4-pro"
      status={status}
      sidebar={
        <>
          <ChatPanel
            question={question}
            status={status}
            history={history}
            onQuestionChange={setQuestion}
            onRun={run}
          />
          <FileExplorer files={visibleFiles} query={fileQuery} onQueryChange={updateFileQuery} onOpen={openFile} />
        </>
      }
      editor={
        <CodeEditor
          openFiles={openFilePaths}
          activeFile={activeFile}
          highlightedRange={highlightedRange}
          onSelectFile={openFile}
        />
      }
      inspector={
        <div className="tabsPane">
          <AgentTimeline events={events} />
          <EvidencePanel events={events} onOpenEvidence={openEvidence} />
          <CallGraph events={events} />
          <AnswerPanel answer={answer} />
        </div>
      }
      statusbar={<StatusBar status={status} eventCount={events.length} fileCount={openFilePaths.length} runId={runId} />}
    />
  );
}
