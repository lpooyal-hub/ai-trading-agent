import { DecisionEvaluation } from "../api/client";
import { evaluationWindowLabel } from "../utils/labels";

export function EvaluationCard({ evaluation }: { evaluation: DecisionEvaluation }) {
  return (
    <article className="evaluation-card">
      <div>
        <strong>판단 #{evaluation.decision_id}</strong>
        <span>{evaluationWindowLabel(evaluation.evaluation_window)}</span>
      </div>
      <p>{evaluation.agent_self_review}</p>
      <dl>
        <div>
          <dt>수익률</dt>
          <dd>{evaluation.return_percent.toFixed(2)}%</dd>
        </div>
        <div>
          <dt>수익 여부</dt>
          <dd>{evaluation.was_profitable ? "예" : "아니오"}</dd>
        </div>
      </dl>
    </article>
  );
}
