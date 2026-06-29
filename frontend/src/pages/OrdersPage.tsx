import { useEffect, useState } from "react";
import { api, TradeOrder } from "../api/client";
import { OrderTable } from "../components/OrderTable";

export function OrdersPage() {
  const [orders, setOrders] = useState<TradeOrder[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [symbolFilter, setSymbolFilter] = useState("");
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const refresh = (filters = { status: statusFilter, symbol: symbolFilter }) => {
    if (isRefreshing) return;
    setIsRefreshing(true);
    setMessage(null);
    api.getOrders({
      status: filters.status || undefined,
      symbol: filters.symbol || undefined,
      limit: 100,
    })
      .then(setOrders)
      .catch(() => {
        setOrders([]);
        setMessage("Orders refresh failed.");
      })
      .finally(() => setIsRefreshing(false));
  };

  useEffect(() => {
    refresh();
  }, []);

  const clearFilters = () => {
    setStatusFilter("");
    setSymbolFilter("");
    refresh({ status: "", symbol: "" });
  };

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">DRY_RUN</p>
          <h2>Simulated Orders</h2>
        </div>
        <div className="button-row">
          <button className="secondary-button" disabled={isRefreshing} onClick={() => refresh()} type="button">
            {isRefreshing ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      </header>
      <div className="button-row">
        <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
          <option value="">All statuses</option>
          <option value="SIMULATED">Simulated</option>
          <option value="REJECTED">Rejected</option>
          <option value="FAILED">Failed</option>
          <option value="TODO_LIVE_ORDER_NOT_IMPLEMENTED">Live Blocked</option>
        </select>
        <input
          onChange={(event) => setSymbolFilter(event.target.value.toUpperCase())}
          placeholder="Symbol"
          value={symbolFilter}
        />
        <button className="secondary-button" onClick={() => refresh()} type="button">Apply</button>
        <button className="secondary-button" onClick={clearFilters} type="button">Clear</button>
      </div>
      {message ? <div className="notice">{message}</div> : null}
      <OrderTable orders={orders} />
    </section>
  );
}
