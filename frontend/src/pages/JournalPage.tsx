import { useEffect, useState } from "react";
import { api, TradeJournalEntry } from "../api/client";
import { StatCard } from "../components/StatCard";

function formatDate(value: string) {
  return new Date(value).toLocaleString();
}

function formatReward(value: number) {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(4)}`;
}

function outcomeTone(outcome: string) {
  if (outcome === "PROFITABLE") return "positive";
  if (outcome === "UNPROFITABLE") return "negative";
  return "neutral";
}

export function JournalPage() {
  const [entries, setEntries] = useState<TradeJournalEntry[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const refresh = () => {
    setIsRefreshing(true);
    setMessage(null);
    api.getJournalEntries()
      .then(setEntries)
      .catch((error) => {
        setEntries([]);
        setMessage(error instanceof Error ? error.message : "Journal entries are not available.");
      })
      .finally(() => setIsRefreshing(false));
  };

  useEffect(() => {
    refresh();
  }, []);

  const reviewedCount = entries.filter((entry) => entry.outcome_label !== "PENDING_REVIEW").length;
  const averageReward = entries.length
    ? entries.reduce((sum, entry) => sum + entry.reward_score, 0) / entries.length
    : 0;
  const positiveCount = entries.filter((entry) => entry.reward_score > 0).length;

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">Agent Memory</p>
          <h2>Trade Journal</h2>
        </div>
        <button className="primary-button" disabled={isRefreshing} onClick={refresh} type="button">
          {isRefreshing ? "Refreshing..." : "Refresh"}
        </button>
      </header>
      {message ? <div className="notice">{message}</div> : null}
      <div className="stat-grid">
        <StatCard label="Entries" value={`${entries.length}`} />
        <StatCard label="Reviewed" value={`${reviewedCount}`} detail="linked to outcome labels" />
        <StatCard label="Positive Reward" value={`${positiveCount}`} />
        <StatCard label="Avg Reward" value={formatReward(averageReward)} />
      </div>
      <div className="journal-grid">
        {entries.map((entry) => (
          <article className="journal-card" key={entry.id}>
            <div className="journal-card-header">
              <div>
                <p className="eyebrow">Journal #{entry.id}</p>
                <h3>{entry.symbol} {entry.action}</h3>
              </div>
              <span className={`status-pill ${outcomeTone(entry.outcome_label)}`}>{entry.outcome_label}</span>
            </div>
            <dl className="journal-meta">
              <div>
                <dt>Decision</dt>
                <dd>#{entry.decision_id}</dd>
              </div>
              <div>
                <dt>Order</dt>
                <dd>{entry.order_id ? `#${entry.order_id}` : "-"}</dd>
              </div>
              <div>
                <dt>Evaluation</dt>
                <dd>{entry.evaluation_id ? `#${entry.evaluation_id}` : "-"}</dd>
              </div>
              <div>
                <dt>Reward</dt>
                <dd>{formatReward(entry.reward_score)}</dd>
              </div>
            </dl>
            <p className="helper-text">{formatDate(entry.created_at)}</p>
            <section>
              <h4>Self Feedback</h4>
              <p>{entry.agent_self_feedback}</p>
            </section>
            {entry.lesson ? (
              <section>
                <h4>Lesson</h4>
                <p>{entry.lesson}</p>
              </section>
            ) : null}
            <section>
              <h4>Thesis Snapshot</h4>
              <p>{entry.thesis_snapshot}</p>
            </section>
            {entry.strategy_tags_json.length ? (
              <div className="tag-row">
                {entry.strategy_tags_json.map((tag) => <span key={`${entry.id}-${tag}`}>{tag}</span>)}
              </div>
            ) : null}
          </article>
        ))}
      </div>
      {!entries.length && !message ? <div className="notice">No journal entries yet. Create one from a decision detail page.</div> : null}
    </section>
  );
}
