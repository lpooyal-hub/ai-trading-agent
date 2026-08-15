import { useEffect, useState } from "react";
import { api, MemoryGroupStat, MemorySummary } from "../api/client";
import { StatCard } from "../components/StatCard";
import { actionLabel, symbolLabel } from "../utils/labels";

function formatReward(value: number) {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(4)}`;
}

function MemoryStatsTable({ title, rows, formatKey = (value: string) => value }: { title: string; rows: MemoryGroupStat[]; formatKey?: (value: string) => string }) {
  return (
    <div className="memory-table-block">
      <h3>{title}</h3>
      <div className="table-wrap compact-table">
        <table>
          <thead>
            <tr>
              <th>항목</th>
              <th>건수</th>
              <th>승률</th>
              <th>평균 보상</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={`${title}-${row.key}`}>
                <td>{formatKey(row.key)}</td>
                <td>{row.count}</td>
                <td>{row.win_rate_percent.toFixed(2)}%</td>
                <td>{formatReward(row.average_reward_score)}</td>
              </tr>
            ))}
            {!rows.length ? (
              <tr>
                <td colSpan={4}>아직 메모리 통계가 없습니다.</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function MemoryPage() {
  const [summary, setSummary] = useState<MemorySummary | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const refresh = () => {
    if (isRefreshing) return;
    setIsRefreshing(true);
    setMessage(null);
    api.getMemorySummary()
      .then(setSummary)
      .catch((error) => {
        setSummary(null);
        setMessage(error instanceof Error ? error.message : "메모리 요약을 불러올 수 없습니다.");
      })
      .finally(() => setIsRefreshing(false));
  };

  useEffect(() => {
    refresh();
  }, []);

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">메모리 에이전트</p>
          <h2>전략 메모리</h2>
        </div>
        <button className="primary-button" disabled={isRefreshing} onClick={refresh} type="button">
          {isRefreshing ? "새로고침 중..." : "새로고침"}
        </button>
      </header>
      {message ? <div className="notice">{message}</div> : null}
      <div className="stat-grid">
        <StatCard
          label="전략 근거 / 운영 저널"
          value={`${summary?.strategy_entry_count ?? 0} / ${summary?.lookback_journal_entries ?? 0}`}
        />
        <StatCard label="평가 완료" value={`${summary?.evaluated_entry_count ?? 0}`} />
        <StatCard label="승률" value={`${summary ? summary.win_rate_percent.toFixed(2) : "0.00"}%`} />
        <StatCard label="평균 보상" value={formatReward(summary?.average_reward_score ?? 0)} />
      </div>
      <div className="detail-grid">
        <MemoryStatsTable title="판단별 메모리" rows={summary?.action_stats ?? []} formatKey={actionLabel} />
        <MemoryStatsTable title="모델별 메모리" rows={summary?.model_stats ?? []} />
      </div>
      <MemoryStatsTable title="프롬프트별 메모리" rows={summary?.prompt_stats ?? []} />
      <MemoryStatsTable title="종목별 메모리" rows={summary?.symbol_stats ?? []} formatKey={symbolLabel} />
      <div className="detail-grid">
        <section>
          <h3>반복 실수</h3>
          <ul>
            {(summary?.common_mistakes ?? []).map((item) => (
              <li key={item.mistake_type}>{item.mistake_type}: {item.count}</li>
            ))}
            {!(summary?.common_mistakes ?? []).length ? <li>아직 반복 실수가 기록되지 않았습니다.</li> : null}
          </ul>
        </section>
        <section>
          <h3>메모리 노트</h3>
          <ul>
            {(summary?.memory_notes ?? []).map((note) => <li key={note}>{note}</li>)}
          </ul>
        </section>
      </div>
      <section>
        <h3>최근 교훈</h3>
        <div className="journal-grid">
          {(summary?.recent_lessons ?? []).map((lesson) => (
            <article className="journal-card" key={lesson.journal_id}>
              <p className="eyebrow">저널 #{lesson.journal_id}</p>
              <h3>{symbolLabel(lesson.symbol)} {actionLabel(lesson.action)}</h3>
              <p className="helper-text">보상 {formatReward(lesson.reward_score)}</p>
              <p>{lesson.lesson}</p>
            </article>
          ))}
        </div>
        {!(summary?.recent_lessons ?? []).length ? <div className="notice">아직 명시적으로 기록된 교훈이 없습니다.</div> : null}
      </section>
      <section>
        <h3>데이터 공백</h3>
        <ul>
          {(summary?.data_gaps ?? []).map((gap) => <li key={gap}>{gap}</li>)}
        </ul>
      </section>
    </section>
  );
}
