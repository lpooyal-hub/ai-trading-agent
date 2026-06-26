# AI Trading Agent Backend

실험용 AI 트레이딩 에이전트 백엔드입니다.

현재 기본 설정은 DRY_RUN / paper trading입니다. 실거래는 기본값으로 비활성화되어 있으며, 사용자가 명시적으로 환경변수를 바꾸고 주문 동작을 검토한 경우에만 확장할 수 있습니다.

## 현재 단계

현재는 backend 기본 골격, 포트폴리오 조회, mock agent decision 생성까지 구현되어 있습니다.

- FastAPI 앱 엔트리
- dotenv 기반 설정
- SQLite / SQLAlchemy 연결
- 핵심 ORM 모델
- Pydantic 스키마
- 에이전트 판단별 LLM 토큰/예상 비용 기록 필드
- `/health`
- `/settings/safety`
- `/portfolio/initialize-legacy`
- `/portfolio/legacy`
- `/portfolio/bot`
- `/portfolio/summary`
- `/agent/run-once`
- `/agent/status`
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

## 안전 원칙

- `DRY_RUN=true`가 기본값입니다.
- `LIVE_TRADING_ENABLED=false`가 기본값입니다.
- 실주문 API 호출은 기본 설정에서 비활성화되어 있습니다.
- 기존 보유 주식은 legacy position으로 보호해야 합니다.
- 봇은 반도체 Top 10 Universe 허용 종목만 다룰 수 있어야 합니다.
- 에이전트 운용 비용을 보기 위해 판단별 토큰 사용량과 예상 비용을 기록합니다.
- 현재 agent 실행은 mock market data와 mock LLM 응답만 사용합니다.
- LLM 입력 비용을 줄이기 위해 Top 10 전체가 아니라 rule-based pre-filter를 통과한 1~3개 후보만 agent에 전달합니다.

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
4. 후보가 있으면 mock LLM 응답으로 `AgentDecision`을 저장합니다.
5. mock LLM 사용량은 `LLMUsage`에 함께 기록합니다.

현재 mock 설정에서는 실제 OpenAI API와 Toss API를 호출하지 않습니다.
