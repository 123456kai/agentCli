import { useEffect, useState } from "react";
import { TourStep } from "./types";

type WalkthroughPanelProps = {
  steps: TourStep[];
  activeFile: string | null;
  onOpenFile: (path: string, keyLines?: string) => void;
  onClose: () => void;
};

export function WalkthroughPanel({ steps, activeFile, onOpenFile, onClose }: WalkthroughPanelProps) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set([0]));
  const [completed, setCompleted] = useState<Set<number>>(new Set());

  useEffect(() => {
    if (activeFile) {
      const idx = steps.findIndex((s) => s.file === activeFile);
      if (idx >= 0) {
        setCompleted((prev) => new Set([...prev, idx]));
        const next = steps.findIndex((s, i) => i > idx && !completed.has(i));
        if (next >= 0) {
          setExpanded((prev) => new Set([...prev, next]));
        }
      }
    }
  }, [activeFile]);

  function toggleStep(i: number) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  }

  function parseKeyLines(kl?: string): { start: number; end: number } | null {
    if (!kl) return null;
    const parts = kl.split("-");
    const start = parseInt(parts[0], 10);
    const end = parts[1] ? parseInt(parts[1], 10) : start;
    if (isNaN(start)) return null;
    return { start, end: isNaN(end) ? start : end };
  }

  return (
    <div className="walkthroughPanel">
      <div className="walkthroughHeader">
        <h3>代码导览</h3>
        <div className="walkthroughHeaderRight">
          <span className="walkthroughProgress">
            {completed.size}/{steps.length} 已读
          </span>
          <button className="walkthroughCloseBtn" onClick={onClose} title="返回分析视图">
            ✕
          </button>
        </div>
      </div>
      <div className="walkthroughSteps">
        {steps.map((step, i) => {
          const isCompleted = completed.has(i);
          const isExpanded = expanded.has(i);
          const isActive = activeFile === step.file;
          const keyLines = parseKeyLines(step.key_lines);

          return (
            <div
              className={`walkthroughStep ${isCompleted ? "walkthroughStepDone" : ""} ${isActive ? "walkthroughStepActive" : ""}`}
              key={step.order}
            >
              <div className="walkthroughConnector">
                <div className={`walkthroughCircle ${isCompleted ? "walkthroughCircleDone" : ""} ${isActive ? "walkthroughCirclePulse" : ""}`}>
                  {isCompleted ? "✓" : step.order}
                </div>
                {i < steps.length - 1 && (
                  <div className={`walkthroughLine ${isCompleted ? "walkthroughLineDone" : ""}`} />
                )}
              </div>

              <div className="walkthroughContent">
                <div
                  className="walkthroughStepHeader"
                  onClick={() => toggleStep(i)}
                >
                  <span className="walkthroughStepTitle">{step.title}</span>
                  <span className={`walkthroughChevron ${isExpanded ? "walkthroughChevronOpen" : ""}`}>
                    ›
                  </span>
                </div>

                {isExpanded && (
                  <div className="walkthroughBody">
                    <p className="walkthroughDesc">{step.description}</p>

                    <button
                      className="walkthroughFileBtn"
                      onClick={() => onOpenFile(step.file, step.key_lines)}
                    >
                      <span className="walkthroughFileIcon">📄</span>
                      <span className="walkthroughFileName">{step.file.split("/").at(-1)}</span>
                      <span className="walkthroughFilePath">{step.file}</span>
                      {keyLines && (
                        <span className="walkthroughKeyLines">L{keyLines.start}-L{keyLines.end}</span>
                      )}
                    </button>

                    {step.next_read?.file && (
                      <div className="walkthroughNext">
                        <div className="walkthroughNextLabel">接下来看</div>
                        <button
                          className="walkthroughNextBtn"
                          onClick={() => onOpenFile(step.next_read!.file)}
                        >
                          <span className="walkthroughNextFile">{step.next_read.file.split("/").at(-1)}</span>
                          <span className="walkthroughNextReason">{step.next_read.reason}</span>
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
