import { useEffect, useState } from "react";
import { api, BrokerStatus, LLMBudget, SafetySettings } from "../api/client";

export function SettingsPage() {
  const [settings, setSettings] = useState<SafetySettings | null>(null);
  const [budget, setBudget] = useState<LLMBudget | null>(null);
  const [broker, setBroker] = useState<BrokerStatus | null>(null);

  useEffect(() => {
    Promise.all([api.getSafetySettings(), api.getLLMBudget(), api.getBrokerStatus()])
      .then(([safety, llmBudget, brokerStatus]) => {
        setSettings(safety);
        setBudget(llmBudget);
        setBroker(brokerStatus);
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
        <div><dt>Toss Credentials Ready</dt><dd>{String(broker?.credentials_ready ?? false)}</dd></div>
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
        <div><dt>OPENAI_TIMEOUT_SECONDS</dt><dd>{settings?.openai_timeout_seconds ?? 30}</dd></div>
      </dl>
    </section>
  );
}
