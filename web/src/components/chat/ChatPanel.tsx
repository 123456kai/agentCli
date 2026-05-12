import { RunStatus } from "../../api/events";

type ChatPanelProps = {
  question: string;
  status: RunStatus;
  history: string[];
  onQuestionChange: (question: string) => void;
  onRun: () => void;
};

export function ChatPanel({ question, status, history, onQuestionChange, onRun }: ChatPanelProps) {
  return (
    <div className="chatPanel">
      <div>
        <h2>Ask</h2>
        <p className="muted">Describe what you want the agent to read or trace.</p>
      </div>
      <textarea
        className="promptBox"
        value={question}
        onChange={(event) => onQuestionChange(event.target.value)}
        placeholder="Trace the CLI entrypoint to the agent loop..."
      />
      <button className="primaryButton" disabled={status === "running" || !question.trim()} onClick={onRun}>
        {status === "running" ? "Running..." : "Run analysis"}
      </button>
      <div className="history">
        <h3>Recent Questions</h3>
        {history.length === 0 ? <p className="muted">No runs yet.</p> : null}
        {history.map((item) => (
          <div className="historyItem" key={item}>
            {item}
          </div>
        ))}
      </div>
    </div>
  );
}
