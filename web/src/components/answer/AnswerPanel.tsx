type AnswerPanelProps = {
  answer: string;
};

export function AnswerPanel({ answer }: AnswerPanelProps) {
  return (
    <div className="panel answerPanel">
      <h3>Answer</h3>
      <pre>{answer || "The final answer will appear here."}</pre>
    </div>
  );
}
