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
        setMessage("Decision refresh failed.");
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
          <p className="eyebrow">Agent Decisions</p>
          <h2>Decision Log</h2>
        </div>
        <div className="button-row">
          <button className="secondary-button" disabled={isRefreshing} onClick={refreshDecisions} type="button">
            {isRefreshing ? "Refreshing..." : "Refresh"}
          </button>
          <button className="primary-button" disabled={isRunningAgent} onClick={runAgentOnce} type="button">
            {isRunningAgent ? "Running..." : "Run Agent Once"}
          </button>
        </div>
      </header>
      <div className="button-row">
        <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
          <option value="">All statuses</option>
          <option value="PENDING">Pending</option>
          <option value="APPROVED">Approved</option>
          <option value="REJECTED">Rejected</option>
          <option value="EXECUTED">Executed</option>
          <option value="SKIPPED">Skipped</option>
        </select>
        <input
          onChange={(event) => setSymbolFilter(event.target.value.toUpperCase())}
          placeholder="Symbol"
          value={symbolFilter}
        />
        <button className="secondary-button" onClick={() => refreshDecisions()} type="button">Apply</button>
        <button className="secondary-button" onClick={clearFilters} type="button">Clear</button>
      </div>
      {message ? <div className="notice">{message}</div> : null}
      <DecisionTable decisions={decisions} onSelect={onSelectDecision} />
    </section>
  );
}
