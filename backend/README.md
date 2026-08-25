# AI Trading Agent Backend

토스증권 Open API를 기본 브로커 어댑터로 가정한 국내 KRX 멀티섹터·KRW 기반 실험용 AI 트레이딩 에이전트 백엔드입니다.

현재 기본 설정은 DRY_RUN / paper trading입니다. 실행 모드는 별도 브랜치가 아니라 env로 나누며, live order는 Toss credentials, `TOSS_ORDER_PATH`, 관리자 API key가 모두 준비된 경우에만 opt-in으로 전송됩니다.

## 현재 단계

현재 backend는 공개 포트폴리오용 LangGraph agentic workflow 골격을 넘어서, paper trading, PostgreSQL 저장, Redis runtime guard, LLM 비용 추적, 사후 평가, 저널, memory feedback, Toss read-only/live adapter boundary까지 구현된 상태입니다. 기본 실행은 안전한 DRY_RUN / mock / paper trading이며, live order는 env opt-in 조건을 모두 만족할 때만 adapter가 선택됩니다.

- FastAPI 앱 엔트리
- dotenv 기반 설정
- Toss Securities Open API 기준 브로커 설정
- SQLAlchemy 기반 DB 연결(SQLite local fallback, Docker Compose PostgreSQL)
- Redis runtime lock 기반 중복 workflow 실행 방지
- 핵심 ORM 모델
- Pydantic 스키마
- LangGraph agent node 기반 workflow run/step audit 기록
- 에이전트 판단별 LLM 토큰/예상 비용 기록 필드
- LLM client result wrapper: parsed response, raw response, usage, latency, success status
- Market/News/Risk/Memory/Decision/Execution Risk/Logger/Order/Evaluation/Journal agent 분리
- Paper execution adapter와 Toss live execution adapter boundary
- Evaluation, Journal, Memory feedback loop
- `/health`
- `/settings/safety`
- `/settings/llm-budget`
- `/settings/security-readiness`
- `/settings/live-readiness`
- `/demo/status`
- `/demo/seed`
- `/broker/status`
- `/broker/accounts`
- `/broker/accounts/normalized`
- `/broker/positions`
- `/broker/positions/normalized`
- `/portfolio/initialize-legacy`
- `/portfolio/sync-legacy-from-broker`
- `/portfolio/sync-bot-from-market`
- `/portfolio/legacy`
- `/portfolio/bot`
- `/portfolio/summary`
- `/portfolio/performance`
- `/portfolio/cost-recovery`
- `/portfolio/realized-trades`
- `/portfolio/symbol-performance`
- `/agent/run-once`
- `/agent/run-scheduled`
- `/agent/status`
- `/agent/readiness`
- `/agent/schedule`
- `/agent/automation-policy`
- `/agent/operations`
- `/decisions`
- `/decisions/{decision_id}`
- `/decisions/{decision_id}/preview`
- `/decisions/{decision_id}/approve`
- `/decisions/{decision_id}/reject`
- `/orders`
- `/orders/{order_id}`
- `/market/snapshots`
- `/market/snapshots/latest`
- `/evaluations/run`
- `/evaluations/status`
- `/evaluations/{decision_id}`
- `/evaluations`
- `/journal`
- `/journal/decision/{decision_id}`
- `/journal/{entry_id}`
- `/memory/summary`
- `/llm-usage`
- `/llm-usage/summary`
- `/llm-usage/{usage_id}`
- 이후 단계용 모듈 구조

## 실행 명령어

기본 실행은 프로젝트 루트에서 Docker Compose를 사용합니다.

```bash
cd /home/ubuntu/ai-trading-agent
cp backend/.env.example backend/.env
docker compose up --build
```

Docker Compose의 `backend`, `frontend`, `postgres` 컨테이너는 모두 `backend/.env`를 읽습니다. Redis는 runtime lock 전용 서비스로 함께 실행됩니다. 실제 API 키와 운용 설정은 이 파일에 넣고 저장소에는 커밋하지 않습니다.

Docker Compose 기본 DB는 프로젝트 전용 `postgres` 서비스입니다. 데이터는 Docker named volume `postgres_data`에 저장됩니다. 로컬에서 backend만 단독 실행할 때만 SQLite `DATABASE_URL`을 fallback으로 사용할 수 있습니다.

```text
DATABASE_URL=postgresql+psycopg://ai_trading_agent:change_this_postgres_password@postgres:5432/ai_trading_agent
```

운영 서버에서 Postgres 비밀번호를 바꾸는 경우 `backend/.env`에서 `POSTGRES_PASSWORD`와 `DATABASE_URL`을 함께 맞춰야 합니다.

로컬에서 backend만 따로 개발할 때만 아래 명령을 사용합니다.

```bash
cd /home/ubuntu/ai-trading-agent/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

외부 서버에서 frontend를 열어 backend를 호출하려면 `backend/.env`의 `CORS_ALLOWED_ORIGINS`에 브라우저에서 접속하는 frontend 주소를 함께 넣습니다.

```bash
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000,https://your-trading-domain.example
REQUIRE_ADMIN_API_KEY=true
ADMIN_API_KEY=<set-on-server-only>
TOSS_ORDER_PATH=<official-toss-order-path>
```

## 테스트

핵심 guard 로직은 추가 패키지 없이 표준 `unittest`로 검증합니다.

```bash
docker compose exec -T backend python -m unittest discover -s tests
docker compose exec -T backend python -m compileall app
```

현재 테스트 범위는 `DecisionResponseGuard`, `CandidateSelector`, `RiskManager`, market/news data client와 `NewsAgent`의 fail-soft 동작을 포함합니다. 외부 API를 다루는 테스트는 모두 mock을 사용합니다.

## Execution Modes

기본은 paper trading입니다.

```bash
DRY_RUN=true
LIVE_TRADING_ENABLED=false
USE_MOCK_DATA=true
AGENT_AUTOMATION_MODE=manual_approval
```

실제 Toss/OpenAI 설정을 확인하는 live-ready 모드는 env로 전환합니다.

```bash
DRY_RUN=false
LIVE_TRADING_ENABLED=true
USE_MOCK_DATA=false
REQUIRE_ADMIN_API_KEY=true
TOSS_ORDER_PATH=<official-toss-order-path>
TOSS_ORDER_STATUS_PATH=<official-toss-order-status-path>
```

위 값과 Toss credentials가 모두 준비되면 `TossLiveExecutionAdapter`가 broker order endpoint를 호출합니다. readiness가 부족하면 `BlockedLiveExecutionAdapter`가 order intent와 idempotency key를 저장하고 endpoint 호출은 차단합니다.

## 안전 원칙

- 기본 브로커 provider는 `toss_securities`입니다.
- `DRY_RUN=true`가 기본값입니다.
- `LIVE_TRADING_ENABLED=false`가 기본값입니다.
- 실주문 API 호출은 기본 설정에서 비활성화되어 있으며, env opt-in과 관리자 API key guard가 필요합니다.
- 기존 보유 주식은 legacy position으로 보호해야 합니다.
- 봇은 `.env`의 `ALLOWED_SYMBOLS`로 정의된 active universe 허용 종목만 다룰 수 있어야 합니다. 운영 universe는 KOSPI 멀티섹터 대형주와 명시적으로 검토한 비레버리지 ETF만 포함합니다 — 정확한 목록은 아래 "Universe" 절 참고.
- 에이전트 운용 비용을 보기 위해 판단별 토큰 사용량과 예상 비용을 기록합니다.
- `USE_MOCK_DATA=true`에서는 mock market data와 mock LLM 응답을 사용합니다.
- `USE_MOCK_DATA=false`와 `INTRADAY_SIGNALS_ENABLED=true`에서는 Toss 현재가를 한 번에 조회해 active universe를 갱신하고, 1차 후보에만 1분봉/호가를 조회합니다. 수동 입력 경로도 함께 사용할 수 있습니다.
- `MARKET_SNAPSHOT_MAX_AGE_MINUTES`보다 오래된 snapshot은 agent 입력에서 제외합니다.
- `USE_MOCK_DATA=false`, `OPENAI_API_KEY`, `LLM_MODEL_DECISION`이 모두 설정되면 실제 OpenAI Responses API를 사용할 수 있습니다.
- LLM 입력 비용을 줄이기 위해 active universe 전체가 아니라 rule-based pre-filter를 통과한 상위 후보만 agent에 전달하며, `LLM_MAX_CANDIDATES_PER_RUN`으로 개수를 제한합니다.
- 후보 선택 규칙은 `CandidateSelector` 전략 클래스로 분리되어 있으며, LLM 호출 전 deterministic pre-filter로 동작합니다. 섹터는 정보성 메타데이터이며, 후보 필터와 주문 안전 경계는 멀티섹터 `ALLOWED_SYMBOLS` 화이트리스트를 기준으로 합니다.
- LLM 호출 전 budget guard를 확인하고, 비용/토큰/호출 횟수/최소 호출 간격 한도를 넘으면 LLM 호출 없이 `SKIPPED` decision을 저장합니다.
- LLM 응답은 저장 직전 `DecisionResponseGuard`를 한 번 더 통과하며, 후보 밖 symbol, enum 밖 action, 범위 밖 confidence/order amount, 빈 thesis/risk_notes가 있으면 paper execution도 `SKIPPED`로 차단합니다.
- decision 승인 시에도 RiskManager가 최종 검증하며, env에 따라 DRY_RUN simulated order 또는 Toss live order 제출로 분기합니다.
- `PositionExitManager`는 매 가격 사이클에 모든 bot-only 보유종목을 LLM과 독립적으로 평가합니다. 기본 paper 정책은 -5% 손절, +8% 익절, +4% 수익 이후 고점 대비 2.5% 하락 트레일링, 최대 10거래일 보유이며 오래된 시세로는 청산하지 않습니다.
- 손실·거래횟수·건별금액 가드는 신규 BUY와 물타기를 차단하지만, bot 보유수량 이내의 위험 축소 SELL은 차단하지 않습니다. 자동 청산은 `DRY_RUN`의 `paper_auto`에서만 실행되며 live adapter로 전달되지 않습니다.
- `LIVE_TRADING_ENABLED=true`, `DRY_RUN=false`, `USE_MOCK_DATA=false`, Toss credentials, `TOSS_ORDER_PATH`가 준비되면 `TossLiveExecutionAdapter`가 live order를 제출합니다.
- Portfolio/Dashboard는 `LIVE_SUBMITTED` 주문을 제출 건수와 제출 금액으로 별도 표시하며, 체결 전 주문은 paper PnL이나 bot position 수량에 섞지 않습니다. `TOSS_ORDER_STATUS_PATH`가 있으면 `/orders/{order_id}/sync-live-status` 또는 `/orders/sync-live-status`로 broker 체결 상태를 조회하고, `LIVE_FILLED`로 정규화된 주문만 bot position에 한 번 반영합니다.
- readiness가 부족한 live intent는 `TODO_LIVE_ORDER_NOT_IMPLEMENTED`로 차단되며, order intent와 idempotency key가 raw payload에 남습니다.
- `/decisions/{decision_id}/preview`는 승인 전 예상 주문 수량, 금액, 예산 영향, legacy 보호 여부, RiskManager 결과를 보여줍니다.
- decision evaluation은 최신 snapshot 가격과 결정 당시 가격을 비교해 hindsight review를 저장합니다.
- Memory Agent는 journal/evaluation/decision 이력을 요약해 최근 성과, 반복 실수, lesson, 모델별 성과를 확인하는 read-only 분석 레이어입니다.
- `/broker/status`는 Toss API key/secret 준비 상태, 계좌 목록 조회 준비 상태, `TOSS_ACCOUNT_ID` 설정 여부, live readiness를 마스킹된 상태값으로만 보여줍니다.
- `/broker/accounts`, `/broker/positions`는 Toss read-only endpoint path가 `.env`에 설정된 경우에만 호출됩니다.
- `/broker/accounts/normalized`는 Toss 계좌 응답을 마스킹된 내부 표준 계좌 형태로 변환해 보여줍니다.
- `/broker/positions/normalized`는 Toss 잔고 응답을 내부 표준 포지션 형태로 변환해 보여줍니다.
- `/portfolio/sync-legacy-from-broker`는 Toss 조회 잔고를 protected legacy position으로 가져오며, bot position이 이미 있으면 import를 차단합니다.
- `/portfolio/sync-bot-from-market`는 freshness window 안의 최신 market snapshot으로 bot-only position의 현재가와 미실현 PnL을 갱신하며, legacy position은 건드리지 않습니다.
- `/settings/security-readiness`는 secret 값을 노출하지 않고 demo 안전 상태, Toss/OpenAI 준비 여부, 관리자 API key guard 상태, 경고와 다음 조치만 반환합니다.
- `REQUIRE_ADMIN_API_KEY=true`일 때 agent run, workflow run, decision approve/reject, demo seed, market refresh, portfolio sync, journal/evaluation 생성, LLM smoke test 같은 실행/변경성 API는 `X-Admin-API-Key` 또는 `Authorization: Bearer ...` 헤더가 필요합니다.

## Universe

감시 대상은 아래 KOSPI 멀티섹터 대형주 46개와 대표 비레버리지 ETF 6개로 제한합니다. `ALLOWED_SYMBOLS`가 실제 안전 경계이며, 여기 나열된 sector는 정보성 메타데이터일 뿐 후보 필터링에는 쓰이지 않습니다 (`CandidateSelector`/`RiskManager` 참고). 레버리지·인버스 ETF는 포함하지 않습니다. `000660`(SK하이닉스)은 사용자의 기존 실보유 종목이라 `PROTECTED_SYMBOLS`로만 보호하고 `ALLOWED_SYMBOLS`에는 넣지 않습니다 — 다시 추가하지 마세요.

- `005930` 삼성전자 — semiconductor
- `402340` SK스퀘어 — holding
- `009150` 삼성전기 — electronics
- `373220` LG에너지솔루션 — battery
- `005380` 현대차 — automobile
- `207940` 삼성바이오로직스 — bio
- `105560` KB금융 — finance
- `032830` 삼성생명 — finance
- `012450` 한화에어로스페이스 — defense
- `028260` 삼성물산 — holding
- `329180` HD현대중공업 — shipbuilding
- `000270` 기아 — automobile
- `034020` 두산에너빌리티 — heavy_industry
- `055550` 신한지주 — finance
- `068270` 셀트리온 — bio
- `012330` 현대모비스 — automobile
- `034730` SK — holding
- `006400` 삼성SDI — battery
- `086790` 하나금융지주 — finance
- `035420` NAVER — internet
- `010120` LS ELECTRIC — electrical_equipment
- `066570` LG전자 — electronics
- `000810` 삼성화재 — finance
- `009540` HD한국조선해양 — shipbuilding
- `042660` 한화오션 — shipbuilding
- `267260` HD현대일렉트릭 — electrical_equipment
- `298040` 효성중공업 — heavy_industry
- `005490` POSCO홀딩스 — steel
- `010130` 고려아연 — metals
- `316140` 우리금융지주 — finance
- `015760` 한국전력 — utility
- `096770` SK이노베이션 — energy
- `138040` 메리츠금융지주 — finance
- `011200` HMM — shipping
- `042700` 한미반도체 — semiconductor
- `006800` 미래에셋증권 — finance
- `051910` LG화학 — chemicals
- `010140` 삼성중공업 — shipbuilding
- `000150` 두산 — holding
- `033780` KT&G — consumer
- `017670` SK텔레콤 — telecom
- `018260` 삼성에스디에스 — it_services
- `035720` 카카오 — internet
- `267250` HD현대 — holding
- `079550` LIG넥스원 — defense
- `003550` LG — holding
- `069500` KODEX 200 — etf_domestic_equity
- `229200` KODEX 코스닥150 — etf_domestic_equity
- `379800` KODEX 미국S&P500 — etf_global_equity
- `379810` KODEX 미국나스닥100 — etf_global_equity
- `273130` KODEX 종합채권(AA-이상) 액티브 — etf_bond
- `411060` ACE KRX금현물 — etf_gold

## Agent 실행 흐름

현재 `/agent/run-once`는 아래 순서로 동작합니다.

1. `USE_MOCK_DATA=false`이면 Toss 현재가로 active universe의 snapshot을 갱신·저장하고, 1차 후보에만 1분봉/호가 시그널을 계산합니다. 실패 시 freshness window 안의 기존 snapshot을 사용합니다. mock mode이면 active universe의 mock snapshot을 저장합니다.
2. rule-based pre-filter로 1~3개 후보만 고릅니다. 후보는 change percent 절대값, volume, 상승/하락 압력 사유로 점수화됩니다.
3. 후보가 없으면 LLM을 호출하지 않고 `SKIPPED` 결정을 저장합니다.
4. 후보가 있으면 LLM budget guard를 확인합니다.
5. budget이 초과되면 LLM을 호출하지 않고 `SKIPPED` 결정을 저장합니다.
6. budget이 남아 있고 `USE_MOCK_DATA=true`이면 공개 데모용 mock LLM 응답으로 `AgentDecision`을 저장합니다.
7. `USE_MOCK_DATA=false`, `OPENAI_API_KEY`, `LLM_MODEL_DECISION`이 모두 준비되면 real OpenAI LLM 응답으로 `AgentDecision`을 저장합니다.
8. LLM client는 parsed response, raw response, usage, latency, success status를 반환합니다.
9. LLM 응답은 저장 직전 guard를 통과하며, 안전하지 않은 JSON 값이 있으면 `HOLD`/`SKIPPED`로 정규화하고 guard warning을 decision raw payload에 남깁니다.
10. LLM 사용량은 `LLMUsage`에 함께 기록합니다.
11. 기본값에서는 사용자가 decision을 승인하면 RiskManager 검증 후 `PaperExecutionAdapter`가 `TradeOrder`를 `SIMULATED` 상태로 저장합니다. `paper_auto` 정책이 켜져 있고 confidence/order amount 기준을 통과하면 run-once 직후 paper order까지 자동 실행할 수 있습니다.
12. BUY/SELL 시뮬레이션은 bot-only `BotPosition`만 갱신하고 legacy position은 건드리지 않습니다.
13. simulated order raw payload에는 fill 요약과 bot position 수량 before/after가 남습니다.
14. `/evaluations` API로 decision별 사후 평가를 저장하고 조회합니다. Evaluation window 기간이 지난 decision만 due 평가 대상으로 잡습니다.
15. Decision의 input snapshot에는 candidate symbols와 candidate score/reason이 저장되어, 이후 evaluation/journal에서 당시 후보 선정 근거를 추적할 수 있습니다.
16. `/journal` API와 Dashboard Journal 화면으로 decision/order/evaluation을 묶은 self feedback, lesson, reward score를 저장합니다. guard로 스킵된 run도 `SKIPPED_GUARD` 저널로 남겨 반복적인 데이터/예산/후보 부족 패턴을 추적할 수 있습니다.
17. `/memory/summary`는 최근 journal 100건 기준 action/symbol/model/prompt version별 win rate, reward, 반복 mistake, lesson, data gap을 요약합니다.
18. `TossLiveExecutionAdapter`는 env opt-in live order 연결 지점입니다. 준비가 완료되면 broker order endpoint를 호출하고, 준비가 부족하면 blocked-live adapter가 order intent만 저장합니다.

## Agent Roles

목표 구조는 아래 역할 분리를 기준으로 확장합니다.

1. Scheduler: 정해진 주기와 market-hours guard에 따라 agent run을 트리거합니다.
2. News Agent: rule-based pre-filter를 통과한 후보 종목에 한해 Naver 공개 시세뉴스 API의 실제 헤드라인을 가져오고, market snapshot 기반 가격·거래량 신호와 함께 이벤트 컨텍스트를 만듭니다. 뉴스 조회 실패 시 snapshot context로 fail-soft 처리합니다.
3. Market Agent: 시세, 재무, 기술지표 계산을 담당합니다. 현재 `MarketAgent`가 market snapshot refresh/readiness preview와 후보 pre-filter를 맡습니다.
4. Decision Agent: LLM으로 매수/매도/HOLD 판단과 이유를 생성합니다. 현재 `DecisionAgent`가 LLM 호출, 응답 guard, 예상 비용 계산을 맡습니다.
5. Position Exit Manager / Risk Agent: 보유 포지션의 결정적 손절·익절과 신규 주문의 투자 비중, protected legacy position, budget guard를 각각 검증합니다.
6. Order Agent: paper/live execution adapter를 통해 주문 intent, simulated fill, 향후 Toss 주문/체결 조회를 담당합니다.
7. Logger Agent: decision, order, usage, journal을 DB에 저장합니다.
8. Evaluation Agent: 거래 결과와 전략 성과를 사후 평가합니다.
9. Memory Agent: 최근 journal/evaluation/decision 이력을 요약해 다음 전략 개선에 쓸 패턴을 관리합니다.

현재 공개 포트폴리오 버전은 LangGraph node 기반 agentic workflow, audit trail, risk guard, paper execution, journal, memory feedback loop를 중심으로 역할을 분리합니다. 프롬프트 버전별 승률은 decision audit payload 기준으로 집계되며, 뉴스 유형별 성공률은 헤드라인 분류 데이터를 확장할 때 활용할 수 있도록 `/memory/summary`의 `data_gaps`에 명시됩니다.

`/agent/readiness`는 run-once 전 market 후보, LLM budget, DRY_RUN/mock 상태를 확인하는 preflight 응답입니다.
`automation_ready`는 real OpenAI LLM이 준비된 경우에만 true이며, mock 실행 가능 상태와 구분됩니다.
`paper_auto_ready`는 `AGENT_AUTOMATION_ENABLED=true`, `AGENT_AUTOMATION_MODE=paper_auto`, `DRY_RUN=true`, `LIVE_TRADING_ENABLED=false`가 모두 만족될 때만 true입니다.
`/agent/automation-policy`는 현재 자동화 모드, confidence/order amount 기준, blocker를 반환합니다.
`/agent/schedule`은 마지막 decision 기준 다음 실행 시각과 due 여부를 반환합니다.
`/agent/run-scheduled`는 schedule이 due일 때만 `/agent/run-once`를 실행하고, due가 아니면 decision 없이 reason만 반환합니다.
`AGENT_SCHEDULER_MARKET_HOURS_ONLY=true`에서는 `Asia/Seoul`, `09:00`~`15:30` KRX 평일 정규장 안에서만 scheduled run을 통과시킵니다.
`AGENT_MARKET_CLOSED_DATES`에 `YYYY-MM-DD` CSV로 휴장일을 지정하면 해당 날짜도 차단합니다. 공개 버전은 고정 휴장일 CSV를 사용하고, 조기폐장 캘린더 provider는 별도 확장 지점으로 둡니다.
`/agent/run-once`/`/agent/run-scheduled`는 여전히 "1회 실행" 엔드포인트로 남아 있고, 대시보드의 "지금 실행" 버튼이 씁니다 (아래 Continuous Session Loop와는 별도 경로).
`/settings/llm-readiness`는 LLM mode, blockers, next actions를 별도로 반환합니다.
`/settings/llm-smoke-test`는 실제 OpenAI 키와 모델 연결만 작게 확인하고 `LLMUsage`에 `test` 목적의 usage row를 저장합니다. 이 endpoint는 trading decision이나 order를 만들지 않습니다.
Frontend Dashboard는 이 preflight 결과를 Run Agent 버튼 근처의 상태 카드로 보여줍니다.
Dashboard의 `Refresh` 버튼으로 portfolio, market, agent readiness, decision/order 요약을 다시 불러올 수 있습니다.
`/decisions`는 `status`, `symbol`, `limit` query parameter로 decision log를 좁혀 볼 수 있습니다.
`/orders`도 `status`, `symbol`, `limit` query parameter로 simulated/live-blocked order log를 좁혀 볼 수 있습니다.

현재 mock 설정에서는 실제 OpenAI API와 Toss API를 호출하지 않습니다. 실제 OpenAI 호출은 Responses API의 `model`, `input`, `text.format` 구조를 사용하며, API 키는 로그나 DB에 저장하지 않습니다.

## Continuous Session Loop

`/agent/run-once`가 "tick 1회 = decision 1회"인 것과 별도로, `AgentGraphService.run_session()`은 하나의 그래프 실행 안에서 여러 decision 사이클이 순환하는 **세션**을 돈다 (설계 문서: `docs/plans/continuous-session-loop.md`).

- 그래프: `market_agent → news_agent → risk_agent → memory_agent → decision_agent → execution_risk_agent → logger_agent → order_agent → evaluation_agent → journal_agent → loop_gate`, `loop_gate`가 계속할지(`market_agent`로 back-edge) 멈출지(`session_finish`) 판단한다.
- `loop_gate`가 매 사이클 확인하는 정지 조건(하나라도 걸리면 세션 종료): `AgentSession.stop_requested`(관리자 kill switch), `cycle_count >= max_cycles`, 경과 시간 `>= agent_session_max_minutes`, 장 마감(`Asia/Seoul` KRX 정규장 09:00~15:30 기준), LLM 비용·토큰·횟수 budget 초과, 일일 거래 한도 도달, Redis 락 갱신 실패. 호출 직후 cooldown은 종료 사유로 쓰지 않고 다음 사이클 대기 시간에 반영합니다.
- `AGENT_SESSION_MAX_CYCLES`(기본 90) × `AGENT_SCHEDULER_INTERVAL_MINUTES`(intraday 권장값 5분)가 KRX 정규장 390분을 충분히 커버하도록 잡혀 있습니다. 실제 세션은 보통 사이클 수가 아니라 장 마감 또는 `AGENT_SESSION_MAX_MINUTES`(기본 420분)에서 끝납니다 — pacing 간격을 바꾸면 이 값도 같이 재계산해야 오후 세션이 조기 종료되지 않습니다.
- 세션/사이클은 `AgentSession`(세션 1개)과 `WorkflowRun.session_id`/`cycle_index`(사이클마다 1개)로 저장된다. 대시보드의 "에이전트 세션" 화면(`/agent/sessions`, `/agent/sessions/{id}`)에서 세션 목록과 사이클별 실행 요약을 볼 수 있고, `POST /agent/sessions/{id}/stop`(admin key 필요)으로 중지시킬 수 있다.
- **워커는 24/7 상시 데몬이다.** `backend/app/worker.py`의 `run_worker()`는 컨테이너가 사는 동안 "장 열릴 때까지 대기 → 세션 1개 실행 → 장 닫힐 때까지 대기"를 계속 반복한다. `docker-compose.yml`의 `worker` 서비스는 `restart: unless-stopped`가 붙은 일반 서비스라 `docker compose up`(또는 `-d`)에 backend/frontend/postgres/redis와 함께 포함된다. 별도 cron 설정은 필요 없다.
- `AGENT_SCHEDULER_ENABLED=false`가 기본값이라, 워커 컨테이너를 띄워도 5분 간격 idle-poll만 하고 세션을 시작하지 않는다 — `.env`에서 명시적으로 `true`로 바꿔야 실제로 세션이 돈다. **이 서버처럼 `USE_MOCK_DATA=false`에 실제 `OPENAI_API_KEY`가 설정된 환경에서 켜면, 세션이 돌 때마다 진짜 OpenAI API 호출 비용이 발생한다** (`LLM_DAILY_CALL_LIMIT`/`LLM_DAILY_COST_LIMIT_USD`/`LLM_MONTHLY_COST_LIMIT_USD` 가드는 있음). `DRY_RUN=true`인 한 실제 주문은 나가지 않는다.

## Market Snapshots

데모/연구 실행 전에는 `/market/snapshots`로 active universe 종목의 최신 가격, 등락률, 거래량을 저장할 수 있습니다.

```bash
curl http://localhost:8000/market/snapshots/status
curl http://localhost:8000/market/snapshots/latest
curl -X POST http://localhost:8000/market/snapshots/refresh
curl -X POST http://localhost:8000/market/snapshots \
  -H "Content-Type: application/json" \
  -d '{"snapshots":[{"symbol":"005930","price":72000,"change_percent":1.2,"volume":1000000,"sector":"semiconductor"}]}'
```

`/market/snapshots/refresh`는 `USE_MOCK_DATA=true`에서 fictional demo market snapshot을 생성합니다. `USE_MOCK_DATA=false`에서는 `MarketDataClient`가 Toss `/api/v1/prices`로 현재가를 일괄 조회합니다. `INTRADAY_SIGNALS_ENABLED=true`인 에이전트 실행은 1차 후보에만 `/api/v1/candles?interval=1m`과 `/api/v1/orderbook`을 추가 조회하며, 시그널이 없으면 LLM을 호출하지 않습니다.
`/market/snapshots/status`는 active universe 중 agent 입력으로 쓸 수 있는 fresh snapshot 수와 누락 symbol을 보여줍니다. Active universe 전체가 freshness window 안에 있을 때만 `ready_for_agent=true`가 됩니다.
Frontend Dashboard와 Market 화면에서도 agent 입력용 market snapshot 준비 상태를 확인할 수 있습니다.

`ALLOWED_SYMBOLS` 허용 universe 밖의 심볼은 저장하지 않습니다. sector는 멀티섹터 후보의 정보성 메타데이터이며 저장 필터로 사용하지 않습니다.

트레이딩 금액과 PnL은 KRW로 처리합니다. LLM 예상 비용은 OpenAI 과금 통화에 맞춰 `LLM_INPUT_COST_PER_1M_TOKENS_USD`, `LLM_OUTPUT_COST_PER_1M_TOKENS_USD`를 기준으로 계속 USD로 계산합니다. 기본값은 `0`이며, 모델 가격은 변동될 수 있으므로 사용자가 현재 단가를 `.env`에 직접 입력합니다.

## Toss Read-Only Setup

Toss Open API 조회 연결은 아래 조건이 모두 맞을 때만 시도합니다.

- `USE_MOCK_DATA=false`
- `TOSS_API_KEY`
- `TOSS_SECRET_KEY`
- `TOSS_TOKEN_PATH`
- `TOSS_ACCOUNT_LIST_PATH`
- `TOSS_HOLDINGS_PATH`

계좌 목록 조회(`/broker/accounts`, `/broker/accounts/normalized`)는 `TOSS_ACCOUNT_ID` 없이도 시도할 수 있습니다. 보유 주식 조회와 legacy sync에는 `TOSS_ACCOUNT_ID`가 필요합니다.

Toss API 응답 지연 때문에 확인 명령이 오래 걸리면 `--max-time`으로 클라이언트 대기 시간을 제한할 수 있습니다. backend의 Toss API 대기 시간은 `TOSS_TIMEOUT_SECONDS`로 조정하며, 기본 예시는 8초입니다.

```bash
curl --max-time 10 http://localhost:8000/broker/accounts/normalized
```

Toss read-only 성공 응답은 `TOSS_READ_CACHE_TTL_SECONDS` 동안 in-memory cache로 재사용합니다. 기본값은 15초이며, 401/429 같은 실패 응답은 캐시하지 않습니다.

토큰과 API 응답 원문은 저장하지 않습니다.

Endpoint path는 `https://openapi.tossinvest.com` 뒤에 붙는 경로입니다. 기본값은 Toss OpenAPI 1.1.5 기준으로 아래와 같습니다.

- `TOSS_TOKEN_PATH=/oauth2/token`
- `TOSS_ACCOUNT_LIST_PATH=/api/v1/accounts`
- `TOSS_HOLDINGS_PATH=/api/v1/holdings`

처음에는 `TOSS_ACCOUNT_ID`가 비어 있어도 `/broker/accounts`로 계좌 목록을 조회할 수 있습니다. 응답에서 계좌 식별값을 확인한 뒤 `TOSS_ACCOUNT_ID`에 넣으면 `/broker/positions`와 legacy sync를 사용할 수 있습니다.

이전 이름인 `TOSS_APP_KEY`, `TOSS_APP_SECRET`, `TOSS_ACCOUNTS_PATH`, `TOSS_POSITIONS_PATH`도 호환됩니다.

## Demo Data

대시보드 확인용 fictional demo data는 CLI 또는 API로 생성할 수 있습니다.

```bash
python -m app.seed_demo_data
curl -X POST http://localhost:8000/demo/seed
```

`/demo/seed`는 `USE_MOCK_DATA=true`이고 외부 API credential이 설정되지 않은 경우에만 허용됩니다.
