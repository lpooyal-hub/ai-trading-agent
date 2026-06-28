import { useEffect, useState } from "react";
import { api, AgentDecision, DecisionPreview, TradeOrder } from "../api/client";

function orderFillSummary(order: TradeOrder) {
  const intent = order.raw_response_json.order_intent;
  if (intent && typeof intent === "object") {
    const payload = intent as Record<string, unknown>;
    const side = typeof payload.side === "string" ? payload.side : "LIVE";
    const quantity = typeof payload.quantity === "number" ? payload.quantity.toFixed(6) : "-";
    const idempotencyKey = typeof payload.idempotency_key === "string" ? payload.idempotency_key : "no-key";
    return `${side} ${quantity} · ${idempotencyKey}`;
  }

  const fill = order.raw_response_json.simulated_fill;
  if (!fill || typeof fill !== "object") return null;

  const payload = fill as Record<string, unknown>;
  const before = typeof payload.position_quantity_before === "number" ? payload.position_quantity_before : null;
  const after = typeof payload.position_quantity_after === "number" ? payload.position_quantity_after : null;
  if (before === null || after === null) return null;
  return `Position ${before.toFixed(4)} -> ${after.toFixed(4)}`;
}

export function DecisionDetailPage({ decisionId }: { decisionId: number | null }) {
  const [decision, setDecision] = useState<AgentDecision | null>(null);
  const [preview, setPreview] = useState<DecisionPreview | null>(null);
  const [order, setOrder] = useState<TradeOrder | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [isApproving, setIsApproving] = useState(false);

  useEffect(() => {
    setOrder(null);
    setMessage(null);
    if (!decisionId) {
      setDecision(null);
      setPreview(null);
      return;
    }
    Promise.all([api.getDecision(decisionId), api.previewDecision(decisionId)])
      .then(([decisionResult, previewResult]) => {
        setDecision(decisionResult);
        setPreview(previewResult);
      })
      .catch(() => {
        setDecision(null);
        setPreview(null);
      });
  }, [decisionId]);

  if (!decisionId) {
    return <div className="notice">Select a decision to review its details.</div>;
  }

  if (!decision) {
    return <div className="notice">Decision detail is not available.</div>;
  }

  const approve = () => {
    if (isApproving) return;
    setIsApproving(true);
    setMessage(null);
    api.approveDecision(decision.id)
      .then((result) => {
        setOrder(result);
        setMessage(`Decision approved as ${result.status}.`);
      })
      .catch(() => setMessage("Decision approval failed."))
      .finally(() => setIsApproving(false));
  };

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">Decision #{decision.id}</p>
          <h2>{decision.symbol} {decision.action}</h2>
        </div>
        <button className="primary-button" disabled={isApproving || (preview ? !preview.approved : false)} onClick={approve} type="button">
          {isApproving ? "Approving..." : `Approve ${preview?.execution_mode ?? "Decision"}`}
        </button>
      </header>
      {message ? <div className="notice">{message}</div> : null}
      <div className="detail-grid">
        <section>
          <h3>Order Preview</h3>
          <p>{preview ? `${preview.side ?? "NONE"} ${preview.estimated_quantity.toFixed(6)} ${preview.symbol} at $${preview.estimated_price.toFixed(2)}` : "Preview unavailable"}</p>
          <p>{preview ? `$${preview.estimated_order_amount.toFixed(2)} · ${preview.execution_mode}` : null}</p>
        </section>
        <section>
          <h3>RiskManager</h3>
          <p>{preview ? `${preview.approved ? "Approved" : "Rejected"} · ${preview.reason}` : "Preview unavailable"}</p>
        </section>
        <section>
          <h3>Budget Impact</h3>
          <p>{preview ? `Available $${preview.available_budget.toFixed(2)} · Exposure $${preview.bot_exposure.toFixed(2)}` : "Preview unavailable"}</p>
        </section>
        <section>
          <h3>Position Scope</h3>
          <p>{preview ? `Bot owned ${preview.bot_owned_quantity.toFixed(6)} · Legacy protected ${preview.legacy_protected ? "Yes" : "No"}` : "Preview unavailable"}</p>
        </section>
        <section>
          <h3>Thesis</h3>
          <p>{decision.thesis}</p>
        </section>
        <section>
          <h3>Risk Notes</h3>
          <p>{decision.risk_notes}</p>
        </section>
        <section>
          <h3>LLM Usage</h3>
          <p>{decision.llm_model ?? "mock"} · {decision.total_tokens} tokens · ${decision.estimated_llm_cost_usd.toFixed(4)}</p>
        </section>
        <section>
          <h3>Linked Order</h3>
          <p>{order ? `Order #${order.id} ${order.status}` : decision.executed_order_id ?? "None"}</p>
          <p>{order ? orderFillSummary(order) : null}</p>
        </section>
      </div>
      {preview?.warnings.length ? (
        <section>
          <h3>Preview Warnings</h3>
          <ul>
            {preview.warnings.map((warning) => <li key={warning}>{warning}</li>)}
          </ul>
        </section>
      ) : null}
      <section>
        <h3>Input Snapshot</h3>
        <pre>{JSON.stringify(decision.input_snapshot_json, null, 2)}</pre>
      </section>
      <section>
        <h3>Agent Raw JSON</h3>
        <pre>{JSON.stringify(decision.agent_response_json, null, 2)}</pre>
      </section>
    </section>
  );
}
