import { TradeOrder } from "../api/client";
import { formatKRW } from "../utils/currency";
import { actionLabel, statusLabel, symbolLabel } from "../utils/labels";

function formatDateTime(value: string) {
  return new Date(value).toLocaleString(undefined, {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function fillSummary(order: TradeOrder) {
  const sync = order.raw_response_json.broker_status_sync;
  if (sync && typeof sync === "object") {
    const payload = sync as Record<string, unknown>;
    const applied = payload.position_applied ? " · 포지션 반영" : "";
    const quantity = typeof payload.filled_quantity === "number" ? payload.filled_quantity.toFixed(4) : null;
    if (quantity) return `체결 ${quantity}${applied}`;
    if (typeof payload.message === "string") return payload.message;
  }
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
  if (["SIMULATED", "SIMULATED_FILLED", "LIVE_SUBMITTED", "LIVE_PARTIAL", "LIVE_FILLED", "EXECUTED", "SUCCEEDED"].includes(normalized)) return "positive";
  if (["LIVE_CANCELED"].includes(normalized)) return "neutral";
  if (["FAILED", "REJECTED"].includes(normalized)) return "negative";
  return "neutral";
}

function canSyncLiveStatus(order: TradeOrder) {
  return ["LIVE_SUBMITTED", "LIVE_PARTIAL"].includes(order.status);
}

export function OrderTable({
  orders,
  onSyncLiveStatus,
  syncingOrderId,
}: {
  orders: TradeOrder[];
  onSyncLiveStatus?: (orderId: number) => void;
  syncingOrderId?: number | null;
}) {
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
            <th>동기화</th>
          </tr>
        </thead>
        <tbody>
          {orders.map((order) => (
            <tr key={order.id}>
              <td className="muted-cell">{formatDateTime(order.created_at)}</td>
              <td className="symbol-cell">{symbolLabel(order.symbol)}</td>
              <td>{actionLabel(order.side)}</td>
              <td>{order.quantity.toFixed(4)}</td>
              <td>{formatKRW(order.price)}</td>
              <td>{formatKRW(order.order_amount)}</td>
              <td>{fillSummary(order)}</td>
              <td>
                <span className={`status-pill ${statusTone(order.status)}`}>{statusLabel(order.status)}</span>
              </td>
              <td className="reason-cell">{order.reason}</td>
              <td>
                {onSyncLiveStatus && canSyncLiveStatus(order) ? (
                  <button
                    className="secondary-button compact-button"
                    disabled={syncingOrderId === order.id}
                    onClick={() => onSyncLiveStatus(order.id)}
                    type="button"
                  >
                    {syncingOrderId === order.id ? "확인 중" : "체결 확인"}
                  </button>
                ) : "-"}
              </td>
            </tr>
          ))}
          {!orders.length ? (
            <tr>
              <td colSpan={10}>아직 주문 기록이 없습니다.</td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}
