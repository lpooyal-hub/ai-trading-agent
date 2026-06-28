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
- simulated order 기반 realized/unrealized PnL, win rate, realized trade 요약
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

기본 접속 주소:

- Frontend: `http://localhost:3000`
- Backend health: `http://localhost:81/health`

서버에서 실행 중이면 브라우저에서는 frontend만 열면 됩니다.

```text
http://<SERVER_IP>:3000
```

Frontend는 기본적으로 `/api`를 호출하고, Docker Compose의 Vite proxy가 backend container로 넘깁니다. 그래서 일반 실행에서는 browser가 backend `81` 포트를 직접 호출할 필요가 없습니다.
각 Docker build context는 `.dockerignore`로 `.env`, DB 파일, cache, `node_modules` 같은 로컬 파일을 제외합니다.

## 기본 설정

`backend/.env`는 Docker Compose backend가 읽습니다. 기본값은 안전한 demo / paper trading입니다.

- `DRY_RUN=true`
- `LIVE_TRADING_ENABLED=false`
- `USE_MOCK_DATA=true`
- `BROKER_PROVIDER=toss_securities`
- `BOT_CAPITAL_LIMIT_USD=250`
- `ALLOWED_SYMBOLS=NVDA,AMD,TSM,AVGO,ASML,QCOM,MU,ARM,INTC,AMAT`

실제 API 키, 계좌번호, OpenAI 키는 `backend/.env`에만 넣고 커밋하지 않습니다.

## Dashboard 사용 흐름

Docker를 올린 뒤 Dashboard에서 아래 흐름으로 확인합니다.

1. `Dashboard`: demo 상태, market readiness, agent readiness 확인
2. `Market`: `Refresh Source`로 demo market snapshot 생성 또는 수동 snapshot 저장. Active universe 전체가 fresh일 때 agent ready로 표시됩니다.
3. `Decisions`: `Run Agent Once`로 paper decision 생성
4. `Decision Detail`: preview 확인 후 approve하면 DRY_RUN simulated order 생성
5. `Orders`: simulated fill과 bot position 수량 변화를 확인
6. `Portfolio`: bot-only position, protected legacy position, PnL 확인
7. `Broker`: Toss read-only 계좌/잔고 연결 상태 확인

## 서버 반영

코드를 받은 뒤 컨테이너를 다시 만들 때는 아래만 실행하면 됩니다.

```bash
cd /home/ubuntu/ai-trading-agent
docker compose up --build -d --force-recreate
```

브라우저에서 `Ctrl+Shift+R`로 강력 새로고침합니다.

## API 참고

Dashboard에서 대부분의 기능을 사용할 수 있지만, 직접 확인할 때는 아래 endpoint를 사용할 수 있습니다.

Agent:

```bash
curl http://localhost:81/agent/status
curl http://localhost:81/agent/readiness
curl -X POST http://localhost:81/agent/run-once
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
curl http://localhost:81/portfolio/realized-trades
curl http://localhost:81/portfolio/bot
curl http://localhost:81/portfolio/legacy
curl -X POST http://localhost:81/portfolio/sync-bot-from-market
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

이 조건이 맞지 않으면 실제 OpenAI API를 호출하지 않고 안전한 HOLD / SKIPPED 결과를 남깁니다.

LLM 예상 비용을 기록하려면 사용하는 모델의 현재 input/output 단가를 `.env`에 직접 설정합니다. 기본값은 `0`입니다.

```bash
LLM_INPUT_COST_PER_1M_TOKENS_USD=0
LLM_OUTPUT_COST_PER_1M_TOKENS_USD=0
```

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
- Docker Compose에서 `http://localhost:3000` 또는 `http://<SERVER_IP>:3000`으로 열면 `/api` 프록시를 통해 backend container `http://backend:8000`

Docker 실행 시에도 기본값은 `DRY_RUN=true`, `LIVE_TRADING_ENABLED=false`, `USE_MOCK_DATA=true`입니다.

## Public Repo 운영 방침

- 기본 설정: DRY_RUN / demo / paper trading
- 실거래 활성화는 opt-in이며, 사용자 본인이 브로커 약관과 관련 법규를 확인해야 합니다.
- API 키, 계좌번호, 실거래 로그, 실제 API 응답은 저장소에 포함하지 않습니다.

## 면책 문구

이 프로젝트는 소프트웨어 엔지니어링, AI 에이전트 연구, paper trading 실험을 위한 도구입니다.

투자 조언이나 금융 자문을 제공하지 않으며, 수익을 보장하지 않습니다. 실제 API 키를 연결하거나 설정을 변경해 운용하는 경우, 모든 거래 판단과 그 결과는 사용자 본인의 책임입니다.
