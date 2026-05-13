import { RunStatus } from "../../api/events";

type ChatPanelProps = {
  question: string;
  status: RunStatus;
  history: string[];
  tourLoading: boolean;
  errorMessage: string;
  onQuestionChange: (question: string) => void;
  onRun: () => void;
  onStop: () => void;
  onStartTour: () => void;
};

export function ChatPanel({
  question,
  status,
  history,
  tourLoading,
  errorMessage,
  onQuestionChange,
  onRun,
  onStop,
  onStartTour,
}: ChatPanelProps) {
  const busy = status === "running" || tourLoading;
  const isRunning = status === "running";

  return (
    <div className="chatPanel">
      <div>
        <h2>Ask</h2>
        <p className="muted">描述你想让 Agent 阅读或追踪的内容。</p>
      </div>

      <button
        className="tourButton"
        disabled={busy}
        onClick={onStartTour}
      >
        {tourLoading ? "生成导览中..." : "开始代码导览"}
      </button>

      <div className="chatDivider">
        <span>或直接提问</span>
      </div>

      <textarea
        className="promptBox"
        value={question}
        onChange={(event) => onQuestionChange(event.target.value)}
        placeholder="追踪 CLI 入口到 agent loop 的调用链..."
      />
      <div className="chatActions">
        <button
          className="primaryButton"
          disabled={(!isRunning && !question.trim()) || tourLoading}
          onClick={onRun}
        >
          {isRunning ? "分析中..." : "运行分析"}
        </button>
        {isRunning && (
          <button className="stopButton" onClick={onStop}>
            停止
          </button>
        )}
      </div>
      {errorMessage ? <p className="chatError">{errorMessage}</p> : null}
      <div className="history">
        <h3>最近提问</h3>
        {history.length === 0 ? <p className="muted">还没有运行过。</p> : null}
        {history.map((item) => (
          <div
            className="historyItem"
            key={item}
            onClick={() => { onQuestionChange(item); onRun(); }}
            title="点击重新运行"
          >
            {item}
          </div>
        ))}
      </div>
    </div>
  );
}
