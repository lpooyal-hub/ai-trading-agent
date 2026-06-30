import { TradeOrder } from "../api/client";
import { actionLabel, statusLabel } from "../utils/labels";

function formatDateTime(value: string) {
  return new Date(value).toLocaleString(undefined, {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

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

function statusTone(value: string) {
  const normalized = value.toUpperCase();
  if (["SIMULATED", "SIMULATED_FILLED", "LIVE_SUBMITTED", "EXECUTED", "SUCCEEDED"].includes(normalized)) return "positive";
  if (["FAILED", "REJECTED"].includes(normalized)) return "negative";
  return "neutral";
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
              <td className="muted-cell">{formatDateTime(order.created_at)}</td>
              <td className="symbol-cell">{order.symbol}</td>
              <td>{actionLabel(order.side)}</td>
              <td>{order.quantity.toFixed(4)}</td>
              <td>${order.price.toFixed(2)}</td>
              <td>${order.order_amount.toFixed(2)}</td>
              <td>{fillSummary(order)}</td>
              <td>
                <span className={`status-pill ${statusTone(order.status)}`}>{statusLabel(order.status)}</span>
              </td>
              <td className="reason-cell">{order.reason}</td>
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
