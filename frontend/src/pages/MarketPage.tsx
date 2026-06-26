import { useEffect, useState } from "react";
import { api, MarketSnapshot } from "../api/client";

export function MarketPage() {
  const [snapshots, setSnapshots] = useState<MarketSnapshot[]>([]);
  const [symbol, setSymbol] = useState("NVDA");
  const [price, setPrice] = useState("0");
  const [changePercent, setChangePercent] = useState("0");
  const [volume, setVolume] = useState("0");
  const [message, setMessage] = useState<string | null>(null);

  const refresh = () => {
    api.getLatestMarketSnapshots()
      .then(setSnapshots)
      .catch(() => setSnapshots([]));
  };

  useEffect(() => {
    refresh();
  }, []);

  const saveSnapshot = () => {
    api.createMarketSnapshots([
      {
        symbol,
        price: Number(price),
        change_percent: Number(changePercent),
        volume: Number(volume),
        sector: "semiconductor",
        extra_json: { source: "manual_dashboard" },
      },
    ])
      .then((result) => {
        setMessage(`${result.created_count} saved, ${result.skipped_count} skipped.`);
        refresh();
      })
      .catch(() => setMessage("Market snapshot save failed."));
  };

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">Market Inputs</p>
          <h2>Manual Snapshots</h2>
        </div>
        <button className="secondary-button" onClick={refresh} type="button">Refresh</button>
      </header>
      {message ? <div className="notice">{message}</div> : null}
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
        <button className="primary-button" onClick={saveSnapshot} type="button">Save Snapshot</button>
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
