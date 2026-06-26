import { useEffect, useState } from "react";
import { api, AgentDecision, DemoStatus, LLMBudget, LLMUsageSummary, PortfolioSummary, TradeOrder } from "../api/client";
import { DecisionTable } from "../components/DecisionTable";
import { OrderTable } from "../components/OrderTable";
import { StatCard } from "../components/StatCard";

export function DashboardPage({ onSelectDecision }: { onSelectDecision: (id: number) => void }) {
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [llmSummary, setLlmSummary] = useState<LLMUsageSummary | null>(null);
  const [llmBudget, setLlmBudget] = useState<LLMBudget | null>(null);
  const [demoStatus, setDemoStatus] = useState<DemoStatus | null>(null);
  const [decisions, setDecisions] = useState<AgentDecision[]>([]);
  const [orders, setOrders] = useState<TradeOrder[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.getPortfolioSummary(),
      api.getLLMSummary(),
      api.getLLMBudget(),
      api.getDemoStatus(),
      api.getDecisions(),
      api.getOrders(),
    ])
      .then(([portfolio, usage, budget, demo, decisionRows, orderRows]) => {
        setSummary(portfolio);
        setLlmSummary(usage);
        setLlmBudget(budget);
        setDemoStatus(demo);
        setDecisions(decisionRows.slice(0, 5));
        setOrders(orderRows.slice(0, 5));
      })
      .catch(() => setError("Backend is not available yet."));
  }, []);

  const seedDemoData = () => {
    api.seedDemoData()
      .then((status) => {
        setDemoStatus(status);
        setError(status.message);
        return Promise.all([api.getPortfolioSummary(), api.getDecisions(), api.getOrders(), api.getLLMSummary()]);
      })
      .then(([portfolio, decisionRows, orderRows, usage]) => {
        setSummary(portfolio);
        setDecisions(decisionRows.slice(0, 5));
        setOrders(orderRows.slice(0, 5));
        setLlmSummary(usage);
      })
      .catch(() => setError("Demo seed failed."));
  };

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">Research Dashboard</p>
          <h2>Decision Review</h2>
        </div>
        <button className="primary-button" onClick={() => api.runAgentOnce().then((decision) => onSelectDecision(decision.id))} type="button">
          Run Agent Once
        </button>
        <button
          className="secondary-button"
          disabled={demoStatus ? !demoStatus.demo_enabled : false}
          onClick={seedDemoData}
          type="button"
        >
          Seed Demo Data
        </button>
      </header>
      {error ? <div className="notice">{error}</div> : null}
      <div className="stat-grid">
        <StatCard label="Bot Capital" value={`$${summary?.bot_capital_limit_usd.toFixed(2) ?? "250.00"}`} />
        <StatCard label="Available Budget" value={`$${summary?.available_budget_usd.toFixed(2) ?? "0.00"}`} />
        <StatCard label="Invested" value={`$${summary?.invested_amount_usd.toFixed(2) ?? "0.00"}`} />
        <StatCard label="Bot Positions" value={`${summary?.bot_position_count ?? 0}`} />
        <StatCard label="Today's LLM Calls" value={`${llmSummary?.today_calls ?? 0}`} />
        <StatCard label="Today's Tokens" value={`${llmSummary?.today_total_tokens ?? 0}`} />
        <StatCard label="Today's LLM Cost" value={`$${llmSummary?.today_estimated_cost_usd.toFixed(4) ?? "0.0000"}`} />
        <StatCard label="Monthly LLM Cost" value={`$${llmSummary?.monthly_estimated_cost_usd.toFixed(4) ?? "0.0000"}`} />
        <StatCard label="LLM Budget Left" value={`$${llmBudget?.daily_cost_remaining_usd.toFixed(4) ?? "0.0000"}`} />
        <StatCard label="Average Latency" value={`${Math.round(llmSummary?.average_latency_ms ?? 0)}ms`} />
        <StatCard
          label="Demo Mode"
          value={demoStatus?.demo_enabled ? "Enabled" : "Disabled"}
          detail={demoStatus?.demo_reason}
        />
        <StatCard label="Demo Rows" value={`${demoStatus?.decisions ?? 0}`} detail={`${demoStatus?.orders ?? 0} orders`} />
      </div>
      <section>
        <h3>Active Universe</h3>
        <div className="symbol-list">
          {(summary?.active_universe ?? []).map((symbol) => <span key={symbol}>{symbol}</span>)}
        </div>
      </section>
      <section>
        <h3>Recent Decisions</h3>
        <DecisionTable decisions={decisions} onSelect={onSelectDecision} />
      </section>
      <section>
        <h3>Recent Simulated Orders</h3>
        <OrderTable orders={orders} />
      </section>
    </section>
  );
}
