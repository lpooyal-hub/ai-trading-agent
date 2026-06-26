# AI Trading Agent Research Platform

이 프로젝트는 공개 포트폴리오용 **AI Trading Agent Research Platform**입니다. 목적은 실거래 수익을 보장하는 자동매매가 아니라, 기본 DRY_RUN 환경에서 에이전트의 판단을 기록하고, 리스크 관문을 통과시키고, LLM 사용량과 의사결정 품질을 평가하는 것입니다.

## 이 프로젝트는 무엇인가

- 기본값이 DRY_RUN인 AI 트레이딩 에이전트 연구 플랫폼
- 의사결정 로그, 모의 주문, 리스크 관리, 평가 기록을 남기는 실험 환경
- LLM 토큰 사용량과 예상 비용을 함께 추적하는 분석 도구
- 기본 예시는 `$250` 자본 제한과 반도체 Top 10 Universe를 사용하지만, 사용자는 `.env`에서 자신의 연구 설정으로 바꿀 수 있습니다.
- 현재 public demo는 mock market data와 mock LLM 응답으로 동작합니다.

## 이 프로젝트가 아닌 것

- 수익 보장 자동매매 봇이 아닙니다.
- 투자 조언 도구가 아닙니다.
- 기본 설정 그대로 실행했을 때 실주문이 나가는 도구가 아닙니다.
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

Agent run once:

```bash
curl -X POST http://localhost:8000/agent/run-once
```

Agent status:

```bash
curl http://localhost:8000/agent/status
```

Frontend:

```bash
cd /home/ubuntu/ai-trading-agent/frontend
npm install
npm run dev
```

## Public Repo 운영 방침

- 기본 설정: DRY_RUN / demo / paper trading
- 실거래 활성화는 opt-in이며, 사용자 본인이 브로커 약관과 관련 법규를 확인해야 합니다.
- API 키, 계좌번호, 실거래 로그, 실제 API 응답은 저장소에 포함하지 않습니다.

## 면책 문구

This project is for research and educational purposes only.
