import { TradeOrder } from "../api/client";

function fillSummary(order: TradeOrder) {
  const fill = order.raw_response_json.simulated_fill;
  if (!fill || typeof fill !== "object") return "-";

  const payload = fill as Record<string, unknown>;
  const before = typeof payload.position_quantity_before === "number" ? payload.position_quantity_before : null;
  const after = typeof payload.position_quantity_after === "number" ? payload.position_quantity_after : null;
  if (before === null || after === null) return "-";
  return `${before.toFixed(4)} -> ${after.toFixed(4)}`;
}

export function OrderTable({ orders }: { orders: TradeOrder[] }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Symbol</th>
            <th>Side</th>
            <th>Quantity</th>
            <th>Price</th>
            <th>Amount</th>
            <th>Position Qty</th>
            <th>Status</th>
            <th>Reason</th>
          </tr>
        </thead>
        <tbody>
          {orders.map((order) => (
            <tr key={order.id}>
              <td>{new Date(order.created_at).toLocaleString()}</td>
              <td>{order.symbol}</td>
              <td>{order.side}</td>
              <td>{order.quantity.toFixed(4)}</td>
              <td>${order.price.toFixed(2)}</td>
              <td>${order.order_amount.toFixed(2)}</td>
              <td>{fillSummary(order)}</td>
              <td>{order.status}</td>
              <td>{order.reason}</td>
            </tr>
          ))}
          {!orders.length ? (
            <tr>
              <td colSpan={9}>No simulated orders yet.</td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}
