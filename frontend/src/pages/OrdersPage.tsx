import { useEffect, useState } from "react";
import { api, TradeOrder } from "../api/client";
import { OrderTable } from "../components/OrderTable";

export function OrdersPage() {
  const [orders, setOrders] = useState<TradeOrder[]>([]);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const refresh = () => {
    if (isRefreshing) return;
    setIsRefreshing(true);
    api.getOrders()
      .then(setOrders)
      .catch(() => setOrders([]))
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
      <OrderTable orders={orders} />
    </section>
  );
}
