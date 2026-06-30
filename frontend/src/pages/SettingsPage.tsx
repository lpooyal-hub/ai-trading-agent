import { useEffect, useState } from "react";
import { api, BrokerStatus, LiveTradingReadiness, LLMBudget, LLMReadiness, LLMSmokeTest, SafetySettings, SecurityReadiness } from "../api/client";
import { statusLabel } from "../utils/labels";

function boolLabel(value: boolean | undefined, fallback = false) {
  return (value ?? fallback) ? "예" : "아니오";
}

function listOrNone(values: string[] | undefined) {
  return values?.length ? values.join(" / ") : "없음";
}

export function SettingsPage() {
  const [settings, setSettings] = useState<SafetySettings | null>(null);
  const [budget, setBudget] = useState<LLMBudget | null>(null);
  const [broker, setBroker] = useState<BrokerStatus | null>(null);
  const [security, setSecurity] = useState<SecurityReadiness | null>(null);
  const [liveReadiness, setLiveReadiness] = useState<LiveTradingReadiness | null>(null);
  const [llmReadiness, setLlmReadiness] = useState<LLMReadiness | null>(null);
  const [llmSmokeTest, setLlmSmokeTest] = useState<LLMSmokeTest | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isTestingLLM, setIsTestingLLM] = useState(false);

  const refreshSettings = () => {
    if (isRefreshing) return;
    setIsRefreshing(true);
    Promise.all([
      api.getSafetySettings(),
      api.getLLMBudget(),
      api.getBrokerStatus(),
      api.getSecurityReadiness(),
      api.getLiveTradingReadiness(),
      api.getLLMReadiness(),
    ])
      .then(([safety, llmBudget, brokerStatus, securityReadiness, liveTradingReadiness, llmReadinessStatus]) => {
        setSettings(safety);
        setBudget(llmBudget);
        setBroker(brokerStatus);
        setSecurity(securityReadiness);
        setLiveReadiness(liveTradingReadiness);
        setLlmReadiness(llmReadinessStatus);
      })
      .catch(() => setSettings(null))
      .finally(() => setIsRefreshing(false));
  };

  const runLLMSmokeTest = () => {
    if (isTestingLLM) return;
    setIsTestingLLM(true);
    setLlmSmokeTest(null);
    api.runLLMSmokeTest()
      .then((result) => {
        setLlmSmokeTest(result);
        return refreshSettings();
      })
      .catch((error) => {
        setLlmSmokeTest({
          success: false,
          model: "unknown",
          llm_mode: "unknown",
          latency_ms: 0,
          prompt_tokens: 0,
          completion_tokens: 0,
          total_tokens: 0,
          estimated_cost_usd: 0,
          usage_id: null,
          message: error instanceof Error ? error.message : "LLM 연결 테스트에 실패했습니다.",
        });
      })
      .finally(() => setIsTestingLLM(false));
  };

  useEffect(() => {
    refreshSettings();
  }, []);

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">읽기 전용</p>
          <h2>안전 설정</h2>
        </div>
        <div className="button-row">
          <button className="secondary-button" disabled={isTestingLLM} onClick={runLLMSmokeTest} type="button">
            {isTestingLLM ? "테스트 중..." : "LLM 연결 테스트"}
          </button>
          <button className="secondary-button" disabled={isRefreshing} onClick={refreshSettings} type="button">
            {isRefreshing ? "새로고침 중..." : "새로고침"}
          </button>
        </div>
      </header>
      {llmSmokeTest ? (
        <div className="notice">
          {llmSmokeTest.success ? "LLM 연결 테스트 성공" : "LLM 연결 테스트 실패"}: {llmSmokeTest.message}
          {" "}· {llmSmokeTest.model} · {llmSmokeTest.total_tokens} 토큰 · ${llmSmokeTest.estimated_cost_usd.toFixed(6)}
        </div>
      ) : null}
      <dl className="settings-list">
        <div><dt>브로커 제공자 (BROKER_PROVIDER)</dt><dd>{settings?.broker_provider ?? "toss_securities"}</dd></div>
        <div><dt>브로커 상태</dt><dd>{broker?.status_reason ?? "-"}</dd></div>
        <div><dt>토스 API 인증 정보</dt><dd>{boolLabel(broker?.api_credentials_ready)}</dd></div>
        <div><dt>토스 계좌 ID</dt><dd>{boolLabel(broker?.has_account_id)}</dd></div>
        <div><dt>토스 계좌 조회</dt><dd>{boolLabel(broker?.account_lookup_ready)}</dd></div>
        <div><dt>토스 잔고 조회</dt><dd>{boolLabel(broker?.read_only_ready)}</dd></div>
        <div><dt>OpenAI 설정</dt><dd>{boolLabel(broker?.openai_configured)}</dd></div>
        <div><dt>실제 LLM 준비</dt><dd>{boolLabel(broker?.real_llm_ready)}</dd></div>
        <div><dt>LLM 모드</dt><dd>{llmReadiness?.llm_mode ?? "알 수 없음"}</dd></div>
        <div><dt>LLM 차단 사유</dt><dd>{listOrNone(llmReadiness?.blockers)}</dd></div>
        <div><dt>LLM 다음 조치</dt><dd>{listOrNone(llmReadiness?.next_actions)}</dd></div>
        <div><dt>실거래 준비</dt><dd>{boolLabel(broker?.live_ready)}</dd></div>
        <div><dt>DRY_RUN</dt><dd>{boolLabel(settings?.dry_run, true)}</dd></div>
        <div><dt>LIVE_TRADING_ENABLED</dt><dd>{boolLabel(settings?.live_trading_enabled)}</dd></div>
        <div><dt>USE_MOCK_DATA</dt><dd>{boolLabel(settings?.use_mock_data, true)}</dd></div>
        <div><dt>BOT_CAPITAL_LIMIT_USD</dt><dd>${settings?.bot_capital_limit_usd.toFixed(2) ?? "250.00"}</dd></div>
        <div><dt>MAX_ORDER_AMOUNT_USD</dt><dd>${settings?.max_order_amount_usd.toFixed(2) ?? "100.00"}</dd></div>
        <div><dt>MAX_SYMBOL_EXPOSURE_PERCENT</dt><dd>{settings?.max_symbol_exposure_percent.toFixed(1) ?? "40.0"}%</dd></div>
        <div><dt>MAX_DAILY_TRADES</dt><dd>{settings?.max_daily_trades ?? 5}</dd></div>
        <div><dt>허용 종목</dt><dd>{settings?.allowed_symbols.join(", ") ?? "-"}</dd></div>
        <div><dt>금지 키워드</dt><dd>{settings?.forbidden_keywords.join(", ") ?? "-"}</dd></div>
        <div><dt>보호 종목</dt><dd>{settings?.protected_symbols.join(", ") ?? "-"}</dd></div>
        <div><dt>일일 LLM 예산 잔여</dt><dd>${budget?.daily_cost_remaining_usd.toFixed(4) ?? "0.0000"}</dd></div>
        <div><dt>일일 LLM 호출 잔여</dt><dd>{budget?.daily_calls_remaining ?? 0} / {budget?.daily_call_limit ?? 0}</dd></div>
        <div><dt>일일 토큰 잔여</dt><dd>{budget?.daily_tokens_remaining ?? 0}</dd></div>
        <div><dt>LLM 쿨다운</dt><dd>{budget?.cooldown_remaining_minutes ?? 0}분 남음 / {settings?.llm_min_minutes_between_calls ?? 60}분 간격</dd></div>
        <div><dt>LLM_MAX_CANDIDATES_PER_RUN</dt><dd>{settings?.llm_max_candidates_per_run ?? 3}</dd></div>
        <div><dt>LLM_MODEL_DECISION</dt><dd>{settings?.llm_model_decision ?? "-"}</dd></div>
        <div><dt>LLM_INPUT_COST_PER_1M_TOKENS_USD</dt><dd>${settings?.llm_input_cost_per_1m_tokens_usd.toFixed(4) ?? "0.0000"}</dd></div>
        <div><dt>LLM_OUTPUT_COST_PER_1M_TOKENS_USD</dt><dd>${settings?.llm_output_cost_per_1m_tokens_usd.toFixed(4) ?? "0.0000"}</dd></div>
        <div><dt>OPENAI_TIMEOUT_SECONDS</dt><dd>{settings?.openai_timeout_seconds ?? 30}</dd></div>
        <div><dt>AGENT_AUTOMATION_ENABLED</dt><dd>{boolLabel(settings?.agent_automation_enabled)}</dd></div>
        <div><dt>AGENT_AUTOMATION_MODE</dt><dd>{settings?.agent_automation_mode ?? "manual_approval"}</dd></div>
        <div><dt>PAPER_AUTO_ENABLED</dt><dd>{boolLabel(settings?.paper_auto_enabled)}</dd></div>
        <div><dt>AGENT_AUTO_EXECUTE_MIN_CONFIDENCE</dt><dd>{settings?.agent_auto_execute_min_confidence ?? 0.75}</dd></div>
        <div><dt>AGENT_AUTO_EXECUTE_MAX_ORDER_AMOUNT_USD</dt><dd>${settings?.agent_auto_execute_max_order_amount_usd.toFixed(2) ?? "50.00"}</dd></div>
        <div><dt>AGENT_SCHEDULER_ENABLED</dt><dd>{boolLabel(settings?.agent_scheduler_enabled)}</dd></div>
        <div><dt>AGENT_SCHEDULER_INTERVAL_MINUTES</dt><dd>{settings?.agent_scheduler_interval_minutes ?? 60}</dd></div>
        <div><dt>AGENT_SCHEDULER_MARKET_HOURS_ONLY</dt><dd>{boolLabel(settings?.agent_scheduler_market_hours_only, true)}</dd></div>
        <div><dt>AGENT_MARKET_TIMEZONE</dt><dd>{settings?.agent_market_timezone ?? "America/New_York"}</dd></div>
        <div><dt>AGENT_MARKET_WINDOW</dt><dd>{settings?.agent_market_open_time ?? "09:30"}-{settings?.agent_market_close_time ?? "16:00"}</dd></div>
        <div><dt>AGENT_MARKET_CLOSED_DATES</dt><dd>{(settings?.agent_market_closed_dates ?? []).length ? settings?.agent_market_closed_dates.join(", ") : "-"}</dd></div>
        <div><dt>TOSS_BASE_URL</dt><dd>{settings?.toss_base_url ?? "-"}</dd></div>
        <div><dt>TOSS_TOKEN_PATH</dt><dd>{boolLabel(settings?.toss_token_path_configured)}</dd></div>
        <div><dt>TOSS_ACCOUNT_LIST_PATH</dt><dd>{boolLabel(settings?.toss_accounts_path_configured)}</dd></div>
        <div><dt>TOSS_HOLDINGS_PATH</dt><dd>{boolLabel(settings?.toss_positions_path_configured)}</dd></div>
        <div><dt>MARKET_SNAPSHOT_MAX_AGE_MINUTES</dt><dd>{settings?.market_snapshot_max_age_minutes ?? 30}</dd></div>
        <div><dt>공개 데모 안전 상태</dt><dd>{boolLabel(security?.safe_for_public_demo)}</dd></div>
        <div><dt>실주문 준비</dt><dd>{boolLabel(liveReadiness?.live_order_ready)}</dd></div>
        <div><dt>실주문 실행 모드</dt><dd>{statusLabel(liveReadiness?.execution_mode)}</dd></div>
        <div><dt>실주문 구현 상태</dt><dd>{liveReadiness?.live_order_implementation ?? "-"}</dd></div>
        <div><dt>실주문 차단 사유</dt><dd>{listOrNone(liveReadiness?.blockers)}</dd></div>
        <div><dt>실주문 어댑터 체크리스트</dt><dd>{listOrNone(liveReadiness?.adapter_checklist)}</dd></div>
        <div><dt>보안 경고</dt><dd>{listOrNone(security?.warnings)}</dd></div>
        <div><dt>다음 조치</dt><dd>{listOrNone(security?.next_actions)}</dd></div>
      </dl>
    </section>
  );
}
