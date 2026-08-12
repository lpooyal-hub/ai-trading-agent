function resolveApiBaseUrl() {
  const configuredUrl = import.meta.env.VITE_API_BASE_URL;
  if (typeof window === "undefined") {
    return configuredUrl || "/api";
  }

  const { hostname, port } = window.location;
  const isLocalhost = hostname === "localhost" || hostname === "127.0.0.1";

  if (configuredUrl) {
    const configured = new URL(configuredUrl, window.location.origin);
    const sameBrowserHost = configured.hostname === hostname;
    if (!isLocalhost && sameBrowserHost) {
      return "/api";
    }
    return configuredUrl;
  }

  if (isLocalhost && port === "5173") {
    return "http://localhost:8000";
  }
  return "/api";
}

export const API_BASE_URL = resolveApiBaseUrl();
const REQUEST_TIMEOUT_MS = 12000;

export type HealthResponse = {
  status: string;
  app_name: string;
  dry_run: boolean;
};

export type PortfolioSummary = {
  bot_capital_limit_krw: number;
  invested_amount_krw: number;
  available_budget_krw: number;
  min_cash_reserve_krw: number;
  bot_position_count: number;
  legacy_position_count: number;
  protected_legacy_symbols: string[];
  bot_symbols: string[];
  unrealized_pnl_krw: number;
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

export type TradeJournalEntry = {
  id: number;
  created_at: string;
  decision_id: number;
  order_id: number | null;
  evaluation_id: number | null;
  symbol: string;
  action: "BUY" | "SELL" | "HOLD";
  outcome_label: string;
  reward_score: number;
  thesis_snapshot: string;
  agent_self_feedback: string;
  lesson: string | null;
  strategy_tags_json: string[];
  journal_json: Record<string, unknown>;
};

export type TradeJournalEntryCreate = {
  decision_id: number;
  order_id?: number | null;
  evaluation_id?: number | null;
  outcome_label?: string;
  reward_score?: number;
  agent_self_feedback?: string | null;
  lesson?: string | null;
  strategy_tags?: string[];
  journal_json?: Record<string, unknown>;
};

export type MemoryGroupStat = {
  key: string;
  count: number;
  win_rate_percent: number;
  average_reward_score: number;
};

export type MemoryMistake = {
  mistake_type: string;
  count: number;
};

export type MemoryLesson = {
  journal_id: number;
  symbol: string;
  action: string;
  reward_score: number;
  lesson: string;
};

export type MemorySummary = {
  lookback_journal_entries: number;
  evaluated_entry_count: number;
  average_reward_score: number;
  win_rate_percent: number;
  action_stats: MemoryGroupStat[];
  symbol_stats: MemoryGroupStat[];
  model_stats: MemoryGroupStat[];
  prompt_stats: MemoryGroupStat[];
  common_mistakes: MemoryMistake[];
  recent_lessons: MemoryLesson[];
  memory_notes: string[];
  data_gaps: string[];
};

export type WorkflowStepStatus = "RUNNING" | "SUCCEEDED" | "FAILED" | "SKIPPED";

export type WorkflowRunStatus = "RUNNING" | "SUCCEEDED" | "FAILED" | "SKIPPED";

export type WorkflowStep = {
  id: number;
  run_id: number;
  step_name: string;
  status: WorkflowStepStatus;
  started_at: string;
  finished_at: string | null;
  input_json: Record<string, unknown>;
  output_json: Record<string, unknown>;
  error_message: string | null;
  retry_count: number;
};

export type WorkflowRun = {
  id: number;
  workflow_name: string;
  status: WorkflowRunStatus;
  started_at: string;
  finished_at: string | null;
  trigger_source: string;
  decision_id: number | null;
  input_json: Record<string, unknown>;
  output_json: Record<string, unknown>;
  error_message: string | null;
  steps: WorkflowStep[];
};

export type AgentSessionStatus = "RUNNING" | "SUCCEEDED" | "FAILED" | "STOPPED";

export type AgentSession = {
  id: number;
  status: AgentSessionStatus;
  trigger_source: string;
  started_at: string;
  finished_at: string | null;
  cycle_count: number;
  max_cycles: number;
  stop_reason: string | null;
  stop_requested: boolean;
};

export type AgentSessionWorkflowRun = WorkflowRun & {
  session_id: number;
  cycle_index: number;
};

export type AgentSessionDetail = AgentSession & {
  runs: AgentSessionWorkflowRun[];
};

export type WorkflowNode = {
  id: string;
  label: string;
  agent_type: string;
  uses_llm: boolean;
  runtime: string;
  responsibility: string;
};

export type WorkflowEdge = {
  from: string;
  to: string;
};

export type WorkflowConditionalEdge = {
  from: string;
  condition: string;
  true: string;
  false: string;
};

export type WorkflowSideLoop = {
  name: string;
  description: string;
  nodes: string[];
};

export type WorkflowDefinition = {
  workflow_name: string;
  description: string;
  engine?: string;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  conditional_edges?: WorkflowConditionalEdge[];
  side_loops: WorkflowSideLoop[];
};

export type DecisionFilters = {
  status?: string;
  symbol?: string;
  limit?: number;
};

export type AgentReadiness = {
  ready: boolean;
  reason: string;
  automation_ready: boolean;
  automation_reason: string;
  paper_auto_ready: boolean;
  paper_auto_reason: string;
  llm_mode: string;
  llm_blockers: string[];
  dry_run: boolean;
  use_mock_data: boolean;
  real_llm_ready: boolean;
  market_ready: boolean;
  budget_ready: boolean;
  candidate_symbols: string[];
  candidate_details: AgentCandidate[];
  max_candidates_per_run: number;
  fresh_symbol_count: number;
  missing_symbols: string[];
  llm_budget_reason: string;
};

export type AgentCandidate = {
  symbol: string;
  score: number;
  reason: string;
  change_percent: number;
  volume: number;
  return_5m_percent?: number;
  return_15m_percent?: number;
  volume_ratio?: number;
  vwap_deviation_percent?: number;
  spread_percent?: number;
  event_triggered?: boolean;
};

export type AgentAutomationPolicy = {
  automation_enabled: boolean;
  automation_mode: string;
  paper_auto_enabled: boolean;
  min_confidence: number;
  max_order_amount_krw: number;
  dry_run: boolean;
  live_trading_enabled: boolean;
  blockers: string[];
  next_actions: string[];
};

export type AgentSchedule = {
  scheduler_enabled: boolean;
  interval_minutes: number;
  market_hours_only: boolean;
  market_timezone: string;
  market_open_time: string;
  market_close_time: string;
  market_closed_dates: string[];
  market_open_now: boolean;
  market_session: string;
  due: boolean;
  last_decision_id: number | null;
  last_run_at: string | null;
  next_run_at: string | null;
  minutes_until_next_run: number | null;
  blockers: string[];
  next_actions: string[];
};

export type AgentScheduledRun = {
  triggered: boolean;
  reason: string;
  schedule: AgentSchedule;
  decision: AgentDecision | null;
};

export type AgentOperations = {
  last_decision_id: number | null;
  last_decision_status: string | null;
  last_decision_symbol: string | null;
  last_order_id: number | null;
  last_order_status: string | null;
  last_order_symbol: string | null;
  last_evaluation_id: number | null;
  last_evaluation_window: string | null;
  pending_decision_count: number;
  executable_decision_count: number;
  simulated_order_count: number;
  rejected_order_count: number;
  failed_order_count: number;
  latest_activity_at: string | null;
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
  raw_response_json: Record<string, unknown>;
};

export type LiveOrderBulkSync = {
  scanned_count: number;
  updated_count: number;
  filled_count: number;
  partial_count: number;
  canceled_count: number;
  failed_count: number;
  orders: TradeOrder[];
};

export type OrderFilters = {
  status?: string;
  symbol?: string;
  limit?: number;
};

export type DecisionPreview = {
  decision_id: number;
  approved: boolean;
  reason: string;
  symbol: string;
  action: "BUY" | "SELL" | "HOLD";
  side: "BUY" | "SELL" | null;
  estimated_quantity: number;
  estimated_price: number;
  estimated_order_amount: number;
  available_budget: number;
  bot_exposure: number;
  bot_owned_quantity: number;
  legacy_protected: boolean;
  execution_mode: string;
  dry_run: boolean;
  live_trading_enabled: boolean;
  warnings: string[];
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

export type BotPositionMarketSyncResponse = {
  updated_count: number;
  skipped_count: number;
  success: boolean;
  status: string;
  message: string;
  positions: BotPosition[];
};

export type PortfolioPerformance = {
  simulated_order_count: number;
  live_submitted_order_count: number;
  live_submitted_order_amount_krw: number;
  buy_order_count: number;
  sell_order_count: number;
  gross_bought_krw: number;
  gross_sold_krw: number;
  realized_pnl_krw: number;
  unrealized_pnl_krw: number;
  total_pnl_krw: number;
  total_pnl_percent: number;
  winning_sell_count: number;
  losing_sell_count: number;
  win_rate_percent: number;
  open_bot_position_count: number;
  closed_bot_position_count: number;
};

export type PortfolioCostRecovery = {
  pnl_scope: string;
  llm_cost_scope: string;
  paper_total_pnl_krw: number;
  paper_realized_pnl_krw: number;
  monthly_llm_cost_usd: number;
  today_llm_cost_usd: number;
  net_after_llm_cost_krw: number;
  realized_net_after_llm_cost_krw: number;
  llm_cost_recovery_ratio: number | null;
  realized_llm_cost_recovery_ratio: number | null;
  llm_cost_covered: boolean | null;
  realized_llm_cost_covered: boolean | null;
  simulated_order_count: number;
  today_llm_calls: number;
};

export type PortfolioRealizedTrade = {
  order_id: number;
  created_at: string;
  symbol: string;
  quantity: number;
  sell_amount_krw: number;
  cost_basis_krw: number;
  realized_pnl_krw: number;
  realized_pnl_percent: number;
};

export type PortfolioSymbolPerformance = {
  symbol: string;
  realized_trade_count: number;
  realized_pnl_krw: number;
  sell_amount_krw: number;
  win_rate_percent: number;
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

export type LegacyPositionBrokerSyncResponse = {
  imported_count: number;
  skipped_count: number;
  success: boolean;
  status: string;
  message: string | null;
  positions: LegacyPosition[];
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

export type EvaluationWindowStatus = {
  window: string;
  eligible_count: number;
  evaluated_count: number;
  pending_count: number;
  not_due_count: number;
  coverage_percent: number;
};

export type EvaluationStatus = {
  total_decisions: number;
  total_evaluations: number;
  latest_evaluated_at: string | null;
  windows: EvaluationWindowStatus[];
};

export type MarketSnapshot = {
  id: number;
  created_at: string;
  symbol: string;
  price: number;
  change_percent: number;
  volume: number;
  sector: string;
  extra_json: Record<string, unknown>;
};

export type MarketSnapshotInput = {
  symbol: string;
  price: number;
  change_percent: number;
  volume: number;
  sector: string;
  extra_json: Record<string, unknown>;
};

export type MarketSnapshotCreateResponse = {
  created_count: number;
  skipped_count: number;
  snapshots: MarketSnapshot[];
};

export type MarketSnapshotRefreshResponse = MarketSnapshotCreateResponse & {
  source: string;
  message: string;
};

export type MarketSnapshotStatus = {
  active_universe: string[];
  fresh_symbol_count: number;
  missing_symbol_count: number;
  missing_symbols: string[];
  max_age_minutes: number;
  ready_for_agent: boolean;
  message: string;
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
  today_prompt_tokens: number;
  today_completion_tokens: number;
  today_total_tokens: number;
  today_estimated_cost_usd: number;
  monthly_estimated_cost_usd: number;
  average_latency_ms: number;
  successful_calls: number;
  failed_calls: number;
  last_call_at: string | null;
};

export type LLMBudget = LLMUsageSummary & {
  approved: boolean;
  reason: string;
  daily_cost_remaining_usd: number;
  monthly_cost_remaining_usd: number;
  daily_tokens_remaining: number;
  daily_calls_remaining: number;
  daily_cost_limit_usd: number;
  monthly_cost_limit_usd: number;
  daily_token_limit: number;
  daily_call_limit: number;
  min_minutes_between_calls: number;
  cooldown_remaining_minutes: number;
};

export type LLMReadiness = {
  real_llm_ready: boolean;
  llm_mode: string;
  use_mock_data: boolean;
  openai_configured: boolean;
  llm_model_decision: string | null;
  blockers: string[];
  next_actions: string[];
};

export type LLMSmokeTest = {
  success: boolean;
  model: string;
  llm_mode: string;
  latency_ms: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number;
  usage_id: number | null;
  message: string;
};

export type SafetySettings = {
  broker_provider: string;
  dry_run: boolean;
  live_trading_enabled: boolean;
  use_mock_data: boolean;
  bot_capital_limit_krw: number;
  max_order_amount_krw: number;
  max_positions: number;
  max_daily_trades: number;
  max_symbol_exposure_percent: number;
  min_cash_reserve_krw: number;
  fractional_trading_enabled: boolean;
  min_order_amount_krw: number;
  quantity_decimal_places: number;
  order_sizing_mode: string;
  allowed_symbols: string[];
  forbidden_keywords: string[];
  protected_symbols: string[];
  default_stop_mode: string;
  hard_max_position_loss_percent: number;
  hard_daily_loss_limit_percent: number;
  position_exit_enabled: boolean;
  position_stop_loss_percent: number;
  position_take_profit_percent: number;
  position_trailing_stop_enabled: boolean;
  position_trailing_activation_percent: number;
  position_trailing_distance_percent: number;
  position_max_holding_trading_days: number;
  position_exit_max_snapshot_age_seconds: number;
  llm_daily_call_limit: number;
  llm_min_minutes_between_calls: number;
  llm_max_candidates_per_run: number;
  llm_model_decision: string | null;
  llm_input_cost_per_1m_tokens_usd: number;
  llm_output_cost_per_1m_tokens_usd: number;
  openai_timeout_seconds: number;
  real_llm_enabled: boolean;
  agent_automation_enabled: boolean;
  agent_automation_mode: string;
  agent_auto_execute_min_confidence: number;
  agent_auto_execute_max_order_amount_krw: number;
  paper_auto_enabled: boolean;
  agent_scheduler_enabled: boolean;
  agent_scheduler_interval_minutes: number;
  intraday_signals_enabled: boolean;
  intraday_shortlist_size: number;
  intraday_candle_count: number;
  agent_scheduler_market_hours_only: boolean;
  agent_market_timezone: string;
  agent_market_open_time: string;
  agent_market_close_time: string;
  agent_market_closed_dates: string[];
  toss_base_url: string;
  toss_token_path_configured: boolean;
  toss_accounts_path_configured: boolean;
  toss_positions_path_configured: boolean;
  market_snapshot_max_age_minutes: number;
};

export type SecurityReadiness = {
  safe_for_public_demo: boolean;
  admin_api_key_required: boolean;
  admin_api_key_configured: boolean;
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

export type LiveTradingReadiness = {
  live_order_ready: boolean;
  execution_mode: string;
  dry_run_enabled: boolean;
  live_trading_enabled: boolean;
  mock_data_enabled: boolean;
  toss_credentials_ready: boolean;
  toss_read_only_ready: boolean;
  live_order_implementation: string;
  adapter_checklist: string[];
  blockers: string[];
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
  api_credentials_ready: boolean;
  credentials_ready: boolean;
  account_lookup_ready: boolean;
  read_only_ready: boolean;
  openai_configured: boolean;
  real_llm_ready: boolean;
  live_ready: boolean;
  status_reason: string;
};

export type BrokerAccount = {
  masked_account_no: string;
  account_seq?: number | null;
  account_type?: string | null;
  source: string;
};

export type BrokerPosition = {
  symbol: string;
  name: string;
  quantity: number;
  avg_price: number;
  current_price: number;
  source: string;
};

export type BrokerAccountsResponse = {
  success: boolean;
  status: string;
  http_status_code?: number | null;
  message?: string;
  accounts: BrokerAccount[];
  raw_response_saved: boolean;
  cache_hit: boolean;
};

export type BrokerPositionsResponse = {
  success: boolean;
  status: string;
  http_status_code?: number | null;
  message?: string;
  positions: BrokerPosition[];
  raw_response_saved: boolean;
  cache_hit: boolean;
};

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  let response: Response;
  try {
    response = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      ...options,
      signal: controller.signal,
    });
  } catch (error) {
    const message = error instanceof Error && error.name === "AbortError"
      ? `Request timed out after ${REQUEST_TIMEOUT_MS / 1000}s`
      : error instanceof Error ? error.message : "Network request failed";
    throw new Error(`${url} - ${message}`);
  } finally {
    window.clearTimeout(timeoutId);
  }
  if (!response.ok) {
    throw new Error(`${url} - Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  getHealth: () => request<HealthResponse>("/health"),
  getPortfolioSummary: () => request<PortfolioSummary>("/portfolio/summary"),
  getPortfolioPerformance: () => request<PortfolioPerformance>("/portfolio/performance"),
  getPortfolioCostRecovery: () => request<PortfolioCostRecovery>("/portfolio/cost-recovery"),
  getPortfolioRealizedTrades: () => request<PortfolioRealizedTrade[]>("/portfolio/realized-trades"),
  getPortfolioSymbolPerformance: () => request<PortfolioSymbolPerformance[]>("/portfolio/symbol-performance"),
  getLegacyPositions: () => request<LegacyPosition[]>("/portfolio/legacy"),
  syncLegacyFromBroker: () => request<LegacyPositionBrokerSyncResponse>("/portfolio/sync-legacy-from-broker", { method: "POST" }),
  syncBotFromMarket: () => request<BotPositionMarketSyncResponse>("/portfolio/sync-bot-from-market", { method: "POST" }),
  getBotPositions: () => request<BotPosition[]>("/portfolio/bot"),
  runAgentOnce: () => request<AgentDecision>("/agent/run-once", { method: "POST" }),
  runScheduledAgent: () => request<AgentScheduledRun>("/agent/run-scheduled", { method: "POST" }),
  getAgentReadiness: () => request<AgentReadiness>("/agent/readiness"),
  getAgentAutomationPolicy: () => request<AgentAutomationPolicy>("/agent/automation-policy"),
  getAgentSchedule: () => request<AgentSchedule>("/agent/schedule"),
  getAgentOperations: () => request<AgentOperations>("/agent/operations"),
  getAgentSessions: (limit = 50) => request<AgentSession[]>(`/agent/sessions?limit=${limit}`),
  getAgentSession: (id: number) => request<AgentSessionDetail>(`/agent/sessions/${id}`),
  stopAgentSession: (id: number) => request<AgentSession>(`/agent/sessions/${id}/stop`, { method: "POST" }),
  getDecisions: (filters?: DecisionFilters) => {
    const params = new URLSearchParams();
    if (filters?.status) params.set("status", filters.status);
    if (filters?.symbol) params.set("symbol", filters.symbol);
    if (filters?.limit) params.set("limit", String(filters.limit));
    const query = params.toString();
    return request<AgentDecision[]>(query ? `/decisions?${query}` : "/decisions");
  },
  getDecision: (id: number) => request<AgentDecision>(`/decisions/${id}`),
  previewDecision: (id: number) => request<DecisionPreview>(`/decisions/${id}/preview`),
  approveDecision: (id: number) => request<TradeOrder>(`/decisions/${id}/approve`, { method: "POST" }),
  getOrders: (filters?: OrderFilters) => {
    const params = new URLSearchParams();
    if (filters?.status) params.set("status", filters.status);
    if (filters?.symbol) params.set("symbol", filters.symbol);
    if (filters?.limit) params.set("limit", String(filters.limit));
    const query = params.toString();
    return request<TradeOrder[]>(query ? `/orders?${query}` : "/orders");
  },
  syncOpenLiveOrderStatuses: () => request<LiveOrderBulkSync>("/orders/sync-live-status", { method: "POST" }),
  syncLiveOrderStatus: (id: number) => request<TradeOrder>(`/orders/${id}/sync-live-status`, { method: "POST" }),
  getEvaluations: () => request<DecisionEvaluation[]>("/evaluations"),
  getEvaluationsForDecision: (decisionId: number) => request<DecisionEvaluation[]>(`/evaluations/${decisionId}`),
  getEvaluationStatus: () => request<EvaluationStatus>("/evaluations/status"),
  runEvaluations: () => request<{ created_count: number; evaluations: DecisionEvaluation[] }>("/evaluations/run", { method: "POST" }),
  getJournalEntries: () => request<TradeJournalEntry[]>("/journal"),
  getJournalEntriesForDecision: (decisionId: number) => request<TradeJournalEntry[]>(`/journal/decision/${decisionId}`),
  getMemorySummary: () => request<MemorySummary>("/memory/summary"),
  getWorkflowDefinition: () => request<WorkflowDefinition>("/workflows/definition"),
  getWorkflowRuns: (limit = 50) => request<WorkflowRun[]>(`/workflows?limit=${limit}`),
  getWorkflowRun: (id: number) => request<WorkflowRun>(`/workflows/${id}`),
  runWorkflow: () => request<WorkflowRun>("/workflows/run", { method: "POST" }),
  createJournalEntry: (payload: TradeJournalEntryCreate) => request<TradeJournalEntry>("/journal", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }),
  getMarketSnapshots: () => request<MarketSnapshot[]>("/market/snapshots"),
  getLatestMarketSnapshots: () => request<MarketSnapshot[]>("/market/snapshots/latest"),
  getMarketSnapshotStatus: () => request<MarketSnapshotStatus>("/market/snapshots/status"),
  refreshMarketSnapshots: () => request<MarketSnapshotRefreshResponse>("/market/snapshots/refresh", { method: "POST" }),
  createMarketSnapshots: (snapshots: MarketSnapshotInput[]) => request<MarketSnapshotCreateResponse>("/market/snapshots", {
    method: "POST",
    body: JSON.stringify({ snapshots }),
  }),
  getLLMUsage: () => request<LLMUsage[]>("/llm-usage"),
  getLLMSummary: () => request<LLMUsageSummary>("/llm-usage/summary"),
  getLLMBudget: () => request<LLMBudget>("/settings/llm-budget"),
  getLLMReadiness: () => request<LLMReadiness>("/settings/llm-readiness"),
  runLLMSmokeTest: () => request<LLMSmokeTest>("/settings/llm-smoke-test", { method: "POST" }),
  getSafetySettings: () => request<SafetySettings>("/settings/safety"),
  getSecurityReadiness: () => request<SecurityReadiness>("/settings/security-readiness"),
  getLiveTradingReadiness: () => request<LiveTradingReadiness>("/settings/live-readiness"),
  getDemoStatus: () => request<DemoStatus>("/demo/status"),
  seedDemoData: () => request<DemoSeedResponse>("/demo/seed", { method: "POST" }),
  getBrokerStatus: () => request<BrokerStatus>("/broker/status"),
  getBrokerAccounts: () => request<BrokerAccountsResponse>("/broker/accounts/normalized"),
  getBrokerPositions: () => request<BrokerPositionsResponse>("/broker/positions/normalized"),
};
