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
  RUNNING: "진행 중",
  SUCCEEDED: "성공",
  SIMULATED: "모의 체결",
  SIMULATED_FILLED: "모의 체결",
  LIVE_SUBMITTED: "실주문 제출",
  LIVE_PARTIAL: "부분 체결",
  LIVE_FILLED: "실주문 체결",
  LIVE_CANCELED: "실주문 취소",
  TODO_LIVE_ORDER_NOT_IMPLEMENTED: "실주문 차단",
  FAILED: "실패",
  PENDING_REVIEW: "리뷰 대기",
  EVALUATED: "평가 완료",
  OPEN: "진행 중",
  CLOSED: "종료",
  ACTIVE: "활성",
  DRY_RUN: "모의 실행",
  PAPER_AUTO: "모의 자동",
  LIVE: "실거래",
  LIVE_ORDER: "실주문",
  MANUAL_APPROVAL: "수동 승인",
  MOCK: "모의 응답",
  REAL_OPENAI: "실제 OpenAI",
  UNAVAILABLE: "사용 불가",
  UNKNOWN: "알 수 없음",
};

const OUTCOME_LABELS: Record<string, string> = {
  PROFITABLE: "수익",
  UNPROFITABLE: "손실",
  PENDING_REVIEW: "리뷰 대기",
  SKIPPED_GUARD: "가드로 스킵",
  EVALUATED: "평가 완료",
};

const WINDOW_LABELS: Record<string, string> = {
  "1d": "1일",
  "3d": "3일",
  "7d": "7일",
  "14d": "14일",
  "30d": "30일",
};

// Mirrors backend/app/utils/symbols.py KRX_SYMBOL_NAMES. Kept as a static
// map (like the label tables above) rather than fetched from
// /market/symbol-names -- the frontend image has to be rebuilt to pick up
// any code change regardless, so a fetch buys no staleness protection here,
// only extra loading-state plumbing.
const SYMBOL_NAMES: Record<string, string> = {
  "005930": "삼성전자",
  "000660": "SK하이닉스",
  "005380": "현대차",
  "000270": "기아",
  "373220": "LG에너지솔루션",
  "207940": "삼성바이오로직스",
  "035420": "NAVER",
  "035720": "카카오",
  "005490": "POSCO홀딩스",
  "068270": "셀트리온",
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

// "삼성전자 (005930)" when the code is known, otherwise just the bare code.
export function symbolLabel(value: string | null | undefined) {
  const normalized = normalize(value);
  if (!normalized) return "-";
  const name = SYMBOL_NAMES[normalized];
  return name ? `${name} (${normalized})` : normalized;
}
