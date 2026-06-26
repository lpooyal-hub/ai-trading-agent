import { BotPosition, LegacyPosition } from "../api/client";

type PositionTableProps = {
  botPositions?: BotPosition[];
  legacyPositions?: LegacyPosition[];
};

export function PositionTable({ botPositions = [], legacyPositions = [] }: PositionTableProps) {
  if (legacyPositions.length) {
    return (
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Name</th>
              <th>Quantity</th>
              <th>Avg Price</th>
              <th>Protected</th>
            </tr>
          </thead>
          <tbody>
            {legacyPositions.map((position) => (
              <tr key={position.id}>
                <td>{position.symbol}</td>
                <td>{position.name}</td>
                <td>{position.quantity}</td>
                <td>${position.avg_price.toFixed(2)}</td>
                <td>{position.is_protected ? "Yes" : "No"}</td>
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
            <th>Symbol</th>
            <th>Quantity</th>
            <th>Avg Buy</th>
            <th>Invested</th>
            <th>Current</th>
            <th>PnL</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {botPositions.map((position) => (
            <tr key={position.id}>
              <td>{position.symbol}</td>
              <td>{position.quantity.toFixed(4)}</td>
              <td>${position.avg_buy_price.toFixed(2)}</td>
              <td>${position.total_invested_amount.toFixed(2)}</td>
              <td>${position.current_price.toFixed(2)}</td>
              <td>{position.unrealized_pnl_percent.toFixed(2)}%</td>
              <td>{position.status}</td>
            </tr>
          ))}
          {!botPositions.length ? (
            <tr>
              <td colSpan={7}>No bot positions yet.</td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}
