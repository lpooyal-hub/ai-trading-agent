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
- `/health`
- `/settings/safety`
- `/settings/llm-budget`
- `/demo/status`
- `/demo/seed`
- `/portfolio/initialize-legacy`
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
docker compose up --build
```

## 안전 원칙

- 기본 브로커 provider는 `toss_securities`입니다.
- `DRY_RUN=true`가 기본값입니다.
- `LIVE_TRADING_ENABLED=false`가 기본값입니다.
- 실주문 API 호출은 기본 설정에서 비활성화되어 있습니다.
- 기존 보유 주식은 legacy position으로 보호해야 합니다.
- 봇은 반도체 Top 10 Universe 허용 종목만 다룰 수 있어야 합니다.
- 에이전트 운용 비용을 보기 위해 판단별 토큰 사용량과 예상 비용을 기록합니다.
- 현재 agent 실행은 mock market data와 mock LLM 응답만 사용합니다.
- LLM 입력 비용을 줄이기 위해 Top 10 전체가 아니라 rule-based pre-filter를 통과한 1~3개 후보만 agent에 전달합니다.
- LLM 호출 전 budget guard를 확인하고, 한도를 넘으면 LLM 호출 없이 `SKIPPED` decision을 저장합니다.
- decision 승인 시에도 RiskManager가 최종 검증하며, 현재는 DRY_RUN simulated order만 생성합니다.
- decision evaluation은 mock snapshot 가격과 결정 당시 가격을 비교해 hindsight review를 저장합니다.

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

1. Top 10 Universe의 mock market snapshot을 저장합니다.
2. rule-based pre-filter로 1~3개 후보만 고릅니다.
3. 후보가 없으면 LLM을 호출하지 않고 `SKIPPED` 결정을 저장합니다.
4. 후보가 있으면 LLM budget guard를 확인합니다.
5. budget이 초과되면 LLM을 호출하지 않고 `SKIPPED` 결정을 저장합니다.
6. budget이 남아 있으면 mock LLM 응답으로 `AgentDecision`을 저장합니다.
7. mock LLM 사용량은 `LLMUsage`에 함께 기록합니다.
8. 사용자가 decision을 승인하면 RiskManager 검증 후 `TradeOrder`를 `SIMULATED` 상태로 저장합니다.
9. BUY 시뮬레이션은 bot-only `BotPosition`만 갱신하고 legacy position은 건드리지 않습니다.
10. `/evaluations` API로 decision별 사후 평가를 저장하고 조회합니다.

현재 mock 설정에서는 실제 OpenAI API와 Toss API를 호출하지 않습니다.

## Demo Data

대시보드 확인용 fictional demo data는 CLI 또는 API로 생성할 수 있습니다.

```bash
python -m app.seed_demo_data
curl -X POST http://localhost:8000/demo/seed
```

`/demo/seed`는 `USE_MOCK_DATA=true`이고 외부 API credential이 설정되지 않은 경우에만 허용됩니다.
