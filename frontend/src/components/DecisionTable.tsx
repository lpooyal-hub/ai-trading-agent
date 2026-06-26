import { AgentDecision } from "../api/client";

type DecisionTableProps = {
  decisions: AgentDecision[];
  onSelect?: (id: number) => void;
};

export function DecisionTable({ decisions, onSelect }: DecisionTableProps) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Symbol</th>
            <th>Action</th>
            <th>Confidence</th>
            <th>Amount</th>
            <th>Status</th>
            <th>Dry Run</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {decisions.map((decision) => (
            <tr key={decision.id}>
              <td>{new Date(decision.created_at).toLocaleString()}</td>
              <td>{decision.symbol}</td>
              <td>{decision.action}</td>
              <td>{Math.round(decision.confidence * 100)}%</td>
              <td>${decision.recommended_order_amount.toFixed(2)}</td>
              <td>{decision.status}</td>
              <td>{decision.dry_run ? "Yes" : "No"}</td>
              <td>
                {onSelect ? (
                  <button className="small-button" onClick={() => onSelect(decision.id)} type="button">
                    Detail
                  </button>
                ) : null}
              </td>
            </tr>
          ))}
          {!decisions.length ? (
            <tr>
              <td colSpan={8}>No decisions yet.</td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}
