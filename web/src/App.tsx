import { useEffect, useMemo, useRef, useState } from "react";

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
import { WalkthroughPanel } from "./components/tour/WalkthroughPanel";
import { NextReadBar } from "./components/tour/NextReadBar";
import { TourData } from "./components/tour/types";

type InspectorTab = "analysis" | "tour";

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
  const [tour, setTour] = useState<TourData | null>(null);
  const [tourLoading, setTourLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<InspectorTab>("analysis");
  const eventSourceRef = useRef<EventSource | null>(null);

  const visibleFiles = useMemo(() => files.slice(0, 200), [files]);

  useEffect(() => {
    refreshFiles("");
    return () => {
      eventSourceRef.current?.close();
    };
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

  function openFileByKeyLines(path: string, keyLines?: string) {
    let range: HighlightedRange | undefined;
    if (keyLines) {
      const parts = keyLines.split("-");
      const start = parseInt(parts[0], 10);
      const end = parts[1] ? parseInt(parts[1], 10) : start;
      if (!isNaN(start)) {
        range = { path, startLine: start, endLine: isNaN(end) ? start : end };
      }
    }
    openFile(path, range);
  }

  function closeFile(path: string) {
    setOpenFilePaths((current) => {
      const next = current.filter((p) => p !== path);
      if (activeFile?.path === path) {
        const nextActive = next.length > 0 ? next[next.length - 1] : null;
        if (nextActive) openFile(nextActive);
        else setActiveFile(null);
      }
      return next;
    });
  }

  async function startTour() {
    setTourLoading(true);
    setTour(null);
    setActiveTab("tour");
    try {
      const resp = await fetch("/api/tour", { method: "POST" });
      const data: TourData = await resp.json();
      setTour(data);
      if (data.steps.length > 0) {
        openFileByKeyLines(data.steps[0].file, data.steps[0].key_lines);
      }
    } catch {
      // tour failed silently
    } finally {
      setTourLoading(false);
    }
  }

  async function run() {
    setEvents([]);
    setAnswer("");
    setStatus("running");
    setActiveTab("analysis");
    setHistory((current) => [question, ...current.filter((item) => item !== question)].slice(0, 8));
    const nextRunId = await startRun(question);
    setRunId(nextRunId);
    const es = subscribeRunEvents(
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
    eventSourceRef.current = es;
  }

  function stop() {
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
    setStatus("finished");
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

  const tourCompleted = tour ? tour.steps.filter((s) => openFilePaths.includes(s.file)).length : 0;
  const hasTour = tour !== null;

  const inspectorContent = (
    <div className="inspectorInner">
      <div className="inspectorTabs">
        <button
          className={`inspectorTab ${activeTab === "analysis" ? "inspectorTabActive" : ""}`}
          onClick={() => setActiveTab("analysis")}
        >
          分析
          {status === "running" && <span className="inspectorTabDot" />}
        </button>
        <button
          className={`inspectorTab ${activeTab === "tour" ? "inspectorTabActive" : ""}`}
          onClick={() => setActiveTab("tour")}
        >
          导览
          {hasTour && <span className="inspectorTabBadge">{tourCompleted}/{tour!.steps.length}</span>}
        </button>
      </div>
      <div className="inspectorContent">
        {activeTab === "analysis" ? (
          <div className="tabsPane">
            <AgentTimeline events={events} status={status} />
            <EvidencePanel events={events} onOpenEvidence={openEvidence} />
            <CallGraph events={events} />
            <AnswerPanel answer={answer} />
          </div>
        ) : tour ? (
          <div className="tabsPane">
            <WalkthroughPanel
              steps={tour.steps}
              activeFile={activeFile?.path ?? null}
              onOpenFile={openFileByKeyLines}
              onClose={() => setActiveTab("analysis")}
            />
          </div>
        ) : (
          <div className="tabsPane">
            <div className="panel">
              <p className="muted">还没有导览数据。点击左侧 "Start Code Tour" 生成。</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );

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
            tourLoading={tourLoading}
            onQuestionChange={setQuestion}
            onRun={run}
            onStop={stop}
            onStartTour={startTour}
          />
          <FileExplorer files={visibleFiles} query={fileQuery} onQueryChange={updateFileQuery} onOpen={openFile} />
        </>
      }
      editor={
        <div className="editorWrapper">
          <CodeEditor
            openFiles={openFilePaths}
            activeFile={activeFile}
            highlightedRange={highlightedRange}
            onSelectFile={openFile}
            onCloseFile={closeFile}
          />
          {hasTour && (
            <NextReadBar
              steps={tour!.steps}
              activeFile={activeFile?.path ?? null}
              onOpenFile={openFile}
            />
          )}
        </div>
      }
      inspector={inspectorContent}
      statusbar={
        <StatusBar
          status={status}
          eventCount={events.length}
          fileCount={openFilePaths.length}
          runId={runId}
        />
      }
    />
  );
}
