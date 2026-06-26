# AI Trading Agent Research Platform

이 프로젝트는 **Toss Securities Open API**를 기본 브로커 어댑터로 가정한 공개 포트폴리오용 **AI Trading Agent Research Platform**입니다. 목적은 실거래 수익을 보장하는 자동매매가 아니라, 기본 DRY_RUN 환경에서 에이전트의 판단을 기록하고, 리스크 관문을 통과시키고, LLM 사용량과 의사결정 품질을 평가하는 것입니다.

## 이 프로젝트는 무엇인가

- 기본값이 DRY_RUN인 AI 트레이딩 에이전트 연구 플랫폼
- 기본 브로커 대상은 토스증권 Open API입니다.
- 의사결정 로그, 모의 주문, 리스크 관리, 평가 기록을 남기는 실험 환경
- LLM 토큰 사용량과 예상 비용을 함께 추적하는 분석 도구
- 기본 예시는 `$250` 자본 제한과 반도체 Top 10 Universe를 사용하지만, 사용자는 `.env`에서 자신의 연구 설정으로 바꿀 수 있습니다.
- 현재 public demo는 mock market data와 mock LLM 응답으로 동작합니다.

## 이 프로젝트가 아닌 것

- 수익 보장 자동매매 봇이 아닙니다.
- 투자 조언 도구가 아닙니다.
- 기본 설정 그대로 실행했을 때 실주문이 나가는 도구가 아닙니다.
- 여러 증권사 API를 동시에 지원하는 범용 브로커 플랫폼이 아닙니다.
- 실제 계좌 데이터, 실제 주문 기록, 실제 API 응답을 저장소에 포함하지 않습니다.

## 핵심 기능

- AI Agent decision logging
- 설정 가능한 trading universe
- 기본 예시: semiconductor Top 10 universe
- 기본 예시: `$250` paper trading capital
- RiskManager 기반 최종 승인/거절
- legacy position protection
- DRY_RUN simulated orders
- Decision approval API for DRY_RUN order simulation
- LLM token/cost tracking
- LLM usage summary and budget guardrails
- LLM client result wrapper for parsed/raw response, usage, latency, and success tracking
- rule-based candidate pre-filter로 LLM 입력 후보를 1~3개로 제한
- decision evaluation and reflection
- React dashboard 구조

## 보안 원칙

- `.env`는 절대 커밋하지 않습니다.
- API Key는 환경변수로만 관리합니다.
- 실계좌 데이터는 저장소에 포함하지 않습니다.
- public demo는 `USE_MOCK_DATA=true`로 실행합니다.
- live trading은 사용자가 명시적으로 설정을 바꾸고, 코드와 주문 동작을 검토한 뒤 자기 책임으로 활성화해야 합니다.

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

- `TOSS_APP_KEY`
- `TOSS_APP_SECRET`
- `TOSS_ACCOUNT_ID`

위 값은 토스증권 Open API 사용자가 자신의 `.env`에 직접 넣는 값입니다. 저장소에는 실제 키나 계좌 정보를 포함하지 않습니다.

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
curl http://localhost:8000/broker/positions
```

Toss read-only API 연결은 `USE_MOCK_DATA=false`, `TOSS_APP_KEY`, `TOSS_APP_SECRET`, `TOSS_ACCOUNT_ID`와 함께 공식 문서 기준 endpoint path를 `.env`에 설정해야 활성화됩니다. endpoint path는 문서 버전에 따라 달라질 수 있어 코드에 고정하지 않습니다.

Frontend:

```bash
cd /home/ubuntu/ai-trading-agent/frontend
npm install
npm run dev
```

기본 frontend API 주소는 `http://localhost:8000`입니다. 다른 주소를 쓰려면 `VITE_API_BASE_URL`을 설정합니다.

Docker Compose:

```bash
cd /home/ubuntu/ai-trading-agent
docker compose up --build
```

Docker 실행 시에도 기본값은 `DRY_RUN=true`, `LIVE_TRADING_ENABLED=false`, `USE_MOCK_DATA=true`입니다. 실제 키를 넣은 `.env` 파일은 커밋하지 않습니다.

## Public Repo 운영 방침

- 기본 설정: DRY_RUN / demo / paper trading
- 실거래 활성화는 opt-in이며, 사용자 본인이 브로커 약관과 관련 법규를 확인해야 합니다.
- API 키, 계좌번호, 실거래 로그, 실제 API 응답은 저장소에 포함하지 않습니다.

## 면책 문구

This project is for research and educational purposes only.
