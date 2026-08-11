# 해외장 → 국내장 전환 + KRW 통화 + 멀티섹터 개편

작성일: 2026-08-11
목적: 시장을 해외장(America/New_York, 반도체 US 종목)에서 국내장(KRX, Asia/Seoul)으로,
통화를 USD에서 KRW로, 섹터 필터를 단일 섹터에서 멀티섹터(화이트리스트 기반)로 바꾼다.
`docs/plans/continuous-session-loop.md`(LangGraph 세션 루프)와는 독립적인 변경이다.

## 0. 사용자 결정사항

- **통화: KRW로 전면 전환.** `_usd` 필드/표시를 트레이딩 관련 금액은 전부 `_krw`로 바꾼다.
- **섹터: 화이트리스트(`ALLOWED_SYMBOLS`)는 유지하되 범위만 멀티섹터로 넓힌다.** `ALLOWED_SECTOR` 단일 섹터 제한 자체를 없앤다. AGENTS.md의 "active universe 밖 종목 금지" 절대규칙은 `ALLOWED_SYMBOLS`로 계속 지켜진다.
- 워커 실행 모델(24/7 vs 하이브리드)은 `continuous-session-loop.md` §1.4에서 이미 하이브리드로 결정됨 — 이 문서와 무관.

## 1. 중요 예외: LLM 비용은 그대로 USD

**OpenAI는 USD로 과금하므로, LLM/토큰 비용 관련 필드는 이번 통화 전환 대상이 아니다.** 아래 필드/키는 이름과 값 모두 절대 건드리지 않는다:

- `config.py`: `llm_daily_cost_limit_usd`, `llm_monthly_cost_limit_usd`, `llm_input_cost_per_1m_tokens_usd`, `llm_output_cost_per_1m_tokens_usd`
- `models.py`: `AgentDecision.estimated_llm_cost_usd`, `LLMUsage.estimated_cost_usd`
- `llm_cost_service.py`, `llm_usage_service.py`, `llm_budget_manager.py`의 모든 `_usd` 필드/딕�너리 키 (`today_estimated_cost_usd`, `monthly_estimated_cost_usd`, `daily_cost_remaining_usd`, `monthly_cost_remaining_usd` 등)
- `decision_agent.py`/`logger_agent.py`/`agent_graph_service.py`의 `estimated_cost_usd`/`estimated_llm_cost_usd`

**단, 트레이딩 금액(KRW)과 LLM 비용(USD)을 한 지표에서 섞는 곳이 있다 — 여기가 이번 개편의 진짜 위험 지점이다.**
`portfolio_service.py::get_cost_recovery()`가 `total_pnl - monthly_llm_cost`, `total_pnl / monthly_llm_cost` 식으로 KRW와 USD를 그대로 빼고 나눈다. 통화 단위가 갈리면 이 계산은 그냥 틀린 숫자가 된다.

**해결책 (Claude가 이미 `config.py`에 추가함):** `Settings.usd_to_krw_display_rate: float = 1300` — 실시간 환율 연동이 아니라 표시용 고정 근사치. `get_cost_recovery()`에서 `monthly_llm_cost_usd`를 이 비율로 KRW 환산한 뒤에만 KRW PnL과 연산할 것. 원본 `monthly_llm_cost_usd`/`today_llm_cost_usd`는 그대로 USD로도 같이 노출(참고용).

## 2. Claude가 이미 완료한 부분 (계약 파일, 커밋됨)

| 파일 | 변경 |
|---|---|
| `backend/app/config.py` | `agent_market_timezone/open/close` → `Asia/Seoul`/`09:00`/`15:30`. `allowed_sector` 필드 제거. `bot_capital_limit_usd→_krw`(300000), `max_order_amount_usd→_krw`(130000), `min_cash_reserve_usd→_krw`(30000), `min_order_amount_usd→_krw`(5000), `agent_auto_execute_max_order_amount_usd→_krw`(65000). `fractional_trading_enabled` 기본값 `False`, `quantity_decimal_places` 기본값 `0` (KRX는 정수 주 단위). `allowed_symbols_csv` 기본값을 멀티섹터 KRX 종목코드로 교체 (아래 §3). `usd_to_krw_display_rate=1300` 신규 추가 |
| `backend/app/risk/risk_manager.py` | 섹터 일치 검증 제거. `_usd` 금액 필드 전부 `_krw`로 교체 |
| `backend/app/strategy/sector_candidate_selector.py` | 클래스명 `SectorCandidateSelector` → `CandidateSelector`, `allowed_sector` 파라미터/필터 제거 (universe 필터만 남음) |
| `backend/app/agents/market_agent.py` | `CandidateSelector` 사용으로 갱신, `get_demo_snapshots(sector=...)` 인자 제거 |
| `backend/app/services/market_service.py` | `get_demo_snapshots(sector=...)` 호출부·수동 스냅샷 섹터 검증 제거 (universe 검증만 남음) |
| `backend/app/services/agent_service.py`, `agent_graph_service.py` | **버그 수정**: `AgentDecision.sector`가 전역 `allowed_sector` 상수 대신 실제 선택된 `selected_snapshot.sector`를 쓰도록 수정 (섹터가 하나뿐이던 예전엔 우연히 맞았지만, 멀티섹터에서는 실제 종목 섹터를 반영해야 함). `_save_skipped_decision`의 `sector`는 `"unknown"` |
| `backend/app/services/trading_service.py` | 포지션 생성 시 섹터 fallback을 `"unknown"`으로 변경 (그 외 `_usd`는 아직 미변경, §4 참고) |
| `backend/app/clients/mock_market_data_client.py` | `get_demo_snapshots(symbols)`에서 `sector` 인자 제거, 심볼별 섹터 매핑(`_DEFAULT_SECTORS`)으로 대체, 가격을 KRW 스케일(50000~)로 조정 |
| `backend/app/clients/mock_toss_client.py` | `cash_usd=250` → `cash_krw=300000`, `avg_price` KRW 스케일로 조정 |
| `backend/.env.example`, `backend/.env` | 위 계약과 동일하게 갱신 (`.env`는 gitignore됨, 커밋 안 됨) |

**주의: 이 상태로는 백엔드가 실행되지 않는다.** `routes/settings.py`, `llm_client.py`, `decision_agent.py`, `order_agent.py`, `portfolio_service.py` 등이 아직 존재하지 않는 `settings.allowed_sector`/`settings.bot_capital_limit_usd` 등을 참조해서 `AttributeError`가 난다 — §4가 이어서 고친다. 이 커밋을 실행 중인 `ai-trading-agent-backend-1`에 반영(재기동)하지 말 것.

## 3. 신규 기본 종목 유니버스 (멀티섹터 KRX 대형주)

```
005930  삼성전자        semiconductor
000660  SK하이닉스      semiconductor
005380  현대차          automobile
000270  기아            automobile
373220  LG에너지솔루션  battery
207940  삼성바이오로직스 bio
035420  NAVER           internet
035720  카카오          internet
005490  POSCO홀딩스     steel
068270  셀트리온        bio
```

`mock_market_data_client.py`의 `_DEFAULT_SECTORS`가 이 매핑을 갖고 있다. `ALLOWED_SYMBOLS`를 커스텀으로 바꾸면 매핑에 없는 심볼은 섹터 `"unknown"`으로 표시된다 (필터링에는 영향 없음 — 섹터는 이제 정보성 메타데이터일 뿐 화이트리스트 통과 여부와 무관).

## 4. Codex 담당 (기계적 치환 + 도메인 지식이 크게 필요없는 나머지)

### 4.1 규칙

- **"트레이딩 금액" 필드만 `_usd` → `_krw`로 바꾼다.** 아래 목록은 이미 확인된 트레이딩 금액 필드다:
  `bot_capital_limit`, `max_order_amount`, `min_cash_reserve`, `min_order_amount`, `agent_auto_execute_max_order_amount`, `invested_amount`, `available_budget`, `unrealized_pnl`, `realized_pnl`, `total_pnl`, `paper_total_pnl`, `paper_realized_pnl`, `gross_bought`, `gross_sold`, `sell_amount`, `cost_basis`, `live_submitted_order_amount`, `max_symbol_exposure`(risk_manager 내부 변수, 이미 완료).
- **§1의 LLM 비용 필드는 절대 건드리지 않는다.**
- `net_after_llm_cost`/`realized_net_after_llm_cost`/`llm_cost_recovery_ratio`/`realized_llm_cost_recovery_ratio` (`portfolio_service.py::get_cost_recovery`)는 `settings.usd_to_krw_display_rate`로 `monthly_llm_cost_usd`를 KRW 환산한 뒤에만 KRW 값과 연산하도록 고친다. 최종 필드명은 `net_after_llm_cost_krw` 등으로 변경.
- KRW는 소수점을 쓰지 않는다 (원 단위 정수). 프론트엔드 표시에서 `.toFixed(2)` 같은 소수점 포맷은 전부 제거.
- 숫자 리터럴(테스트 픽스처, `seed_demo_data.py`의 시드 금액 등)은 정확한 환율 계산 대신 "그 자리에서 자연스러운 KRW 크기"로 바꾸면 된다 (예: USD 100 → KRW 100000 같은 대략적 스케일. 정밀도가 중요한 곳이 아님).

### 4.2 백엔드 파일 목록

| 파일 | 작업 |
|---|---|
| `backend/app/routes/settings.py` | `allowed_sector` 제거, `_usd`→`_krw` (트레이딩 필드만) |
| `backend/app/schemas.py` | `SettingsRead`에서 `allowed_sector: str` 필드 제거, 트레이딩 관련 `_usd` 필드 전부 `_krw`로. LLM 비용 관련 스키마 필드는 유지 |
| `backend/app/clients/llm_client.py` | 프롬프트에 넘기는 `settings_snapshot`에서 `allowed_sector` 키 제거, `bot_capital_limit_usd`/`max_order_amount_usd` 키를 `_krw`로 (그리고 통화가 KRW임을 LLM이 알 수 있게 프롬프트/컨텍스트에 명시할 것 — 프롬프트가 하드코딩된 "USD" 문구를 갖고 있다면 "KRW"로) |
| `backend/app/agents/decision_agent.py` | `max_order_amount_usd` 파라미터/사용 → `_krw` |
| `backend/app/agents/order_agent.py` | `agent_auto_execute_max_order_amount_usd` → `_krw` |
| `backend/app/strategy/decision_response_guard.py` | `max_order_amount_usd` 파라미터/속성 → `_krw` |
| `backend/app/services/agent_service.py` | 자동화 정책 딕셔너리의 `"max_order_amount_usd"` 키 → `"max_order_amount_krw"` (2곳, `agent_auto_execute_max_order_amount_krw` 참조) |
| `backend/app/services/trading_service.py` | 남은 `bot_capital_limit_usd`/`min_cash_reserve_usd` → `_krw` |
| `backend/app/services/portfolio_service.py` | 위 §4.1 규칙대로 트레이딩 `_usd` 필드 전부 `_krw`로, `get_cost_recovery()`는 환율 변환 적용 |
| `backend/app/seed_demo_data.py` | 트레이딩 관련 시드 금액을 KRW 스케일로 (LLM cost 시드값은 그대로) |
| `backend/tests/test_sector_candidate_selector.py` | `CandidateSelector`로 임포트/생성자 갱신 (`allowed_sector` 인자 제거), 여러 섹터가 섞인 스냅샷으로도 필터링 없이 전부 후보에 오르는지 검증하는 케이스 추가 |
| `backend/tests/test_risk_manager.py` | `allowed_sector` 관련 인자/검증 제거, `_usd`→`_krw` |
| 그 외 `_usd`를 참조하는 테스트 전부 | 위 규칙대로 갱신 (`grep -rn "_usd\|allowed_sector" backend/tests`로 전수 확인) |

### 4.3 프론트엔드

- `frontend/src/api/client.ts`: 트레이딩 관련 타입 필드 `_usd` → `_krw` (LLM 사용량 관련 타입은 유지), `allowed_sector` 필드 제거
- 새 공유 포맷 헬�퍼 추가 (예: `frontend/src/utils/currency.ts`): `formatKRW(value: number): string`이 `Intl.NumberFormat("ko-KR", { style: "currency", currency: "KRW" })` 또는 동등한 방식으로 `₩1,234,000` 형태(소수점 없음)를 반환
- 아래 파일들의 `` `$${value.toFixed(2)}` `` 패턴을 `formatKRW(value)` 호출로 교체: `PositionTable.tsx`, `OrderTable.tsx`, `DecisionTable.tsx`, `MemoryPage.tsx`, `EvaluationsPage.tsx`, `OrdersPage.tsx`, `DecisionDetailPage.tsx`, `WorkflowsPage.tsx`, `SettingsPage.tsx`, `MarketPage.tsx`, `SessionsPage.tsx`, `PortfolioPage.tsx`, `BrokerPage.tsx`, `JournalPage.tsx`, `DashboardPage.tsx`
- `LLMUsagePage.tsx`는 LLM 비용이라 `$` 유지 (건드리지 않음) — 단, 실제로 그 파일이 트레이딩 금액도 같이 보여준다면 그 부분만 KRW로
- `frontend/src/utils/decisionSafety.ts`의 `$` 사용도 트레이딩 금액이면 KRW로
- 화면에 있던 "반도체 섹터" 같은 하드코딩 문구가 있다면 제거하거나 일반화

### 4.4 문서

- `README.md`, `backend/README.md`, `AGENTS.md`: 해외장/반도체/USD 관련 서술을 국내장(KRX)/멀티섹터/KRW로 갱신. `AGENTS.md`의 "절대 규칙" 중 `ALLOWED_SECTOR` 언급은 삭제(더는 존재하지 않음), `ALLOWED_SYMBOLS` 관련 규칙은 유지.

## 5. 제약 (지켜야 함)

- Docker 명령 직접 실행 금지 (기존 컨벤션과 동일).
- `.env`, 실제 계좌 정보 등 절대 커밋 금지.
- 변경사항은 커밋하지 말고 워킹 트리에 남길 것 — Claude가 리뷰 후 커밋.
- §2에 나열된 Claude 소유 파일들의 이미 확정된 필드명/값은 그대로 소비할 것 (다시 바꾸지 말 것).
- `RiskManager`, `market_service.py`의 universe 검증(`ALLOWED_SYMBOLS` 밖 심볼 거부) 로직 자체는 건드리지 말 것 — 안전 경계는 그대로 유지.

## 6. 아직 열려있는 질문

- `usd_to_krw_display_rate=1300`은 고정 근사치다. 나중에 실제 환율 API 연동이 필요하면 별도 논의.
- 실제 라이브 주문 시 Toss가 국내(KRX) 주문 경로를 이 프로젝트의 `TOSS_ORDER_PATH` 등 설정으로 그대로 지원하는지는 아직 확인 안 됨 — `DRY_RUN=true` 상태에서는 문제 없지만, 나중에 실거래 전환 시 확인 필요.
