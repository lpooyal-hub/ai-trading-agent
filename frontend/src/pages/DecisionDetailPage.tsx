import { useEffect, useState } from "react";
import { api, AgentDecision, TradeOrder } from "../api/client";

export function DecisionDetailPage({ decisionId }: { decisionId: number | null }) {
  const [decision, setDecision] = useState<AgentDecision | null>(null);
  const [order, setOrder] = useState<TradeOrder | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!decisionId) return;
    api.getDecision(decisionId).then(setDecision).catch(() => setDecision(null));
  }, [decisionId]);

  if (!decisionId) {
    return <div className="notice">Select a decision to review its details.</div>;
  }

  if (!decision) {
    return <div className="notice">Decision detail is not available.</div>;
  }

  const approve = () => {
    api.approveDecision(decision.id)
      .then((result) => {
        setOrder(result);
        setMessage(`Decision approved as ${result.status}.`);
      })
      .catch(() => setMessage("Decision approval failed."));
  };

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">Decision #{decision.id}</p>
          <h2>{decision.symbol} {decision.action}</h2>
        </div>
        <button className="primary-button" onClick={approve} type="button">Approve DRY_RUN</button>
      </header>
      {message ? <div className="notice">{message}</div> : null}
      <div className="detail-grid">
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
        </section>
      </div>
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
