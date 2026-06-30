import { useEffect, useState } from "react";
import { api, AgentAutomationPolicy, AgentDecision, AgentOperations, AgentReadiness, AgentSchedule, DemoStatus, LiveTradingReadiness, LLMBudget, LLMUsageSummary, MarketSnapshotStatus, PortfolioCostRecovery, PortfolioPerformance, PortfolioSummary, PortfolioSymbolPerformance, TradeOrder } from "../api/client";
import { DecisionTable } from "../components/DecisionTable";
import { OrderTable } from "../components/OrderTable";
import { StatCard } from "../components/StatCard";

export function DashboardPage({ onSelectDecision }: { onSelectDecision: (id: number) => void }) {
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [performance, setPerformance] = useState<PortfolioPerformance | null>(null);
  const [costRecovery, setCostRecovery] = useState<PortfolioCostRecovery | null>(null);
  const [symbolPerformance, setSymbolPerformance] = useState<PortfolioSymbolPerformance[]>([]);
  const [llmSummary, setLlmSummary] = useState<LLMUsageSummary | null>(null);
  const [llmBudget, setLlmBudget] = useState<LLMBudget | null>(null);
  const [demoStatus, setDemoStatus] = useState<DemoStatus | null>(null);
  const [marketStatus, setMarketStatus] = useState<MarketSnapshotStatus | null>(null);
  const [agentReadiness, setAgentReadiness] = useState<AgentReadiness | null>(null);
  const [automationPolicy, setAutomationPolicy] = useState<AgentAutomationPolicy | null>(null);
  const [agentSchedule, setAgentSchedule] = useState<AgentSchedule | null>(null);
  const [agentOperations, setAgentOperations] = useState<AgentOperations | null>(null);
  const [liveReadiness, setLiveReadiness] = useState<LiveTradingReadiness | null>(null);
  const [decisions, setDecisions] = useState<AgentDecision[]>([]);
  const [orders, setOrders] = useState<TradeOrder[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isRunningAgent, setIsRunningAgent] = useState(false);
  const [isRunningScheduledAgent, setIsRunningScheduledAgent] = useState(false);
  const [isSeedingDemo, setIsSeedingDemo] = useState(false);
  const [isRefreshingDashboard, setIsRefreshingDashboard] = useState(false);

  const loadDashboardData = () => (
    Promise.all([
      api.getPortfolioSummary(),
      api.getPortfolioPerformance(),
      api.getPortfolioCostRecovery(),
      api.getPortfolioSymbolPerformance(),
      api.getLLMSummary(),
      api.getLLMBudget(),
      api.getDemoStatus(),
      api.getMarketSnapshotStatus(),
      api.getAgentReadiness(),
      api.getAgentAutomationPolicy(),
      api.getAgentSchedule(),
      api.getAgentOperations(),
      api.getLiveTradingReadiness(),
      api.getDecisions(),
      api.getOrders(),
    ])
      .then(([portfolio, portfolioPerformance, portfolioCostRecovery, symbolRows, usage, budget, demo, market, readiness, policy, schedule, operations, liveTradingReadiness, decisionRows, orderRows]) => {
        setSummary(portfolio);
        setPerformance(portfolioPerformance);
        setCostRecovery(portfolioCostRecovery);
        setSymbolPerformance(symbolRows);
        setLlmSummary(usage);
        setLlmBudget(budget);
        setDemoStatus(demo);
        setMarketStatus(market);
        setAgentReadiness(readiness);
        setAutomationPolicy(policy);
        setAgentSchedule(schedule);
        setAgentOperations(operations);
        setLiveReadiness(liveTradingReadiness);
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

  const runScheduledAgent = () => {
    if (isRunningScheduledAgent) return;
    setError(null);
    setIsRunningScheduledAgent(true);
    api.runScheduledAgent()
      .then((result) => {
        setError(result.reason);
        if (result.decision) {
          onSelectDecision(result.decision.id);
          return;
        }
        return loadDashboardData();
      })
      .catch(() => setError("Scheduled agent run failed."))
      .finally(() => setIsRunningScheduledAgent(false));
  };

  const agentRunLabel = agentReadiness?.llm_mode === "mock" ? "Run Mock Agent Once" : "Run Agent Once";

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
            {isRunningAgent ? "Running..." : agentRunLabel}
          </button>
          <button className="secondary-button" disabled={isRunningScheduledAgent} onClick={runScheduledAgent} type="button">
            {isRunningScheduledAgent ? "Checking..." : "Run If Due"}
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
        <StatCard label="Net After LLM" value={`$${costRecovery?.net_after_llm_cost_usd.toFixed(4) ?? "0.0000"}`} detail={`monthly LLM $${costRecovery?.monthly_llm_cost_usd.toFixed(4) ?? "0.0000"}`} />
        <StatCard label="LLM Recovery" value={costRecovery?.llm_cost_recovery_ratio === null || costRecovery?.llm_cost_recovery_ratio === undefined ? "-" : `${costRecovery.llm_cost_recovery_ratio.toFixed(2)}x`} detail={costRecovery?.llm_cost_covered === null || costRecovery?.llm_cost_covered === undefined ? "No LLM cost yet" : costRecovery.llm_cost_covered ? "paper PnL covers cost" : "paper PnL below cost"} />
        <StatCard label="Realized Net" value={`$${costRecovery?.realized_net_after_llm_cost_usd.toFixed(4) ?? "0.0000"}`} detail={costRecovery?.realized_llm_cost_covered === null || costRecovery?.realized_llm_cost_covered === undefined ? "No LLM cost yet" : costRecovery.realized_llm_cost_covered ? "realized covers cost" : "realized below cost"} />
        <StatCard label="Win Rate" value={`${performance?.win_rate_percent.toFixed(2) ?? "0.00"}%`} detail={`${performance?.winning_sell_count ?? 0} wins / ${performance?.losing_sell_count ?? 0} losses`} />
        <StatCard
          label="Top Symbol"
          value={symbolPerformance[0]?.symbol ?? "-"}
          detail={symbolPerformance[0] ? `$${symbolPerformance[0].realized_pnl_usd.toFixed(2)} realized` : "No realized trades"}
        />
        <StatCard label="Sim Orders" value={`${performance?.simulated_order_count ?? 0}`} detail={`${performance?.buy_order_count ?? 0} buy / ${performance?.sell_order_count ?? 0} sell`} />
        <StatCard label="Bot Positions" value={`${summary?.bot_position_count ?? 0}`} />
        <StatCard label="Today's LLM Calls" value={`${llmSummary?.today_calls ?? 0}`} />
        <StatCard label="LLM Calls Left" value={`${llmBudget?.daily_calls_remaining ?? 0}`} detail={`limit ${llmBudget?.daily_call_limit ?? 0} / cooldown ${llmBudget?.cooldown_remaining_minutes ?? 0} min`} />
        <StatCard label="Today's Tokens" value={`${llmSummary?.today_total_tokens ?? 0}`} />
        <StatCard label="Today's LLM Cost" value={`$${llmSummary?.today_estimated_cost_usd.toFixed(4) ?? "0.0000"}`} />
        <StatCard label="Monthly LLM Cost" value={`$${llmSummary?.monthly_estimated_cost_usd.toFixed(4) ?? "0.0000"}`} />
        <StatCard label="LLM Budget Left" value={`$${llmBudget?.daily_cost_remaining_usd.toFixed(4) ?? "0.0000"}`} />
        <StatCard label="Average Latency" value={`${Math.round(llmSummary?.average_latency_ms ?? 0)}ms`} />
        <StatCard label="Market Ready" value={marketStatus?.ready_for_agent ? "Ready" : "Not Ready"} detail={marketStatus?.message} />
        <StatCard label="Fresh Symbols" value={`${marketStatus?.fresh_symbol_count ?? 0}`} detail={`${marketStatus?.missing_symbol_count ?? 0} missing`} />
        <StatCard label="Agent Preflight" value={agentReadiness?.ready ? "Ready" : "Check"} detail={agentReadiness?.reason} />
        <StatCard label="Last Decision" value={agentOperations?.last_decision_symbol ?? "-"} detail={agentOperations?.last_decision_status ?? "None"} />
        <StatCard label="Pending Decisions" value={`${agentOperations?.pending_decision_count ?? 0}`} detail={`${agentOperations?.executable_decision_count ?? 0} executable`} />
        <StatCard label="Last Order" value={agentOperations?.last_order_symbol ?? "-"} detail={agentOperations?.last_order_status ?? "None"} />
        <StatCard label="AI Automation" value={agentReadiness?.automation_ready ? "Ready" : "Blocked"} detail={agentReadiness?.automation_reason} />
        <StatCard label="Paper Auto" value={agentReadiness?.paper_auto_ready ? "Ready" : "Off"} detail={agentReadiness?.paper_auto_reason} />
        <StatCard label="Auto Policy" value={automationPolicy?.automation_mode ?? "manual_approval"} detail={`min ${automationPolicy?.min_confidence ?? 0.75} / max $${automationPolicy?.max_order_amount_usd.toFixed(2) ?? "50.00"}`} />
        <StatCard label="Schedule" value={agentSchedule?.scheduler_enabled ? "Enabled" : "Off"} detail={agentSchedule?.due ? "Due now" : `${agentSchedule?.minutes_until_next_run ?? 0} min`} />
        <StatCard label="Market Window" value={agentSchedule?.market_open_now ? "Open" : "Closed"} detail={`${agentSchedule?.market_session ?? "unknown"} · ${agentSchedule?.market_open_time ?? "09:30"}-${agentSchedule?.market_close_time ?? "16:00"}`} />
        <StatCard label="Schedule Guard" value={(agentSchedule?.blockers ?? []).length ? "Blocked" : "Ready"} detail={(agentSchedule?.blockers ?? []).join(" / ") || `${agentSchedule?.interval_minutes ?? 60} min interval`} />
        <StatCard label="LLM Mode" value={agentReadiness?.llm_mode ?? "unknown"} detail={(agentReadiness?.llm_blockers ?? []).join(" / ") || "Real LLM ready"} />
        <StatCard label="Live Orders" value={liveReadiness?.live_order_ready ? "Ready" : "Blocked"} detail={liveReadiness?.execution_mode ?? "Unknown"} />
        <StatCard label="Candidates" value={`${agentReadiness?.candidate_symbols.length ?? 0}`} detail={`${agentReadiness?.candidate_symbols.join(", ") || "None"} / max ${agentReadiness?.max_candidates_per_run ?? 3}`} />
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
        <h3>Candidate Queue</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Score</th>
                <th>Reason</th>
                <th>Change</th>
                <th>Volume</th>
              </tr>
            </thead>
            <tbody>
              {(agentReadiness?.candidate_details ?? []).map((candidate) => (
                <tr key={candidate.symbol}>
                  <td>{candidate.symbol}</td>
                  <td>{candidate.score.toFixed(2)}</td>
                  <td>{candidate.reason}</td>
                  <td>{candidate.change_percent.toFixed(2)}%</td>
                  <td>{Math.round(candidate.volume).toLocaleString()}</td>
                </tr>
              ))}
              {!(agentReadiness?.candidate_details ?? []).length ? (
                <tr>
                  <td colSpan={5}>No candidates passed the pre-filter.</td>
                </tr>
              ) : null}
            </tbody>
          </table>
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
