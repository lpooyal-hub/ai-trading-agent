const ACTION_LABELS: Record<string, string> = {
  BUY: "매수",
  SELL: "매도",
  HOLD: "보류",
  SKIP: "건너뜀",
};

const STATUS_LABELS: Record<string, string> = {
  PENDING: "대기",
  APPROVED: "승인",
  REJECTED: "거절",
  EXECUTED: "실행됨",
  SKIPPED: "건너뜀",
  SIMULATED: "모의 체결",
  SIMULATED_FILLED: "모의 체결",
  TODO_LIVE_ORDER_NOT_IMPLEMENTED: "실주문 차단",
  FAILED: "실패",
  PENDING_REVIEW: "리뷰 대기",
  EVALUATED: "평가 완료",
  OPEN: "진행 중",
  CLOSED: "종료",
  ACTIVE: "활성",
  DRY_RUN: "모의 실행",
  PAPER_AUTO: "Paper 자동",
  LIVE: "실거래",
  LIVE_ORDER: "실주문",
  MANUAL_APPROVAL: "수동 승인",
  MOCK: "Mock",
  REAL_OPENAI: "실제 OpenAI",
  UNAVAILABLE: "사용 불가",
  UNKNOWN: "알 수 없음",
};

const OUTCOME_LABELS: Record<string, string> = {
  PROFITABLE: "수익",
  UNPROFITABLE: "손실",
  PENDING_REVIEW: "리뷰 대기",
  EVALUATED: "평가 완료",
};

const WINDOW_LABELS: Record<string, string> = {
  "1d": "1일",
  "3d": "3일",
  "7d": "7일",
  "14d": "14일",
  "30d": "30일",
};

function normalize(value: string | null | undefined) {
  return value?.trim();
}

function labelFromMap(value: string | null | undefined, labels: Record<string, string>) {
  const normalized = normalize(value);
  if (!normalized) return "-";
  const key = normalized.toUpperCase();
  return labels[key] ?? normalized;
}

export function actionLabel(value: string | null | undefined) {
  return labelFromMap(value, ACTION_LABELS);
}

export function statusLabel(value: string | null | undefined) {
  return labelFromMap(value, STATUS_LABELS);
}

export function outcomeLabel(value: string | null | undefined) {
  return labelFromMap(value, OUTCOME_LABELS);
}

export function evaluationWindowLabel(value: string | null | undefined) {
  return labelFromMap(value, WINDOW_LABELS);
}
