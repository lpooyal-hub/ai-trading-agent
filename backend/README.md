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
- `/demo/status`
- `/demo/seed`
- `/broker/status`
- `/broker/accounts`
- `/broker/accounts/normalized`
- `/broker/positions`
- `/broker/positions/normalized`
- `/portfolio/initialize-legacy`
- `/portfolio/sync-legacy-from-broker`
- `/portfolio/legacy`
- `/portfolio/bot`
- `/portfolio/summary`
- `/agent/run-once`
- `/agent/status`
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
- `/evaluations/{decision_id}`
- `/evaluations`
- `/llm-usage`
- `/llm-usage/summary`
- `/llm-usage/{usage_id}`
- 이후 단계용 모듈 구조

## 실행 명령어

아래 명령은 필요할 때 사용자가 직접 실행합니다.

```bash
cd /home/ubuntu/ai-trading-agent/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Docker Compose를 사용할 경우 아래 명령을 프로젝트 루트에서 직접 실행합니다.

```bash
cd /home/ubuntu/ai-trading-agent
cp backend/.env.example backend/.env
docker compose up --build
```

Docker Compose backend는 `backend/.env`를 읽습니다. 실제 API 키와 운용 설정은 이 파일에 넣고 저장소에는 커밋하지 않습니다.

외부 서버에서 frontend를 열어 backend를 호출하려면 `backend/.env`의 `CORS_ALLOWED_ORIGINS`에 브라우저에서 접속하는 frontend 주소를 함께 넣습니다.

```bash
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000,http://<SERVER_IP>:3000
```

## 안전 원칙

- 기본 브로커 provider는 `toss_securities`입니다.
- `DRY_RUN=true`가 기본값입니다.
- `LIVE_TRADING_ENABLED=false`가 기본값입니다.
- 실주문 API 호출은 기본 설정에서 비활성화되어 있습니다.
- 기존 보유 주식은 legacy position으로 보호해야 합니다.
- 봇은 반도체 Top 10 Universe 허용 종목만 다룰 수 있어야 합니다.
- 에이전트 운용 비용을 보기 위해 판단별 토큰 사용량과 예상 비용을 기록합니다.
- `USE_MOCK_DATA=true`에서는 mock market data와 mock LLM 응답을 사용합니다.
- `USE_MOCK_DATA=false`에서는 저장된 최신 market snapshot만 사용하며, `/market/snapshots`로 수동/외부 가격 데이터를 입력할 수 있습니다.
- `MARKET_SNAPSHOT_MAX_AGE_MINUTES`보다 오래된 snapshot은 agent 입력에서 제외합니다.
- `USE_MOCK_DATA=false`, `OPENAI_API_KEY`, `LLM_MODEL_DECISION`이 모두 설정되면 실제 OpenAI Responses API를 사용할 수 있습니다.
- LLM 입력 비용을 줄이기 위해 Top 10 전체가 아니라 rule-based pre-filter를 통과한 1~3개 후보만 agent에 전달합니다.
- LLM 호출 전 budget guard를 확인하고, 한도를 넘으면 LLM 호출 없이 `SKIPPED` decision을 저장합니다.
- decision 승인 시에도 RiskManager가 최종 검증하며, 현재는 DRY_RUN simulated order만 생성합니다.
- `/decisions/{decision_id}/preview`는 승인 전 예상 주문 수량, 금액, 예산 영향, legacy 보호 여부, RiskManager 결과를 보여줍니다.
- decision evaluation은 최신 snapshot 가격과 결정 당시 가격을 비교해 hindsight review를 저장합니다.
- `/broker/status`는 Toss Open API credential 설정 여부와 live readiness를 마스킹된 상태값으로만 보여줍니다.
- `/broker/accounts`, `/broker/positions`는 Toss read-only endpoint path가 `.env`에 설정된 경우에만 호출됩니다.
- `/broker/accounts/normalized`는 Toss 계좌 응답을 마스킹된 내부 표준 계좌 형태로 변환해 보여줍니다.
- `/broker/positions/normalized`는 Toss 잔고 응답을 내부 표준 포지션 형태로 변환해 보여줍니다.
- `/portfolio/sync-legacy-from-broker`는 Toss 조회 잔고를 protected legacy position으로 가져오며, bot position이 이미 있으면 import를 차단합니다.
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

1. `USE_MOCK_DATA=false`이면 저장된 최신 market snapshot만 사용하고, mock mode이면 Top 10 Universe의 mock snapshot을 저장합니다.
2. rule-based pre-filter로 1~3개 후보만 고릅니다.
3. 후보가 없으면 LLM을 호출하지 않고 `SKIPPED` 결정을 저장합니다.
4. 후보가 있으면 LLM budget guard를 확인합니다.
5. budget이 초과되면 LLM을 호출하지 않고 `SKIPPED` 결정을 저장합니다.
6. budget이 남아 있으면 mock LLM 응답으로 `AgentDecision`을 저장합니다.
7. mock LLM client는 parsed response, raw response, usage, latency, success status를 반환합니다.
8. mock LLM 사용량은 `LLMUsage`에 함께 기록합니다.
9. 사용자가 decision을 승인하면 RiskManager 검증 후 `TradeOrder`를 `SIMULATED` 상태로 저장합니다.
10. BUY 시뮬레이션은 bot-only `BotPosition`만 갱신하고 legacy position은 건드리지 않습니다.
11. `/evaluations` API로 decision별 사후 평가를 저장하고 조회합니다.

현재 mock 설정에서는 실제 OpenAI API와 Toss API를 호출하지 않습니다. 실제 OpenAI 호출은 Responses API의 `model`, `input`, `text.format` 구조를 사용하며, API 키는 로그나 DB에 저장하지 않습니다.

## Market Snapshots

실전 운용 전에는 `/market/snapshots`로 Top 10 universe 종목의 최신 가격, 등락률, 거래량을 저장할 수 있습니다.

```bash
curl http://localhost:8000/market/snapshots/latest
curl -X POST http://localhost:8000/market/snapshots \
  -H "Content-Type: application/json" \
  -d '{"snapshots":[{"symbol":"NVDA","price":120,"change_percent":1.2,"volume":1000000}]}'
```

허용 universe 밖의 심볼이나 semiconductor가 아닌 sector는 저장하지 않습니다.

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
