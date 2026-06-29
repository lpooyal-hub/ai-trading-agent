import { useEffect, useState } from "react";
import { api, BrokerStatus, LiveTradingReadiness, LLMBudget, LLMReadiness, LLMSmokeTest, SafetySettings, SecurityReadiness } from "../api/client";

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
          message: error instanceof Error ? error.message : "LLM smoke test failed.",
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
          <p className="eyebrow">Read Only</p>
          <h2>Safety Settings</h2>
        </div>
        <div className="button-row">
          <button className="secondary-button" disabled={isTestingLLM} onClick={runLLMSmokeTest} type="button">
            {isTestingLLM ? "Testing..." : "LLM Smoke Test"}
          </button>
          <button className="secondary-button" disabled={isRefreshing} onClick={refreshSettings} type="button">
            {isRefreshing ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      </header>
      {llmSmokeTest ? (
        <div className="notice">
          {llmSmokeTest.success ? "LLM smoke test succeeded" : "LLM smoke test failed"}: {llmSmokeTest.message}
          {" "}· {llmSmokeTest.model} · {llmSmokeTest.total_tokens} tokens · ${llmSmokeTest.estimated_cost_usd.toFixed(6)}
        </div>
      ) : null}
      <dl className="settings-list">
        <div><dt>BROKER_PROVIDER</dt><dd>{settings?.broker_provider ?? "toss_securities"}</dd></div>
        <div><dt>Broker Status</dt><dd>{broker?.status_reason ?? "-"}</dd></div>
        <div><dt>Toss API Credentials Ready</dt><dd>{String(broker?.api_credentials_ready ?? false)}</dd></div>
        <div><dt>Toss Account ID Set</dt><dd>{String(broker?.has_account_id ?? false)}</dd></div>
        <div><dt>Toss Account Lookup Ready</dt><dd>{String(broker?.account_lookup_ready ?? false)}</dd></div>
        <div><dt>Toss Holdings Lookup Ready</dt><dd>{String(broker?.read_only_ready ?? false)}</dd></div>
        <div><dt>OpenAI Configured</dt><dd>{String(broker?.openai_configured ?? false)}</dd></div>
        <div><dt>Real LLM Ready</dt><dd>{String(broker?.real_llm_ready ?? false)}</dd></div>
        <div><dt>LLM Mode</dt><dd>{llmReadiness?.llm_mode ?? "unknown"}</dd></div>
        <div><dt>LLM Blockers</dt><dd>{llmReadiness?.blockers.length ? llmReadiness.blockers.join(" / ") : "None"}</dd></div>
        <div><dt>LLM Next Actions</dt><dd>{llmReadiness?.next_actions.length ? llmReadiness.next_actions.join(" / ") : "None"}</dd></div>
        <div><dt>Live Ready</dt><dd>{String(broker?.live_ready ?? false)}</dd></div>
        <div><dt>DRY_RUN</dt><dd>{String(settings?.dry_run ?? true)}</dd></div>
        <div><dt>LIVE_TRADING_ENABLED</dt><dd>{String(settings?.live_trading_enabled ?? false)}</dd></div>
        <div><dt>USE_MOCK_DATA</dt><dd>{String(settings?.use_mock_data ?? true)}</dd></div>
        <div><dt>BOT_CAPITAL_LIMIT_USD</dt><dd>${settings?.bot_capital_limit_usd.toFixed(2) ?? "250.00"}</dd></div>
        <div><dt>MAX_ORDER_AMOUNT_USD</dt><dd>${settings?.max_order_amount_usd.toFixed(2) ?? "100.00"}</dd></div>
        <div><dt>MAX_DAILY_TRADES</dt><dd>{settings?.max_daily_trades ?? 5}</dd></div>
        <div><dt>Allowed Symbols</dt><dd>{settings?.allowed_symbols.join(", ") ?? "-"}</dd></div>
        <div><dt>Forbidden Keywords</dt><dd>{settings?.forbidden_keywords.join(", ") ?? "-"}</dd></div>
        <div><dt>Protected Symbols</dt><dd>{settings?.protected_symbols.join(", ") ?? "-"}</dd></div>
        <div><dt>Daily LLM Budget Left</dt><dd>${budget?.daily_cost_remaining_usd.toFixed(4) ?? "0.0000"}</dd></div>
        <div><dt>Daily LLM Calls Left</dt><dd>{budget?.daily_calls_remaining ?? 0} / {budget?.daily_call_limit ?? 0}</dd></div>
        <div><dt>Daily Token Budget Left</dt><dd>{budget?.daily_tokens_remaining ?? 0}</dd></div>
        <div><dt>LLM Cooldown</dt><dd>{budget?.cooldown_remaining_minutes ?? 0} min left / {settings?.llm_min_minutes_between_calls ?? 60} min gap</dd></div>
        <div><dt>LLM_MAX_CANDIDATES_PER_RUN</dt><dd>{settings?.llm_max_candidates_per_run ?? 3}</dd></div>
        <div><dt>LLM_MODEL_DECISION</dt><dd>{settings?.llm_model_decision ?? "-"}</dd></div>
        <div><dt>LLM_INPUT_COST_PER_1M_TOKENS_USD</dt><dd>${settings?.llm_input_cost_per_1m_tokens_usd.toFixed(4) ?? "0.0000"}</dd></div>
        <div><dt>LLM_OUTPUT_COST_PER_1M_TOKENS_USD</dt><dd>${settings?.llm_output_cost_per_1m_tokens_usd.toFixed(4) ?? "0.0000"}</dd></div>
        <div><dt>OPENAI_TIMEOUT_SECONDS</dt><dd>{settings?.openai_timeout_seconds ?? 30}</dd></div>
        <div><dt>AGENT_AUTOMATION_ENABLED</dt><dd>{String(settings?.agent_automation_enabled ?? false)}</dd></div>
        <div><dt>AGENT_AUTOMATION_MODE</dt><dd>{settings?.agent_automation_mode ?? "manual_approval"}</dd></div>
        <div><dt>PAPER_AUTO_ENABLED</dt><dd>{String(settings?.paper_auto_enabled ?? false)}</dd></div>
        <div><dt>AGENT_AUTO_EXECUTE_MIN_CONFIDENCE</dt><dd>{settings?.agent_auto_execute_min_confidence ?? 0.75}</dd></div>
        <div><dt>AGENT_AUTO_EXECUTE_MAX_ORDER_AMOUNT_USD</dt><dd>${settings?.agent_auto_execute_max_order_amount_usd.toFixed(2) ?? "50.00"}</dd></div>
        <div><dt>AGENT_SCHEDULER_ENABLED</dt><dd>{String(settings?.agent_scheduler_enabled ?? false)}</dd></div>
        <div><dt>AGENT_SCHEDULER_INTERVAL_MINUTES</dt><dd>{settings?.agent_scheduler_interval_minutes ?? 60}</dd></div>
        <div><dt>AGENT_SCHEDULER_MARKET_HOURS_ONLY</dt><dd>{String(settings?.agent_scheduler_market_hours_only ?? true)}</dd></div>
        <div><dt>AGENT_MARKET_TIMEZONE</dt><dd>{settings?.agent_market_timezone ?? "America/New_York"}</dd></div>
        <div><dt>AGENT_MARKET_WINDOW</dt><dd>{settings?.agent_market_open_time ?? "09:30"}-{settings?.agent_market_close_time ?? "16:00"}</dd></div>
        <div><dt>AGENT_MARKET_CLOSED_DATES</dt><dd>{(settings?.agent_market_closed_dates ?? []).length ? settings?.agent_market_closed_dates.join(", ") : "-"}</dd></div>
        <div><dt>TOSS_BASE_URL</dt><dd>{settings?.toss_base_url ?? "-"}</dd></div>
        <div><dt>TOSS_TOKEN_PATH</dt><dd>{String(settings?.toss_token_path_configured ?? false)}</dd></div>
        <div><dt>TOSS_ACCOUNT_LIST_PATH</dt><dd>{String(settings?.toss_accounts_path_configured ?? false)}</dd></div>
        <div><dt>TOSS_HOLDINGS_PATH</dt><dd>{String(settings?.toss_positions_path_configured ?? false)}</dd></div>
        <div><dt>MARKET_SNAPSHOT_MAX_AGE_MINUTES</dt><dd>{settings?.market_snapshot_max_age_minutes ?? 30}</dd></div>
        <div><dt>Safe Public Demo</dt><dd>{String(security?.safe_for_public_demo ?? false)}</dd></div>
        <div><dt>Live Order Ready</dt><dd>{String(liveReadiness?.live_order_ready ?? false)}</dd></div>
        <div><dt>Live Execution Mode</dt><dd>{liveReadiness?.execution_mode ?? "-"}</dd></div>
        <div><dt>Live Order Implementation</dt><dd>{liveReadiness?.live_order_implementation ?? "-"}</dd></div>
        <div><dt>Live Blockers</dt><dd>{liveReadiness?.blockers.length ? liveReadiness.blockers.join(" / ") : "None"}</dd></div>
        <div><dt>Live Adapter Checklist</dt><dd>{liveReadiness?.adapter_checklist.length ? liveReadiness.adapter_checklist.join(" / ") : "None"}</dd></div>
        <div><dt>Security Warnings</dt><dd>{security?.warnings.length ? security.warnings.join(" / ") : "None"}</dd></div>
        <div><dt>Next Actions</dt><dd>{security?.next_actions.length ? security.next_actions.join(" / ") : "None"}</dd></div>
      </dl>
    </section>
  );
}
