import { useEffect, useState } from "react";
import { api, TradeOrder } from "../api/client";
import { OrderTable } from "../components/OrderTable";

export function OrdersPage() {
  const [orders, setOrders] = useState<TradeOrder[]>([]);

  useEffect(() => {
    api.getOrders().then(setOrders).catch(() => setOrders([]));
  }, []);

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">DRY_RUN</p>
          <h2>Simulated Orders</h2>
        </div>
      </header>
      <OrderTable orders={orders} />
    </section>
  );
}
