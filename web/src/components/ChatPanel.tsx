type ChatPanelProps = {
  question: string;
  onQuestionChange: (question: string) => void;
  onRun: () => void;
};

export function ChatPanel({ question, onQuestionChange, onRun }: ChatPanelProps) {
  return (
    <aside>
      <h2>agentCli</h2>
      <p className="muted">Ask a source-reading question and watch the agent inspect files.</p>
      <textarea value={question} onChange={(event) => onQuestionChange(event.target.value)} />
      <button onClick={onRun}>Run analysis</button>
    </aside>
  );
}
