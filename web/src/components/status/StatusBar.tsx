import { RunStatus } from "../../api/events";

type StatusBarProps = {
  status: RunStatus;
  eventCount: number;
  fileCount: number;
  runId: string;
};

export function StatusBar({ status, eventCount, fileCount, runId }: StatusBarProps) {
  return (
    <>
      <span>Status: {status}</span>
      <span>Events: {eventCount}</span>
      <span>Files: {fileCount}</span>
      <span>Run: {runId || "none"}</span>
      <span style={{ flex: 1 }} />
      <span className="muted">Ctrl+Enter 提交 · 右侧 Tab 切换视图</span>
    </>
  );
}
