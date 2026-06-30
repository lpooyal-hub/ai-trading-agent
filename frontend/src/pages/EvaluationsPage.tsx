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
        setMessage("평가를 새로고침했습니다.");
        return refresh();
      })
      .catch(() => setMessage("평가 실행에 실패했습니다."))
      .finally(() => setIsRunning(false));
  };

  useEffect(() => {
    refresh();
  }, []);

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">사후 평가</p>
          <h2>판단 성과 평가</h2>
        </div>
        <button className="primary-button" disabled={isRunning} onClick={runEvaluations} type="button">
          {isRunning ? "실행 중..." : "평가 실행"}
        </button>
      </header>
      {message ? <div className="notice">{message}</div> : null}
      <div className="stat-grid">
        <StatCard label="판단 수" value={`${status?.total_decisions ?? 0}`} />
        <StatCard label="평가 수" value={`${status?.total_evaluations ?? 0}`} detail={status?.latest_evaluated_at ? `최근 ${new Date(status.latest_evaluated_at).toLocaleString()}` : "없음"} />
        {(status?.windows ?? []).map((window) => (
          <StatCard
            detail={`${window.pending_count}개 대기 / ${window.not_due_count}개 기한 전`}
            key={window.window}
            label={`${window.window} 커버리지`}
            value={`${window.coverage_percent.toFixed(0)}%`}
          />
        ))}
      </div>
      <div className="evaluation-grid">
        {evaluations.map((evaluation) => <EvaluationCard evaluation={evaluation} key={evaluation.id} />)}
      </div>
      {!evaluations.length ? <div className="notice">아직 평가 기록이 없습니다.</div> : null}
    </section>
  );
}
