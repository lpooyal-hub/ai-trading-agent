import { useEffect, useState } from "react";
import { api, AgentDecision } from "../api/client";
import { DecisionTable } from "../components/DecisionTable";

export function DecisionsPage({ onSelectDecision }: { onSelectDecision: (id: number) => void }) {
  const [decisions, setDecisions] = useState<AgentDecision[]>([]);
  const [isRunningAgent, setIsRunningAgent] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const refreshDecisions = () => {
    if (isRefreshing) return;
    setIsRefreshing(true);
    api.getDecisions()
      .then(setDecisions)
      .catch(() => setDecisions([]))
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
      <DecisionTable decisions={decisions} onSelect={onSelectDecision} />
    </section>
  );
}
