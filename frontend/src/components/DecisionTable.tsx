import { AgentDecision } from "../api/client";
import { decisionBlockReason, decisionGuardWarnings } from "../utils/decisionSafety";

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
            <th>Guard</th>
            <th>Block Reason</th>
            <th>Dry Run</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {decisions.map((decision) => {
            const guardWarnings = decisionGuardWarnings(decision);
            const blockReason = decisionBlockReason(decision);
            return (
              <tr key={decision.id}>
                <td>{new Date(decision.created_at).toLocaleString()}</td>
                <td>{decision.symbol}</td>
                <td>{decision.action}</td>
                <td>{Math.round(decision.confidence * 100)}%</td>
                <td>${decision.recommended_order_amount.toFixed(2)}</td>
                <td>{decision.status}</td>
                <td>{guardWarnings.length ? `${guardWarnings.length} warning${guardWarnings.length > 1 ? "s" : ""}` : "OK"}</td>
                <td className="reason-cell">{blockReason || "-"}</td>
                <td>{decision.dry_run ? "Yes" : "No"}</td>
                <td>
                  {onSelect ? (
                    <button className="small-button" onClick={() => onSelect(decision.id)} type="button">
                      Detail
                    </button>
                  ) : null}
                </td>
              </tr>
            );
          })}
          {!decisions.length ? (
            <tr>
              <td colSpan={10}>No decisions yet.</td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}
