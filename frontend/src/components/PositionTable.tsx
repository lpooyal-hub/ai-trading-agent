import { BotPosition, LegacyPosition } from "../api/client";
import { formatKRW } from "../utils/currency";
import { statusLabel, symbolLabel } from "../utils/labels";

type PositionTableProps = {
  botPositions?: BotPosition[];
  legacyPositions?: LegacyPosition[];
};

function formatOptionalCurrency(value: number) {
  return value > 0 ? formatKRW(value) : "-";
}

export function PositionTable({ botPositions = [], legacyPositions = [] }: PositionTableProps) {
  if (legacyPositions.length) {
    return (
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>종목</th>
              <th>이름</th>
              <th>수량</th>
              <th>평균가</th>
              <th>보호</th>
            </tr>
          </thead>
          <tbody>
            {legacyPositions.map((position) => (
              <tr key={position.id}>
                <td>{symbolLabel(position.symbol)}</td>
                <td>{position.name}</td>
                <td>{position.quantity}</td>
                <td>{formatOptionalCurrency(position.avg_price)}</td>
                <td>{position.is_protected ? "예" : "아니오"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>종목</th>
            <th>수량</th>
            <th>평균 매수가</th>
            <th>투입 금액</th>
            <th>현재가</th>
            <th>손익률</th>
            <th>상태</th>
          </tr>
        </thead>
        <tbody>
          {botPositions.map((position) => (
            <tr key={position.id}>
              <td>{symbolLabel(position.symbol)}</td>
              <td>{position.quantity.toFixed(4)}</td>
              <td>{formatKRW(position.avg_buy_price)}</td>
              <td>{formatKRW(position.total_invested_amount)}</td>
              <td>{formatKRW(position.current_price)}</td>
              <td>{position.unrealized_pnl_percent.toFixed(2)}%</td>
              <td>{statusLabel(position.status)}</td>
            </tr>
          ))}
          {!botPositions.length ? (
            <tr>
              <td colSpan={7}>아직 봇 포지션이 없습니다.</td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}
