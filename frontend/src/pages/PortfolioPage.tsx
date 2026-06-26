import { useEffect, useState } from "react";
import { api, BotPosition, LegacyPosition, PortfolioSummary } from "../api/client";
import { PositionTable } from "../components/PositionTable";
import { StatCard } from "../components/StatCard";

export function PortfolioPage() {
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [botPositions, setBotPositions] = useState<BotPosition[]>([]);
  const [legacyPositions, setLegacyPositions] = useState<LegacyPosition[]>([]);

  useEffect(() => {
    Promise.all([api.getPortfolioSummary(), api.getBotPositions(), api.getLegacyPositions()])
      .then(([portfolio, bot, legacy]) => {
        setSummary(portfolio);
        setBotPositions(bot);
        setLegacyPositions(legacy);
      })
      .catch(() => {
        setBotPositions([]);
        setLegacyPositions([]);
      });
  }, []);

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">Portfolio</p>
          <h2>Bot-Only Positions</h2>
        </div>
      </header>
      <div className="stat-grid">
        <StatCard label="Available Budget" value={`$${summary?.available_budget_usd.toFixed(2) ?? "0.00"}`} />
        <StatCard label="Invested" value={`$${summary?.invested_amount_usd.toFixed(2) ?? "0.00"}`} />
        <StatCard label="PnL" value={`${summary?.unrealized_pnl_percent.toFixed(2) ?? "0.00"}%`} />
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
