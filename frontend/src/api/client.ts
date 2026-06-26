const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export type PortfolioSummary = {
  bot_capital_limit_usd: number;
  invested_amount_usd: number;
  available_budget_usd: number;
  min_cash_reserve_usd: number;
  bot_position_count: number;
  legacy_position_count: number;
  protected_legacy_symbols: string[];
  bot_symbols: string[];
  unrealized_pnl_usd: number;
  unrealized_pnl_percent: number;
  dry_run: boolean;
  live_trading_enabled: boolean;
  use_mock_data: boolean;
  active_universe: string[];
};

export type AgentDecision = {
  id: number;
  created_at: string;
  symbol: string;
  sector: string;
  action: "BUY" | "SELL" | "HOLD";
  confidence: number;
  current_price: number;
  recommended_order_amount: number;
  thesis: string;
  risk_notes: string;
  input_snapshot_json: Record<string, unknown>;
  agent_response_json: Record<string, unknown>;
  status: string;
  rejection_reason: string | null;
  executed_order_id: number | null;
  dry_run: boolean;
  llm_model: string | null;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  estimated_llm_cost_usd: number;
};

export type TradeOrder = {
  id: number;
  decision_id: number;
  created_at: string;
  symbol: string;
  side: "BUY" | "SELL";
  quantity: number;
  price: number;
  order_amount: number;
  status: string;
  dry_run: boolean;
  reason: string;
};

export type BotPosition = {
  id: number;
  symbol: string;
  name: string;
  sector: string;
  quantity: number;
  avg_buy_price: number;
  total_invested_amount: number;
  current_price: number;
  unrealized_pnl: number;
  unrealized_pnl_percent: number;
  status: string;
};

export type LegacyPosition = {
  id: number;
  symbol: string;
  name: string;
  quantity: number;
  avg_price: number;
  source: string;
  is_protected: boolean;
};

export type DecisionEvaluation = {
  id: number;
  decision_id: number;
  evaluated_at: string;
  evaluation_window: string;
  price_at_decision: number;
  price_at_evaluation: number;
  return_percent: number;
  was_profitable: boolean;
  agent_self_review: string;
  mistake_type: string | null;
  improvement_note: string | null;
};

export type LLMUsage = {
  id: number;
  created_at: string;
  purpose: string;
  model: string;
  symbol: string | null;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number;
  latency_ms: number;
  success: boolean;
  error_message: string | null;
};

export type LLMUsageSummary = {
  today_calls: number;
  today_total_tokens: number;
  today_estimated_cost_usd: number;
  monthly_estimated_cost_usd: number;
  average_latency_ms: number;
  successful_calls: number;
  failed_calls: number;
};

export type LLMBudget = LLMUsageSummary & {
  approved: boolean;
  reason: string;
  daily_cost_remaining_usd: number;
  monthly_cost_remaining_usd: number;
  daily_tokens_remaining: number;
  daily_cost_limit_usd: number;
  monthly_cost_limit_usd: number;
  daily_token_limit: number;
};

export type SafetySettings = {
  broker_provider: string;
  dry_run: boolean;
  live_trading_enabled: boolean;
  use_mock_data: boolean;
  bot_capital_limit_usd: number;
  max_order_amount_usd: number;
  max_positions: number;
  max_daily_trades: number;
  min_cash_reserve_usd: number;
  allowed_sector: string;
  allowed_symbols: string[];
  forbidden_keywords: string[];
  protected_symbols: string[];
  default_stop_mode: string;
  hard_max_position_loss_percent: number;
  hard_daily_loss_limit_percent: number;
  llm_model_decision: string | null;
  openai_timeout_seconds: number;
  real_llm_enabled: boolean;
  toss_base_url: string;
  toss_token_path_configured: boolean;
  toss_accounts_path_configured: boolean;
  toss_positions_path_configured: boolean;
};

export type SecurityReadiness = {
  safe_for_public_demo: boolean;
  mock_data_enabled: boolean;
  dry_run_enabled: boolean;
  live_trading_enabled: boolean;
  toss_credentials_configured: boolean;
  toss_read_only_ready: boolean;
  openai_configured: boolean;
  real_llm_ready: boolean;
  warnings: string[];
  next_actions: string[];
};

export type DemoStatus = {
  demo_enabled: boolean;
  demo_reason: string;
  legacy_positions: number;
  bot_positions: number;
  decisions: number;
  orders: number;
  evaluations: number;
  llm_usage_rows: number;
};

export type DemoSeedResponse = DemoStatus & {
  created: boolean;
  message: string;
};

export type BrokerStatus = {
  broker_provider: string;
  use_mock_data: boolean;
  dry_run: boolean;
  live_trading_enabled: boolean;
  has_app_key: boolean;
  has_app_secret: boolean;
  has_account_id: boolean;
  credentials_ready: boolean;
  read_only_ready: boolean;
  openai_configured: boolean;
  real_llm_ready: boolean;
  live_ready: boolean;
  status_reason: string;
};

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  getPortfolioSummary: () => request<PortfolioSummary>("/portfolio/summary"),
  getLegacyPositions: () => request<LegacyPosition[]>("/portfolio/legacy"),
  getBotPositions: () => request<BotPosition[]>("/portfolio/bot"),
  runAgentOnce: () => request<AgentDecision>("/agent/run-once", { method: "POST" }),
  getDecisions: () => request<AgentDecision[]>("/decisions"),
  getDecision: (id: number) => request<AgentDecision>(`/decisions/${id}`),
  approveDecision: (id: number) => request<TradeOrder>(`/decisions/${id}/approve`, { method: "POST" }),
  getOrders: () => request<TradeOrder[]>("/orders"),
  getEvaluations: () => request<DecisionEvaluation[]>("/evaluations"),
  runEvaluations: () => request<{ created_count: number; evaluations: DecisionEvaluation[] }>("/evaluations/run", { method: "POST" }),
  getLLMUsage: () => request<LLMUsage[]>("/llm-usage"),
  getLLMSummary: () => request<LLMUsageSummary>("/llm-usage/summary"),
  getLLMBudget: () => request<LLMBudget>("/settings/llm-budget"),
  getSafetySettings: () => request<SafetySettings>("/settings/safety"),
  getSecurityReadiness: () => request<SecurityReadiness>("/settings/security-readiness"),
  getDemoStatus: () => request<DemoStatus>("/demo/status"),
  seedDemoData: () => request<DemoSeedResponse>("/demo/seed", { method: "POST" }),
  getBrokerStatus: () => request<BrokerStatus>("/broker/status"),
};
