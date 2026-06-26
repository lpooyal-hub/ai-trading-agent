import { TradeOrder } from "../api/client";

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
              <td>{order.status}</td>
              <td>{order.reason}</td>
            </tr>
          ))}
          {!orders.length ? (
            <tr>
              <td colSpan={8}>No simulated orders yet.</td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}
