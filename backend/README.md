# AI Trading Agent Backend

토스증권 Open API를 기본 브로커 어댑터로 가정한 실험용 AI 트레이딩 에이전트 백엔드입니다.

현재 기본 설정은 DRY_RUN / paper trading입니다. 실거래는 기본값으로 비활성화되어 있으며, 사용자가 명시적으로 환경변수를 바꾸고 주문 동작을 검토한 경우에만 확장할 수 있습니다.

## 현재 단계

현재는 backend 기본 골격, 포트폴리오 조회, mock agent decision 생성까지 구현되어 있습니다.

- FastAPI 앱 엔트리
- dotenv 기반 설정
- Toss Securities Open API 기준 브로커 설정
- SQLite / SQLAlchemy 연결
- 핵심 ORM 모델
- Pydantic 스키마
- 에이전트 판단별 LLM 토큰/예상 비용 기록 필드
- LLM client result wrapper: parsed response, raw response, usage, latency, success status
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

Docker Compose backend는 `backend/.env`를 읽습니다. 실제 API 키와 운용 설정은 이 파일에 넣고 저장소에는 커밋하지 않습니다.

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
```

## 안전 원칙

- 기본 브로커 provider는 `toss_securities`입니다.
- `DRY_RUN=true`가 기본값입니다.
- `LIVE_TRADING_ENABLED=false`가 기본값입니다.
- 실주문 API 호출은 기본 설정에서 비활성화되어 있습니다.
- 기존 보유 주식은 legacy position으로 보호해야 합니다.
- 봇은 `.env`의 `ALLOWED_SECTOR`, `ALLOWED_SYMBOLS`로 정의된 active universe 허용 종목만 다룰 수 있어야 합니다. 기본 예시는 반도체 Top 10입니다.
- 에이전트 운용 비용을 보기 위해 판단별 토큰 사용량과 예상 비용을 기록합니다.
- `USE_MOCK_DATA=true`에서는 mock market data와 mock LLM 응답을 사용합니다.
- `USE_MOCK_DATA=false`에서는 저장된 최신 market snapshot만 사용하며, `/market/snapshots`로 수동/외부 가격 데이터를 입력할 수 있습니다.
- `MARKET_SNAPSHOT_MAX_AGE_MINUTES`보다 오래된 snapshot은 agent 입력에서 제외합니다.
- `USE_MOCK_DATA=false`, `OPENAI_API_KEY`, `LLM_MODEL_DECISION`이 모두 설정되면 실제 OpenAI Responses API를 사용할 수 있습니다.
- LLM 입력 비용을 줄이기 위해 active universe 전체가 아니라 rule-based pre-filter를 통과한 상위 후보만 agent에 전달하며, `LLM_MAX_CANDIDATES_PER_RUN`으로 개수를 제한합니다.
- 후보 선택 규칙은 `SectorCandidateSelector` 전략 클래스로 분리되어 있으며, LLM 호출 전 deterministic pre-filter로 동작합니다. 기본 universe는 반도체 Top 10이지만, `ALLOWED_SECTOR`와 `ALLOWED_SYMBOLS`를 바꾸면 다른 섹터에도 같은 후보 선택 구조를 적용할 수 있습니다.
- LLM 호출 전 budget guard를 확인하고, 비용/토큰/호출 횟수/최소 호출 간격 한도를 넘으면 LLM 호출 없이 `SKIPPED` decision을 저장합니다.
- LLM 응답은 저장 직전 `DecisionResponseGuard`를 한 번 더 통과하며, 후보 밖 symbol, enum 밖 action, 범위 밖 confidence/order amount, 빈 thesis/risk_notes가 있으면 paper execution도 `SKIPPED`로 차단합니다.
- decision 승인 시에도 RiskManager가 최종 검증하며, 현재는 DRY_RUN simulated order만 생성합니다.
- `LIVE_TRADING_ENABLED=true`, `DRY_RUN=false` 조합에서도 live order adapter가 아직 연결되지 않아 실제 주문은 전송되지 않고 `TODO_LIVE_ORDER_NOT_IMPLEMENTED`로 차단됩니다.
- 차단된 live order에는 order intent와 idempotency key가 raw payload에 남으며, 이는 실제 주문 전송이 아니라 향후 broker adapter 구현 검토용입니다.
- `/decisions/{decision_id}/preview`는 승인 전 예상 주문 수량, 금액, 예산 영향, legacy 보호 여부, RiskManager 결과를 보여줍니다.
- decision evaluation은 최신 snapshot 가격과 결정 당시 가격을 비교해 hindsight review를 저장합니다.
- Memory Agent는 journal/evaluation/decision 이력을 요약해 최근 성과, 반복 실수, lesson, 모델별 성과를 확인하는 read-only 분석 레이어입니다.
- `/broker/status`는 Toss API key/secret 준비 상태, 계좌 목록 조회 준비 상태, `TOSS_ACCOUNT_ID` 설정 여부, live readiness를 마스킹된 상태값으로만 보여줍니다.
- `/broker/accounts`, `/broker/positions`는 Toss read-only endpoint path가 `.env`에 설정된 경우에만 호출됩니다.
- `/broker/accounts/normalized`는 Toss 계좌 응답을 마스킹된 내부 표준 계좌 형태로 변환해 보여줍니다.
- `/broker/positions/normalized`는 Toss 잔고 응답을 내부 표준 포지션 형태로 변환해 보여줍니다.
- `/portfolio/sync-legacy-from-broker`는 Toss 조회 잔고를 protected legacy position으로 가져오며, bot position이 이미 있으면 import를 차단합니다.
- `/portfolio/sync-bot-from-market`는 freshness window 안의 최신 market snapshot으로 bot-only position의 현재가와 미실현 PnL을 갱신하며, legacy position은 건드리지 않습니다.
- `/settings/security-readiness`는 secret 값을 노출하지 않고 demo 안전 상태, Toss/OpenAI 준비 여부, 경고와 다음 조치만 반환합니다.

## Universe

초기 감시 대상은 아래 10개 종목으로 제한합니다.

- NVDA
- AMD
- TSM
- AVGO
- ASML
- QCOM
- MU
- ARM
- INTC
- AMAT

## Agent 실행 흐름

현재 `/agent/run-once`는 아래 순서로 동작합니다.

1. `USE_MOCK_DATA=false`이면 저장된 최신 market snapshot만 사용하고, mock mode이면 active universe의 mock snapshot을 저장합니다.
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
16. `/journal` API와 Dashboard Journal 화면으로 decision/order/evaluation을 묶은 self feedback, lesson, reward score를 저장합니다. 이 기록은 이후 strategy weight learning 또는 lightweight reinforcement learning의 입력으로 사용할 수 있습니다.
17. `/memory/summary`는 최근 journal 100건 기준 action/symbol/model별 win rate, reward, 반복 mistake, lesson, data gap을 요약합니다.
18. `LiveTossExecutionAdapter`는 live order 연결 지점입니다. 현재는 실제 주문을 보내지 않고 `TODO_LIVE_ORDER_NOT_IMPLEMENTED`로 차단된 order intent만 저장합니다.

## Agent Roles

목표 구조는 아래 역할 분리를 기준으로 확장합니다.

1. Scheduler: 정해진 주기와 market-hours guard에 따라 agent run을 트리거합니다.
2. News Agent: 뉴스 수집과 요약을 담당합니다. 아직 구현 전이며 LLM 사용 후보입니다.
3. Market Agent: 시세, 재무, 기술지표 계산을 담당합니다. 현재 `MarketAgent`가 market snapshot refresh/readiness preview와 후보 pre-filter를 맡습니다.
4. Decision Agent: LLM으로 매수/매도/HOLD 판단과 이유를 생성합니다. 현재 `DecisionAgent`가 LLM 호출, 응답 guard, 예상 비용 계산을 맡습니다.
5. Risk Agent: 투자 비중, 손절/익절, protected legacy position, budget guard를 검증합니다.
6. Order Agent: paper/live execution adapter를 통해 주문 intent, simulated fill, 향후 Toss 주문/체결 조회를 담당합니다.
7. Logger Agent: decision, order, usage, journal을 DB에 저장합니다.
8. Evaluation Agent: 거래 결과와 전략 성과를 사후 평가합니다.
9. Memory Agent: 최근 journal/evaluation/decision 이력을 요약해 다음 전략 개선에 쓸 패턴을 관리합니다.

현재 구현된 역할 분리는 점진 적용 중입니다. `MarketAgent`와 `DecisionAgent`는 코드 레벨로 분리되었고, Memory Agent는 read-only 요약 단계입니다. 프롬프트 버전별 승률과 뉴스 유형별 성공률은 아직 원천 필드가 없어 `/memory/summary`의 `data_gaps`에 명시됩니다.

`/agent/readiness`는 run-once 전 market 후보, LLM budget, DRY_RUN/mock 상태를 확인하는 preflight 응답입니다.
`automation_ready`는 real OpenAI LLM이 준비된 경우에만 true이며, mock 실행 가능 상태와 구분됩니다.
`paper_auto_ready`는 `AGENT_AUTOMATION_ENABLED=true`, `AGENT_AUTOMATION_MODE=paper_auto`, `DRY_RUN=true`, `LIVE_TRADING_ENABLED=false`가 모두 만족될 때만 true입니다.
`/agent/automation-policy`는 현재 자동화 모드, confidence/order amount 기준, blocker를 반환합니다.
`/agent/schedule`은 마지막 decision 기준 다음 실행 시각과 due 여부를 반환합니다.
`/agent/run-scheduled`는 schedule이 due일 때만 `/agent/run-once`를 실행하고, due가 아니면 decision 없이 reason만 반환합니다.
`AGENT_SCHEDULER_MARKET_HOURS_ONLY=true`에서는 설정된 timezone/open/close 기준 평일 정규장 안에서만 scheduled run을 통과시킵니다.
`AGENT_MARKET_CLOSED_DATES`에 `YYYY-MM-DD` CSV로 휴장일을 지정하면 해당 날짜도 차단합니다. 조기폐장 캘린더는 아직 별도 반영하지 않았습니다.
내부 백그라운드 루프는 아직 켜지지 않았으며, 외부 cron/스케줄러가 `/agent/run-scheduled`를 호출하는 구조를 기본으로 합니다.
`/settings/llm-readiness`는 LLM mode, blockers, next actions를 별도로 반환합니다.
`/settings/llm-smoke-test`는 실제 OpenAI 키와 모델 연결만 작게 확인하고 `LLMUsage`에 `test` 목적의 usage row를 저장합니다. 이 endpoint는 trading decision이나 order를 만들지 않습니다.
Frontend Dashboard는 이 preflight 결과를 Run Agent 버튼 근처의 상태 카드로 보여줍니다.
Dashboard의 `Refresh` 버튼으로 portfolio, market, agent readiness, decision/order 요약을 다시 불러올 수 있습니다.
`/decisions`는 `status`, `symbol`, `limit` query parameter로 decision log를 좁혀 볼 수 있습니다.
`/orders`도 `status`, `symbol`, `limit` query parameter로 simulated/live-blocked order log를 좁혀 볼 수 있습니다.

현재 mock 설정에서는 실제 OpenAI API와 Toss API를 호출하지 않습니다. 실제 OpenAI 호출은 Responses API의 `model`, `input`, `text.format` 구조를 사용하며, API 키는 로그나 DB에 저장하지 않습니다.

## Market Snapshots

실전 운용 전에는 `/market/snapshots`로 active universe 종목의 최신 가격, 등락률, 거래량을 저장할 수 있습니다.

```bash
curl http://localhost:8000/market/snapshots/status
curl http://localhost:8000/market/snapshots/latest
curl -X POST http://localhost:8000/market/snapshots/refresh
curl -X POST http://localhost:8000/market/snapshots \
  -H "Content-Type: application/json" \
  -d '{"snapshots":[{"symbol":"NVDA","price":120,"change_percent":1.2,"volume":1000000}]}'
```

`/market/snapshots/refresh`는 `USE_MOCK_DATA=true`에서 fictional demo market snapshot을 생성합니다. `USE_MOCK_DATA=false`에서는 아직 외부 시세 provider를 호출하지 않고, 수동 입력 또는 별도 feeder가 저장한 최신 snapshot을 반환합니다.
외부 시세 client는 현재 명시적인 `NOT_CONFIGURED` stub이며, 실제 provider 호출은 아직 연결하지 않았습니다.
`/market/snapshots/status`는 active universe 중 agent 입력으로 쓸 수 있는 fresh snapshot 수와 누락 symbol을 보여줍니다. Active universe 전체가 freshness window 안에 있을 때만 `ready_for_agent=true`가 됩니다.
Frontend Dashboard와 Market 화면에서도 agent 입력용 market snapshot 준비 상태를 확인할 수 있습니다.

허용 universe 밖의 심볼이나 `ALLOWED_SECTOR`와 다른 sector는 저장하지 않습니다.

LLM 예상 비용은 `LLM_INPUT_COST_PER_1M_TOKENS_USD`, `LLM_OUTPUT_COST_PER_1M_TOKENS_USD`를 기준으로 계산합니다. 기본값은 `0`이며, 모델 가격은 변동될 수 있으므로 사용자가 현재 단가를 `.env`에 직접 입력합니다.

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
