import { useState } from "react";
import { Layout } from "./components/Layout";
import { DashboardPage } from "./pages/DashboardPage";
import { DecisionDetailPage } from "./pages/DecisionDetailPage";
import { DecisionsPage } from "./pages/DecisionsPage";
import { EvaluationsPage } from "./pages/EvaluationsPage";
import { LLMUsagePage } from "./pages/LLMUsagePage";
import { MarketPage } from "./pages/MarketPage";
import { OrdersPage } from "./pages/OrdersPage";
import { PortfolioPage } from "./pages/PortfolioPage";
import { SettingsPage } from "./pages/SettingsPage";

const navItems = [
  { id: "dashboard", label: "Dashboard" },
  { id: "decisions", label: "Decisions" },
  { id: "decision-detail", label: "Decision Detail" },
  { id: "orders", label: "Orders" },
  { id: "portfolio", label: "Portfolio" },
  { id: "market", label: "Market" },
  { id: "evaluations", label: "Evaluations" },
  { id: "llm-usage", label: "LLM Usage" },
  { id: "settings", label: "Settings" },
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
      {activePage === "portfolio" ? <PortfolioPage /> : null}
      {activePage === "market" ? <MarketPage /> : null}
      {activePage === "evaluations" ? <EvaluationsPage /> : null}
      {activePage === "llm-usage" ? <LLMUsagePage /> : null}
      {activePage === "settings" ? <SettingsPage /> : null}
    </Layout>
  );
}
