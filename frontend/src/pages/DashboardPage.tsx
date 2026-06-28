import { useEffect, useState } from "react";
import { api, AgentDecision, AgentReadiness, DemoStatus, LLMBudget, LLMUsageSummary, MarketSnapshotStatus, PortfolioPerformance, PortfolioSummary, PortfolioSymbolPerformance, TradeOrder } from "../api/client";
import { DecisionTable } from "../components/DecisionTable";
import { OrderTable } from "../components/OrderTable";
import { StatCard } from "../components/StatCard";

export function DashboardPage({ onSelectDecision }: { onSelectDecision: (id: number) => void }) {
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [performance, setPerformance] = useState<PortfolioPerformance | null>(null);
  const [symbolPerformance, setSymbolPerformance] = useState<PortfolioSymbolPerformance[]>([]);
  const [llmSummary, setLlmSummary] = useState<LLMUsageSummary | null>(null);
  const [llmBudget, setLlmBudget] = useState<LLMBudget | null>(null);
  const [demoStatus, setDemoStatus] = useState<DemoStatus | null>(null);
  const [marketStatus, setMarketStatus] = useState<MarketSnapshotStatus | null>(null);
  const [agentReadiness, setAgentReadiness] = useState<AgentReadiness | null>(null);
  const [decisions, setDecisions] = useState<AgentDecision[]>([]);
  const [orders, setOrders] = useState<TradeOrder[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isRunningAgent, setIsRunningAgent] = useState(false);
  const [isSeedingDemo, setIsSeedingDemo] = useState(false);
  const [isRefreshingDashboard, setIsRefreshingDashboard] = useState(false);

  const loadDashboardData = () => (
    Promise.all([
      api.getPortfolioSummary(),
      api.getPortfolioPerformance(),
      api.getPortfolioSymbolPerformance(),
      api.getLLMSummary(),
      api.getLLMBudget(),
      api.getDemoStatus(),
      api.getMarketSnapshotStatus(),
      api.getAgentReadiness(),
      api.getDecisions(),
      api.getOrders(),
    ])
      .then(([portfolio, portfolioPerformance, symbolRows, usage, budget, demo, market, readiness, decisionRows, orderRows]) => {
        setSummary(portfolio);
        setPerformance(portfolioPerformance);
        setSymbolPerformance(symbolRows);
        setLlmSummary(usage);
        setLlmBudget(budget);
        setDemoStatus(demo);
        setMarketStatus(market);
        setAgentReadiness(readiness);
        setDecisions(decisionRows.slice(0, 5));
        setOrders(orderRows.slice(0, 5));
      })
  );

  useEffect(() => {
    loadDashboardData().catch(() => setError("Backend is not available yet."));
  }, []);

  const seedDemoData = () => {
    if (isSeedingDemo || (demoStatus ? !demoStatus.demo_enabled : false)) return;
    setIsSeedingDemo(true);
    api.seedDemoData()
      .then((status) => {
        setDemoStatus(status);
        setError(status.message);
        return loadDashboardData();
      })
      .catch(() => setError("Demo seed failed."))
      .finally(() => setIsSeedingDemo(false));
  };

  const refreshDashboard = () => {
    if (isRefreshingDashboard) return;
    setError(null);
    setIsRefreshingDashboard(true);
    loadDashboardData()
      .catch(() => setError("Dashboard refresh failed."))
      .finally(() => setIsRefreshingDashboard(false));
  };

  const runAgentOnce = () => {
    if (isRunningAgent) return;
    setError(null);
    setIsRunningAgent(true);
    api.runAgentOnce()
      .then((decision) => onSelectDecision(decision.id))
      .catch(() => setError("Agent run failed."))
      .finally(() => setIsRunningAgent(false));
  };

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">Research Dashboard</p>
          <h2>Decision Review</h2>
        </div>
        <div className="button-row">
          <button className="secondary-button" disabled={isRefreshingDashboard} onClick={refreshDashboard} type="button">
            {isRefreshingDashboard ? "Refreshing..." : "Refresh"}
          </button>
          <button className="primary-button" disabled={isRunningAgent} onClick={runAgentOnce} type="button">
            {isRunningAgent ? "Running..." : "Run Agent Once"}
          </button>
          <button
            className="secondary-button"
            disabled={isSeedingDemo || (demoStatus ? !demoStatus.demo_enabled : false)}
            onClick={seedDemoData}
            type="button"
          >
            {isSeedingDemo ? "Seeding..." : "Seed Demo Data"}
          </button>
        </div>
      </header>
      {error ? <div className="notice">{error}</div> : null}
      <div className="stat-grid">
        <StatCard label="Bot Capital" value={`$${summary?.bot_capital_limit_usd.toFixed(2) ?? "250.00"}`} />
        <StatCard label="Available Budget" value={`$${summary?.available_budget_usd.toFixed(2) ?? "0.00"}`} />
        <StatCard label="Invested" value={`$${summary?.invested_amount_usd.toFixed(2) ?? "0.00"}`} />
        <StatCard label="Total PnL" value={`$${performance?.total_pnl_usd.toFixed(2) ?? "0.00"}`} detail={`${performance?.total_pnl_percent.toFixed(2) ?? "0.00"}%`} />
        <StatCard label="Realized PnL" value={`$${performance?.realized_pnl_usd.toFixed(2) ?? "0.00"}`} />
        <StatCard label="Win Rate" value={`${performance?.win_rate_percent.toFixed(2) ?? "0.00"}%`} detail={`${performance?.winning_sell_count ?? 0} wins / ${performance?.losing_sell_count ?? 0} losses`} />
        <StatCard
          label="Top Symbol"
          value={symbolPerformance[0]?.symbol ?? "-"}
          detail={symbolPerformance[0] ? `$${symbolPerformance[0].realized_pnl_usd.toFixed(2)} realized` : "No realized trades"}
        />
        <StatCard label="Sim Orders" value={`${performance?.simulated_order_count ?? 0}`} detail={`${performance?.buy_order_count ?? 0} buy / ${performance?.sell_order_count ?? 0} sell`} />
        <StatCard label="Bot Positions" value={`${summary?.bot_position_count ?? 0}`} />
        <StatCard label="Today's LLM Calls" value={`${llmSummary?.today_calls ?? 0}`} />
        <StatCard label="Today's Tokens" value={`${llmSummary?.today_total_tokens ?? 0}`} />
        <StatCard label="Today's LLM Cost" value={`$${llmSummary?.today_estimated_cost_usd.toFixed(4) ?? "0.0000"}`} />
        <StatCard label="Monthly LLM Cost" value={`$${llmSummary?.monthly_estimated_cost_usd.toFixed(4) ?? "0.0000"}`} />
        <StatCard label="LLM Budget Left" value={`$${llmBudget?.daily_cost_remaining_usd.toFixed(4) ?? "0.0000"}`} />
        <StatCard label="Average Latency" value={`${Math.round(llmSummary?.average_latency_ms ?? 0)}ms`} />
        <StatCard label="Market Ready" value={marketStatus?.ready_for_agent ? "Ready" : "Not Ready"} detail={marketStatus?.message} />
        <StatCard label="Fresh Symbols" value={`${marketStatus?.fresh_symbol_count ?? 0}`} detail={`${marketStatus?.missing_symbol_count ?? 0} missing`} />
        <StatCard label="Agent Preflight" value={agentReadiness?.ready ? "Ready" : "Check"} detail={agentReadiness?.reason} />
        <StatCard label="Candidates" value={`${agentReadiness?.candidate_symbols.length ?? 0}`} detail={agentReadiness?.candidate_symbols.join(", ") || "None"} />
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
        <h3>Top Symbols</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Realized PnL</th>
                <th>Trades</th>
                <th>Win Rate</th>
              </tr>
            </thead>
            <tbody>
              {symbolPerformance.slice(0, 5).map((row) => (
                <tr key={row.symbol}>
                  <td>{row.symbol}</td>
                  <td>${row.realized_pnl_usd.toFixed(2)}</td>
                  <td>{row.realized_trade_count}</td>
                  <td>{row.win_rate_percent.toFixed(2)}%</td>
                </tr>
              ))}
              {!symbolPerformance.length ? (
                <tr>
                  <td colSpan={4}>No symbol performance yet.</td>
                </tr>
              ) : null}
            </tbody>
          </table>
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
