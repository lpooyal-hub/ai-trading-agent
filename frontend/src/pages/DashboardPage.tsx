import { useEffect, useState } from "react";
import { api, AgentAutomationPolicy, AgentDecision, AgentOperations, AgentReadiness, AgentSchedule, DemoStatus, LiveTradingReadiness, LLMBudget, LLMUsageSummary, MarketSnapshotStatus, PortfolioCostRecovery, PortfolioPerformance, PortfolioSummary, PortfolioSymbolPerformance, TradeOrder } from "../api/client";
import { DecisionTable } from "../components/DecisionTable";
import { OrderTable } from "../components/OrderTable";
import { StatCard } from "../components/StatCard";
import { formatKRW } from "../utils/currency";

function modeLabel(value: string | null | undefined) {
  if (!value) return "알 수 없음";
  const labels: Record<string, string> = {
    manual_approval: "수동 승인",
    paper_auto: "모의 자동",
    mock: "모의 응답",
    real_openai: "실제 OpenAI",
    unavailable: "사용 불가",
    unknown: "알 수 없음",
  };
  return labels[value] ?? value;
}

function statusText(value: boolean | null | undefined, positive = "준비됨", negative = "확인 필요") {
  if (value === null || value === undefined) return "알 수 없음";
  return value ? positive : negative;
}

function DashboardStatusPanel({
  title,
  items,
}: {
  title: string;
  items: { label: string; value: string; detail?: string }[];
}) {
  return (
    <section className="dashboard-status-panel">
      <h3>{title}</h3>
      <div className="dashboard-status-list">
        {items.map((item) => (
          <div key={item.label}>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
            {item.detail ? <small>{item.detail}</small> : null}
          </div>
        ))}
      </div>
    </section>
  );
}

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
    loadDashboardData().catch(() => setError("백엔드에 아직 연결할 수 없습니다."));
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
      .catch(() => setError("데모 데이터 생성에 실패했습니다."))
      .finally(() => setIsSeedingDemo(false));
  };

  const refreshDashboard = () => {
    if (isRefreshingDashboard) return;
    setError(null);
    setIsRefreshingDashboard(true);
    loadDashboardData()
      .catch(() => setError("대시보드 새로고침에 실패했습니다."))
      .finally(() => setIsRefreshingDashboard(false));
  };

  const runAgentOnce = () => {
    if (isRunningAgent) return;
    setError(null);
    setIsRunningAgent(true);
    api.runWorkflow()
      .then((run) => {
        if (run.decision_id) {
          onSelectDecision(run.decision_id);
          return;
        }
        return loadDashboardData();
      })
      .catch(() => setError("워크플로 실행에 실패했습니다."))
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
      .catch(() => setError("예약 워크플로 실행에 실패했습니다."))
      .finally(() => setIsRunningScheduledAgent(false));
  };

  const agentRunLabel = agentReadiness?.llm_mode === "mock" ? "모의 워크플로 실행" : "워크플로 실행";
  const topSymbol = symbolPerformance[0];

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">리서치 대시보드</p>
          <h2>AI 판단 리뷰</h2>
        </div>
        <div className="button-row">
          <button className="secondary-button" disabled={isRefreshingDashboard} onClick={refreshDashboard} type="button">
            {isRefreshingDashboard ? "새로고침 중..." : "새로고침"}
          </button>
          <button className="primary-button" disabled={isRunningAgent} onClick={runAgentOnce} type="button">
            {isRunningAgent ? "실행 중..." : agentRunLabel}
          </button>
          <button className="secondary-button" disabled={isRunningScheduledAgent} onClick={runScheduledAgent} type="button">
            {isRunningScheduledAgent ? "확인 중..." : "예약 조건 실행"}
          </button>
          <button
            className="secondary-button"
            disabled={isSeedingDemo || (demoStatus ? !demoStatus.demo_enabled : false)}
            onClick={seedDemoData}
            type="button"
          >
            {isSeedingDemo ? "생성 중..." : "데모 데이터 생성"}
          </button>
        </div>
      </header>
      {error ? <div className="notice">{error}</div> : null}
      <div className="stat-grid">
        <StatCard label="사용 가능 예산" value={formatKRW(summary?.available_budget_krw ?? 0)} />
        <StatCard label="투입 금액" value={formatKRW(summary?.invested_amount_krw ?? 0)} />
        <StatCard label="전체 손익" value={formatKRW(performance?.total_pnl_krw ?? 0)} detail={`${performance?.total_pnl_percent?.toFixed(2) ?? "0.00"}%`} />
        <StatCard label="승률" value={`${performance?.win_rate_percent?.toFixed(2) ?? "0.00"}%`} detail={`${performance?.winning_sell_count ?? 0}승 / ${performance?.losing_sell_count ?? 0}패`} />
        <StatCard label="모의 주문" value={`${performance?.simulated_order_count ?? 0}`} detail={`${performance?.buy_order_count ?? 0} 매수 / ${performance?.sell_order_count ?? 0} 매도`} />
        <StatCard label="실주문 제출" value={`${performance?.live_submitted_order_count ?? 0}`} detail={formatKRW(performance?.live_submitted_order_amount_krw ?? 0)} />
        <StatCard label="순손익" value={formatKRW(costRecovery?.net_after_llm_cost_krw ?? 0)} detail="LLM 비용 환산 반영" />
        <StatCard label="워크플로 준비" value={statusText(agentReadiness?.ready)} detail={agentReadiness?.reason} />
        <StatCard label="최근 판단" value={agentOperations?.last_decision_symbol ?? "-"} detail={agentOperations?.last_decision_status ?? "없음"} />
        <StatCard label="대기 판단" value={`${agentOperations?.pending_decision_count ?? 0}`} detail={`${agentOperations?.executable_decision_count ?? 0}개 실행 가능`} />
      </div>
      <div className="dashboard-status-grid">
        <DashboardStatusPanel
          title="에이전트 상태"
          items={[
            { label: "시장 데이터", value: statusText(marketStatus?.ready_for_agent, "준비됨", "미준비"), detail: marketStatus?.message },
            { label: "후보 종목", value: `${agentReadiness?.candidate_symbols?.length ?? 0}`, detail: agentReadiness?.candidate_symbols?.join(", ") || "없음" },
            { label: "자동화", value: statusText(agentReadiness?.automation_ready, "준비됨", "차단됨"), detail: agentReadiness?.automation_reason },
            { label: "모의 자동", value: statusText(agentReadiness?.paper_auto_ready, "준비됨", "꺼짐"), detail: agentReadiness?.paper_auto_reason },
          ]}
        />
        <DashboardStatusPanel
          title="LLM / 비용"
          items={[
            { label: "LLM 모드", value: modeLabel(agentReadiness?.llm_mode), detail: (agentReadiness?.llm_blockers ?? []).join(" / ") || "사용 가능" },
            { label: "오늘 호출", value: `${llmSummary?.today_calls ?? 0}`, detail: `잔여 ${llmBudget?.daily_calls_remaining ?? 0}회` },
            { label: "오늘 비용", value: `$${llmSummary?.today_estimated_cost_usd?.toFixed(4) ?? "0.0000"}`, detail: `잔여 $${llmBudget?.daily_cost_remaining_usd?.toFixed(4) ?? "0.0000"}` },
            { label: "평균 지연", value: `${Math.round(llmSummary?.average_latency_ms ?? 0)}ms`, detail: `오늘 ${llmSummary?.today_total_tokens ?? 0} 토큰` },
          ]}
        />
        <DashboardStatusPanel
          title="실행 정책"
          items={[
            { label: "자동화 정책", value: modeLabel(automationPolicy?.automation_mode ?? "manual_approval"), detail: `최소 ${automationPolicy?.min_confidence ?? 0.75} / 최대 ${formatKRW(automationPolicy?.max_order_amount_krw ?? 65000)}` },
            { label: "스케줄", value: agentSchedule?.scheduler_enabled ? "켜짐" : "꺼짐", detail: agentSchedule?.due ? "지금 실행 가능" : `${agentSchedule?.minutes_until_next_run ?? 0}분 후` },
            { label: "실주문", value: statusText(liveReadiness?.live_order_ready, "준비됨", "차단됨"), detail: modeLabel(liveReadiness?.execution_mode) },
            { label: "상위 종목", value: topSymbol?.symbol ?? "-", detail: topSymbol ? `${formatKRW(topSymbol.realized_pnl_krw)} 실현` : "실현 거래 없음" },
          ]}
        />
        <DashboardStatusPanel
          title="데모 / 운영"
          items={[
            { label: "데모 모드", value: demoStatus?.demo_enabled ? "켜짐" : "꺼짐", detail: demoStatus?.demo_reason },
            { label: "데모 데이터", value: `${demoStatus?.decisions ?? 0}`, detail: `${demoStatus?.orders ?? 0}개 주문` },
            { label: "최근 주문", value: agentOperations?.last_order_symbol ?? "-", detail: agentOperations?.last_order_status ?? "없음" },
            { label: "봇 포지션", value: `${summary?.bot_position_count ?? 0}`, detail: `운용 한도 ${formatKRW(summary?.bot_capital_limit_krw ?? 300000)}` },
          ]}
        />
      </div>
      <section>
        <h3>후보 큐</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>종목</th>
                <th>점수</th>
                <th>사유</th>
                <th>등락률</th>
                <th>거래량</th>
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
                  <td colSpan={5}>사전 필터를 통과한 후보가 없습니다.</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
      <section>
        <h3>최근 판단</h3>
        <DecisionTable decisions={decisions} onSelect={onSelectDecision} />
      </section>
      <section>
        <h3>최근 모의 주문</h3>
        <OrderTable orders={orders} />
      </section>
    </section>
  );
}
