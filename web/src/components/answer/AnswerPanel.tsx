type AnswerPanelProps = {
  answer: string;
  canSave: boolean;
  noteStatus: "idle" | "saving" | "saved" | "failed";
  notePath: string;
  onSaveNote: () => void;
};

export function AnswerPanel({ answer, canSave, noteStatus, notePath, onSaveNote }: AnswerPanelProps) {
  const buttonLabel = noteStatus === "saving" ? "保存中..." : "保存笔记";
  return (
    <div className="panel answerPanel">
      <h3>Answer</h3>
      <div className="answerActions">
        <button className="primaryButton" disabled={!canSave || noteStatus === "saving"} onClick={onSaveNote}>
          {buttonLabel}
        </button>
        {noteStatus === "saved" ? <span className="muted">已保存到 {notePath}</span> : null}
        {noteStatus === "failed" ? <span className="muted">笔记保存失败，请重试。</span> : null}
      </div>
      <pre>{answer || "The final answer will appear here."}</pre>
    </div>
  );
}
