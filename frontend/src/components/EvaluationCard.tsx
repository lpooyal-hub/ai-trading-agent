import { DecisionEvaluation } from "../api/client";

export function EvaluationCard({ evaluation }: { evaluation: DecisionEvaluation }) {
  return (
    <article className="evaluation-card">
      <div>
        <strong>Decision #{evaluation.decision_id}</strong>
        <span>{evaluation.evaluation_window}</span>
      </div>
      <p>{evaluation.agent_self_review}</p>
      <dl>
        <div>
          <dt>Return</dt>
          <dd>{evaluation.return_percent.toFixed(2)}%</dd>
        </div>
        <div>
          <dt>Profitable</dt>
          <dd>{evaluation.was_profitable ? "Yes" : "No"}</dd>
        </div>
      </dl>
    </article>
  );
}
