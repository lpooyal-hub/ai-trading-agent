import { useState } from "react";
import { Layout } from "./components/Layout";
import { DashboardPage } from "./pages/DashboardPage";
import { BrokerPage } from "./pages/BrokerPage";
import { DecisionDetailPage } from "./pages/DecisionDetailPage";
import { DecisionsPage } from "./pages/DecisionsPage";
import { EvaluationsPage } from "./pages/EvaluationsPage";
import { JournalPage } from "./pages/JournalPage";
import { LLMUsagePage } from "./pages/LLMUsagePage";
import { MarketPage } from "./pages/MarketPage";
import { MemoryPage } from "./pages/MemoryPage";
import { OrdersPage } from "./pages/OrdersPage";
import { PortfolioPage } from "./pages/PortfolioPage";
import { SettingsPage } from "./pages/SettingsPage";
import { WorkflowsPage } from "./pages/WorkflowsPage";

const navItems = [
  { id: "dashboard", label: "대시보드" },
  { id: "decisions", label: "판단 기록" },
  { id: "decision-detail", label: "판단 상세" },
  { id: "orders", label: "주문 기록" },
  { id: "broker", label: "브로커" },
  { id: "portfolio", label: "포트폴리오" },
  { id: "market", label: "시장 데이터" },
  { id: "evaluations", label: "성과 평가" },
  { id: "journal", label: "저널" },
  { id: "memory", label: "메모리" },
  { id: "workflows", label: "실행 흐름" },
  { id: "llm-usage", label: "LLM 사용량" },
  { id: "settings", label: "설정" },
];

export default function App() {
  const [activePage, setActivePage] = useState("dashboard");
  const [selectedDecisionId, setSelectedDecisionId] = useState<number | null>(null);

  const selectDecision = (id: number) => {
    setSelectedDecisionId(id);
    setActivePage("decision-detail");
  };

  return (
    <Layout activePage={activePage} navItems={navItems} onNavigate={setActivePage}>
      {activePage === "dashboard" ? <DashboardPage onSelectDecision={selectDecision} /> : null}
      {activePage === "decisions" ? <DecisionsPage onSelectDecision={selectDecision} /> : null}
      {activePage === "decision-detail" ? <DecisionDetailPage decisionId={selectedDecisionId} /> : null}
      {activePage === "orders" ? <OrdersPage /> : null}
      {activePage === "broker" ? <BrokerPage /> : null}
      {activePage === "portfolio" ? <PortfolioPage /> : null}
      {activePage === "market" ? <MarketPage /> : null}
      {activePage === "evaluations" ? <EvaluationsPage /> : null}
      {activePage === "journal" ? <JournalPage /> : null}
      {activePage === "memory" ? <MemoryPage /> : null}
      {activePage === "workflows" ? <WorkflowsPage /> : null}
      {activePage === "llm-usage" ? <LLMUsagePage /> : null}
      {activePage === "settings" ? <SettingsPage /> : null}
    </Layout>
  );
}
