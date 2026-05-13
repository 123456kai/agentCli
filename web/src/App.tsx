import { useEffect, useMemo, useRef, useState } from "react";

import { AgentEvent, EvidenceItem, HighlightedRange, RunStatus, SourceFile } from "./api/events";
import {
  cancelRun,
  createSession,
  getLatestSession,
  getProjectInfo,
  readSourceFile,
  saveAnalysisNote,
  searchProjectFilesDetailed,
  startRun,
  subscribeRunEvents,
} from "./api/client";
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
  const [sessionId, setSessionId] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [history, setHistory] = useState<string[]>([]);
  const [files, setFiles] = useState<string[]>([]);
  const [fileTotalMatches, setFileTotalMatches] = useState(0);
  const [fileListTruncated, setFileListTruncated] = useState(false);
  const [fileQuery, setFileQuery] = useState("");
  const [openFilePaths, setOpenFilePaths] = useState<string[]>([]);
  const [activeFile, setActiveFile] = useState<SourceFile | null>(null);
  const [highlightedRange, setHighlightedRange] = useState<HighlightedRange | undefined>();
  const [tour, setTour] = useState<TourData | null>(null);
  const [tourLoading, setTourLoading] = useState(false);
  const [projectName, setProjectName] = useState("agentCli");
  const [projectRepoLabel, setProjectRepoLabel] = useState("loading project...");
  const [modelLabel, setModelLabel] = useState("loading model...");
  const [noteStatus, setNoteStatus] = useState<"idle" | "saving" | "saved" | "failed">("idle");
  const [notePath, setNotePath] = useState("");
  const [activeTab, setActiveTab] = useState<InspectorTab>("analysis");
  const eventSourceRef = useRef<EventSource | null>(null);

  const visibleFiles = useMemo(() => files.slice(0, 200), [files]);

  useEffect(() => {
    (async () => {
      try {
        const [project, latestSession] = await Promise.all([getProjectInfo(), getLatestSession()]);
        setProjectName(project.name || "agentCli");
        setProjectRepoLabel(project.repoRoot || "unknown repository");
        setModelLabel(project.model || "unknown model");
        if (latestSession) {
          setSessionId(latestSession);
        } else {
          setSessionId(await createSession());
        }
      } catch {
        setErrorMessage("项目初始化失败，请刷新页面重试。");
      }
      await refreshFiles("");
    })();
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
    setErrorMessage("");
    setTourLoading(true);
    setTour(null);
    setActiveTab("tour");
    try {
      const resp = await fetch("/api/tour", { method: "POST" });
      if (!resp.ok) {
        throw new Error("tour request failed");
      }
      const data: TourData = await resp.json();
      setTour(data);
      if (data.warning) {
        setErrorMessage("导览生成不完整，已展示降级内容。");
      }
      if (data.steps.length > 0) {
        openFileByKeyLines(data.steps[0].file, data.steps[0].key_lines);
      }
    } catch {
      setErrorMessage("导览生成失败，请稍后重试。");
    } finally {
      setTourLoading(false);
    }
  }

  async function run() {
    setErrorMessage("");
    setNoteStatus("idle");
    setNotePath("");
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
    setEvents([]);
    setAnswer("");
    setStatus("running");
    setActiveTab("analysis");
    setHistory((current) => [question, ...current.filter((item) => item !== question)].slice(0, 8));
    try {
      const activeSessionId = sessionId || (await createSession());
      setSessionId(activeSessionId);
      const nextRun = await startRun(question, activeSessionId);
      setRunId(nextRun.runId);
      setSessionId(nextRun.sessionId);
      const es = subscribeRunEvents(
        nextRun.runId,
        (parsed) => {
          setEvents((current) => [...current, parsed]);
          if (parsed.type === "answer_final") {
            setAnswer(String(parsed.payload.answer || ""));
          }
          if (parsed.type === "run_finished") {
            const statusPayload = String(parsed.payload.status ?? "finished");
            if (statusPayload === "failed") setStatus("failed");
            else if (statusPayload === "cancelled") setStatus("cancelled");
            else setStatus("finished");
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
            setErrorMessage(String(parsed.payload.error ?? "分析失败，请重试。"));
            setStatus("failed");
          }
        },
        () => setStatus((current) => (current === "failed" || current === "cancelled" ? current : "finished")),
        () => {
          setErrorMessage("分析连接中断，请重试。");
          setStatus("failed");
        },
      );
      eventSourceRef.current = es;
    } catch {
      setErrorMessage("启动分析失败，请确认会话和后端状态。");
      setStatus("failed");
    }
  }

  async function stop() {
    if (runId) {
      try {
        await cancelRun(runId);
      } catch {
        setErrorMessage("停止请求失败，已关闭前端订阅。");
      }
    }
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
    setStatus("cancelled");
  }

  async function refreshFiles(query = fileQuery) {
    const result = await searchProjectFilesDetailed(query);
    setFiles(result.matches);
    setFileTotalMatches(result.totalMatches);
    setFileListTruncated(result.truncated);
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

  async function saveNote() {
    if (!answer.trim()) return;
    setNoteStatus("saving");
    try {
      const savedPath = await saveAnalysisNote(question, answer);
      setNotePath(savedPath);
      setNoteStatus("saved");
    } catch {
      setNoteStatus("failed");
    }
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
            <AnswerPanel
              answer={answer}
              canSave={Boolean(answer.trim())}
              noteStatus={noteStatus}
              notePath={notePath}
              onSaveNote={saveNote}
            />
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
      title={projectName}
      repoLabel={projectRepoLabel}
      modelLabel={modelLabel}
      status={status}
      sidebar={
        <>
          <ChatPanel
            question={question}
            status={status}
            history={history}
            tourLoading={tourLoading}
            errorMessage={errorMessage}
            onQuestionChange={setQuestion}
            onRun={run}
            onStop={stop}
            onStartTour={startTour}
          />
          <FileExplorer
            files={visibleFiles}
            totalMatches={fileTotalMatches}
            truncated={fileListTruncated}
            query={fileQuery}
            onQueryChange={updateFileQuery}
            onOpen={openFile}
          />
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
