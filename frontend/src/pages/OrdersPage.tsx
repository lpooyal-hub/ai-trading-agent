import { useEffect, useState } from "react";
import { api, TradeOrder } from "../api/client";
import { OrderTable } from "../components/OrderTable";

export function OrdersPage() {
  const [orders, setOrders] = useState<TradeOrder[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [symbolFilter, setSymbolFilter] = useState("");
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [syncingOrderId, setSyncingOrderId] = useState<number | null>(null);
  const [isSyncingOpenLiveOrders, setIsSyncingOpenLiveOrders] = useState(false);
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
        setMessage("주문 기록 새로고침에 실패했습니다.");
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

  const syncLiveStatus = (orderId: number) => {
    if (syncingOrderId) return;
    setSyncingOrderId(orderId);
    setMessage(null);
    api.syncLiveOrderStatus(orderId)
      .then((updatedOrder) => {
        setOrders((current) => current.map((order) => order.id === updatedOrder.id ? updatedOrder : order));
        setMessage("실주문 체결 상태를 동기화했습니다.");
      })
      .catch(() => setMessage("실주문 체결 상태 동기화에 실패했습니다."))
      .finally(() => setSyncingOrderId(null));
  };

  const syncOpenLiveStatuses = () => {
    if (isSyncingOpenLiveOrders) return;
    setIsSyncingOpenLiveOrders(true);
    setMessage(null);
    api.syncOpenLiveOrderStatuses()
      .then((result) => {
        const updatedById = new Map(result.orders.map((order) => [order.id, order]));
        setOrders((current) => current.map((order) => updatedById.get(order.id) ?? order));
        setMessage(
          `실주문 ${result.scanned_count}건 확인 · 체결 ${result.filled_count} · 부분 ${result.partial_count} · 취소 ${result.canceled_count} · 실패 ${result.failed_count}`
        );
      })
      .catch(() => setMessage("대기 실주문 상태 동기화에 실패했습니다."))
      .finally(() => setIsSyncingOpenLiveOrders(false));
  };

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">모의 실행</p>
          <h2>모의 주문 기록</h2>
        </div>
        <div className="button-row">
          <button
            className="secondary-button"
            disabled={isSyncingOpenLiveOrders}
            onClick={syncOpenLiveStatuses}
            type="button"
          >
            {isSyncingOpenLiveOrders ? "동기화 중..." : "대기 실주문 동기화"}
          </button>
          <button className="secondary-button" disabled={isRefreshing} onClick={() => refresh()} type="button">
            {isRefreshing ? "새로고침 중..." : "새로고침"}
          </button>
        </div>
      </header>
      <div className="button-row">
        <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
          <option value="">전체 상태</option>
          <option value="SIMULATED">모의 체결</option>
          <option value="LIVE_SUBMITTED">실주문 제출</option>
          <option value="LIVE_PARTIAL">부분 체결</option>
          <option value="LIVE_FILLED">실주문 체결</option>
          <option value="LIVE_CANCELED">실주문 취소</option>
          <option value="REJECTED">거절</option>
          <option value="FAILED">실패</option>
          <option value="TODO_LIVE_ORDER_NOT_IMPLEMENTED">실주문 차단</option>
        </select>
        <input
          onChange={(event) => setSymbolFilter(event.target.value.toUpperCase())}
          placeholder="종목"
          value={symbolFilter}
        />
        <button className="secondary-button" onClick={() => refresh()} type="button">적용</button>
        <button className="secondary-button" onClick={clearFilters} type="button">초기화</button>
      </div>
      {message ? <div className="notice">{message}</div> : null}
      <OrderTable orders={orders} onSyncLiveStatus={syncLiveStatus} syncingOrderId={syncingOrderId} />
    </section>
  );
}
