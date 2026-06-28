import { useEffect, useState } from "react";
import { api, TradeOrder } from "../api/client";
import { OrderTable } from "../components/OrderTable";

export function OrdersPage() {
  const [orders, setOrders] = useState<TradeOrder[]>([]);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const refresh = () => {
    if (isRefreshing) return;
    setIsRefreshing(true);
    setMessage(null);
    api.getOrders()
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

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">DRY_RUN</p>
          <h2>Simulated Orders</h2>
        </div>
        <button className="secondary-button" disabled={isRefreshing} onClick={refresh} type="button">
          {isRefreshing ? "Refreshing..." : "Refresh"}
        </button>
      </header>
      {message ? <div className="notice">{message}</div> : null}
      <OrderTable orders={orders} />
    </section>
  );
}
