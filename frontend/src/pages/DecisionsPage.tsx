import { useEffect, useState } from "react";
import { api, AgentDecision } from "../api/client";
import { DecisionTable } from "../components/DecisionTable";

export function DecisionsPage({ onSelectDecision }: { onSelectDecision: (id: number) => void }) {
  const [decisions, setDecisions] = useState<AgentDecision[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [symbolFilter, setSymbolFilter] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [isRunningAgent, setIsRunningAgent] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const refreshDecisions = (filters = { status: statusFilter, symbol: symbolFilter }) => {
    if (isRefreshing) return;
    setIsRefreshing(true);
    setMessage(null);
    api.getDecisions({
      status: filters.status || undefined,
      symbol: filters.symbol || undefined,
      limit: 100,
    })
      .then(setDecisions)
      .catch(() => {
        setDecisions([]);
        setMessage("판단 기록 새로고침에 실패했습니다.");
      })
      .finally(() => setIsRefreshing(false));
  };

  useEffect(() => {
    refreshDecisions();
  }, []);

  const runAgentOnce = () => {
    if (isRunningAgent) return;
    setIsRunningAgent(true);
    api.runAgentOnce()
      .then((decision) => onSelectDecision(decision.id))
      .catch(() => undefined)
      .finally(() => setIsRunningAgent(false));
  };

  const clearFilters = () => {
    setStatusFilter("");
    setSymbolFilter("");
    refreshDecisions({ status: "", symbol: "" });
  };

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">에이전트 판단</p>
          <h2>판단 기록</h2>
        </div>
        <div className="button-row">
          <button className="secondary-button" disabled={isRefreshing} onClick={refreshDecisions} type="button">
            {isRefreshing ? "새로고침 중..." : "새로고침"}
          </button>
          <button className="primary-button" disabled={isRunningAgent} onClick={runAgentOnce} type="button">
            {isRunningAgent ? "실행 중..." : "에이전트 실행"}
          </button>
        </div>
      </header>
      <div className="button-row">
        <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
          <option value="">전체 상태</option>
          <option value="PENDING">대기</option>
          <option value="APPROVED">승인</option>
          <option value="REJECTED">거절</option>
          <option value="EXECUTED">실행됨</option>
          <option value="SKIPPED">건너뜀</option>
        </select>
        <input
          onChange={(event) => setSymbolFilter(event.target.value.toUpperCase())}
          placeholder="종목"
          value={symbolFilter}
        />
        <button className="secondary-button" onClick={() => refreshDecisions()} type="button">적용</button>
        <button className="secondary-button" onClick={clearFilters} type="button">초기화</button>
      </div>
      {message ? <div className="notice">{message}</div> : null}
      <DecisionTable decisions={decisions} onSelect={onSelectDecision} />
    </section>
  );
}
