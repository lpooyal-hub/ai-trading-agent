import { useEffect, useState } from "react";
import { api, BotPosition, LegacyPosition, PortfolioPerformance, PortfolioRealizedTrade, PortfolioSummary, PortfolioSymbolPerformance } from "../api/client";
import { PositionTable } from "../components/PositionTable";
import { StatCard } from "../components/StatCard";

export function PortfolioPage() {
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [performance, setPerformance] = useState<PortfolioPerformance | null>(null);
  const [realizedTrades, setRealizedTrades] = useState<PortfolioRealizedTrade[]>([]);
  const [symbolPerformance, setSymbolPerformance] = useState<PortfolioSymbolPerformance[]>([]);
  const [botPositions, setBotPositions] = useState<BotPosition[]>([]);
  const [legacyPositions, setLegacyPositions] = useState<LegacyPosition[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [isRefreshingPortfolio, setIsRefreshingPortfolio] = useState(false);
  const [isRefreshingValuation, setIsRefreshingValuation] = useState(false);
  const [isSyncingLegacy, setIsSyncingLegacy] = useState(false);
  const legacySyncBlocked = Boolean(summary && summary.bot_position_count > 0);
  const recentRealizedTrades = realizedTrades.slice(0, 10);

  const loadPortfolioData = () => (
    Promise.all([api.getPortfolioSummary(), api.getPortfolioPerformance(), api.getPortfolioRealizedTrades(), api.getPortfolioSymbolPerformance(), api.getBotPositions(), api.getLegacyPositions()])
      .then(([portfolio, portfolioPerformance, trades, symbolRows, bot, legacy]) => {
        setSummary(portfolio);
        setPerformance(portfolioPerformance);
        setRealizedTrades(trades);
        setSymbolPerformance(symbolRows);
        setBotPositions(bot);
        setLegacyPositions(legacy);
      })
  );

  useEffect(() => {
    loadPortfolioData()
      .catch(() => {
        setPerformance(null);
        setRealizedTrades([]);
        setSymbolPerformance([]);
        setBotPositions([]);
        setLegacyPositions([]);
      });
  }, []);

  const refreshPortfolio = () => {
    if (isRefreshingPortfolio) return;
    setIsRefreshingPortfolio(true);
    loadPortfolioData()
      .then(() => setMessage("포트폴리오를 새로고침했습니다."))
      .catch(() => setMessage("포트폴리오 새로고침에 실패했습니다."))
      .finally(() => setIsRefreshingPortfolio(false));
  };

  const syncLegacyFromBroker = () => {
    if (isSyncingLegacy || legacySyncBlocked) return;
    setIsSyncingLegacy(true);
    api.syncLegacyFromBroker()
      .then((result) => {
        setMessage(result.message ?? `${result.imported_count}개 가져옴, ${result.skipped_count}개 건너뜀.`);
        return loadPortfolioData();
      })
      .catch(() => setMessage("브로커 기존 보유분 동기화에 실패했습니다."))
      .finally(() => setIsSyncingLegacy(false));
  };

  const syncBotFromMarket = () => {
    if (isRefreshingValuation) return;
    setIsRefreshingValuation(true);
    api.syncBotFromMarket()
      .then((result) => {
        setMessage(`${result.message} ${result.updated_count}개 갱신, ${result.skipped_count}개 건너뜀.`);
        return loadPortfolioData();
      })
      .catch(() => setMessage("봇 포지션 평가 갱신에 실패했습니다."))
      .finally(() => setIsRefreshingValuation(false));
  };

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">포트폴리오</p>
          <h2>봇 전용 포지션</h2>
        </div>
        <div className="button-row">
          <button className="secondary-button" disabled={isRefreshingPortfolio} onClick={refreshPortfolio} type="button">
            {isRefreshingPortfolio ? "새로고침 중..." : "새로고침"}
          </button>
          <button className="secondary-button" disabled={isRefreshingValuation} onClick={syncBotFromMarket} type="button">
            {isRefreshingValuation ? "갱신 중..." : "봇 평가 갱신"}
          </button>
          <button className="secondary-button" disabled={legacySyncBlocked || isSyncingLegacy} onClick={syncLegacyFromBroker} type="button">
            {isSyncingLegacy ? "동기화 중..." : "기존 보유분 동기화"}
          </button>
        </div>
      </header>
      {legacySyncBlocked ? <div className="notice">봇 포지션이 생긴 뒤에는 기존 보유분 브로커 동기화를 차단합니다.</div> : null}
      {message ? <div className="notice">{message}</div> : null}
      <div className="stat-grid">
        <StatCard label="사용 가능 예산" value={`$${summary?.available_budget_usd.toFixed(2) ?? "0.00"}`} />
        <StatCard label="투입 금액" value={`$${summary?.invested_amount_usd.toFixed(2) ?? "0.00"}`} />
        <StatCard label="미실현 손익률" value={`${summary?.unrealized_pnl_percent.toFixed(2) ?? "0.00"}%`} />
        <StatCard label="실현 손익" value={`$${performance?.realized_pnl_usd.toFixed(2) ?? "0.00"}`} />
        <StatCard label="전체 손익" value={`$${performance?.total_pnl_usd.toFixed(2) ?? "0.00"}`} detail={`${performance?.total_pnl_percent.toFixed(2) ?? "0.00"}%`} />
        <StatCard label="매수 금액" value={`$${performance?.gross_bought_usd.toFixed(2) ?? "0.00"}`} />
        <StatCard label="매도 금액" value={`$${performance?.gross_sold_usd.toFixed(2) ?? "0.00"}`} />
        <StatCard label="승률" value={`${performance?.win_rate_percent.toFixed(2) ?? "0.00"}%`} detail={`${performance?.winning_sell_count ?? 0}승 / ${performance?.losing_sell_count ?? 0}패`} />
        <StatCard label="모의 주문" value={`${performance?.simulated_order_count ?? 0}`} detail={`${performance?.buy_order_count ?? 0} 매수 / ${performance?.sell_order_count ?? 0} 매도`} />
        <StatCard label="실주문 제출" value={`${performance?.live_submitted_order_count ?? 0}`} detail={`$${performance?.live_submitted_order_amount_usd.toFixed(2) ?? "0.00"}`} />
        <StatCard label="봇 포지션" value={`${summary?.bot_position_count ?? 0}`} />
        <StatCard label="기존 보유분" value={`${summary?.legacy_position_count ?? 0}`} />
      </div>
      <section>
        <h3>종목별 성과</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>종목</th>
                <th>거래</th>
                <th>매도 금액</th>
                <th>실현 손익</th>
                <th>승률</th>
              </tr>
            </thead>
            <tbody>
              {symbolPerformance.map((row) => (
                <tr key={row.symbol}>
                  <td>{row.symbol}</td>
                  <td>{row.realized_trade_count}</td>
                  <td>${row.sell_amount_usd.toFixed(2)}</td>
                  <td>${row.realized_pnl_usd.toFixed(2)}</td>
                  <td>{row.win_rate_percent.toFixed(2)}%</td>
                </tr>
              ))}
              {!symbolPerformance.length ? (
                <tr>
                  <td colSpan={5}>아직 종목별 성과가 없습니다.</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
      <section>
        <h3>실현 거래</h3>
        {realizedTrades.length > recentRealizedTrades.length ? (
          <p className="helper-text">총 {realizedTrades.length}건 중 최근 {recentRealizedTrades.length}건을 표시합니다.</p>
        ) : null}
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>시각</th>
                <th>종목</th>
                <th>수량</th>
                <th>매도 금액</th>
                <th>원가</th>
                <th>실현 손익</th>
              </tr>
            </thead>
            <tbody>
              {recentRealizedTrades.map((trade) => (
                <tr key={trade.order_id}>
                  <td>{new Date(trade.created_at).toLocaleString()}</td>
                  <td>{trade.symbol}</td>
                  <td>{trade.quantity.toFixed(4)}</td>
                  <td>${trade.sell_amount_usd.toFixed(2)}</td>
                  <td>${trade.cost_basis_usd.toFixed(2)}</td>
                  <td>${trade.realized_pnl_usd.toFixed(2)} ({trade.realized_pnl_percent.toFixed(2)}%)</td>
                </tr>
              ))}
              {!recentRealizedTrades.length ? (
                <tr>
                  <td colSpan={6}>아직 실현 거래가 없습니다.</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
      <section>
        <h3>봇 포지션</h3>
        <PositionTable botPositions={botPositions} />
      </section>
      <section>
        <h3>보호 중인 기존 보유분</h3>
        <PositionTable legacyPositions={legacyPositions} />
      </section>
    </section>
  );
}
