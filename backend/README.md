# AI Trading Agent Backend

실험용 AI 트레이딩 에이전트 백엔드입니다.

V1은 반드시 DRY_RUN / paper trading 전용입니다. 실제 토스증권 주문 실행은 구현하지 않으며, 관련 함수는 TODO 또는 `NotImplementedError`로 남깁니다.

## 현재 단계

Step 1만 구현되어 있습니다.

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
- 실주문 API 호출은 V1에서 의도적으로 구현하지 않습니다.
- 기존 보유 주식은 legacy position으로 보호해야 합니다.
- 봇은 반도체 Top 10 Universe 허용 종목만 다룰 수 있어야 합니다.
- 에이전트 운용 비용을 보기 위해 판단별 토큰 사용량과 예상 비용을 기록합니다.

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
