import { useEffect, useState } from "react";
import { api, LLMBudget, LLMUsage } from "../api/client";
import { StatCard } from "../components/StatCard";

export function LLMUsagePage() {
  const [usage, setUsage] = useState<LLMUsage[]>([]);
  const [budget, setBudget] = useState<LLMBudget | null>(null);
  const [purposeFilter, setPurposeFilter] = useState("");
  const [symbolFilter, setSymbolFilter] = useState("");
  const [successFilter, setSuccessFilter] = useState("all");
  const [isRefreshing, setIsRefreshing] = useState(false);

  const refreshUsage = () => {
    if (isRefreshing) return;
    setIsRefreshing(true);
    Promise.all([api.getLLMUsage(), api.getLLMBudget()])
      .then(([rows, currentBudget]) => {
        setUsage(rows);
        setBudget(currentBudget);
      })
      .catch(() => setUsage([]))
      .finally(() => setIsRefreshing(false));
  };

  useEffect(() => {
    refreshUsage();
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
          <p className="eyebrow">비용 가드레일</p>
          <h2>LLM 사용량</h2>
        </div>
        <button className="secondary-button" disabled={isRefreshing} onClick={refreshUsage} type="button">
          {isRefreshing ? "새로고침 중..." : "새로고침"}
        </button>
      </header>
      <div className="stat-grid">
        <StatCard label="오늘 호출" value={`${budget?.today_calls ?? 0}`} />
        <StatCard label="오늘 토큰" value={`${budget?.today_total_tokens ?? 0}`} />
        <StatCard label="일일 비용 잔여" value={`$${budget?.daily_cost_remaining_usd.toFixed(4) ?? "0.0000"}`} />
        <StatCard label="월 비용 잔여" value={`$${budget?.monthly_cost_remaining_usd.toFixed(4) ?? "0.0000"}`} />
      </div>
      <div className="filter-row">
        <label>
          목적
          <select value={purposeFilter} onChange={(event) => setPurposeFilter(event.target.value)}>
            <option value="">전체</option>
            <option value="decision">판단</option>
            <option value="evaluation">평가</option>
            <option value="reflection">회고</option>
            <option value="summary">요약</option>
            <option value="test">테스트</option>
          </select>
        </label>
        <label>
          종목
          <input value={symbolFilter} onChange={(event) => setSymbolFilter(event.target.value)} placeholder="NVDA" />
        </label>
        <label>
          상태
          <select value={successFilter} onChange={(event) => setSuccessFilter(event.target.value)}>
            <option value="all">전체</option>
            <option value="success">성공</option>
            <option value="failed">실패</option>
          </select>
        </label>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>시각</th>
              <th>목적</th>
              <th>모델</th>
              <th>종목</th>
              <th>프롬프트</th>
              <th>응답</th>
              <th>합계</th>
              <th>비용</th>
              <th>지연</th>
              <th>성공</th>
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
                <td>{row.success ? "예" : "아니오"}</td>
              </tr>
            ))}
            {!filteredUsage.length ? (
              <tr>
                <td colSpan={10}>현재 필터와 일치하는 LLM 사용 기록이 없습니다.</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}
