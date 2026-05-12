import { TourStep } from "./types";

type NextReadBarProps = {
  steps: TourStep[];
  activeFile: string | null;
  onOpenFile: (path: string) => void;
};

export function NextReadBar({ steps, activeFile, onOpenFile }: NextReadBarProps) {
  if (!activeFile) return null;

  const currentStep = steps.find((s) => s.file === activeFile);
  if (!currentStep?.next_read?.file) return null;

  const nextFile = currentStep.next_read.file;
  const reason = currentStep.next_read.reason;

  return (
    <div className="nextReadBar">
      <div className="nextReadLabel">下一读:</div>
      <button className="nextReadFile" onClick={() => onOpenFile(nextFile)}>
        {nextFile.split("/").at(-1)}
      </button>
      <div className="nextReadReason">{reason}</div>
    </div>
  );
}
