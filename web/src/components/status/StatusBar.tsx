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
    </>
  );
}
