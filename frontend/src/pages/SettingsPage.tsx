import { useEffect, useState } from "react";
import { api, BrokerStatus, LLMBudget, SafetySettings, SecurityReadiness } from "../api/client";

export function SettingsPage() {
  const [settings, setSettings] = useState<SafetySettings | null>(null);
  const [budget, setBudget] = useState<LLMBudget | null>(null);
  const [broker, setBroker] = useState<BrokerStatus | null>(null);
  const [security, setSecurity] = useState<SecurityReadiness | null>(null);

  useEffect(() => {
    Promise.all([api.getSafetySettings(), api.getLLMBudget(), api.getBrokerStatus(), api.getSecurityReadiness()])
      .then(([safety, llmBudget, brokerStatus, securityReadiness]) => {
        setSettings(safety);
        setBudget(llmBudget);
        setBroker(brokerStatus);
        setSecurity(securityReadiness);
      })
      .catch(() => setSettings(null));
  }, []);

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">Read Only</p>
          <h2>Safety Settings</h2>
        </div>
      </header>
      <dl className="settings-list">
        <div><dt>BROKER_PROVIDER</dt><dd>{settings?.broker_provider ?? "toss_securities"}</dd></div>
        <div><dt>Broker Status</dt><dd>{broker?.status_reason ?? "-"}</dd></div>
        <div><dt>Toss API Credentials Ready</dt><dd>{String(broker?.api_credentials_ready ?? false)}</dd></div>
        <div><dt>Toss Account ID Set</dt><dd>{String(broker?.has_account_id ?? false)}</dd></div>
        <div><dt>Toss Account Lookup Ready</dt><dd>{String(broker?.account_lookup_ready ?? false)}</dd></div>
        <div><dt>Toss Holdings Lookup Ready</dt><dd>{String(broker?.read_only_ready ?? false)}</dd></div>
        <div><dt>OpenAI Configured</dt><dd>{String(broker?.openai_configured ?? false)}</dd></div>
        <div><dt>Real LLM Ready</dt><dd>{String(broker?.real_llm_ready ?? false)}</dd></div>
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
        <div><dt>Daily Token Budget Left</dt><dd>{budget?.daily_tokens_remaining ?? 0}</dd></div>
        <div><dt>LLM_MODEL_DECISION</dt><dd>{settings?.llm_model_decision ?? "-"}</dd></div>
        <div><dt>LLM_INPUT_COST_PER_1M_TOKENS_USD</dt><dd>${settings?.llm_input_cost_per_1m_tokens_usd.toFixed(4) ?? "0.0000"}</dd></div>
        <div><dt>LLM_OUTPUT_COST_PER_1M_TOKENS_USD</dt><dd>${settings?.llm_output_cost_per_1m_tokens_usd.toFixed(4) ?? "0.0000"}</dd></div>
        <div><dt>OPENAI_TIMEOUT_SECONDS</dt><dd>{settings?.openai_timeout_seconds ?? 30}</dd></div>
        <div><dt>TOSS_BASE_URL</dt><dd>{settings?.toss_base_url ?? "-"}</dd></div>
        <div><dt>TOSS_TOKEN_PATH</dt><dd>{String(settings?.toss_token_path_configured ?? false)}</dd></div>
        <div><dt>TOSS_ACCOUNT_LIST_PATH</dt><dd>{String(settings?.toss_accounts_path_configured ?? false)}</dd></div>
        <div><dt>TOSS_HOLDINGS_PATH</dt><dd>{String(settings?.toss_positions_path_configured ?? false)}</dd></div>
        <div><dt>MARKET_SNAPSHOT_MAX_AGE_MINUTES</dt><dd>{settings?.market_snapshot_max_age_minutes ?? 30}</dd></div>
        <div><dt>Safe Public Demo</dt><dd>{String(security?.safe_for_public_demo ?? false)}</dd></div>
        <div><dt>Security Warnings</dt><dd>{security?.warnings.length ? security.warnings.join(" / ") : "None"}</dd></div>
        <div><dt>Next Actions</dt><dd>{security?.next_actions.length ? security.next_actions.join(" / ") : "None"}</dd></div>
      </dl>
    </section>
  );
}
