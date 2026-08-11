import { useEffect, useState } from "react";
import { api, MarketSnapshot, MarketSnapshotStatus } from "../api/client";
import { StatCard } from "../components/StatCard";
import { formatKRW } from "../utils/currency";

export function MarketPage() {
  const [snapshots, setSnapshots] = useState<MarketSnapshot[]>([]);
  const [status, setStatus] = useState<MarketSnapshotStatus | null>(null);
  const [symbol, setSymbol] = useState("005930");
  const [sector, setSector] = useState("unknown");
  const [price, setPrice] = useState("0");
  const [changePercent, setChangePercent] = useState("0");
  const [volume, setVolume] = useState("0");
  const [message, setMessage] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isRefreshingSource, setIsRefreshingSource] = useState(false);
  const [isSavingSnapshot, setIsSavingSnapshot] = useState(false);

  const refresh = () => {
    if (isRefreshing) return;
    setIsRefreshing(true);
    Promise.all([api.getLatestMarketSnapshots(), api.getMarketSnapshotStatus()])
      .then(([snapshotRows, snapshotStatus]) => {
        setSnapshots(snapshotRows);
        setStatus(snapshotStatus);
      })
      .catch(() => {
        setSnapshots([]);
        setStatus(null);
      })
      .finally(() => setIsRefreshing(false));
  };

  useEffect(() => {
    refresh();
  }, []);

  const saveSnapshot = () => {
    if (isSavingSnapshot) return;
    const normalizedSymbol = symbol.trim().toUpperCase();
    const parsedPrice = Number(price);
    const parsedChangePercent = Number(changePercent);
    const parsedVolume = Number(volume);

    if (!normalizedSymbol) {
      setMessage("종목을 입력해야 합니다.");
      return;
    }
    if (!Number.isFinite(parsedPrice) || parsedPrice <= 0) {
      setMessage("가격은 0보다 커야 합니다.");
      return;
    }
    if (!Number.isFinite(parsedChangePercent)) {
      setMessage("등락률은 숫자여야 합니다.");
      return;
    }
    if (!Number.isFinite(parsedVolume) || parsedVolume < 0) {
      setMessage("거래량은 0 이상이어야 합니다.");
      return;
    }

    setIsSavingSnapshot(true);
    api.createMarketSnapshots([
      {
        symbol: normalizedSymbol,
        price: parsedPrice,
        change_percent: parsedChangePercent,
        volume: parsedVolume,
        sector: sector.trim() || "unknown",
        extra_json: { source: "manual_dashboard" },
      },
    ])
      .then((result) => {
        setMessage(`${result.created_count}개 저장, ${result.skipped_count}개 건너뜀.`);
        if (result.created_count > 0) {
          setPrice("0");
          setChangePercent("0");
          setVolume("0");
        }
        return Promise.all([api.getLatestMarketSnapshots(), api.getMarketSnapshotStatus()]);
      })
      .then(([snapshotRows, snapshotStatus]) => {
        setSnapshots(snapshotRows);
        setStatus(snapshotStatus);
      })
      .catch(() => setMessage("시장 스냅샷 저장에 실패했습니다."))
      .finally(() => setIsSavingSnapshot(false));
  };

  const refreshFromSource = () => {
    if (isRefreshingSource) return;
    setIsRefreshingSource(true);
    api.refreshMarketSnapshots()
      .then((result) => {
        setSnapshots(result.snapshots);
        setMessage(`${result.message} ${result.created_count}개 저장, ${result.skipped_count}개 건너뜀.`);
        return api.getMarketSnapshotStatus();
      })
      .then(setStatus)
      .catch(() => setMessage("시장 스냅샷 새로고침에 실패했습니다."))
      .finally(() => setIsRefreshingSource(false));
  };

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">시장 입력</p>
          <h2>수동 스냅샷</h2>
        </div>
        <div className="button-row">
          <button className="secondary-button" disabled={isRefreshing} onClick={refresh} type="button">
            {isRefreshing ? "새로고침 중..." : "새로고침"}
          </button>
          <button className="primary-button" disabled={isRefreshingSource} onClick={refreshFromSource} type="button">
            {isRefreshingSource ? "갱신 중..." : "소스 갱신"}
          </button>
        </div>
      </header>
      {message ? <div className="notice">{message}</div> : null}
      <div className="stat-grid">
        <StatCard label="에이전트 준비" value={status?.ready_for_agent ? "준비됨" : "미준비"} detail={status?.message} />
        <StatCard label="신선한 종목" value={`${status?.fresh_symbol_count ?? 0}`} detail={`${status?.max_age_minutes ?? 0}분 freshness window`} />
        <StatCard label="누락 종목" value={`${status?.missing_symbol_count ?? 0}`} detail={status?.missing_symbols.join(", ") || "없음"} />
      </div>
      <div className="filter-row">
        <label>
          종목
          <input value={symbol} onChange={(event) => setSymbol(event.target.value.toUpperCase())} />
        </label>
        <label>
          가격
          <input value={price} onChange={(event) => setPrice(event.target.value)} type="number" />
        </label>
        <label>
          섹터
          <input value={sector} onChange={(event) => setSector(event.target.value)} />
        </label>
        <label>
          등락률 %
          <input value={changePercent} onChange={(event) => setChangePercent(event.target.value)} type="number" />
        </label>
        <label>
          거래량
          <input value={volume} onChange={(event) => setVolume(event.target.value)} type="number" />
        </label>
        <button className="primary-button" disabled={isSavingSnapshot} onClick={saveSnapshot} type="button">
          {isSavingSnapshot ? "저장 중..." : "스냅샷 저장"}
        </button>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>시각</th>
              <th>종목</th>
              <th>가격</th>
              <th>등락률</th>
              <th>거래량</th>
              <th>소스</th>
            </tr>
          </thead>
          <tbody>
            {snapshots.map((row) => (
              <tr key={row.id}>
                <td>{new Date(row.created_at).toLocaleString()}</td>
                <td>{row.symbol}</td>
                <td>{formatKRW(row.price)}</td>
                <td>{row.change_percent.toFixed(2)}%</td>
                <td>{row.volume.toLocaleString()}</td>
                <td>{String(row.extra_json.source ?? "-")}</td>
              </tr>
            ))}
            {!snapshots.length ? (
              <tr>
                <td colSpan={6}>아직 시장 스냅샷이 없습니다.</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}
