import { useEffect, useMemo, useState } from "react";
import { AgentSession, AgentSessionDetail, api } from "../api/client";
import { StatCard } from "../components/StatCard";
import { statusLabel } from "../utils/labels";
import { WorkflowRunSummary } from "./WorkflowsPage";


const SESSION_STATUS_LABELS: Record<string, string> = {
  RUNNING: "진행 중",
  SUCCEEDED: "성공",
  FAILED: "실패",
  STOPPED: "중지됨",
};


function sessionStatusLabel(status: string) {
  return SESSION_STATUS_LABELS[status] ?? statusLabel(status);
}


function formatDate(value: string | null) {
  if (!value) return "-";
  return new Date(value).toLocaleString();
}


function stopReasonLabel(reason: string | null) {
  if (!reason) return "정지 사유 없음";
  if (reason === "Admin requested the session to stop.") return "관리자 요청으로 세션을 중지했습니다.";
  if (reason === "Market is not in regular session.") return "정규장이 종료되어 세션을 중지했습니다.";
  if (reason.startsWith("Session reached its max cycle count")) return "세션의 최대 사이클 수에 도달했습니다.";
  if (reason.startsWith("Session reached its max duration")) return "세션의 최대 실행 시간에 도달했습니다.";
  if (reason.startsWith("LLM budget exceeded")) return `LLM 예산 가드가 세션을 중지했습니다: ${reason.split(": ").slice(1).join(": ")}`;
  if (reason.startsWith("Daily trade limit reached")) return "일일 거래 횟수 상한에 도달했습니다.";
  return reason;
}


function statusTone(status: string) {
  if (status === "SUCCEEDED") return "positive";
  if (status === "FAILED") return "negative";
  return "neutral";
}


export function SessionsPage() {
  const [sessions, setSessions] = useState<AgentSession[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<number | null>(null);
  const [selectedSession, setSelectedSession] = useState<AgentSessionDetail | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isStopping, setIsStopping] = useState(false);

  const stats = useMemo(() => ({
    running: sessions.filter((session) => session.status === "RUNNING").length,
    succeeded: sessions.filter((session) => session.status === "SUCCEEDED").length,
    stopped: sessions.filter((session) => session.status === "STOPPED").length,
    failed: sessions.filter((session) => session.status === "FAILED").length,
  }), [sessions]);

  const refresh = () => {
    if (isRefreshing) return;
    setIsRefreshing(true);
    setMessage(null);
    api.getAgentSessions()
      .then((rows) => {
        setSessions(rows);
        const selectedStillExists = rows.some((session) => session.id === selectedSessionId);
        const targetId = selectedStillExists ? selectedSessionId : rows[0]?.id ?? null;
        setSelectedSessionId(targetId);
        if (targetId === null) {
          setSelectedSession(null);
          return null;
        }
        return api.getAgentSession(targetId).then(setSelectedSession);
      })
      .catch((error) => {
        setSessions([]);
        setSelectedSession(null);
        setMessage(error instanceof Error ? error.message : "세션 기록을 불러올 수 없습니다.");
      })
      .finally(() => setIsRefreshing(false));
  };

  const selectSession = (sessionId: number) => {
    setSelectedSessionId(sessionId);
    setMessage(null);
    api.getAgentSession(sessionId)
      .then(setSelectedSession)
      .catch((error) => setMessage(error instanceof Error ? error.message : "세션 상세를 불러올 수 없습니다."));
  };

  const requestStop = () => {
    if (!selectedSession || selectedSession.status !== "RUNNING" || selectedSession.stop_requested || isStopping) return;
    if (!window.confirm(`Session #${selectedSession.id}에 중지 요청을 보낼까요?`)) return;

    const sessionId = selectedSession.id;
    setIsStopping(true);
    setMessage(null);
    api.stopAgentSession(sessionId)
      .then(() => Promise.all([api.getAgentSession(sessionId), api.getAgentSessions()]))
      .then(([detail, rows]) => {
        setSelectedSession(detail);
        setSessions(rows);
        setMessage(`Session #${sessionId}에 중지 요청을 보냈습니다. 현재 사이클 종료 시 반영됩니다.`);
      })
      .catch((error) => setMessage(error instanceof Error ? error.message : "세션 중지 요청에 실패했습니다."))
      .finally(() => setIsStopping(false));
  };

  useEffect(() => {
    refresh();
  }, []);

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">Continuous Agent Loop</p>
          <h2>에이전트 세션</h2>
        </div>
        <div className="button-row">
          <button
            className="secondary-button"
            disabled={!selectedSession || selectedSession.status !== "RUNNING" || selectedSession.stop_requested || isStopping}
            onClick={requestStop}
            type="button"
          >
            {isStopping ? "중지 요청 중..." : selectedSession?.stop_requested ? "중지 요청됨" : "세션 중지"}
          </button>
          <button className="primary-button" disabled={isRefreshing} onClick={refresh} type="button">
            {isRefreshing ? "새로고침 중..." : "새로고침"}
          </button>
        </div>
      </header>

      {message ? <div className="notice">{message}</div> : null}

      <div className="stat-grid">
        <StatCard label="전체 세션" value={`${sessions.length}`} />
        <StatCard label="진행 중" value={`${stats.running}`} />
        <StatCard label="성공 / 중지" value={`${stats.succeeded} / ${stats.stopped}`} />
        <StatCard label="실패" value={`${stats.failed}`} />
      </div>

      <div className="workflow-layout">
        <section className="workflow-run-list">
          <h3>최근 세션</h3>
          <div className="table-wrap compact-table">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>상태</th>
                  <th>사이클</th>
                  <th>시작</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((session) => (
                  <tr
                    className={selectedSession?.id === session.id ? "selected-row" : ""}
                    key={session.id}
                    onClick={() => selectSession(session.id)}
                  >
                    <td>#{session.id}</td>
                    <td>{sessionStatusLabel(session.status)}</td>
                    <td>{session.cycle_count}/{session.max_cycles}</td>
                    <td>{formatDate(session.started_at)}</td>
                  </tr>
                ))}
                {!sessions.length ? (
                  <tr>
                    <td colSpan={4}>아직 세션 기록이 없습니다.</td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </section>

        <section className="workflow-detail">
          <div className="workflow-detail-header">
            <div>
              <p className="eyebrow">{selectedSession?.trigger_source ?? "session"}</p>
              <h3>{selectedSession ? `Session #${selectedSession.id}` : "선택된 세션 없음"}</h3>
            </div>
            {selectedSession ? (
              <span className={`status-pill ${statusTone(selectedSession.status)}`}>
                {sessionStatusLabel(selectedSession.status)}
              </span>
            ) : null}
          </div>

          {selectedSession ? (
            <>
              <dl className="workflow-meta">
                <div>
                  <dt>시작</dt>
                  <dd>{formatDate(selectedSession.started_at)}</dd>
                </div>
                <div>
                  <dt>종료</dt>
                  <dd>{formatDate(selectedSession.finished_at)}</dd>
                </div>
                <div>
                  <dt>사이클</dt>
                  <dd>{selectedSession.cycle_count}/{selectedSession.max_cycles}</dd>
                </div>
                <div>
                  <dt>중지 요청</dt>
                  <dd>{selectedSession.stop_requested ? "요청됨" : "없음"}</dd>
                </div>
              </dl>
              <div className={selectedSession.stop_reason ? "warning-panel" : "notice"}>
                {stopReasonLabel(selectedSession.stop_reason)}
              </div>

              {selectedSession.runs.map((run) => (
                <article className="workflow-definition" key={run.id}>
                  <div className="workflow-detail-header">
                    <div>
                      <p className="eyebrow">Cycle #{run.cycle_index + 1}</p>
                      <h3>Workflow Run #{run.id}</h3>
                    </div>
                    <span className={`status-pill ${statusTone(run.status)}`}>{statusLabel(run.status)}</span>
                  </div>
                  <p className="helper-text">
                    {formatDate(run.started_at)} · 판단 {run.decision_id ? `#${run.decision_id}` : "없음"}
                  </p>
                  <WorkflowRunSummary run={run} />
                  {run.error_message ? <div className="warning-panel">{run.error_message}</div> : null}
                </article>
              ))}
              {!selectedSession.runs.length ? <div className="notice">아직 시작된 사이클이 없습니다.</div> : null}
            </>
          ) : (
            <div className="notice">세션을 선택하면 사이클별 워크플로 요약이 표시됩니다.</div>
          )}
        </section>
      </div>
    </section>
  );
}
