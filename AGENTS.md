# AGENTS.md

이 저장소에서 작업하는 모든 코딩 에이전트(Claude, Codex 등)가 공통으로 따르는 기본 규칙이다. 도구별 추가 지침은 `CLAUDE.md` 같은 파일에 별도로 두되, 여기 있는 규칙과 충돌하면 이 문서가 우선한다.

## 프로젝트 정체성

- **AI Trading Agent Research Platform** — Toss Securities Open API를 기본 브로커 어댑터로 가정한 공개 포트폴리오용 연구 프로젝트다.
- 목적은 실거래 수익을 보장하는 자동매매가 아니라, 에이전트의 판단·리스크 검증·주문 시뮬레이션·LLM 비용·사후 평가를 **감사 가능한 workflow**로 남기는 것이다.
- 투자 조언/금융 자문/매매 권유가 아니다 (`DISCLAIMER.md`). 수익을 보장하지 않는다.

## 절대 규칙 (예외 없음)

- `.env` 파일, API 키, 실제 증권 계좌 ID/번호, 실제 보유 종목·수량, 실제 주문 내역, 실제 API 응답 원문, 로컬 DB/로그 파일을 **절대 커밋하지 않는다**. (`SECURITY.md`)
- `DRY_RUN=true`, `LIVE_TRADING_ENABLED=false`, `USE_MOCK_DATA=true`가 기본값이다. 사용자가 명시적으로 요청하지 않는 한 이 기본값을 바꾸는 코드/설정을 작성하지 않는다.
- Live trading 관련 코드(`TossLiveExecutionAdapter`, 실주문 경로)를 건드릴 때는 항상 env opt-in(`DRY_RUN=false`, `LIVE_TRADING_ENABLED=true`, Toss credentials, `TOSS_ORDER_PATH`, 관리자 API key)이 모두 갖춰졌을 때만 동작하도록 유지한다. 이 가드 중 하나라도 약화시키는 변경은 하지 않는다.
- `ALLOWED_SYMBOLS`로 정의된 active universe 밖 종목을 다루는 코드를 추가하지 않는다.
- **Legacy position(기존 실보유 종목)과 bot position(봇 시뮬레이션)을 절대 섞지 않는다.** bot 관련 로직이 legacy position을 갱신하거나 읽어서 매매 판단에 쓰면 안 된다.
- 공개 데모/포트폴리오 시연 경로는 `USE_MOCK_DATA=true`를 전제로 하며, mock mode에서는 실제 Toss API/OpenAI API를 호출하지 않는다.

## 아키텍처 규칙

- 하나의 코드베이스를 유지하고 실행 모드는 `.env`로 분기한다. 모드별로 별도 브랜치를 만들지 않는다.
- LLM이 꼭 필요한 판단/요약(예: BUY/SELL/HOLD 판단, thesis)만 LLM에 맡기고, 계산/검증/필터링은 Python으로 처리해 비용과 리스크를 줄인다. 새 로직을 추가할 때 이 원칙을 먼저 검토한다.
- Execution adapter 경계(`PaperExecutionAdapter` / `TossLiveExecutionAdapter` / `BlockedLiveExecutionAdapter`)를 유지한다. 새 실행 경로를 추가할 때도 이 3분류 구조에 맞춘다.
- `backend/app/services/agent_graph_service.py`는 LangGraph `StateGraph` 기반 orchestration만 담당한다. 도메인 로직은 `backend/app/agents/*`, `backend/app/risk/*`, `backend/app/execution/*`에 있는 각 agent/서비스가 소유한다 — graph service 안에 도메인 로직을 새로 밀어넣지 않는다.
- 리스크/예산 가드(`LLMBudgetManager`, `RiskManager`, `DecisionResponseGuard`)는 이미 있는 걸 재사용한다. 유사한 검증 로직을 다른 곳에 새로 만들지 않는다.

## 실행 & 테스트

```bash
cd /home/ubuntu/ai-trading-agent
cp backend/.env.example backend/.env   # 최초 1회
docker compose up --build
```

테스트 (추가 패키지 없이 표준 `unittest`):

```bash
docker compose exec -T backend python -m unittest discover -s tests
docker compose exec -T backend python -m compileall app
```

- Alembic 같은 마이그레이션 도구가 없다. `backend/app/database.py`의 `Base.metadata.create_all(bind=engine)`로 스키마를 만든다. **모델 필드를 추가/변경하면 로컬 DB는 재생성하면 되지만, 운영 DB가 있는 서버라면 스키마 변경 전에 반드시 사용자에게 마이그레이션 방식을 확인한다.**
- Frontend: `cd frontend && npm install && npm run dev`, 또는 루트에서 `docker compose up --build`.

## 여러 에이전트가 동시에 작업할 때

- 이 저장소는 Claude와 Codex가 같은 브랜치/워킹 트리에서 병렬로 작업하는 경우가 있다.
- 진행 중인 대규모 변경은 `docs/plans/`에 설계 문서가 먼저 만들어진다. 큰 구조 변경을 시작하기 전에 `docs/plans/`에 관련 문서가 있는지 확인하고, 있다면 그 문서의 **파일 소유권 표(누가 어떤 파일을 담당하는지)**를 따른다.
- 파일 소유권 표에 없는 파일을 새로 건드려야 하면, 작업을 시작하기 전에 계획 문서에 그 사실을 추가해 다른 에이전트와의 충돌을 피한다.
- 계획 문서 없이 그래프 구조(`agent_graph_service.py`), 리스크 가드, 락/스케줄링 로직처럼 안전에 직결되는 파일을 크게 뜯어고치지 않는다.

## 참고 문서

- `README.md` — 전체 아키텍처, 멀티에이전트 구조, Quick Start, API 목록
- `SECURITY.md` — 커밋 금지 항목, 비밀값 노출 시 대응
- `DISCLAIMER.md` — 면책 고지
- `backend/README.md` — backend 실행/테스트, 안전 원칙, agent 실행 흐름 상세
- `frontend/README.md` — frontend 실행, 주요 화면
- `docs/plans/` — 진행 중인 설계 변경 계획 문서
