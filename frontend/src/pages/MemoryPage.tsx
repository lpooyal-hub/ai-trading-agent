import { useEffect, useState } from "react";
import { api, MemoryGroupStat, MemorySummary } from "../api/client";
import { StatCard } from "../components/StatCard";

function formatReward(value: number) {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(4)}`;
}

function MemoryStatsTable({ title, rows }: { title: string; rows: MemoryGroupStat[] }) {
  return (
    <div className="memory-table-block">
      <h3>{title}</h3>
      <div className="table-wrap compact-table">
        <table>
          <thead>
            <tr>
              <th>Key</th>
              <th>Count</th>
              <th>Win Rate</th>
              <th>Avg Reward</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={`${title}-${row.key}`}>
                <td>{row.key}</td>
                <td>{row.count}</td>
                <td>{row.win_rate_percent.toFixed(2)}%</td>
                <td>{formatReward(row.average_reward_score)}</td>
              </tr>
            ))}
            {!rows.length ? (
              <tr>
                <td colSpan={4}>No memory stats yet.</td>
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
        setMessage(error instanceof Error ? error.message : "Memory summary is not available.");
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
          <p className="eyebrow">Memory Agent</p>
          <h2>Strategy Memory</h2>
        </div>
        <button className="primary-button" disabled={isRefreshing} onClick={refresh} type="button">
          {isRefreshing ? "Refreshing..." : "Refresh"}
        </button>
      </header>
      {message ? <div className="notice">{message}</div> : null}
      <div className="stat-grid">
        <StatCard label="Journal Lookback" value={`${summary?.lookback_journal_entries ?? 0}`} />
        <StatCard label="Evaluated" value={`${summary?.evaluated_entry_count ?? 0}`} />
        <StatCard label="Win Rate" value={`${summary ? summary.win_rate_percent.toFixed(2) : "0.00"}%`} />
        <StatCard label="Avg Reward" value={formatReward(summary?.average_reward_score ?? 0)} />
      </div>
      <div className="detail-grid">
        <MemoryStatsTable title="Action Memory" rows={summary?.action_stats ?? []} />
        <MemoryStatsTable title="Model Memory" rows={summary?.model_stats ?? []} />
      </div>
      <MemoryStatsTable title="Symbol Memory" rows={summary?.symbol_stats ?? []} />
      <div className="detail-grid">
        <section>
          <h3>Common Mistakes</h3>
          <ul>
            {(summary?.common_mistakes ?? []).map((item) => (
              <li key={item.mistake_type}>{item.mistake_type}: {item.count}</li>
            ))}
            {!(summary?.common_mistakes ?? []).length ? <li>No repeated mistakes tracked yet.</li> : null}
          </ul>
        </section>
        <section>
          <h3>Memory Notes</h3>
          <ul>
            {(summary?.memory_notes ?? []).map((note) => <li key={note}>{note}</li>)}
          </ul>
        </section>
      </div>
      <section>
        <h3>Recent Lessons</h3>
        <div className="journal-grid">
          {(summary?.recent_lessons ?? []).map((lesson) => (
            <article className="journal-card" key={lesson.journal_id}>
              <p className="eyebrow">Journal #{lesson.journal_id}</p>
              <h3>{lesson.symbol} {lesson.action}</h3>
              <p className="helper-text">Reward {formatReward(lesson.reward_score)}</p>
              <p>{lesson.lesson}</p>
            </article>
          ))}
        </div>
        {!(summary?.recent_lessons ?? []).length ? <div className="notice">No explicit lessons recorded yet.</div> : null}
      </section>
      <section>
        <h3>Data Gaps</h3>
        <ul>
          {(summary?.data_gaps ?? []).map((gap) => <li key={gap}>{gap}</li>)}
        </ul>
      </section>
    </section>
  );
}
