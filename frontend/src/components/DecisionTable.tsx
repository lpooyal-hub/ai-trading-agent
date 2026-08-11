import { AgentDecision } from "../api/client";
import { formatKRW } from "../utils/currency";
import { decisionBlockReason, decisionGuardWarnings } from "../utils/decisionSafety";
import { actionLabel, statusLabel } from "../utils/labels";

function formatDateTime(value: string) {
  return new Date(value).toLocaleString(undefined, {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function statusTone(value: string) {
  const normalized = value.toUpperCase();
  if (["APPROVED", "EXECUTED", "SUCCEEDED", "SIMULATED", "SIMULATED_FILLED"].includes(normalized)) return "positive";
  if (["REJECTED", "FAILED"].includes(normalized)) return "negative";
  return "neutral";
}

type DecisionTableProps = {
  decisions: AgentDecision[];
  onSelect?: (id: number) => void;
};

export function DecisionTable({ decisions, onSelect }: DecisionTableProps) {
  return (
    <div className="table-wrap wide-table">
      <table>
        <thead>
          <tr>
            <th>시각</th>
            <th>종목</th>
            <th>판단</th>
            <th>신뢰도</th>
            <th>금액</th>
            <th>상태</th>
            <th>가드</th>
            <th>차단 사유</th>
            <th>모의</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {decisions.map((decision) => {
            const guardWarnings = decisionGuardWarnings(decision);
            const blockReason = decisionBlockReason(decision);
            return (
              <tr key={decision.id}>
                <td className="muted-cell">{formatDateTime(decision.created_at)}</td>
                <td className="symbol-cell">{decision.symbol}</td>
                <td>{actionLabel(decision.action)}</td>
                <td>{Math.round(decision.confidence * 100)}%</td>
                <td>{formatKRW(decision.recommended_order_amount)}</td>
                <td>
                  <span className={`status-pill ${statusTone(decision.status)}`}>{statusLabel(decision.status)}</span>
                </td>
                <td>
                  <span className={`status-pill ${guardWarnings.length ? "negative" : "positive"}`}>
                    {guardWarnings.length ? `경고 ${guardWarnings.length}개` : "정상"}
                  </span>
                </td>
                <td className="reason-cell">{blockReason || "-"}</td>
                <td>{decision.dry_run ? "예" : "아니오"}</td>
                <td>
                  {onSelect ? (
                    <button className="small-button" onClick={() => onSelect(decision.id)} type="button">
                      상세
                    </button>
                  ) : null}
                </td>
              </tr>
            );
          })}
          {!decisions.length ? (
            <tr>
              <td colSpan={10}>아직 판단 기록이 없습니다.</td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}
