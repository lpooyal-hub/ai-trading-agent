import { useEffect, useState } from "react";
import { api, AgentDecision, DecisionEvaluation, DecisionPreview, TradeJournalEntry, TradeOrder } from "../api/client";
import { decisionGuardWarnings } from "../utils/decisionSafety";

function orderFillSummary(order: TradeOrder) {
  const intent = order.raw_response_json.order_intent;
  if (intent && typeof intent === "object") {
    const payload = intent as Record<string, unknown>;
    const side = typeof payload.side === "string" ? payload.side : "실주문";
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
  return `포지션 ${before.toFixed(4)} -> ${after.toFixed(4)}`;
}

export function DecisionDetailPage({ decisionId }: { decisionId: number | null }) {
  const [decision, setDecision] = useState<AgentDecision | null>(null);
  const [preview, setPreview] = useState<DecisionPreview | null>(null);
  const [order, setOrder] = useState<TradeOrder | null>(null);
  const [evaluations, setEvaluations] = useState<DecisionEvaluation[]>([]);
  const [journalEntries, setJournalEntries] = useState<TradeJournalEntry[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [isApproving, setIsApproving] = useState(false);
  const [isCreatingJournal, setIsCreatingJournal] = useState(false);

  useEffect(() => {
    setOrder(null);
    setEvaluations([]);
    setJournalEntries([]);
    setMessage(null);
    if (!decisionId) {
      setDecision(null);
      setPreview(null);
      return;
    }
    Promise.all([
      api.getDecision(decisionId),
      api.previewDecision(decisionId),
      api.getEvaluationsForDecision(decisionId),
      api.getJournalEntriesForDecision(decisionId),
    ])
      .then(([decisionResult, previewResult, evaluationRows, journalRows]) => {
        setDecision(decisionResult);
        setPreview(previewResult);
        setEvaluations(evaluationRows);
        setJournalEntries(journalRows);
      })
      .catch(() => {
        setDecision(null);
        setPreview(null);
        setEvaluations([]);
        setJournalEntries([]);
      });
  }, [decisionId]);

  if (!decisionId) {
    return <div className="notice">상세를 확인할 판단을 선택하세요.</div>;
  }

  if (!decision) {
    return <div className="notice">판단 상세를 불러올 수 없습니다.</div>;
  }

  const approve = () => {
    if (isApproving) return;
    setIsApproving(true);
    setMessage(null);
    api.approveDecision(decision.id)
      .then((result) => {
        setOrder(result);
        setMessage(`판단이 ${result.status} 상태로 승인되었습니다.`);
      })
      .catch(() => setMessage("판단 승인에 실패했습니다."))
      .finally(() => setIsApproving(false));
  };

  const createJournalEntry = () => {
    if (isCreatingJournal) return;
    const latestEvaluation = evaluations[0] ?? null;
    const linkedOrderId = order?.id ?? decision.executed_order_id;
    setIsCreatingJournal(true);
    setMessage(null);
    api.createJournalEntry({
      decision_id: decision.id,
      order_id: linkedOrderId,
      evaluation_id: latestEvaluation?.id ?? null,
      strategy_tags: [
        "agent_feedback",
        decision.action.toLowerCase(),
        latestEvaluation ? "evaluated" : "pending_review",
      ],
    })
      .then((entry) => {
        setJournalEntries((current) => [entry, ...current]);
        setMessage(`저널 #${entry.id}을 생성했습니다.`);
      })
      .catch((error) => {
        setMessage(error instanceof Error ? error.message : "저널 생성에 실패했습니다.");
      })
      .finally(() => setIsCreatingJournal(false));
  };

  const latestJournal = journalEntries[0] ?? null;
  const latestEvaluation = evaluations[0] ?? null;
  const guardWarnings = decisionGuardWarnings(decision);

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">판단 #{decision.id}</p>
          <h2>{decision.symbol} {decision.action}</h2>
        </div>
        <button className="primary-button" disabled={isApproving || (preview ? !preview.approved : false)} onClick={approve} type="button">
          {isApproving ? "승인 중..." : `${preview?.execution_mode ?? "판단"} 승인`}
        </button>
      </header>
      {message ? <div className="notice">{message}</div> : null}
      <div className="detail-grid">
        <section>
          <h3>주문 미리보기</h3>
          <p>{preview ? `${preview.side ?? "없음"} ${preview.estimated_quantity.toFixed(6)} ${preview.symbol} · $${preview.estimated_price.toFixed(2)}` : "미리보기를 사용할 수 없습니다."}</p>
          <p>{preview ? `$${preview.estimated_order_amount.toFixed(2)} · ${preview.execution_mode}` : null}</p>
        </section>
        <section>
          <h3>리스크 검증</h3>
          <p>{preview ? `${preview.approved ? "승인" : "거절"} · ${preview.reason}` : "미리보기를 사용할 수 없습니다."}</p>
        </section>
        <section>
          <h3>예산 영향</h3>
          <p>{preview ? `사용 가능 $${preview.available_budget.toFixed(2)} · 노출 $${preview.bot_exposure.toFixed(2)}` : "미리보기를 사용할 수 없습니다."}</p>
        </section>
        <section>
          <h3>포지션 범위</h3>
          <p>{preview ? `봇 보유 ${preview.bot_owned_quantity.toFixed(6)} · 기존 보유 보호 ${preview.legacy_protected ? "예" : "아니오"}` : "미리보기를 사용할 수 없습니다."}</p>
        </section>
        <section>
          <h3>판단 근거</h3>
          <p>{decision.thesis}</p>
        </section>
        <section>
          <h3>리스크 메모</h3>
          <p>{decision.risk_notes}</p>
        </section>
        <section>
          <h3>LLM 사용량</h3>
          <p>{decision.llm_model ?? "mock"} · {decision.total_tokens} tokens · ${decision.estimated_llm_cost_usd.toFixed(4)}</p>
        </section>
        <section>
          <h3>연결 주문</h3>
          <p>{order ? `주문 #${order.id} ${order.status}` : decision.executed_order_id ?? "없음"}</p>
          <p>{order ? orderFillSummary(order) : null}</p>
        </section>
        <section>
          <h3>저널</h3>
          <p>{latestJournal ? `최근 #${latestJournal.id} · ${latestJournal.outcome_label} · 보상 ${latestJournal.reward_score.toFixed(4)}` : "아직 저널이 없습니다."}</p>
          <p>{latestEvaluation ? `평가 #${latestEvaluation.id} · ${latestEvaluation.evaluation_window} · ${latestEvaluation.return_percent.toFixed(2)}%` : "연결된 평가가 없습니다."}</p>
          <button className="secondary-button" disabled={isCreatingJournal} onClick={createJournalEntry} type="button">
            {isCreatingJournal ? "생성 중..." : "저널 생성"}
          </button>
        </section>
      </div>
      {guardWarnings.length ? (
        <section className="warning-panel">
          <h3>응답 가드</h3>
          <p>LLM 응답이 저장 전 정규화되어 이 판단은 실행이 차단되었습니다.</p>
          <ul>
            {guardWarnings.map((warning) => <li key={warning}>{warning}</li>)}
          </ul>
        </section>
      ) : null}
      {preview?.warnings.length ? (
        <section>
          <h3>미리보기 경고</h3>
          <ul>
            {preview.warnings.map((warning) => <li key={warning}>{warning}</li>)}
          </ul>
        </section>
      ) : null}
      <section>
        <h3>입력 스냅샷</h3>
        <pre>{JSON.stringify(decision.input_snapshot_json, null, 2)}</pre>
      </section>
      <section>
        <h3>에이전트 Raw JSON</h3>
        <pre>{JSON.stringify(decision.agent_response_json, null, 2)}</pre>
      </section>
    </section>
  );
}
