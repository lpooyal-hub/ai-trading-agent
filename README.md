# AI Trading Agent Research Platform

이 프로젝트는 **Toss Securities Open API**를 기본 브로커 어댑터로 가정한 국내 KRX 멀티섹터 기반의 공개 포트폴리오용 **AI Trading Agent Research Platform**입니다. 목적은 실거래 수익을 보장하는 자동매매가 아니라, 기본 DRY_RUN 환경에서 에이전트의 판단, 리스크 검증, KRW 주문 시뮬레이션, LLM 비용, 사후 평가를 감사 가능한 workflow로 남기는 것입니다.

## Preview

브라우저 주소, 서버 IP, 북마크, 작업표시줄 같은 개인 정보가 보이지 않도록 앱 화면만 재구성한 포트폴리오용 redacted preview입니다.

![Redacted dashboard screenshot](docs/assets/dashboard-redacted.svg)

## Architecture

![AI Trading Agent architecture diagram](docs/assets/architecture.svg)

## 프로젝트 목표

- AI 에이전트의 매매 판단을 기록하고 사후 평가할 수 있는 연구 환경을 만듭니다.
- 토스증권 Open API를 기준 브로커로 두고, 계좌/잔고 조회와 주문 실행 흐름을 단계적으로 분리합니다.
- 기본값은 DRY_RUN / mock mode로 유지해 공개 데모와 로컬 실험을 안전하게 시작할 수 있게 합니다.
- LLM 토큰 사용량, 예상 비용, 판단 근거, 리스크 검토 결과를 함께 남깁니다.
- 운용 한도, 후보 universe, 주문 정책은 `.env`에서 연구 목적에 맞게 바꿀 수 있습니다.

## 범위와 한계

- 수익을 보장하지 않습니다.
- 투자 판단을 대신하지 않습니다.
- 기본 설정만으로 실제 주문을 보내지 않습니다.
- 여러 증권사를 한 번에 지원하는 범용 브로커 플랫폼은 아닙니다.
- 실주문은 env opt-in이며, Toss 주문 endpoint와 credentials가 준비된 경우에만 `TossLiveExecutionAdapter`가 broker order endpoint를 호출합니다.
- 실제 계좌 정보, 실거래 기록, 실제 주문 API 응답은 저장소에 포함하지 않습니다.

## 핵심 기능

- LangGraph agentic workflow: Runtime Lock, Market, News, Risk, Memory, Decision, Execution Risk, Logger, Order, Evaluation, Journal node 실행 및 단계 기록
- Runtime guard: Redis lock으로 중복 실행 방지
- Decision audit: 판단 근거, 신뢰도, LLM 사용량, 비용, latency 저장
- Paper execution: DRY_RUN 기반 금액 주문 시뮬레이션과 bot-only position 갱신
- Risk control: 예산, 노출 한도, 보호 포지션, 일일 거래 수, 금지 키워드 검증
- Performance loop: simulated PnL, win rate, symbol performance, evaluation, journal, memory feedback
- Broker boundary: Toss read-only 조회와 env opt-in live order adapter 분리
- React dashboard: 대시보드, 실행 흐름, 판단, 주문, 포트폴리오, 평가, 저널, 메모리 화면

## 멀티에이전트 구조

이 프로젝트의 핵심 실행 흐름은 하나의 거대한 agent가 아니라, 역할별 agent가 순서대로 데이터를 넘기는 구조입니다. LLM이 꼭 필요한 판단/요약 역할과 Python으로 충분한 계산/검증 역할을 분리해 비용과 리스크를 줄입니다.

```text
SchedulerAgent
  -> RuntimeLock(Redis)
  -> MarketAgent
  -> NewsAgent
  -> RiskAgent
  -> MemoryAgent
  -> DecisionAgent
  -> ExecutionRiskAgent
  -> LoggerAgent
  -> OrderAgent
  -> EvaluationAgent
  -> JournalAgent
  -> MemoryAgent
  -> next DecisionAgent input
```

- `SchedulerAgent`: `/agent/run-scheduled` 호출 시 실행 가능 시간, 장중 여부, 실행 간격을 확인합니다.
- `RuntimeLock`: Compose 기본 Redis 또는 설정된 Redis에서 `agent:run_once:lock`으로 중복 실행을 막습니다.
- `MarketAgent`: 최신 market snapshot을 준비하고, rule-based pre-filter로 LLM에 넘길 후보를 1~3개로 줄입니다.
- `NewsAgent`: 현재는 외부 뉴스 API 없이 시장 스냅샷 기반 이벤트 컨텍스트를 만들고, 향후 뉴스/실적/캘린더 API 입력으로 확장할 자리입니다.
- `RiskAgent`: LLM 예산과 실행 전제 조건을 확인하고, LLM 호출 전에 비용/쿨다운 가드를 적용합니다.
- `MemoryAgent`: 최근 저널/평가를 요약해 승률, 반복 실수, 모델/종목/프롬프트 버전별 개선 힌트를 `DecisionAgent` 입력에 포함합니다.
- `DecisionAgent`: LLM 또는 mock LLM을 호출해 BUY/SELL/HOLD 판단, 신뢰도, 근거, 리스크 메모를 생성합니다.
- `ExecutionRiskAgent`: 포지션, 예산, 종목별 최대 노출, 보호 종목, 금지 키워드, 일일 거래 수, 손실 제한 같은 deterministic risk rule을 검증합니다.
- `LoggerAgent`: 판단 입력, LLM 응답, 사용량, 비용, latency, news context를 DB에 기록합니다.
- `OrderAgent`: 승인된 판단을 paper 또는 live execution adapter로 넘깁니다. live order는 env opt-in과 관리자 API key guard를 요구합니다.
- `EvaluationAgent`: 시간이 지난 판단의 사후 수익률, 성공 여부, mistake type, 개선 메모를 계산합니다.
- `JournalAgent`: decision/order/evaluation을 묶어 거래 저널과 보상/교훈을 저장합니다. 후보 없음, 예산 초과처럼 guard에서 멈춘 실행도 별도 저널로 남겨 Memory Agent가 반복 패턴을 볼 수 있게 합니다.

현재 `NewsAgent`는 “실제 뉴스 수집기”가 아니라 `DecisionAgent` 입력 계약을 먼저 만든 버전입니다. 실제 뉴스 API를 붙이면 `NewsAgent` 내부 수집 로직만 교체하고 downstream agent 흐름은 유지할 수 있습니다.

### Workflow audit layer

현재 구현은 LangGraph `StateGraph` 기반 agentic workflow 실행 단위입니다. `/workflows/run` 실행 시 각 agent를 node로 실행하고, node가 공유 state를 업데이트한 뒤 `workflow_runs`, `workflow_steps`에 Runtime Lock, Market, News, Risk, Memory, Decision, Execution Risk, Logger, Order, Evaluation, Journal 단계의 성공/스킵/실패 상태와 핵심 입출력을 저장합니다. 실행 전 guard에서 멈춘 경우에도 스킵 사유와 저널 ID가 함께 남습니다.

이 레이어는 포트폴리오 관점에서 “에이전트가 어떤 순서로 판단했고 어떤 state를 다음 node로 넘겼으며 어디서 멈췄는지”를 보여주기 위한 구조이며, 수동 실행 버튼과 scheduler 실행도 같은 LangGraph workflow recording 경로를 통과합니다.

### Redis runtime guard

Redis는 영구 기록 저장소가 아니라 runtime guard로 사용합니다. Docker Compose 기본 구성에는 Redis 컨테이너가 포함되어 있고, `backend/.env.example`도 `REDIS_ENABLED=true`, `REDIS_URL=redis://redis:6379/0` 기준으로 맞춰져 있습니다. `/workflows/run` 실행 시 `agent:run_once:lock` lock을 잡아 중복 실행을 막습니다.

- Redis 사용 가능: 같은 순간 두 번째 agent 실행은 `409 Conflict` 또는 scheduled run skip으로 처리됩니다.
- Redis를 의도적으로 끄거나 일시적으로 사용할 수 없음: 기존 DB 기반 실행 흐름을 유지하고, workflow에는 runtime lock 단계가 skipped로 남습니다.
- 기본 TTL은 `REDIS_AGENT_RUN_LOCK_TTL_SECONDS=300`입니다.

## 보안 원칙

- `.env`는 절대 커밋하지 않습니다.
- API 키는 환경변수로만 관리합니다.
- 실계좌 데이터는 저장소에 포함하지 않습니다.
- 공개 데모는 `USE_MOCK_DATA=true`로 실행합니다.
- 운영 도메인에 노출할 때는 `REQUIRE_ADMIN_API_KEY=true`와 `ADMIN_API_KEY`를 실제 서버 `.env`에만 설정해 실행/변경성 API를 보호합니다.
- 관리자 키는 `X-Admin-API-Key` 또는 `Authorization: Bearer ...` 헤더로 전달하며, 공개 `.env.example`에는 실제 값을 넣지 않습니다.
- 실주문 전송은 `DRY_RUN=false`, `LIVE_TRADING_ENABLED=true`, Toss credentials, `TOSS_ORDER_PATH`, 관리자 API key가 모두 준비된 경우에만 활성화되는 opt-in 경로입니다.

## Quick Start

처음 한 번만 `.env`를 만들고 실행합니다.

```bash
cd /home/ubuntu/ai-trading-agent
cp backend/.env.example backend/.env
docker compose up --build
```

이미 `backend/.env`가 있으면 아래만 실행하면 됩니다.

```bash
cd /home/ubuntu/ai-trading-agent
docker compose up --build
```

컨테이너 상태 확인:

```bash
docker compose ps
```

Docker Compose 실행 시 backend는 전용 `postgres` 서비스에 연결됩니다. `backend`, `frontend`, `postgres` 컨테이너가 모두 `backend/.env`를 읽으므로 설정 위치를 하나로 유지합니다. Postgres 데이터는 named volume인 `postgres_data`에 저장되고, backend의 `/app/data`는 SQLite fallback이나 파일성 데이터를 위해 `backend_data`로 유지합니다.

기본 개발용 DB 값:

```text
POSTGRES_DB=ai_trading_agent
POSTGRES_USER=ai_trading_agent
POSTGRES_PASSWORD=change_this_postgres_password
DATABASE_URL=postgresql+psycopg://ai_trading_agent:change_this_postgres_password@postgres:5432/ai_trading_agent
```

운영/서버에서는 `backend/.env`에서 `POSTGRES_PASSWORD`와 `DATABASE_URL`을 함께 바꿔 사용합니다. Docker 없이 backend를 단독 실행할 때만 `DATABASE_URL=sqlite:///./data/trading_agent.db`를 fallback으로 사용할 수 있습니다.

기본 접속 주소:

- Frontend: `http://localhost:3000`
- Backend health: `http://localhost:81/health`
- Production domain example: `https://your-trading-domain.example`

서버에서 실행 중이면 브라우저에서는 frontend만 열면 됩니다.

```text
http://<SERVER_IP>:3000
```

Frontend는 기본적으로 `/api`를 호출하고, Docker Compose의 Vite proxy가 backend container로 넘깁니다. 그래서 일반 실행에서는 browser가 backend `81` 포트를 직접 호출할 필요가 없습니다.
각 Docker build context는 `.dockerignore`로 `.env`, DB 파일, cache, `node_modules` 같은 로컬 파일을 제외합니다.

운영 도메인에서는 Nginx가 HTTPS 요청을 frontend `127.0.0.1:3000`으로, `/api/*` 요청을 backend `127.0.0.1:81`로 reverse proxy합니다.

## 기본 설정

`backend/.env`는 Docker Compose backend가 읽습니다. 기본값은 안전한 demo / paper trading입니다. 아래 항목은 로컬 연구 목적에 맞춰 조정하는 설정 키입니다.

- `DRY_RUN=true`
- `LIVE_TRADING_ENABLED=false`
- `USE_MOCK_DATA=true`
- `BROKER_PROVIDER`
- `BOT_CAPITAL_LIMIT_KRW`
- `MAX_ORDER_AMOUNT_KRW`
- `MAX_SYMBOL_EXPOSURE_PERCENT`
- `FRACTIONAL_TRADING_ENABLED`
- `ORDER_SIZING_MODE`
- `MIN_CASH_RESERVE_KRW`
- `MIN_ORDER_AMOUNT_KRW`
- `ALLOWED_SYMBOLS`
- `REDIS_ENABLED`
- `REDIS_URL`

실제 API 키, 계좌번호, OpenAI 키는 `backend/.env`에만 넣고 커밋하지 않습니다.
Compose 기본 실행에서는 `postgres`와 `redis` 서비스 이름을 그대로 사용합니다. 따라서 컨테이너 내부 연결값은 `DATABASE_URL=...@postgres:5432/...`, `REDIS_URL=redis://redis:6379/0` 형태를 유지합니다.
OpenAI 키를 처음 연결한 뒤에는 `Settings` 화면의 `LLM Smoke Test` 버튼 또는 아래 endpoint로 작은 연결 테스트를 먼저 실행합니다. 이 테스트는 trading decision을 만들지 않고 LLM usage row만 기록합니다.

### Execution Modes

하나의 코드베이스를 유지하고 실행 모드는 env로 나눕니다.

Paper trading이 기본값입니다.

```bash
DRY_RUN=true
LIVE_TRADING_ENABLED=false
USE_MOCK_DATA=true
AGENT_AUTOMATION_MODE=manual_approval
```

실제 API 키와 계좌 조회를 연결하는 live-ready 모드는 env에서 명시적으로 전환합니다.

```bash
DRY_RUN=false
LIVE_TRADING_ENABLED=true
USE_MOCK_DATA=false
REQUIRE_ADMIN_API_KEY=true
TOSS_ORDER_PATH=<official-toss-order-path>
TOSS_ORDER_STATUS_PATH=<official-toss-order-status-path>
```

위 값과 Toss credentials가 모두 준비되면 `TossLiveExecutionAdapter`가 주문 endpoint를 호출합니다. `TOSS_ORDER_PATH`가 비어 있거나 readiness가 부족하면 `BlockedLiveExecutionAdapter`가 order intent와 차단 사유를 저장합니다.

## Dashboard 사용 흐름

Docker를 올린 뒤 Dashboard에서 아래 흐름으로 확인합니다.

1. `Dashboard`: demo 상태, market readiness, agent readiness, candidate queue 확인
2. `Market`: `Refresh Source`로 demo market snapshot 생성 또는 수동 snapshot 저장. Active universe 전체가 fresh일 때 agent ready로 표시됩니다.
3. `Workflows`: `워크플로 실행`으로 agentic workflow run 생성
4. `Decisions`: workflow에서 생성된 paper decision 확인
5. `Decision Detail`: preview 확인 후 approve하면 DRY_RUN simulated order 생성
6. `Orders`: simulated fill과 bot position 수량 변화를 확인
7. `Portfolio`: bot-only position, protected legacy position, PnL 확인
8. `Broker`: Toss read-only 계좌/잔고 연결 상태 확인
9. `Evaluations`: window별 evaluation coverage, pending, not-due decision 수 확인
10. `Journal`: decision/order/evaluation을 묶어 self feedback과 reward 입력을 누적하고 UI에서 확인

## Execution 구조

`TradingService`는 decision 승인, RiskManager 검증, order 저장 흐름을 조율합니다. 주문 처리 방식은 execution adapter로 분리되어 있으며, env 설정에 따라 paper, blocked-live, Toss live 경로를 선택합니다.

- `PaperExecutionAdapter`: 기본 DRY_RUN / paper trading 실행 경로입니다. simulated order를 저장하고 bot-only position만 갱신합니다.
- `TossLiveExecutionAdapter`: `DRY_RUN=false`, `LIVE_TRADING_ENABLED=true`, Toss credentials, `TOSS_ORDER_PATH`가 준비되면 broker order endpoint를 호출하고 `LIVE_SUBMITTED` 또는 `FAILED` order를 저장합니다.
- `BlockedLiveExecutionAdapter`: live intent는 있지만 readiness가 부족한 경우 실제 endpoint 호출 없이 order intent, idempotency key, 차단 사유를 `TODO_LIVE_ORDER_NOT_IMPLEMENTED` order로 저장합니다.

Paper trading은 기본적으로 금액 기반 수량 계산을 사용합니다. `ORDER_SIZING_MODE=notional`에서 `recommended_order_amount / current_price`로 수량을 계산하고, `QUANTITY_DECIMAL_PLACES` 기준으로 반올림합니다. 실제 broker live adapter를 연결할 때는 해당 브로커의 주문 단위, 소수점/금액 주문 지원 범위, 계좌 권한, idempotency 전략을 별도로 검증해야 합니다.

Portfolio/Dashboard는 `LIVE_SUBMITTED` 주문을 실주문 제출 건수와 제출 금액으로 별도 표시합니다. 체결 전 주문은 paper PnL이나 bot position 수량에 섞지 않습니다. `TOSS_ORDER_STATUS_PATH`가 설정된 경우 Orders 화면의 체결 확인 액션이 `/orders/{order_id}/sync-live-status`를 호출하고, broker 응답이 `LIVE_FILLED`로 정규화되면 bot position에 한 번만 반영합니다. 여러 대기 주문은 `/orders/sync-live-status`로 일괄 동기화할 수 있습니다.

이 구조 덕분에 agent core, risk check, journal/evaluation 흐름은 유지하면서 env에 따라 paper, blocked-live, Toss live adapter를 선택할 수 있습니다.

## 서버 반영

코드를 받은 뒤 컨테이너를 다시 만들 때는 아래만 실행하면 됩니다.

```bash
cd /home/ubuntu/ai-trading-agent
docker compose up --build -d --force-recreate
```

서버에서 frontend와 backend를 같은 Docker Compose로 띄우는 경우 `VITE_API_BASE_URL`을 외부 IP의 `:81`로 지정하지 않는 것을 권장합니다. Frontend는 기본 `/api` proxy를 통해 backend container로 접근하므로, browser가 backend public port를 직접 열 필요가 없습니다.

운영 도메인 뒤에서 Vite dev server를 그대로 사용할 경우, frontend container 환경변수에 허용 host를 추가합니다. 이 값은 공개 `.env.example`이 아니라 실제 서버 환경에서만 설정합니다.

```bash
VITE_ALLOWED_HOSTS=your-trading-domain.example
```

브라우저에서 `Ctrl+Shift+R`로 강력 새로고침합니다.

### 운영 도메인 + SSL

DNS A 레코드가 서버 IP를 바라보고 있으면, 기존 Nginx reverse proxy에 이 앱용 `server_name` 블록을 추가합니다. 루트 도메인을 다른 프로젝트가 이미 사용 중이라면, 루트 설정을 덮어쓰지 말고 같은 Nginx 설정 파일에 별도 서브도메인용 server block만 추가합니다.

공개 기본값인 `.env.example`에는 개인 운영 도메인을 넣지 않습니다. 운영 도메인은 실제 서버의 `.env`와 Nginx 설정에서만 관리합니다.

1. `backend/.env`에 운영 도메인 CORS를 포함합니다.

```bash
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000,https://your-trading-domain.example
VITE_ALLOWED_HOSTS=your-trading-domain.example
REQUIRE_ADMIN_API_KEY=true
ADMIN_API_KEY=<set-on-server-only>
```

2. 기존 Nginx 설정에 앱용 server block을 추가합니다.

```bash
# 예: 기존 reverse proxy 프로젝트의 Nginx conf에 your-trading-domain.example server block 추가
```

3. 인증서가 운영 도메인을 포함하는지 확인합니다. 기존 인증서가 wildcard 또는 SAN으로 서브도메인을 포함한다면 그대로 사용할 수 있습니다. 포함하지 않는다면 인증서를 확장 발급해야 합니다.

```bash
sudo certbot certificates
```

4. Nginx 설정을 검증하고 백신일보 frontend Nginx를 재반영합니다.

```bash
cd /home/ubuntu/VaccineDailyReport
docker compose restart frontend
```

5. 인증서 자동 갱신을 확인합니다.

```bash
sudo certbot renew --dry-run
```

최종 접속 주소는 운영 도메인입니다. Backend public port `81`을 브라우저에 직접 노출하지 않고, 외부 요청은 Nginx의 `/api` reverse proxy를 통해 backend로 전달하는 구성을 권장합니다.

## API 참고

Dashboard에서 대부분의 기능을 사용할 수 있지만, 직접 확인할 때는 아래 endpoint를 사용할 수 있습니다.

Agent:

```bash
curl http://localhost:81/agent/status
curl http://localhost:81/agent/readiness
curl http://localhost:81/agent/schedule
curl http://localhost:81/agent/operations
curl -X POST http://localhost:81/agent/run-scheduled
```

Workflows:

```bash
curl -X POST http://localhost:81/workflows/run
curl http://localhost:81/workflows
curl http://localhost:81/workflows/definition
curl http://localhost:81/workflows/1
```

LLM:

```bash
curl http://localhost:81/settings/llm-readiness
curl http://localhost:81/settings/llm-budget
curl -X POST http://localhost:81/settings/llm-smoke-test
```

Market snapshots:

```bash
curl http://localhost:81/market/snapshots/status
curl http://localhost:81/market/snapshots/latest
curl -X POST http://localhost:81/market/snapshots/refresh
```

Portfolio:

```bash
curl http://localhost:81/portfolio/summary
curl http://localhost:81/portfolio/performance
curl http://localhost:81/portfolio/cost-recovery
curl http://localhost:81/portfolio/realized-trades
curl http://localhost:81/portfolio/symbol-performance
curl http://localhost:81/portfolio/bot
curl http://localhost:81/portfolio/legacy
curl -X POST http://localhost:81/portfolio/sync-bot-from-market
```

Journal:

```bash
curl http://localhost:81/journal
curl http://localhost:81/journal/decision/1
curl -X POST http://localhost:81/journal \
  -H "Content-Type: application/json" \
  -d '{"decision_id":1,"strategy_tags":["agent_feedback","pending_review"]}'
```

Broker read-only:

```bash
curl http://localhost:81/broker/status
curl http://localhost:81/broker/accounts/normalized
curl http://localhost:81/broker/positions/normalized
```

## Toss / OpenAI 설정

기본 demo 실행에는 외부 API 키가 필요 없습니다.

Toss read-only 조회를 사용하려면 `backend/.env`에 아래 값을 설정합니다.

- `USE_MOCK_DATA=false`
- `TOSS_API_KEY`
- `TOSS_SECRET_KEY`
- `TOSS_ACCOUNT_ID`

계좌 목록 조회는 `TOSS_ACCOUNT_ID` 없이도 시도할 수 있지만, 보유 주식 조회와 legacy sync에는 `TOSS_ACCOUNT_ID`가 필요합니다. 계좌 목록 endpoint가 Toss 권한 또는 상품 범위 문제로 `401 Unauthorized`를 반환해도, `TOSS_ACCOUNT_ID` 기반 holdings 조회가 성공하면 보유 종목은 계속 표시됩니다.

실제 OpenAI LLM 호출을 사용하려면 아래 조건을 모두 만족해야 합니다.

- `USE_MOCK_DATA=false`
- `OPENAI_API_KEY`
- `LLM_MODEL_DECISION`

이 조건이 맞지 않으면 실제 OpenAI API를 호출하지 않습니다. `USE_MOCK_DATA=true`에서는 공개 데모용 mock decision을 만들 수 있고, `USE_MOCK_DATA=false`에서 LLM 설정이 부족하면 안전한 HOLD / SKIPPED 결과를 남깁니다.
`/settings/llm-readiness`와 Dashboard의 `AI Automation` 카드는 mock 응답, real OpenAI LLM, unavailable 상태를 분리해서 보여줍니다.
`USE_MOCK_DATA=true`에서 실행되는 agent는 공개 데모용 mock decision이며, 실제 AI 판단 기반 자동매매로 취급하지 않습니다.

Paper 자동 실행은 기본적으로 꺼져 있습니다. 아래 값을 모두 의도적으로 설정해야 `/workflows/run`이 승인 대기 decision을 paper order까지 자동 실행할 수 있습니다.

```bash
AGENT_AUTOMATION_ENABLED=true
AGENT_AUTOMATION_MODE=paper_auto
AGENT_AUTO_EXECUTE_MIN_CONFIDENCE=0.75
AGENT_AUTO_EXECUTE_MAX_ORDER_AMOUNT_KRW=65000
```

`paper_auto`는 `DRY_RUN=true`, `LIVE_TRADING_ENABLED=false`에서만 동작합니다. live order는 별도 approval endpoint와 관리자 API key guard를 통과한 경우에만 실행됩니다.

반복 실행은 내부 백그라운드 루프를 바로 켜지 않고, 외부 cron/스케줄러가 호출할 수 있는 `/agent/run-scheduled`로 준비합니다.

```bash
AGENT_SCHEDULER_ENABLED=false
AGENT_SCHEDULER_INTERVAL_MINUTES=60
AGENT_SCHEDULER_MARKET_HOURS_ONLY=true
AGENT_MARKET_TIMEZONE=Asia/Seoul
AGENT_MARKET_OPEN_TIME=09:00
AGENT_MARKET_CLOSE_TIME=15:30
AGENT_MARKET_CLOSED_DATES=2026-01-01,2026-12-25
```

`AGENT_SCHEDULER_MARKET_HOURS_ONLY=true`는 Asia/Seoul 기준 KRX 평일 정규장 안에서만 `/agent/run-scheduled`를 통과시킵니다. `AGENT_MARKET_CLOSED_DATES`에 휴장일을 `YYYY-MM-DD` CSV로 넣으면 해당 날짜도 차단합니다. 조기폐장 캘린더는 아직 별도 반영하지 않았습니다.

LLM 예상 비용을 기록하려면 사용하는 모델의 현재 input/output 단가를 `.env`에 직접 설정합니다. 기본값은 `0`입니다.

```bash
LLM_INPUT_COST_PER_1M_TOKENS_USD=0
LLM_OUTPUT_COST_PER_1M_TOKENS_USD=0
```

장기 paper trading에서는 비용 단가가 잘못 설정돼도 호출량이 폭주하지 않도록 호출 횟수와 최소 간격도 함께 제한합니다.

```bash
LLM_DAILY_CALL_LIMIT=5
LLM_MIN_MINUTES_BETWEEN_CALLS=60
LLM_MAX_CANDIDATES_PER_RUN=3
```

`LLM_MAX_CANDIDATES_PER_RUN`을 `1`이나 `2`로 낮추면 rule-based pre-filter를 통과한 후보 중 상위 일부만 LLM 입력으로 전달합니다. 실제 적용값은 비용 보호를 위해 1~3 범위로 제한됩니다. `/settings/llm-budget`와 Dashboard는 남은 호출 수, 쿨다운, 비용/토큰 잔여량을 함께 보여줍니다. 예산이나 쿨다운을 넘으면 agent run은 실제 LLM을 호출하지 않고 `SKIPPED` decision을 남깁니다.

`/portfolio/cost-recovery`와 Dashboard의 cost recovery 카드는 KRW paper PnL에서 월간 LLM 예상 비용(USD)을 `USD_TO_KRW_DISPLAY_RATE` 고정 근사 환율로 원화 환산한 값을 뺀 결과를 보여줍니다. 원본 LLM 비용은 USD로 함께 유지되며, 이는 실수익 보장이 아니라 장기 paper trading에서 “LLM 비용을 감당할 가능성이 있는지”를 관찰하기 위한 운영 지표입니다.

## Local Development

Docker가 기본 실행 방법입니다. backend/frontend를 따로 띄우고 싶을 때만 아래를 사용합니다.

Backend:

```bash
cd /home/ubuntu/ai-trading-agent/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Frontend:

```bash
cd /home/ubuntu/ai-trading-agent/frontend
npm install
npm run dev
```

Frontend API 주소는 `VITE_API_BASE_URL`이 있으면 그 값을 우선 사용합니다. 값이 없으면 기본값 `/api`를 사용하고, Vite dev server가 backend로 프록시합니다.

- `http://localhost:5173`에서 열면 local backend `http://localhost:8000`
- Docker Compose에서 `http://localhost:3000` 또는 운영 도메인으로 열면 `/api` 프록시를 통해 backend container `http://backend:8000`

Docker 실행 시에도 기본값은 `DRY_RUN=true`, `LIVE_TRADING_ENABLED=false`, `USE_MOCK_DATA=true`입니다.

## Verification

핵심 guard 로직은 표준 `unittest` 기반 테스트로 검증합니다. 추가 패키지 없이 backend container 안에서 실행할 수 있습니다.

```bash
docker compose exec -T backend python -m unittest discover -s tests
docker compose exec -T backend python -m compileall app
docker compose exec -T frontend npm run build
```

현재 테스트 범위는 LLM 응답 정규화(`DecisionResponseGuard`), rule-based 후보 선별(`CandidateSelector`), 주문 전 deterministic risk guard(`RiskManager`)입니다. News Agent는 외부 provider 연결 전 보류 상태이므로 테스트 범위에 포함하지 않았습니다.

## Live Trading Readiness

기본값은 paper trading이며 실제 주문은 전송하지 않습니다. `DRY_RUN=false`, `LIVE_TRADING_ENABLED=true`, `USE_MOCK_DATA=false`, Toss credentials, `TOSS_ORDER_PATH`, 관리자 API key가 모두 준비되면 `TossLiveExecutionAdapter`가 broker order endpoint를 호출합니다. readiness가 부족하면 `BlockedLiveExecutionAdapter`가 `TODO_LIVE_ORDER_NOT_IMPLEMENTED` 상태로 order intent만 저장합니다.

실전 전환 전 점검은 아래 endpoint와 Dashboard/Settings 화면에서 확인할 수 있습니다.

```bash
curl http://localhost:81/settings/live-readiness
```

live order와 차단된 live intent는 Orders와 Decision Detail에서 확인할 수 있습니다. raw payload에는 order intent, idempotency key, broker response 또는 차단 사유가 남습니다.

live order를 켜기 전에는 같은 코드베이스 안에서 env 전환과 adapter 경계를 유지한 채 최소한 아래 항목을 검증해야 합니다.

- 공식 주문 endpoint, 필수 header, 계좌 scope, 주문 가능 상품 범위 확인
- 내부 `BUY/SELL`, 수량, 금액 주문 의도를 브로커 요청 필드로 매핑
- 중복 제출 방지용 idempotency 또는 client order key 전략 추가
- 주문 전 preview, 주문 후 status polling, 실패/취소 상태 처리
- 실제 응답 저장 시 민감 정보 masking
- 최소 금액 또는 sandbox 수준의 수동 검증

## Public Repo 운영 방침

- 기본 설정: DRY_RUN / demo / paper trading
- live order 전환은 env opt-in으로 관리하며, API 키와 주문 권한 사용 책임은 실행자에게 있습니다.
- API 키, 계좌번호, 실거래 로그, 실제 API 응답은 저장소에 포함하지 않습니다.

## 면책 문구

이 프로젝트는 소프트웨어 엔지니어링, AI 에이전트 연구, paper trading 실험을 위한 도구입니다.

투자 조언이나 금융 자문을 제공하지 않으며, 수익을 보장하지 않습니다. 실제 API 키를 연결하거나 설정을 변경해 운용하는 경우, 모든 거래 판단과 그 결과는 사용자 본인의 책임입니다.
