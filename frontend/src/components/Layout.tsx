import { ReactNode } from "react";
import { DryRunBanner } from "./DryRunBanner";

type NavItem = {
  id: string;
  label: string;
};

type LayoutProps = {
  activePage: string;
  navItems: NavItem[];
  onNavigate: (page: string) => void;
  children: ReactNode;
};

export function Layout({ activePage, navItems, onNavigate, children }: LayoutProps) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div>
          <p className="eyebrow">토스증권 Open API</p>
          <h1>AI 트레이딩 에이전트</h1>
        </div>
        <nav className="nav-list">
          {navItems.map((item) => (
            <button
              className={activePage === item.id ? "nav-item active" : "nav-item"}
              key={item.id}
              onClick={() => onNavigate(item.id)}
              type="button"
            >
              {item.label}
            </button>
          ))}
        </nav>
      </aside>
      <section className="content">
        <DryRunBanner />
        {children}
      </section>
    </div>
  );
}
