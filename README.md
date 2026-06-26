# AI Trading Agent Research Platform

이 프로젝트는 공개 포트폴리오용 **AI Trading Agent Research Platform**입니다. 목적은 실거래 수익을 보장하는 자동매매가 아니라, paper trading 환경에서 에이전트의 판단을 기록하고, 리스크 관문을 통과시키고, LLM 사용량과 의사결정 품질을 평가하는 것입니다.

## 이 프로젝트는 무엇인가

- DRY_RUN 전용 AI 트레이딩 에이전트 연구 플랫폼
- 의사결정 로그, 모의 주문, 리스크 관리, 평가 기록을 남기는 실험 환경
- LLM 토큰 사용량과 예상 비용을 함께 추적하는 분석 도구
- 기본 예시는 `$250` 자본 제한과 반도체 Top 10 Universe를 사용하지만, 사용자는 `.env`에서 자신의 연구 설정으로 바꿀 수 있습니다.

## 이 프로젝트가 아닌 것

- 수익 보장 자동매매 봇이 아닙니다.
- 투자 조언 도구가 아닙니다.
- public main 브랜치에는 실거래 기능을 포함하지 않습니다.
- 실제 계좌 데이터, 실제 주문 기록, 실제 API 응답을 저장소에 포함하지 않습니다.

## 핵심 기능

- AI Agent decision logging
- 설정 가능한 trading universe
- 기본 예시: semiconductor Top 10 universe
- 기본 예시: `$250` paper trading capital
- RiskManager 기반 최종 승인/거절
- legacy position protection
- DRY_RUN simulated orders
- LLM token/cost tracking
- decision evaluation and reflection
- React dashboard 구조

## 보안 원칙

- `.env`는 절대 커밋하지 않습니다.
- API Key는 환경변수로만 관리합니다.
- 실계좌 데이터는 저장소에 포함하지 않습니다.
- public demo는 `USE_MOCK_DATA=true`로 실행합니다.
- live trading 구현은 private branch 또는 private repository에서만 다룹니다.

## 환경변수 설정

`backend/.env.example`을 참고해 `backend/.env`를 만듭니다. 기본값은 공개 저장소에서 안전하게 보이도록 mock/paper trading 중심입니다.

```bash
cd backend
cp .env.example .env
```

중요 설정:

- `DRY_RUN=true`
- `LIVE_TRADING_ENABLED=false`
- `USE_MOCK_DATA=true`
- `BOT_CAPITAL_LIMIT_USD=250`
- `ALLOWED_SYMBOLS=NVDA,AMD,TSM,AVGO,ASML,QCOM,MU,ARM,INTC,AMAT`

다른 사용자는 `BOT_CAPITAL_LIMIT_USD`, `ALLOWED_SECTOR`, `ALLOWED_SYMBOLS`, LLM 예산 제한을 자신의 연구 목적에 맞게 바꿀 수 있습니다.

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

Frontend:

```bash
cd /home/ubuntu/ai-trading-agent/frontend
npm install
npm run dev
```

## Public Repo 운영 방침

- `main` branch: DRY_RUN / demo / paper trading only
- private branch or private repo: real API integration only
- public main branch는 실행해도 실주문이 나가지 않아야 합니다.

## 면책 문구

This project is for research and educational purposes only.
