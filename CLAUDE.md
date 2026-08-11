# CLAUDE.md

이 저장소의 공통 규칙(안전 원칙, 아키텍처 원칙, 실행/테스트 명령, 멀티 에이전트 협업 규칙)은 [`AGENTS.md`](./AGENTS.md)에 있다. 먼저 그 문서를 읽는다. Codex를 포함한 다른 에이전트도 같은 문서를 기준으로 움직이므로, 이 저장소에서는 `AGENTS.md`가 항상 우선한다.

## 진행 중인 작업

- `docs/plans/continuous-session-loop.md`: LangGraph 그래프를 선형 DAG에서 연속 다회차 세션 루프로 재설계하는 계획. Claude와 Codex의 파일 소유권 경계가 표로 정리되어 있다.
  - **Phase 0(Claude 담당 계약 파일)은 완료됨** — `models.py`, `config.py`, `agent_graph_service.py`(`run_session()`/`session_graph`), `redis_runtime_service.py`, `workflow_service.py`, `utils/market_hours.py`. 검증까지 끝났다 (문서 §0.1 참고).
  - 다음은 Codex 담당 파일(§2의 표) 진행 여부 확인, 끝나면 "통합 단계" 절 진행.
