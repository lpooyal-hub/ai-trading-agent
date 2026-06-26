import { useEffect, useState } from "react";
import { api, DecisionEvaluation } from "../api/client";
import { EvaluationCard } from "../components/EvaluationCard";

export function EvaluationsPage() {
  const [evaluations, setEvaluations] = useState<DecisionEvaluation[]>([]);

  const refresh = () => api.getEvaluations().then(setEvaluations).catch(() => setEvaluations([]));

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
        <button className="primary-button" onClick={() => api.runEvaluations().then(refresh)} type="button">
          Run Evaluations
        </button>
      </header>
      <div className="evaluation-grid">
        {evaluations.map((evaluation) => <EvaluationCard evaluation={evaluation} key={evaluation.id} />)}
      </div>
      {!evaluations.length ? <div className="notice">No evaluations yet.</div> : null}
    </section>
  );
}
