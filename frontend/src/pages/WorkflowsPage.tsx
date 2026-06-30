import { useEffect, useMemo, useState } from "react";
import { api, WorkflowDefinition, WorkflowRun, WorkflowStep } from "../api/client";
import { StatCard } from "../components/StatCard";
import { statusLabel } from "../utils/labels";

const STEP_LABELS: Record<string, string> = {
  runtime_lock: "런타임 락",
  market_agent: "시장 에이전트",
  news_agent: "뉴스 에이전트",
  risk_agent: "리스크 에이전트",
  memory_agent: "메모리 에이전트",
  decision_agent: "판단 에이전트",
  logger_agent: "로거 에이전트",
  order_agent: "주문 에이전트",
  evaluation_agent: "평가 에이전트",
  journal_agent: "저널 에이전트",
};

function stepLabel(stepName: string) {
  return STEP_LABELS[stepName] ?? stepName;
}

function formatDate(value: string | null) {
  if (!value) return "-";
  return new Date(value).toLocaleString();
}

function durationMs(startedAt: string, finishedAt: string | null) {
  if (!finishedAt) return null;
  const duration = new Date(finishedAt).getTime() - new Date(startedAt).getTime();
  return Number.isFinite(duration) ? Math.max(duration, 0) : null;
}

function formatDuration(startedAt: string, finishedAt: string | null) {
  const duration = durationMs(startedAt, finishedAt);
  if (duration === null) return "진행 중";
  if (duration < 1000) return `${duration}ms`;
  return `${(duration / 1000).toFixed(1)}s`;
}

function compactJson(value: Record<string, unknown>) {
  const entries = Object.entries(value).filter(([, item]) => item !== null && item !== undefined && item !== "");
  if (!entries.length) return "-";
  return entries
    .slice(0, 5)
    .map(([key, item]) => `${key}: ${Array.isArray(item) ? item.join(", ") : String(item)}`)
    .join(" · ");
}

function WorkflowStepTimeline({ steps }: { steps: WorkflowStep[] }) {
  return (
    <div className="workflow-timeline">
      {steps.map((step) => (
        <article className={`workflow-step ${step.status.toLowerCase()}`} key={step.id}>
          <div className="workflow-step-marker" />
          <div>
            <div className="workflow-step-header">
              <h3>{stepLabel(step.step_name)}</h3>
              <span className={`status-pill ${step.status === "SUCCEEDED" ? "positive" : step.status === "FAILED" ? "negative" : "neutral"}`}>
                {statusLabel(step.status)}
              </span>
            </div>
            <p className="helper-text">{formatDate(step.started_at)} · {formatDuration(step.started_at, step.finished_at)}</p>
            <p>{compactJson(step.output_json)}</p>
            {step.error_message ? <p className="workflow-error">{step.error_message}</p> : null}
          </div>
        </article>
      ))}
      {!steps.length ? <div className="notice">아직 기록된 단계가 없습니다.</div> : null}
    </div>
  );
}

export function WorkflowsPage() {
  const [runs, setRuns] = useState<WorkflowRun[]>([]);
  const [definition, setDefinition] = useState<WorkflowDefinition | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [selectedRun, setSelectedRun] = useState<WorkflowRun | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const latestRun = runs[0] ?? null;
  const visibleRun = selectedRun ?? latestRun;

  const stats = useMemo(() => {
    const succeeded = runs.filter((run) => run.status === "SUCCEEDED").length;
    const skipped = runs.filter((run) => run.status === "SKIPPED").length;
    const failed = runs.filter((run) => run.status === "FAILED").length;
    const running = runs.filter((run) => run.status === "RUNNING").length;
    return { succeeded, skipped, failed, running };
  }, [runs]);

  const refresh = () => {
    if (isRefreshing) return;
    setIsRefreshing(true);
    setMessage(null);
    Promise.all([api.getWorkflowDefinition(), api.getWorkflowRuns()])
      .then(([workflowDefinition, rows]) => {
        setDefinition(workflowDefinition);
        setRuns(rows);
        const targetId = selectedRunId ?? rows[0]?.id ?? null;
        if (!targetId) {
          setSelectedRun(null);
          return null;
        }
        setSelectedRunId(targetId);
        return api.getWorkflowRun(targetId).then(setSelectedRun);
      })
      .catch((error) => {
        setDefinition(null);
        setRuns([]);
        setSelectedRun(null);
        setMessage(error instanceof Error ? error.message : "워크플로 기록을 불러올 수 없습니다.");
      })
      .finally(() => setIsRefreshing(false));
  };

  const selectRun = (runId: number) => {
    setSelectedRunId(runId);
    setMessage(null);
    api.getWorkflowRun(runId)
      .then(setSelectedRun)
      .catch((error) => setMessage(error instanceof Error ? error.message : "워크플로 상세를 불러올 수 없습니다."));
  };

  useEffect(() => {
    refresh();
  }, []);

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">Agentic Workflow</p>
          <h2>실행 흐름</h2>
        </div>
        <button className="secondary-button" disabled={isRefreshing} onClick={refresh} type="button">
          {isRefreshing ? "새로고침 중..." : "새로고침"}
        </button>
      </header>
      {message ? <div className="notice">{message}</div> : null}
      <div className="stat-grid">
        <StatCard label="최근 실행" value={latestRun ? `#${latestRun.id}` : "-"} detail={latestRun ? statusLabel(latestRun.status) : "기록 없음"} />
        <StatCard label="성공" value={`${stats.succeeded}`} />
        <StatCard label="스킵" value={`${stats.skipped}`} />
        <StatCard label="실패" value={`${stats.failed}`} detail={`${stats.running}개 진행 중`} />
      </div>
      <section className="workflow-definition">
        <div className="workflow-detail-header">
          <div>
            <p className="eyebrow">{definition?.workflow_name ?? "agent.run_once"}</p>
            <h3>정의된 Agent Graph</h3>
          </div>
          <span className="status-pill neutral">{definition?.nodes.length ?? 0} nodes</span>
        </div>
        <p className="helper-text">{definition?.description ?? "Workflow definition is not loaded yet."}</p>
        <div className="workflow-node-grid">
          {(definition?.nodes ?? []).map((node) => (
            <article className="workflow-node-card" key={node.id}>
              <div className="workflow-step-header">
                <h3>{stepLabel(node.id)}</h3>
                <span className="status-pill neutral">{node.uses_llm ? "LLM" : node.runtime}</span>
              </div>
              <p className="helper-text">{node.agent_type}</p>
              <p>{node.responsibility}</p>
            </article>
          ))}
        </div>
        {(definition?.side_loops ?? []).map((loop) => (
          <div className="workflow-side-loop" key={loop.name}>
            <strong>{loop.name}</strong>
            <span>{loop.description}</span>
          </div>
        ))}
      </section>
      <div className="workflow-layout">
        <section className="workflow-run-list">
          <h3>최근 Run</h3>
          <div className="table-wrap compact-table">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>상태</th>
                  <th>시작</th>
                  <th>판단</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr className={visibleRun?.id === run.id ? "selected-row" : ""} key={run.id} onClick={() => selectRun(run.id)}>
                    <td>#{run.id}</td>
                    <td>{statusLabel(run.status)}</td>
                    <td>{formatDate(run.started_at)}</td>
                    <td>{run.decision_id ? `#${run.decision_id}` : "-"}</td>
                  </tr>
                ))}
                {!runs.length ? (
                  <tr>
                    <td colSpan={4}>아직 워크플로 실행 기록이 없습니다.</td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </section>
        <section className="workflow-detail">
          <div className="workflow-detail-header">
            <div>
              <p className="eyebrow">{visibleRun?.workflow_name ?? "workflow"}</p>
              <h3>{visibleRun ? `Run #${visibleRun.id}` : "선택된 Run 없음"}</h3>
            </div>
            {visibleRun ? <span className="status-pill neutral">{statusLabel(visibleRun.status)}</span> : null}
          </div>
          {visibleRun ? (
            <>
              <dl className="workflow-meta">
                <div>
                  <dt>트리거</dt>
                  <dd>{visibleRun.trigger_source}</dd>
                </div>
                <div>
                  <dt>시작</dt>
                  <dd>{formatDate(visibleRun.started_at)}</dd>
                </div>
                <div>
                  <dt>종료</dt>
                  <dd>{formatDate(visibleRun.finished_at)}</dd>
                </div>
                <div>
                  <dt>판단 ID</dt>
                  <dd>{visibleRun.decision_id ? `#${visibleRun.decision_id}` : "-"}</dd>
                </div>
              </dl>
              {visibleRun.error_message ? <div className="warning-panel">{visibleRun.error_message}</div> : null}
              <WorkflowStepTimeline steps={visibleRun.steps} />
            </>
          ) : (
            <div className="notice">워크플로 실행 후 단계별 타임라인이 표시됩니다.</div>
          )}
        </section>
      </div>
    </section>
  );
}
