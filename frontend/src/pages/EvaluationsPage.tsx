import { useEffect, useState } from "react";
import { api, DecisionEvaluation } from "../api/client";
import { EvaluationCard } from "../components/EvaluationCard";

export function EvaluationsPage() {
  const [evaluations, setEvaluations] = useState<DecisionEvaluation[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const refresh = () => api.getEvaluations().then(setEvaluations).catch(() => setEvaluations([]));

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
      <div className="evaluation-grid">
        {evaluations.map((evaluation) => <EvaluationCard evaluation={evaluation} key={evaluation.id} />)}
      </div>
      {!evaluations.length ? <div className="notice">No evaluations yet.</div> : null}
    </section>
  );
}
