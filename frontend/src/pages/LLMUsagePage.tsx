import { useEffect, useState } from "react";
import { api, LLMBudget, LLMUsage } from "../api/client";
import { StatCard } from "../components/StatCard";

export function LLMUsagePage() {
  const [usage, setUsage] = useState<LLMUsage[]>([]);
  const [budget, setBudget] = useState<LLMBudget | null>(null);
  const [purposeFilter, setPurposeFilter] = useState("");
  const [symbolFilter, setSymbolFilter] = useState("");
  const [successFilter, setSuccessFilter] = useState("all");

  useEffect(() => {
    Promise.all([api.getLLMUsage(), api.getLLMBudget()])
      .then(([rows, currentBudget]) => {
        setUsage(rows);
        setBudget(currentBudget);
      })
      .catch(() => setUsage([]));
  }, []);

  const filteredUsage = usage.filter((row) => {
    const purposeMatches = purposeFilter ? row.purpose === purposeFilter : true;
    const symbolMatches = symbolFilter ? row.symbol === symbolFilter.toUpperCase() : true;
    const successMatches =
      successFilter === "all" ? true : row.success === (successFilter === "success");
    return purposeMatches && symbolMatches && successMatches;
  });

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">Cost Guardrails</p>
          <h2>LLM Usage</h2>
        </div>
      </header>
      <div className="stat-grid">
        <StatCard label="Today's Calls" value={`${budget?.today_calls ?? 0}`} />
        <StatCard label="Today's Tokens" value={`${budget?.today_total_tokens ?? 0}`} />
        <StatCard label="Daily Cost Left" value={`$${budget?.daily_cost_remaining_usd.toFixed(4) ?? "0.0000"}`} />
        <StatCard label="Monthly Cost Left" value={`$${budget?.monthly_cost_remaining_usd.toFixed(4) ?? "0.0000"}`} />
      </div>
      <div className="filter-row">
        <label>
          Purpose
          <select value={purposeFilter} onChange={(event) => setPurposeFilter(event.target.value)}>
            <option value="">All</option>
            <option value="decision">Decision</option>
            <option value="evaluation">Evaluation</option>
            <option value="reflection">Reflection</option>
            <option value="summary">Summary</option>
            <option value="test">Test</option>
          </select>
        </label>
        <label>
          Symbol
          <input value={symbolFilter} onChange={(event) => setSymbolFilter(event.target.value)} placeholder="NVDA" />
        </label>
        <label>
          Status
          <select value={successFilter} onChange={(event) => setSuccessFilter(event.target.value)}>
            <option value="all">All</option>
            <option value="success">Success</option>
            <option value="failed">Failed</option>
          </select>
        </label>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Time</th>
              <th>Purpose</th>
              <th>Model</th>
              <th>Symbol</th>
              <th>Prompt</th>
              <th>Completion</th>
              <th>Total</th>
              <th>Cost</th>
              <th>Latency</th>
              <th>Success</th>
            </tr>
          </thead>
          <tbody>
            {filteredUsage.map((row) => (
              <tr key={row.id}>
                <td>{new Date(row.created_at).toLocaleString()}</td>
                <td>{row.purpose}</td>
                <td>{row.model}</td>
                <td>{row.symbol ?? "-"}</td>
                <td>{row.prompt_tokens}</td>
                <td>{row.completion_tokens}</td>
                <td>{row.total_tokens}</td>
                <td>${row.estimated_cost_usd.toFixed(4)}</td>
                <td>{row.latency_ms}ms</td>
                <td>{row.success ? "Yes" : "No"}</td>
              </tr>
            ))}
            {!filteredUsage.length ? (
              <tr>
                <td colSpan={10}>No LLM usage rows match the current filters.</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}
