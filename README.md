# AI Trading Agent Research Platform

이 프로젝트는 **Toss Securities Open API**를 기본 브로커 어댑터로 가정한 공개 포트폴리오용 **AI Trading Agent Research Platform**입니다. 목적은 실거래 수익을 보장하는 자동매매가 아니라, 기본 DRY_RUN 환경에서 에이전트의 판단을 기록하고, 리스크 관문을 통과시키고, LLM 사용량과 의사결정 품질을 평가하는 것입니다.

## 프로젝트 목표

- AI 에이전트의 매매 판단을 기록하고 사후 평가할 수 있는 연구 환경을 만듭니다.
- 토스증권 Open API를 기준 브로커로 두고, 계좌/잔고 조회와 주문 실행 흐름을 단계적으로 분리합니다.
- 기본값은 DRY_RUN / mock mode로 유지해 공개 데모와 로컬 실험을 안전하게 시작할 수 있게 합니다.
- LLM 토큰 사용량, 예상 비용, 판단 근거, 리스크 검토 결과를 함께 남깁니다.
- 기본 예시는 `$250` 자본 제한과 반도체 Top 10 Universe를 사용하지만, 사용자는 `.env`에서 자신의 연구 설정으로 바꿀 수 있습니다.

## 범위와 한계

- 수익을 보장하지 않습니다.
- 투자 판단을 대신하지 않습니다.
- 기본 설정만으로 실제 주문을 보내지 않습니다.
- 여러 증권사를 한 번에 지원하는 범용 브로커 플랫폼은 아닙니다.
- 실제 계좌 정보, 실거래 기록, 실제 API 응답은 저장소에 포함하지 않습니다.

## 핵심 기능

- AI 에이전트 의사결정 기록
- 설정 가능한 매매 universe
- 기본 예시: 반도체 Top 10 universe
- 기본 예시: `$250` paper trading 자본
- RiskManager 기반 최종 승인/거절
- 기존 보유 포지션 보호
- DRY_RUN 기반 모의 주문
- decision 승인 후 DRY_RUN 주문 시뮬레이션
- LLM 토큰/예상 비용 기록
- LLM 사용량 요약과 예산 제한
- LLM 응답, 사용량, 지연 시간, 성공 여부 기록
- rule-based candidate pre-filter로 LLM 입력 후보를 1~3개로 제한
- decision 사후 평가와 회고 기록
- React dashboard 구조

## 보안 원칙

- `.env`는 절대 커밋하지 않습니다.
- API 키는 환경변수로만 관리합니다.
- 실계좌 데이터는 저장소에 포함하지 않습니다.
- 공개 데모는 `USE_MOCK_DATA=true`로 실행합니다.
- 실거래는 사용자가 명시적으로 설정을 바꾸고, 코드와 주문 동작을 검토한 뒤 자기 책임으로 활성화해야 합니다.

## 환경변수 설정

`backend/.env.example`을 참고해 `backend/.env`를 만듭니다. 기본값은 안전하게 실행되도록 mock/paper trading 중심입니다.

```bash
cd backend
cp .env.example .env
```

중요 설정:

- `DRY_RUN=true`
- `LIVE_TRADING_ENABLED=false`
- `USE_MOCK_DATA=true`
- `BROKER_PROVIDER=toss_securities`
- `BOT_CAPITAL_LIMIT_USD=250`
- `ALLOWED_SYMBOLS=NVDA,AMD,TSM,AVGO,ASML,QCOM,MU,ARM,INTC,AMAT`

다른 사용자는 `BOT_CAPITAL_LIMIT_USD`, `ALLOWED_SECTOR`, `ALLOWED_SYMBOLS`, LLM 예산 제한을 자신의 연구 목적에 맞게 바꿀 수 있습니다. 브로커 연동은 기본적으로 토스증권 Open API 키 구조를 기준으로 합니다.

실제 OpenAI LLM 호출을 사용하려면 아래 조건을 모두 만족해야 합니다.

- `USE_MOCK_DATA=false`
- `OPENAI_API_KEY` 설정
- `LLM_MODEL_DECISION` 설정

이 조건이 맞지 않으면 실제 OpenAI API를 호출하지 않고 안전한 HOLD / SKIPPED 결과를 남깁니다.

LLM 예상 비용을 기록하려면 사용하는 모델의 현재 input/output 단가를 `.env`에 직접 설정합니다. 기본값은 `0`이며, 가격은 모델과 시점에 따라 바뀔 수 있어 코드에 고정하지 않습니다.

```bash
LLM_INPUT_COST_PER_1M_TOKENS_USD=0
LLM_OUTPUT_COST_PER_1M_TOKENS_USD=0
```

## Broker Integration

기본 브로커 provider는 `toss_securities`입니다.

- `TOSS_API_KEY`
- `TOSS_SECRET_KEY`
- `TOSS_ACCOUNT_ID`

위 값은 토스증권 Open API 사용자가 자신의 `.env`에 직접 넣는 값입니다. 저장소에는 실제 키나 계좌 정보를 포함하지 않습니다. 예전 이름인 `TOSS_APP_KEY`, `TOSS_APP_SECRET`도 호환되지만, 새 설정에는 `TOSS_API_KEY`, `TOSS_SECRET_KEY`를 권장합니다.

## 실행 방법

아래 명령은 사용자가 직접 실행합니다.

Backend:

```bash
cd /home/ubuntu/ai-trading-agent/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Demo seed data:

```bash
cd /home/ubuntu/ai-trading-agent/backend
python -m app.seed_demo_data
```

Demo seed API:

```bash
curl http://localhost:8000/demo/status
curl -X POST http://localhost:8000/demo/seed
```

Demo seed는 `USE_MOCK_DATA=true`이고 Toss/OpenAI 같은 외부 API credential이 설정되지 않은 경우에만 활성화됩니다.

Agent run once:

```bash
curl -X POST http://localhost:8000/agent/run-once
```

Agent status:

```bash
curl http://localhost:8000/agent/status
```

Preview and approve a decision:

```bash
curl http://localhost:8000/decisions/1/preview
curl -X POST http://localhost:8000/decisions/1/approve
```

`/decisions/{id}/preview`는 예상 side, 수량, 가격, 주문금액, 예산 영향, bot-owned 수량, legacy 보호 여부, RiskManager 결과를 먼저 보여줍니다.

List simulated orders:

```bash
curl http://localhost:8000/orders
```

Run decision evaluations:

```bash
curl -X POST http://localhost:8000/evaluations/run
curl -X POST http://localhost:8000/evaluations/1
curl http://localhost:8000/evaluations
```

Update market snapshots:

```bash
curl http://localhost:8000/market/snapshots/latest
curl -X POST http://localhost:8000/market/snapshots \
  -H "Content-Type: application/json" \
  -d '{"snapshots":[{"symbol":"NVDA","price":120,"change_percent":1.2,"volume":1000000}]}'
```

`USE_MOCK_DATA=false`에서는 agent가 저장된 최신 market snapshot만 사용합니다. 허용 Top 10 universe 밖의 심볼은 저장하지 않으며, `MARKET_SNAPSHOT_MAX_AGE_MINUTES`보다 오래된 snapshot은 agent 입력에서 제외합니다.

Review LLM usage and budget:

```bash
curl http://localhost:8000/llm-usage
curl http://localhost:8000/llm-usage/summary
curl http://localhost:8000/settings/llm-budget
curl http://localhost:8000/settings/security-readiness
```

`/settings/security-readiness`는 API 키 값을 반환하지 않고, mock/demo 안전 상태, Toss/OpenAI 설정 여부, 필요한 다음 조치만 boolean과 문구로 보여줍니다.

Broker readiness:

```bash
curl http://localhost:8000/broker/status
curl http://localhost:8000/broker/accounts
curl http://localhost:8000/broker/accounts/normalized
curl http://localhost:8000/broker/positions
curl http://localhost:8000/broker/positions/normalized
curl -X POST http://localhost:8000/portfolio/sync-legacy-from-broker
```

Toss read-only 계좌 목록 조회는 `USE_MOCK_DATA=false`, `TOSS_API_KEY`, `TOSS_SECRET_KEY`가 필요합니다. 보유 주식 조회와 legacy sync에는 `TOSS_ACCOUNT_ID`도 필요합니다.

Toss API 응답 지연 때문에 확인 명령이 오래 걸리면 `--max-time`으로 클라이언트 대기 시간을 제한할 수 있습니다. backend의 Toss API 대기 시간은 `TOSS_TIMEOUT_SECONDS`로 조정하며, 기본 예시는 8초입니다.

```bash
curl --max-time 10 http://localhost:8000/broker/accounts/normalized
```

Endpoint path는 base URL 뒤에 붙는 API 경로입니다. 기본값은 Toss OpenAPI 1.1.5 기준으로 `TOSS_TOKEN_PATH=/oauth2/token`, `TOSS_ACCOUNT_LIST_PATH=/api/v1/accounts`, `TOSS_HOLDINGS_PATH=/api/v1/holdings`입니다.

처음에는 `TOSS_ACCOUNT_ID`가 비어 있어도 `/broker/accounts`로 계좌 목록을 조회할 수 있습니다. 응답에서 계좌 식별값을 확인한 뒤 `TOSS_ACCOUNT_ID`에 넣으면 보유 주식 조회와 legacy sync를 사용할 수 있습니다.

`/portfolio/sync-legacy-from-broker`는 Toss 조회 잔고를 protected legacy position으로 가져옵니다. 봇 포지션이 이미 있으면 기존 보유분과 봇 포지션이 섞이지 않도록 import를 차단합니다.

Frontend의 `Broker` 화면에서는 backend health, Toss API key/secret 준비 상태, 계좌 목록 조회 준비 상태, `TOSS_ACCOUNT_ID` 설정 여부, `/broker/accounts/normalized` 기준의 마스킹된 계좌 목록, normalized holdings, legacy sync 버튼을 확인할 수 있습니다.
Toss holdings 응답에 평균단가나 현재가 필드가 없으면 Broker 화면에서는 `0` 대신 `-`로 표시합니다. 별도 현재가 시세 조회는 아직 연결하지 않았습니다.

Frontend:

```bash
cd /home/ubuntu/ai-trading-agent/frontend
npm install
npm run dev
```

Frontend API 주소는 `VITE_API_BASE_URL`이 있으면 그 값을 우선 사용합니다. 값이 없으면 기본값 `/api`를 사용하고, Vite dev server가 backend로 프록시합니다.

- `http://localhost:5173`에서 열면 local backend `http://localhost:8000`
- Docker Compose에서 `http://localhost:3000` 또는 `http://<SERVER_IP>:3000`으로 열면 `/api` 프록시를 통해 backend container `http://backend:8000`

다른 주소를 쓰려면 `VITE_API_BASE_URL`을 명시합니다.

Docker Compose:

```bash
cd /home/ubuntu/ai-trading-agent
cp backend/.env.example backend/.env
docker compose up --build
```

Docker Compose backend는 `backend/.env`를 읽습니다. Toss/OpenAI 키, `USE_MOCK_DATA`, 리스크 제한값은 이 파일에서 관리합니다. Frontend는 기본적으로 `/api`를 호출하고 Vite proxy가 backend container로 전달합니다.

Docker Compose 기본 host port는 frontend `3000`, backend `81`입니다. 브라우저 대시보드는 기본적으로 frontend `3000`만 호출하고, API 요청은 `/api` proxy를 거쳐 backend로 전달됩니다.

```bash
curl http://localhost:81/health
```

외부 서버에서 브라우저로 확인할 때는 기본적으로 `http://<SERVER_IP>:3000`만 열면 됩니다. backend `81` 포트를 브라우저에 직접 노출하거나 호출할 필요는 없습니다. 명시적으로 고정해야 할 때만 frontend가 호출할 backend 주소를 서버 IP 기준으로 지정합니다.

```bash
VITE_API_BASE_URL=http://<SERVER_IP>:81 docker compose up --build
```

이때 backend가 브라우저 요청을 허용하도록 `backend/.env`의 `CORS_ALLOWED_ORIGINS`에도 frontend 주소를 추가합니다.

```bash
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000,http://<SERVER_IP>:3000
```

다른 포트를 쓰려면 실행 시 `BACKEND_PORT`, `FRONTEND_PORT`, `VITE_API_BASE_URL`을 함께 지정합니다.

```bash
BACKEND_PORT=8083 FRONTEND_PORT=3001 VITE_API_BASE_URL=http://<SERVER_IP>:8083 docker compose up --build
```

Docker 실행 시에도 기본값은 `DRY_RUN=true`, `LIVE_TRADING_ENABLED=false`, `USE_MOCK_DATA=true`입니다. 실제 키를 넣은 `.env` 파일은 커밋하지 않습니다.

## Public Repo 운영 방침

- 기본 설정: DRY_RUN / demo / paper trading
- 실거래 활성화는 opt-in이며, 사용자 본인이 브로커 약관과 관련 법규를 확인해야 합니다.
- API 키, 계좌번호, 실거래 로그, 실제 API 응답은 저장소에 포함하지 않습니다.

## 면책 문구

이 프로젝트는 소프트웨어 엔지니어링, AI 에이전트 연구, paper trading 실험을 위한 도구입니다.

투자 조언이나 금융 자문을 제공하지 않으며, 수익을 보장하지 않습니다. 실제 API 키를 연결하거나 설정을 변경해 운용하는 경우, 모든 거래 판단과 그 결과는 사용자 본인의 책임입니다.
