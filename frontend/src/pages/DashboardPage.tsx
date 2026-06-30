import { useEffect, useState } from "react";
import { api, AgentAutomationPolicy, AgentDecision, AgentOperations, AgentReadiness, AgentSchedule, DemoStatus, LiveTradingReadiness, LLMBudget, LLMUsageSummary, MarketSnapshotStatus, PortfolioCostRecovery, PortfolioPerformance, PortfolioSummary, PortfolioSymbolPerformance, TradeOrder } from "../api/client";
import { DecisionTable } from "../components/DecisionTable";
import { OrderTable } from "../components/OrderTable";
import { StatCard } from "../components/StatCard";

function modeLabel(value: string | null | undefined) {
  if (!value) return "알 수 없음";
  const labels: Record<string, string> = {
    manual_approval: "수동 승인",
    paper_auto: "Paper 자동",
    mock: "Mock",
    real_openai: "실제 OpenAI",
    unavailable: "사용 불가",
    unknown: "알 수 없음",
  };
  return labels[value] ?? value;
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
    api.runAgentOnce()
      .then((decision) => onSelectDecision(decision.id))
      .catch(() => setError("에이전트 실행에 실패했습니다."))
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
      .catch(() => setError("예약 에이전트 실행에 실패했습니다."))
      .finally(() => setIsRunningScheduledAgent(false));
  };

  const agentRunLabel = agentReadiness?.llm_mode === "mock" ? "Mock 에이전트 실행" : "에이전트 실행";

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
        <StatCard label="봇 운용 한도" value={`$${summary?.bot_capital_limit_usd.toFixed(2) ?? "250.00"}`} />
        <StatCard label="사용 가능 예산" value={`$${summary?.available_budget_usd.toFixed(2) ?? "0.00"}`} />
        <StatCard label="투입 금액" value={`$${summary?.invested_amount_usd.toFixed(2) ?? "0.00"}`} />
        <StatCard label="전체 손익" value={`$${performance?.total_pnl_usd.toFixed(2) ?? "0.00"}`} detail={`${performance?.total_pnl_percent.toFixed(2) ?? "0.00"}%`} />
        <StatCard label="실현 손익" value={`$${performance?.realized_pnl_usd.toFixed(2) ?? "0.00"}`} />
        <StatCard label="LLM 비용 반영 후" value={`$${costRecovery?.net_after_llm_cost_usd.toFixed(4) ?? "0.0000"}`} detail={`월 LLM $${costRecovery?.monthly_llm_cost_usd.toFixed(4) ?? "0.0000"}`} />
        <StatCard label="LLM 비용 회수" value={costRecovery?.llm_cost_recovery_ratio === null || costRecovery?.llm_cost_recovery_ratio === undefined ? "-" : `${costRecovery.llm_cost_recovery_ratio.toFixed(2)}x`} detail={costRecovery?.llm_cost_covered === null || costRecovery?.llm_cost_covered === undefined ? "아직 LLM 비용 없음" : costRecovery.llm_cost_covered ? "모의 손익이 비용 상회" : "모의 손익이 비용 미달"} />
        <StatCard label="실현 기준 순손익" value={`$${costRecovery?.realized_net_after_llm_cost_usd.toFixed(4) ?? "0.0000"}`} detail={costRecovery?.realized_llm_cost_covered === null || costRecovery?.realized_llm_cost_covered === undefined ? "아직 LLM 비용 없음" : costRecovery.realized_llm_cost_covered ? "실현 손익이 비용 상회" : "실현 손익이 비용 미달"} />
        <StatCard label="승률" value={`${performance?.win_rate_percent.toFixed(2) ?? "0.00"}%`} detail={`${performance?.winning_sell_count ?? 0}승 / ${performance?.losing_sell_count ?? 0}패`} />
        <StatCard
          label="상위 종목"
          value={symbolPerformance[0]?.symbol ?? "-"}
          detail={symbolPerformance[0] ? `$${symbolPerformance[0].realized_pnl_usd.toFixed(2)} 실현` : "실현 거래 없음"}
        />
        <StatCard label="모의 주문" value={`${performance?.simulated_order_count ?? 0}`} detail={`${performance?.buy_order_count ?? 0} 매수 / ${performance?.sell_order_count ?? 0} 매도`} />
        <StatCard label="봇 포지션" value={`${summary?.bot_position_count ?? 0}`} />
        <StatCard label="오늘 LLM 호출" value={`${llmSummary?.today_calls ?? 0}`} />
        <StatCard label="남은 LLM 호출" value={`${llmBudget?.daily_calls_remaining ?? 0}`} detail={`한도 ${llmBudget?.daily_call_limit ?? 0} / 쿨다운 ${llmBudget?.cooldown_remaining_minutes ?? 0}분`} />
        <StatCard label="오늘 토큰" value={`${llmSummary?.today_total_tokens ?? 0}`} />
        <StatCard label="오늘 LLM 비용" value={`$${llmSummary?.today_estimated_cost_usd.toFixed(4) ?? "0.0000"}`} />
        <StatCard label="월 LLM 비용" value={`$${llmSummary?.monthly_estimated_cost_usd.toFixed(4) ?? "0.0000"}`} />
        <StatCard label="남은 LLM 예산" value={`$${llmBudget?.daily_cost_remaining_usd.toFixed(4) ?? "0.0000"}`} />
        <StatCard label="평균 지연" value={`${Math.round(llmSummary?.average_latency_ms ?? 0)}ms`} />
        <StatCard label="시장 준비" value={marketStatus?.ready_for_agent ? "준비됨" : "미준비"} detail={marketStatus?.message} />
        <StatCard label="신선한 종목" value={`${marketStatus?.fresh_symbol_count ?? 0}`} detail={`${marketStatus?.missing_symbol_count ?? 0}개 누락`} />
        <StatCard label="에이전트 점검" value={agentReadiness?.ready ? "준비됨" : "확인 필요"} detail={agentReadiness?.reason} />
        <StatCard label="최근 판단" value={agentOperations?.last_decision_symbol ?? "-"} detail={agentOperations?.last_decision_status ?? "없음"} />
        <StatCard label="대기 판단" value={`${agentOperations?.pending_decision_count ?? 0}`} detail={`${agentOperations?.executable_decision_count ?? 0}개 실행 가능`} />
        <StatCard label="최근 주문" value={agentOperations?.last_order_symbol ?? "-"} detail={agentOperations?.last_order_status ?? "없음"} />
        <StatCard label="AI 자동화" value={agentReadiness?.automation_ready ? "준비됨" : "차단됨"} detail={agentReadiness?.automation_reason} />
        <StatCard label="Paper 자동매매" value={agentReadiness?.paper_auto_ready ? "준비됨" : "꺼짐"} detail={agentReadiness?.paper_auto_reason} />
        <StatCard label="자동화 정책" value={modeLabel(automationPolicy?.automation_mode ?? "manual_approval")} detail={`최소 ${automationPolicy?.min_confidence ?? 0.75} / 최대 $${automationPolicy?.max_order_amount_usd.toFixed(2) ?? "50.00"}`} />
        <StatCard label="스케줄" value={agentSchedule?.scheduler_enabled ? "켜짐" : "꺼짐"} detail={agentSchedule?.due ? "지금 실행 가능" : `${agentSchedule?.minutes_until_next_run ?? 0}분 후`} />
        <StatCard label="장 상태" value={agentSchedule?.market_open_now ? "열림" : "닫힘"} detail={`${modeLabel(agentSchedule?.market_session)} · ${agentSchedule?.market_open_time ?? "09:30"}-${agentSchedule?.market_close_time ?? "16:00"}`} />
        <StatCard label="스케줄 가드" value={(agentSchedule?.blockers ?? []).length ? "차단됨" : "준비됨"} detail={(agentSchedule?.blockers ?? []).join(" / ") || `${agentSchedule?.interval_minutes ?? 60}분 간격`} />
        <StatCard label="LLM 모드" value={modeLabel(agentReadiness?.llm_mode)} detail={(agentReadiness?.llm_blockers ?? []).join(" / ") || "실제 LLM 준비됨"} />
        <StatCard label="실주문" value={liveReadiness?.live_order_ready ? "준비됨" : "차단됨"} detail={modeLabel(liveReadiness?.execution_mode)} />
        <StatCard label="후보 종목" value={`${agentReadiness?.candidate_symbols.length ?? 0}`} detail={`${agentReadiness?.candidate_symbols.join(", ") || "없음"} / 최대 ${agentReadiness?.max_candidates_per_run ?? 3}`} />
        <StatCard
          label="데모 모드"
          value={demoStatus?.demo_enabled ? "켜짐" : "꺼짐"}
          detail={demoStatus?.demo_reason}
        />
        <StatCard label="데모 데이터" value={`${demoStatus?.decisions ?? 0}`} detail={`${demoStatus?.orders ?? 0}개 주문`} />
      </div>
      <section>
        <h3>감시 종목</h3>
        <div className="symbol-list">
          {(summary?.active_universe ?? []).map((symbol) => <span key={symbol}>{symbol}</span>)}
        </div>
      </section>
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
        <h3>상위 종목 성과</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>종목</th>
                <th>실현 손익</th>
                <th>거래</th>
                <th>승률</th>
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
                  <td colSpan={4}>아직 종목별 성과가 없습니다.</td>
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
