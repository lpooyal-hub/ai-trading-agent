# LangGraph 연속 다회차 세션 루프 — 설계 & 작업 분담 플랜

작성일: 2026-08-10
목적: 현재 "tick 1회 = decision 1회" 구조를, **하나의 LangGraph 실행 안에서 여러 decision 사이클이 순환하는 세션 구조**로 재설계한다. Claude와 Codex가 동시에 작업할 수 있도록 파일 단위로 경계를 나눈다.

> **Phase 0 완료 (2026-08-10).** Claude 담당 파일(§2)은 모두 구현·검증 완료. Codex는 §2.1의 실제 계약을 기준으로 바로 시작할 수 있다. §2.1을 먼저 읽을 것 — 원래 초안에서 몇 가지가 실제 구현 중에 바뀌었다.

## 0.1 Phase 0 완료 요약 — Codex는 여기부터 읽는다

구현하면서 원안(§1)에서 아래처럼 확정/변경됐다.

- **`run_once()`와 `run_session()`은 별도 그래프를 쓰는 완전히 분리된 경로다.** 처음 계획한 "기존 HTTP 엔드포인트가 내부적으로 `run_session(max_cycles=1)`을 호출하도록 통합"은 **하지 않았다.** `AgentGraphService`는 이제 `self.graph`(기존 선형, `run_once()`가 씀, 완전히 그대로)와 `self.session_graph`(신규 순환, `run_session()`이 씀)를 둘 다 갖는다. 두 그래프는 같은 노드 메서드(`_market_agent_node` 등)를 공유하지만 배선(엣지)만 다르다. 이유: `run_once()`는 `AgentDecision`을 반환하고 `run_session()`은 `AgentSession`을 반환해서 리턴 타입이 다르고, 기존 `/agent/run-once`, `/workflows/run` 같은 라우트와 대시보드 "지금 실행" 버튼이 `run_once()`/`AgentDecision` 계약에 의존하고 있어 그걸 건드리면 Codex의 세션 UI가 준비되기 전에 기존 화면이 깨질 위험이 있었다. **`workflow_execution_service.py`와 기존 라우트는 전혀 건드리지 않았다** — 회귀 테스트로 확인 완료(아래 참고).
- **Kill switch는 Redis가 아니라 DB 컬럼이다.** `AgentSession.stop_requested: bool`. Redis가 꺼져 있어도(`REDIS_ENABLED=false`) 동작해야 하므로 이렇게 결정했다. Codex의 `POST /agent/sessions/{id}/stop`은 이 컬럼을 `True`로 세팅하고 commit만 하면 된다. `loop_gate` 노드가 매 사이클 `db.refresh(session)`으로 최신값을 읽는다.
- **락 TTL은 신규 env var가 아니라 계산된 property다.** `Settings.agent_session_lock_ttl_seconds`는 `agent_scheduler_interval_minutes`의 2배(최소 `redis_agent_run_lock_ttl_seconds`)로 자동 계산된다. 별도로 설정할 필요 없음.
- **`agent_scheduler_interval_minutes`는 최소 1로 클램프된다** (`agent_scheduler_interval_minutes_safe`). 로컬에서 페이싱 없이 빠르게 테스트하려면 이 클램프 때문에 사이클당 최소 ~60초는 걸린다는 점을 감안할 것 (의도된 안전장치이지 버그 아님).

### 확정된 함수/필드 시그니처

```python
# backend/app/models.py
class AgentSessionStatus(str, enum.Enum):
    RUNNING = "RUNNING"; SUCCEEDED = "SUCCEEDED"; FAILED = "FAILED"; STOPPED = "STOPPED"

class AgentSession(Base):
    __tablename__ = "agent_sessions"
    id: int
    status: AgentSessionStatus
    trigger_source: str
    started_at: datetime
    finished_at: datetime | None
    cycle_count: int          # loop_gate가 사이클이 끝날 때마다 +1
    max_cycles: int           # run_session(max_cycles=...)로 세션별 override 가능, 전역 설정 이하로 clamp됨
    stop_reason: str | None
    stop_requested: bool      # Codex의 stop 엔드포인트가 세팅하는 kill switch
    redis_lock_key: str | None
    redis_lock_token: str | None
    runs: list[WorkflowRun]   # session_id로 연결된 사이클들, cycle_index 순 정렬

# WorkflowRun에 추가된 필드 (nullable, 기존 row/기존 run_once 경로는 항상 None)
session_id: int | None
cycle_index: int | None
```

```python
# backend/app/services/agent_graph_service.py
class AgentGraphService:
    def run_session(
        self,
        db: Session,
        trigger_source: str = "worker",
        max_cycles: int | None = None,   # None이면 settings.agent_session_max_cycles_safe 사용, 값을 주면 그 이하로 clamp
    ) -> AgentSession:
        """동기 호출, 사이클 사이에 실제 time.sleep으로 페이싱한다.
        절대 FastAPI 요청 핸들러 안에서 부르지 말 것 — 백그라운드 워커 전용."""
```

```python
# backend/app/services/workflow_service.py — 추가된 메서드만
def start_run(self, db, *, workflow_name, trigger_source, input_json=None,
               session_id: int | None = None, cycle_index: int | None = None) -> WorkflowRun: ...
def list_runs_for_session(self, db: Session, session_id: int) -> list[WorkflowRun]: ...  # cycle_index asc 정렬, steps eager-load됨
def fail_running_runs_for_session(self, db: Session, session_id: int, error_message: str) -> None: ...
```

```python
# backend/app/utils/market_hours.py — Codex의 worker.py가 그대로 재사용
def get_market_window(settings: Settings) -> dict  # {"open_now": bool, "session": str}
def is_market_open(settings: Settings) -> bool
```

```python
# backend/app/services/redis_runtime_service.py — 추가된 메서드만
def renew_agent_run_lock(self, lock: RedisLockResult, ttl_seconds: int) -> RedisLockResult: ...
```

### 검증한 것 (그대로 신뢰하고 그 위에 쌓아도 됨)

- 기존 `unittest` 8개 전부 통과 (`DecisionResponseGuard`, `RiskManager`, `SectorCandidateSelector`).
- `run_once()`가 만드는 `WorkflowRun`은 `session_id`/`cycle_index`가 항상 `None` — 기존 경로 완전 무변화 확인.
- `run_session()`을 mock 모드로 실제 3사이클 끝까지 돌려서 `next_cycle -> market_agent` back-edge, 사이클별 `WorkflowRun` 분리, `runtime_lock`이 세션당 1회만 실행되는 것, `max_cycles` 도달 시 정상 종료(`stop_reason="Session reached its max cycle count (3)"`, `status=SUCCEEDED`)까지 확인.
- 기존 `LLMBudgetManager` 쿨다운(`LLM_MIN_MINUTES_BETWEEN_CALLS`)이 `loop_gate`에서 그대로 작동해 실제로 세션을 멈추는 것도 실환경 시나리오로 확인됨 — 새 정지 조건뿐 아니라 기존 가드도 자연스럽게 세션을 멈춘다.
- `AgentSession.stop_requested=True`를 DB에 세팅하면 `_session_stop_reason`이 바로 "Admin requested the session to stop."을 반환하는 것 확인.

### Codex가 지금 바로 시작할 수 있는 것

§2의 표에 있는 파일들 그대로 진행하면 된다. 특히:
- `agent_session_service.py`: `AgentSession` 모델은 이미 있으니 CRUD만 얹으면 됨. `request_stop(db, session_id)`은 그냥 `session.stop_requested = True; db.commit()`.
- `routes/agent.py`의 신규 엔드포인트: `WorkflowService().list_runs_for_session(db, session_id)`을 그대로 쓰면 세션 상세 화면에 필요한 사이클별 `WorkflowRun`(및 각 run의 `steps`)이 다 나온다.
- `worker.py`: `AgentGraphService().run_session(db, trigger_source="worker")` 호출 하나가 핵심이다. 세션이 끝나면(정상/예외 무관하게 반환하거나 raise) 다음 market open까지 대기했다가 다시 호출하는 루프만 짜면 됨. `app.utils.market_hours.is_market_open(settings)`로 대기 여부 판단.

---

## 0. 현재 구조 진단

`backend/app/services/agent_graph_service.py`의 `_build_graph()`는 순수 선형 DAG다. 조건부 엣지는 `news_agent`/`risk_agent` 뒤의 skip 분기뿐이고, `journal_agent -> finish -> END`로 끝난다. README의 멀티에이전트 다이어그램에 있는 `JournalAgent -> MemoryAgent -> next DecisionAgent input` 화살표는 그래프 사이클이 아니라, **외부 스케줄러가 매 tick마다 새 프로세스/요청으로 DB에 저장된 memory/evaluation을 다시 읽어오는 것**으로 흉내만 내고 있다.

관련 기존 장치 (그대로 재사용 가능):
- `SchedulerAgent.run_if_due` (`agents/scheduler_agent.py`) — market hours 체크(`agent_market_open_time/close_time`, `agent_scheduler_market_hours_only`), interval 체크(`agent_scheduler_interval_minutes`)
- `LLMBudgetManager.check_budget` — 일일/월간 비용, 토큰, 호출 수 한도, 쿨다운
- `RiskManager.count_today_simulated_trades` vs `settings.max_daily_trades` — 일일 거래 수 상한
- `RedisRuntimeService.acquire_agent_run_lock` — 현재는 **갱신(heartbeat) 없는 고정 TTL(300s) 락**. 세션이 길어지면 만료되므로 반드시 손봐야 함.
- `WorkflowRun`/`WorkflowStep` (`models.py`) — 실행 1회당 row 1개. 다회차가 되면 "세션 1개 : 사이클(run) N개" 관계로 확장 필요.

이 문서는 "완전 새 구조"가 아니라 **위 장치들을 그래프 내부 루프의 정지 조건으로 재사용**하는 것을 전제로 한다.

---

## 1. 목표 아키텍처

### 1.1 그래프 레벨 변경 — 사이클 엣지 추가

```
session_start (1회)
  -> market_agent
  -> news_agent --skip--> [session_finish]
       |continue
  -> risk_agent --skip--> [session_finish]
       |continue
  -> memory_agent
  -> decision_agent
  -> execution_risk_agent
  -> logger_agent
  -> order_agent
  -> evaluation_agent
  -> journal_agent
  -> loop_gate ---stop---> session_finish -> END
       |continue (사이클 페이싱 포함)
       -> market_agent   (사이클 다시 시작)
```

핵심 차이:
- `runtime_lock`은 **세션 시작 시 1회만** 실행 (`session_start` 노드로 이름 변경/이동). 사이클마다 다시 락을 잡지 않고 **락 TTL을 매 사이클 갱신(heartbeat)** 한다.
- 새 노드 `loop_gate`: LLM 호출 없는 순수 라우팅 노드. `journal_agent` 다음에 실행되며 아래 정지 조건을 모두 통과해야 `continue`.
- `continue`일 때 `market_agent`로 돌아가는 게 핵심 back-edge (LangGraph `add_conditional_edges`로 구현, `market_agent`가 이미 그래프에 있는 노드이므로 사실상 사이클 그래프가 됨).
- `skip` 분기(`news_agent`/`risk_agent` 뒤)로 빠지는 경우도 이제는 세션을 완전히 끝내지 않고, **다음 사이클로 넘어갈지 세션을 끝낼지**를 판단해야 한다 (예: 후보 없음은 재시도 가치가 있지만, LLM 예산 초과는 세션을 끝내야 함). 기존 `skipped_decision` 노드도 `loop_gate`와 같은 정지 조건 체크를 거치도록 라우팅을 다시 설계해야 한다.

### 1.2 `loop_gate` 정지 조건 (모두 AND, 하나라도 실패하면 stop)

1. `cycle_index < settings.agent_session_max_cycles` (신규 설정, 기본값 제안: 30)
2. 세션 경과 시간 < `settings.agent_session_max_minutes` (신규 설정, 기본값 제안: market open~close 총 분량과 비슷하게)
3. 장중 여부 — `SchedulerAgent`가 쓰던 것과 동일한 market-hours 판정 로직을 공용 함수로 뽑아서 재사용 (`agents/scheduler_agent.py`의 판정 로직을 `app/utils/market_hours.py` 같은 공용 모듈로 추출 권장)
4. `LLMBudgetManager.check_budget(db)["approved"]`
5. `RiskManager.count_today_simulated_trades(db) < settings.max_daily_trades`
6. 외부 정지 신호 없음 — 신규: `AgentSession.stop_requested` 플래그 (관리자가 `POST /agent/sessions/{id}/stop` 호출 시 세팅)
7. Redis 락을 여전히 우리가 들고 있음 (heartbeat 갱신 성공) — 실패하면 다른 프로세스가 재기동됐다고 보고 즉시 stop

정지 사유는 `AgentSession.stop_reason`에 사람이 읽을 수 있는 문자열로 남긴다 (`"market closed"`, `"daily trade limit reached"`, `"admin stop"` 등). 이건 대시보드에 그대로 노출할 값이니 처음부터 열거형이 아니라 문자열로 자유롭게 적되, 프론트에서 매핑 테이블로 한글 라벨을 입히는 지금 패턴(`STEP_LABELS`)을 그대로 따른다.

### 1.3 사이클 페이싱 (실시간 간격)

지금 `agent_scheduler_interval_minutes`(기본 60분)는 "외부 tick 간격"이었는데, 이제 **세션 내부 사이클 간격**으로 의미가 바뀐다. `loop_gate`가 `continue`를 반환하기 직전에, 이번 사이클 소요 시간을 재서 `max(0, interval - elapsed)`만큼 대기한다.

이 대기(수십 분 단위)는 FastAPI 요청-응답 스레드에서 절대 블로킹하면 안 된다. 그래서 실행 모델도 같이 바뀐다 (§1.4).

### 1.4 실행 모델 — 세션은 백그라운드 워커가 소유

> **결정됨 (2026-08-11, 재변경): 24/7 상시 데몬.** 처음엔 하이브리드(외부 host cron이 하루 1번 트리거하는 1회성 프로세스)로 갔다가, 사용자가 "crontab 말고 그냥 상시 실행하고 agent가 알아서 거래하게" 하는 게 목표라고 명확히 해서 다시 24/7 상시 데몬으로 되돌렸다. §4에 있던 "24/7 vs 하이브리드" 질문은 이걸로 최종 확정.

- 신규 파일 `backend/app/worker.py`: 기존 `AgentGraphService`를 그대로 재사용하되 `run_session()`이라는 새 진입점을 호출. `run_worker()`는 컨테이너가 사는 동안 `while True`로 "장 열릴 때까지 대기 → 세션 1회(`run_session()`) 실행 → 장 닫힐 때까지 대기"를 반복한다. `agent_scheduler_enabled=False`인 동안은 5분 간격으로 idle-poll만 하고 세션을 시작하지 않는다 (컨테이너는 계속 떠 있어도 안전).
- `docker-compose.yml`의 `worker` 서비스는 `restart: unless-stopped`가 붙은 일반 서비스라 `docker compose up`에 포함된다 — 다른 서비스(backend/frontend/postgres/redis)처럼 상시 실행. cron 관련 설정은 없다.
- 기존 HTTP 엔드포인트(`POST /agent/run-once`, `POST /workflows/run`, `POST /agent/run-scheduled`)는 **하위 호환 유지**: 내부적으로 `run_session(max_cycles=1)`을 호출하도록 감싸서, "1회 실행" 시맨틱은 그대로 유지한 채 코드 경로만 통합한다. 대시보드의 "지금 실행" 버튼 동작이 바뀌지 않아야 한다. (이 통합 자체는 아직 미착수 — §2 통합 단계의 선택 항목 참고.)

### 1.5 데이터 모델 변경 (`backend/app/models.py`)

신규 테이블 `AgentSession`:
```python
class AgentSessionStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    STOPPED = "STOPPED"  # 관리자 stop 또는 정지 조건으로 정상 종료

class AgentSession(Base):
    __tablename__ = "agent_sessions"
    id: Mapped[int]
    status: Mapped[AgentSessionStatus]
    trigger_source: Mapped[str]          # "worker" | "manual" | "agent_legacy"
    started_at / finished_at
    cycle_count: Mapped[int] = 0
    stop_reason: Mapped[str | None]
    stop_requested: Mapped[bool] = False   # 관리자 kill switch
    redis_lock_token: Mapped[str | None]   # heartbeat 갱신용
```

`WorkflowRun`에 추가 (additive, nullable → 기존 row 마이그레이션 불필요, `create_all` 그대로 사용 가능):
```python
session_id: Mapped[int | None] = mapped_column(ForeignKey("agent_sessions.id"), nullable=True, index=True)
cycle_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

세션 하나 = `WorkflowRun` 여러 개(사이클마다 1개)로 모델링한다. 즉 사이클 내부의 노드 기록(`workflow_service.record_step`)은 **지금 코드를 거의 그대로 재사용**할 수 있다 — 사이클마다 새 `WorkflowRun`을 `start_run`으로 만들고 `session_id`/`cycle_index`만 채워 넣으면 된다. 이 설계를 고른 이유: 대시보드가 이미 "WorkflowRun 1개 = 카드 1개, 안에 step 리스트"로 렌더링하고 있어서, 세션 뷰는 이 카드들을 세션으로 묶어서 보여주기만 하면 되고 카드 내부 렌더링 로직은 재사용 가능.

마이그레이션 도구가 없고 `Base.metadata.create_all`만 쓰므로 (alembic 없음), 로컬/데모 DB는 재생성하면 되고 운영 DB가 따로 있다면 수동 `ALTER TABLE`이 필요하다는 점을 실행 전에 사용자에게 확인받을 것.

---

## 2. Claude ↔ Codex 작업 경계

병렬 작업 시 같은 파일을 동시에 건드리면 충돌하니, **Claude는 기존 안전 필수 파일(그래프/락/설정/모델 정의)을, Codex는 그 계약을 소비하는 신규 파일 위주**로 나눈다. Claude가 0단계(계약 확정)를 먼저 끝내야 Codex가 막힘없이 시작할 수 있다.

### Phase 0 — 계약 확정 (Claude, 완료됨 ✅)
구현 결과와 실제 함수/필드 시그니처는 §0.1 참고.
- `models.py`: `AgentSession`, `AgentSessionStatus`, `WorkflowRun.session_id`/`cycle_index` 필드 — 완료
- `config.py`: `agent_session_max_cycles`, `agent_session_max_minutes`, `agent_session_lock_ttl_seconds`(property) — 완료
- `AgentGraphService.run_session(db, trigger_source="worker", max_cycles=None) -> AgentSession` — 완료. `run_once()`와는 별도 그래프(`self.session_graph`)로 분리, `run_once()`는 무변화.
- `redis_runtime_service.py`의 `renew_agent_run_lock` — 완료
- `workflow_service.py`의 `start_run`(session_id/cycle_index 옵션), `list_runs_for_session`, `fail_running_runs_for_session` — 완료
- `utils/market_hours.py` 신규 추출, `agent_schedule_service.py`가 이걸 재사용하도록 리팩터 — 완료
- 검증: 기존 unittest 8개 통과, mock 모드 3사이클 실제 실행, `run_once()` 회귀 없음, admin stop 플래그 동작 확인 (§0.1 참고)

### Claude 담당 (기존 파일, 판단 난이도 높음) — 완료
| 파일 | 작업 | 상태 |
|---|---|---|
| `backend/app/services/agent_graph_service.py` | `loop_gate`/`next_cycle`/`session_finish` 노드, cyclic edge(`session_graph`), `run_session()` 진입점 | ✅ |
| `backend/app/services/redis_runtime_service.py` | 락 heartbeat 갱신 메서드(`renew_agent_run_lock`) 추가 | ✅ |
| `backend/app/config.py` | 신규 세션/루프 관련 설정값 추가 | ✅ |
| `backend/app/models.py` | `AgentSession` 모델, `WorkflowRun` 필드 추가 | ✅ |
| `backend/app/services/workflow_service.py` | `start_run`에 `session_id`/`cycle_index` 옵션 인자, `list_runs_for_session`, `fail_running_runs_for_session` 추가 | ✅ |
| `backend/app/utils/market_hours.py` (신규) | `scheduler_agent.py`에서 market-hours 판정 로직 추출 — Codex의 워커가 그대로 import해서 씀 | ✅ |

### Codex 담당 (신규 파일 위주, 충돌 위험 낮음) — 완료
| 파일 | 작업 | 상태 |
|---|---|---|
| `backend/app/worker.py` (신규) | market open 대기 → `run_session()` 호출 → market close/세션 종료 후 대기, 반복 (24/7 상시 데몬, §1.4 참고 — 한때 하이브리드로 바꿨다가 사용자 요청으로 다시 이 방식으로 확정) | ✅ |
| `docker-compose.yml` | `worker` 서비스 추가, `restart: unless-stopped`로 기본 `up`에 포함 | ✅ |
| `backend/app/services/agent_session_service.py` (신규) | `AgentSession` CRUD: list/get/request_stop | ✅ |
| `backend/app/routes/agent.py` | `GET /agent/sessions`, `GET /agent/sessions/{id}`, `POST /agent/sessions/{id}/stop` 엔드포인트 추가 (기존 라우트 건드리지 않고 append) | ✅ |
| `backend/app/schemas.py` | `AgentSessionRead` 등 신규 Pydantic 스키마 추가 (append) | ✅ |
| `frontend/src/api/client.ts` | 세션 관련 타입/fetch 함수 추가 (append) | ✅ |
| `frontend/src/pages/SessionsPage.tsx` (신규) | 세션 목록 + 세션 상세(사이클별 `WorkflowRun` 카드 나열, 기존 `WorkflowRunSummary` 재사용) + Stop 버튼, 라우팅 등록 | ✅ |
| `frontend/src/App.tsx` | `SessionsPage` 내비게이션/화면 등록 (위 라우팅 등록 작업의 지원 파일) | ✅ |
| `frontend/src/pages/WorkflowsPage.tsx` | 기존 `WorkflowRunSummary`를 세션 화면에서 재사용할 수 있도록 export만 추가 | ✅ |
| `backend/tests/test_agent_session_service.py`, `test_worker_pacing.py` 등 (신규) | 신규 서비스/워커 단위 테스트 | ✅ |

### 통합 단계 (Claude, Codex 결과물이 나온 뒤 마지막에)
- Codex의 `agent_session_service.request_stop()`이 실제로 `AgentSession.stop_requested`를 세팅하는지, `loop_gate`가 그걸 매 사이클 `db.refresh`로 잘 읽는지 배선 확인 (로직 자체는 이미 검증됨, Codex 쪽 호출부만 확인하면 됨)
- `worker.py`가 부르는 `run_session()` 호출부가 Phase 0 계약(§0.1)과 일치하는지, 특히 **FastAPI 요청 스레드가 아니라 별도 프로세스/스레드에서 도는지** 확인 — `run_session()`은 실제로 블로킹 `time.sleep`을 한다
- 락 heartbeat + stop 플래그 경합 조건(레이스) 리뷰 — 트레이딩 시스템이라 여기는 내가 직접 훑어봐야 함
- (선택, 나중 리팩터) 대시보드 "지금 실행" 버튼을 `run_session(max_cycles=1)` 경로로 통합할지는 Codex의 세션 UI가 자리잡은 뒤 별도로 결정 — Phase 0에서는 일부러 손대지 않았다 (§0.1 참고)

---

## 3. 안전 관련 필수 체크 (구현 중 반드시 지켜야 함)

- **Kill switch 없이 배포 금지**: `stop_requested` 체크가 `loop_gate`에 실제로 연결되기 전까지는 세션 자동 시작(워커)을 켜지 않는다.
- **락 heartbeat 실패 시 즉시 stop**: 락을 잃었는데 계속 도는 것이 가장 위험한 실패 모드 (동시에 두 세션이 주문을 낼 수 있음).
- **`session_max_cycles`/`session_max_minutes` 하드 캡은 협상 불가**: 다른 정지 조건이 다 실패해도 이 두 개는 무조건 지켜야 하는 최후 방어선.
- DRY_RUN이 기본값인 지금 안전장치(`README.md` "범위와 한계" 절)는 세션 루프 도입 후에도 그대로 유지 — 이 리팩터는 실행 빈도만 바꾸는 것이지 live trading 활성화 조건을 건드리지 않는다.

---

## 4. 아직 사용자 확인이 필요한 부분

- `agent_session_max_cycles`, `agent_session_max_minutes` 기본값 — 위 제안값(30, market 세션 길이)은 임시. 실제 리스크 허용치에 맞게 조정 필요. (국장 전환 후 세션 길이는 §5 참고 — 09:00~15:30 KST 기준으로 다시 계산 필요)
- ~~워커를 24/7 vs 하이브리드로 둘지~~ → **최종 결정됨 (§1.4): 24/7 상시 데몬.** crontab은 안 씀. 남은 건 실제로 `AGENT_SCHEDULER_ENABLED=true`로 켜고 `docker compose up -d worker`로 띄울지 — 이 서버는 `USE_MOCK_DATA=false` + 실제 `OPENAI_API_KEY`가 설정돼 있어서 켜는 순간부터 실제 OpenAI 호출 비용이 발생한다 (LLM_DAILY_CALL_LIMIT=5, LLM_DAILY_COST_LIMIT_USD=2, LLM_MONTHLY_COST_LIMIT_USD=30 가드는 있음). DRY_RUN=true라 실제 주문은 안 나감. 사용자 확인 후 진행.
- ~~운영 DB 마이그레이션 방식~~ → **완료 (2026-08-11).** 이 서버의 Postgres는 세션 루프 기능 이전부터 있던 DB라 `create_all`이 `workflow_runs.session_id`/`cycle_index` 컬럼을 추가해주지 않아서, 배포 직후 `/workflows`가 500 에러를 냈다 (라이브 회귀). 사용자 확인 후 `ALTER TABLE workflow_runs ADD COLUMN session_id INTEGER REFERENCES agent_sessions(id), ADD COLUMN cycle_index INTEGER`(+ 인덱스)로 수동 마이그레이션 적용, 기존 데이터 손실 없이 복구 확인. `run_session()`을 실제 Postgres에 대고 mock 모드로 end-to-end 실행해서 세션/사이클/12개 노드 스텝이 전부 정상 기록되는 것까지 검증함 (테스트 데이터는 정리함).

## 5. 국장 전환 + 통화/섹터 개편 (2026-08-11 추가)

시장을 해외장(America/New_York)에서 국내장(KRX, Asia/Seoul)으로, 종목 필터를 단일 섹터(`반도체`)에서 멀티섹터 화이트리스트로, 통화를 USD에서 KRW로 바꾸는 대규모 개편이 별도로 진행된다. 이 문서(LangGraph 세션 루프)와는 독립적인 변경이며, 상세 계획은 `docs/plans/domestic-krw-conversion.md`에 있다.
