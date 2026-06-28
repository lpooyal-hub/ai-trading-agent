import { useEffect, useState } from "react";
import { api, BotPosition, LegacyPosition, PortfolioSummary } from "../api/client";
import { PositionTable } from "../components/PositionTable";
import { StatCard } from "../components/StatCard";

export function PortfolioPage() {
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [botPositions, setBotPositions] = useState<BotPosition[]>([]);
  const [legacyPositions, setLegacyPositions] = useState<LegacyPosition[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const legacySyncBlocked = Boolean(summary && summary.bot_position_count > 0);

  const loadPortfolioData = () => (
    Promise.all([api.getPortfolioSummary(), api.getBotPositions(), api.getLegacyPositions()])
      .then(([portfolio, bot, legacy]) => {
        setSummary(portfolio);
        setBotPositions(bot);
        setLegacyPositions(legacy);
      })
  );

  useEffect(() => {
    loadPortfolioData()
      .catch(() => {
        setBotPositions([]);
        setLegacyPositions([]);
      });
  }, []);

  const syncLegacyFromBroker = () => {
    api.syncLegacyFromBroker()
      .then((result) => {
        setMessage(result.message ?? `${result.imported_count} imported, ${result.skipped_count} skipped.`);
        return loadPortfolioData();
      })
      .catch(() => setMessage("Broker legacy sync failed."));
  };

  const syncBotFromMarket = () => {
    api.syncBotFromMarket()
      .then((result) => {
        setMessage(`${result.message} ${result.updated_count} updated, ${result.skipped_count} skipped.`);
        return loadPortfolioData();
      })
      .catch(() => setMessage("Bot valuation refresh failed."));
  };

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">Portfolio</p>
          <h2>Bot-Only Positions</h2>
        </div>
        <div className="button-row">
          <button className="secondary-button" onClick={syncBotFromMarket} type="button">
            Refresh Bot Valuation
          </button>
          <button className="secondary-button" disabled={legacySyncBlocked} onClick={syncLegacyFromBroker} type="button">
            Sync Legacy From Broker
          </button>
        </div>
      </header>
      {legacySyncBlocked ? <div className="notice">Broker legacy sync is blocked after bot positions exist.</div> : null}
      {message ? <div className="notice">{message}</div> : null}
      <div className="stat-grid">
        <StatCard label="Available Budget" value={`$${summary?.available_budget_usd.toFixed(2) ?? "0.00"}`} />
        <StatCard label="Invested" value={`$${summary?.invested_amount_usd.toFixed(2) ?? "0.00"}`} />
        <StatCard label="PnL" value={`${summary?.unrealized_pnl_percent.toFixed(2) ?? "0.00"}%`} />
        <StatCard label="Bot Positions" value={`${summary?.bot_position_count ?? 0}`} />
        <StatCard label="Legacy Positions" value={`${summary?.legacy_position_count ?? 0}`} />
      </div>
      <section>
        <h3>Bot Positions</h3>
        <PositionTable botPositions={botPositions} />
      </section>
      <section>
        <h3>Protected Legacy Positions</h3>
        <PositionTable legacyPositions={legacyPositions} />
      </section>
    </section>
  );
}
