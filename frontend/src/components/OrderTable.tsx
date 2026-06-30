import { TradeOrder } from "../api/client";

function fillSummary(order: TradeOrder) {
  if (order.raw_response_json.live_order_blocked) {
    const intent = order.raw_response_json.order_intent;
    if (intent && typeof intent === "object") {
      const payload = intent as Record<string, unknown>;
      const key = typeof payload.idempotency_key === "string" ? payload.idempotency_key : "no-key";
      return `실주문 차단 · ${key}`;
    }
    return "실주문 차단";
  }
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
    <div className="table-wrap wide-table">
      <table>
        <thead>
          <tr>
            <th>시각</th>
            <th>종목</th>
            <th>방향</th>
            <th>수량</th>
            <th>가격</th>
            <th>금액</th>
            <th>포지션 수량</th>
            <th>상태</th>
            <th>사유</th>
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
              <td colSpan={9}>아직 모의 주문이 없습니다.</td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}
