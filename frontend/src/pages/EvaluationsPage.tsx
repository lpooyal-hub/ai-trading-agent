import { useEffect, useState } from "react";
import { api, DecisionEvaluation, EvaluationStatus } from "../api/client";
import { EvaluationCard } from "../components/EvaluationCard";
import { StatCard } from "../components/StatCard";

export function EvaluationsPage() {
  const [evaluations, setEvaluations] = useState<DecisionEvaluation[]>([]);
  const [status, setStatus] = useState<EvaluationStatus | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const refresh = () => (
    Promise.all([api.getEvaluations(), api.getEvaluationStatus()])
      .then(([rows, evaluationStatus]) => {
        setEvaluations(rows);
        setStatus(evaluationStatus);
      })
      .catch(() => {
        setEvaluations([]);
        setStatus(null);
      })
  );

  const runEvaluations = () => {
    if (isRunning) return;
    setIsRunning(true);
    setMessage(null);
    api.runEvaluations()
      .then(() => {
        setMessage("Evaluations refreshed.");
        return refresh();
      })
      .catch(() => setMessage("Evaluation run failed."))
      .finally(() => setIsRunning(false));
  };

  useEffect(() => {
    refresh();
  }, []);

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">Hindsight</p>
          <h2>Decision Evaluations</h2>
        </div>
        <button className="primary-button" disabled={isRunning} onClick={runEvaluations} type="button">
          {isRunning ? "Running..." : "Run Evaluations"}
        </button>
      </header>
      {message ? <div className="notice">{message}</div> : null}
      <div className="stat-grid">
        <StatCard label="Decisions" value={`${status?.total_decisions ?? 0}`} />
        <StatCard label="Evaluations" value={`${status?.total_evaluations ?? 0}`} detail={status?.latest_evaluated_at ? `latest ${new Date(status.latest_evaluated_at).toLocaleString()}` : "None"} />
        {(status?.windows ?? []).map((window) => (
          <StatCard
            detail={`${window.pending_count} pending / ${window.not_due_count} not due`}
            key={window.window}
            label={`${window.window} Coverage`}
            value={`${window.coverage_percent.toFixed(0)}%`}
          />
        ))}
      </div>
      <div className="evaluation-grid">
        {evaluations.map((evaluation) => <EvaluationCard evaluation={evaluation} key={evaluation.id} />)}
      </div>
      {!evaluations.length ? <div className="notice">No evaluations yet.</div> : null}
    </section>
  );
}
