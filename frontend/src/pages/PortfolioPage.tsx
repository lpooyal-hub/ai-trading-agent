import { useEffect, useState } from "react";
import { api, BotPosition, LegacyPosition, PortfolioPerformance, PortfolioSummary } from "../api/client";
import { PositionTable } from "../components/PositionTable";
import { StatCard } from "../components/StatCard";

export function PortfolioPage() {
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [performance, setPerformance] = useState<PortfolioPerformance | null>(null);
  const [botPositions, setBotPositions] = useState<BotPosition[]>([]);
  const [legacyPositions, setLegacyPositions] = useState<LegacyPosition[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [isRefreshingPortfolio, setIsRefreshingPortfolio] = useState(false);
  const [isRefreshingValuation, setIsRefreshingValuation] = useState(false);
  const [isSyncingLegacy, setIsSyncingLegacy] = useState(false);
  const legacySyncBlocked = Boolean(summary && summary.bot_position_count > 0);

  const loadPortfolioData = () => (
    Promise.all([api.getPortfolioSummary(), api.getPortfolioPerformance(), api.getBotPositions(), api.getLegacyPositions()])
      .then(([portfolio, portfolioPerformance, bot, legacy]) => {
        setSummary(portfolio);
        setPerformance(portfolioPerformance);
        setBotPositions(bot);
        setLegacyPositions(legacy);
      })
  );

  useEffect(() => {
    loadPortfolioData()
      .catch(() => {
        setPerformance(null);
        setBotPositions([]);
        setLegacyPositions([]);
      });
  }, []);

  const refreshPortfolio = () => {
    if (isRefreshingPortfolio) return;
    setIsRefreshingPortfolio(true);
    loadPortfolioData()
      .then(() => setMessage("Portfolio refreshed."))
      .catch(() => setMessage("Portfolio refresh failed."))
      .finally(() => setIsRefreshingPortfolio(false));
  };

  const syncLegacyFromBroker = () => {
    if (isSyncingLegacy || legacySyncBlocked) return;
    setIsSyncingLegacy(true);
    api.syncLegacyFromBroker()
      .then((result) => {
        setMessage(result.message ?? `${result.imported_count} imported, ${result.skipped_count} skipped.`);
        return loadPortfolioData();
      })
      .catch(() => setMessage("Broker legacy sync failed."))
      .finally(() => setIsSyncingLegacy(false));
  };

  const syncBotFromMarket = () => {
    if (isRefreshingValuation) return;
    setIsRefreshingValuation(true);
    api.syncBotFromMarket()
      .then((result) => {
        setMessage(`${result.message} ${result.updated_count} updated, ${result.skipped_count} skipped.`);
        return loadPortfolioData();
      })
      .catch(() => setMessage("Bot valuation refresh failed."))
      .finally(() => setIsRefreshingValuation(false));
  };

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">Portfolio</p>
          <h2>Bot-Only Positions</h2>
        </div>
        <div className="button-row">
          <button className="secondary-button" disabled={isRefreshingPortfolio} onClick={refreshPortfolio} type="button">
            {isRefreshingPortfolio ? "Refreshing..." : "Refresh"}
          </button>
          <button className="secondary-button" disabled={isRefreshingValuation} onClick={syncBotFromMarket} type="button">
            {isRefreshingValuation ? "Refreshing..." : "Refresh Bot Valuation"}
          </button>
          <button className="secondary-button" disabled={legacySyncBlocked || isSyncingLegacy} onClick={syncLegacyFromBroker} type="button">
            {isSyncingLegacy ? "Syncing..." : "Sync Legacy From Broker"}
          </button>
        </div>
      </header>
      {legacySyncBlocked ? <div className="notice">Broker legacy sync is blocked after bot positions exist.</div> : null}
      {message ? <div className="notice">{message}</div> : null}
      <div className="stat-grid">
        <StatCard label="Available Budget" value={`$${summary?.available_budget_usd.toFixed(2) ?? "0.00"}`} />
        <StatCard label="Invested" value={`$${summary?.invested_amount_usd.toFixed(2) ?? "0.00"}`} />
        <StatCard label="PnL" value={`${summary?.unrealized_pnl_percent.toFixed(2) ?? "0.00"}%`} />
        <StatCard label="Realized PnL" value={`$${performance?.realized_pnl_usd.toFixed(2) ?? "0.00"}`} />
        <StatCard label="Total PnL" value={`$${performance?.total_pnl_usd.toFixed(2) ?? "0.00"}`} detail={`${performance?.total_pnl_percent.toFixed(2) ?? "0.00"}%`} />
        <StatCard label="Sim Orders" value={`${performance?.simulated_order_count ?? 0}`} detail={`${performance?.buy_order_count ?? 0} buy / ${performance?.sell_order_count ?? 0} sell`} />
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
