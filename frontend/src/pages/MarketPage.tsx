import { useEffect, useState } from "react";
import { api, MarketSnapshot, MarketSnapshotStatus } from "../api/client";
import { StatCard } from "../components/StatCard";

export function MarketPage() {
  const [snapshots, setSnapshots] = useState<MarketSnapshot[]>([]);
  const [status, setStatus] = useState<MarketSnapshotStatus | null>(null);
  const [symbol, setSymbol] = useState("NVDA");
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
      setMessage("Symbol is required.");
      return;
    }
    if (!Number.isFinite(parsedPrice) || parsedPrice <= 0) {
      setMessage("Price must be greater than zero.");
      return;
    }
    if (!Number.isFinite(parsedChangePercent)) {
      setMessage("Change percent must be a valid number.");
      return;
    }
    if (!Number.isFinite(parsedVolume) || parsedVolume < 0) {
      setMessage("Volume must be zero or greater.");
      return;
    }

    setIsSavingSnapshot(true);
    api.createMarketSnapshots([
      {
        symbol: normalizedSymbol,
        price: parsedPrice,
        change_percent: parsedChangePercent,
        volume: parsedVolume,
        sector: "semiconductor",
        extra_json: { source: "manual_dashboard" },
      },
    ])
      .then((result) => {
        setMessage(`${result.created_count} saved, ${result.skipped_count} skipped.`);
        return Promise.all([api.getLatestMarketSnapshots(), api.getMarketSnapshotStatus()]);
      })
      .then(([snapshotRows, snapshotStatus]) => {
        setSnapshots(snapshotRows);
        setStatus(snapshotStatus);
      })
      .catch(() => setMessage("Market snapshot save failed."))
      .finally(() => setIsSavingSnapshot(false));
  };

  const refreshFromSource = () => {
    if (isRefreshingSource) return;
    setIsRefreshingSource(true);
    api.refreshMarketSnapshots()
      .then((result) => {
        setSnapshots(result.snapshots);
        setMessage(`${result.message} ${result.created_count} saved, ${result.skipped_count} skipped.`);
        return api.getMarketSnapshotStatus();
      })
      .then(setStatus)
      .catch(() => setMessage("Market snapshot refresh failed."))
      .finally(() => setIsRefreshingSource(false));
  };

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">Market Inputs</p>
          <h2>Manual Snapshots</h2>
        </div>
        <div className="button-row">
          <button className="secondary-button" disabled={isRefreshing} onClick={refresh} type="button">
            {isRefreshing ? "Refreshing..." : "Refresh"}
          </button>
          <button className="primary-button" disabled={isRefreshingSource} onClick={refreshFromSource} type="button">
            {isRefreshingSource ? "Refreshing..." : "Refresh Source"}
          </button>
        </div>
      </header>
      {message ? <div className="notice">{message}</div> : null}
      <div className="stat-grid">
        <StatCard label="Agent Ready" value={status?.ready_for_agent ? "Ready" : "Not Ready"} detail={status?.message} />
        <StatCard label="Fresh Symbols" value={`${status?.fresh_symbol_count ?? 0}`} detail={`${status?.max_age_minutes ?? 0}m freshness window`} />
        <StatCard label="Missing Symbols" value={`${status?.missing_symbol_count ?? 0}`} detail={status?.missing_symbols.join(", ") || "None"} />
      </div>
      <div className="filter-row">
        <label>
          Symbol
          <input value={symbol} onChange={(event) => setSymbol(event.target.value.toUpperCase())} />
        </label>
        <label>
          Price
          <input value={price} onChange={(event) => setPrice(event.target.value)} type="number" />
        </label>
        <label>
          Change %
          <input value={changePercent} onChange={(event) => setChangePercent(event.target.value)} type="number" />
        </label>
        <label>
          Volume
          <input value={volume} onChange={(event) => setVolume(event.target.value)} type="number" />
        </label>
        <button className="primary-button" disabled={isSavingSnapshot} onClick={saveSnapshot} type="button">
          {isSavingSnapshot ? "Saving..." : "Save Snapshot"}
        </button>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Time</th>
              <th>Symbol</th>
              <th>Price</th>
              <th>Change</th>
              <th>Volume</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            {snapshots.map((row) => (
              <tr key={row.id}>
                <td>{new Date(row.created_at).toLocaleString()}</td>
                <td>{row.symbol}</td>
                <td>${row.price.toFixed(2)}</td>
                <td>{row.change_percent.toFixed(2)}%</td>
                <td>{row.volume.toLocaleString()}</td>
                <td>{String(row.extra_json.source ?? "-")}</td>
              </tr>
            ))}
            {!snapshots.length ? (
              <tr>
                <td colSpan={6}>No market snapshots yet.</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}
