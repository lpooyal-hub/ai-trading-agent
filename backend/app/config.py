from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AI Trading Agent Research Platform"
    environment: str = "development"
    database_url: str = "sqlite:///./data/trading_agent.db"
    cors_allowed_origins_csv: str = Field(
        default="http://localhost:5173,http://localhost:3000",
        validation_alias="CORS_ALLOWED_ORIGINS",
    )
    require_admin_api_key: bool = False
    admin_api_key: str | None = None

    broker_provider: str = "toss_securities"
    dry_run: bool = True
    live_trading_enabled: bool = False
    use_mock_data: bool = True
    # Trading-money amounts are KRW (domestic KRX market). LLM cost tracking
    # below stays in USD on purpose: OpenAI bills in USD regardless of which
    # market the agent trades, so it is not part of this currency switch.
    bot_capital_limit_krw: float = 300000
    max_order_amount_krw: float = 130000
    max_positions: int = 3
    max_daily_trades: int = 5
    max_symbol_exposure_percent: float = 40
    min_cash_reserve_krw: float = 30000
    fractional_trading_enabled: bool = False
    min_order_amount_krw: float = 5000
    quantity_decimal_places: int = 0
    order_sizing_mode: str = "notional"
    # No single-sector restriction: the agent picks freely across sectors
    # within allowed_symbols_csv (the actual safety boundary, enforced by
    # RiskManager). Defaults to a small multi-sector KRX large-cap set.
    allowed_symbols_csv: str = Field(
        default="005930,000660,005380,000270,373220,207940,035420,035720,005490,068270",
        validation_alias="ALLOWED_SYMBOLS",
    )
    forbidden_keywords_csv: str = Field(
        default="leveraged,inverse,2x,3x,bull,bear,short",
        validation_alias="FORBIDDEN_KEYWORDS",
    )
    protected_symbols_csv: str = Field(
        default="",
        validation_alias="PROTECTED_SYMBOLS",
    )
    default_stop_mode: str = "agent_with_hard_guardrails"
    hard_max_position_loss_percent: float = 25
    hard_daily_loss_limit_percent: float = 10
    llm_daily_cost_limit_usd: float = 2
    llm_monthly_cost_limit_usd: float = 30
    llm_daily_token_limit: int = 100000
    llm_daily_call_limit: int = 5
    llm_min_minutes_between_calls: int = 60
    llm_max_candidates_per_run: int = 3
    llm_model_decision: str | None = None
    llm_model_evaluation: str | None = None
    llm_model_reflection: str | None = None
    llm_input_cost_per_1m_tokens_usd: float = 0
    llm_output_cost_per_1m_tokens_usd: float = 0
    # Rough, fixed display-only conversion rate (not a live FX feed). Trading
    # PnL is KRW but OpenAI still bills in USD, so anything that combines the
    # two (e.g. portfolio "net after LLM cost") must convert through this
    # first -- never subtract/divide a USD amount against a KRW amount directly.
    usd_to_krw_display_rate: float = 1300
    openai_responses_url: str = "https://api.openai.com/v1/responses"
    openai_timeout_seconds: int = 30
    market_snapshot_max_age_minutes: int = 30
    agent_automation_enabled: bool = False
    agent_automation_mode: str = "manual_approval"
    agent_auto_execute_min_confidence: float = 0.75
    agent_auto_execute_max_order_amount_krw: float = 65000
    agent_scheduler_enabled: bool = False
    agent_scheduler_interval_minutes: int = 60
    agent_scheduler_market_hours_only: bool = True
    # Domestic KRX regular session (KOSPI/KOSDAQ), not the prior overseas
    # (NYSE/NASDAQ) hours this project started with.
    agent_market_timezone: str = "Asia/Seoul"
    agent_market_open_time: str = "09:00"
    agent_market_close_time: str = "15:30"
    agent_market_closed_dates_csv: str = Field(
        default="",
        validation_alias="AGENT_MARKET_CLOSED_DATES",
    )
    # Continuous multi-cycle session loop (docs/plans/continuous-session-loop.md).
    # agent_scheduler_interval_minutes above is reused as the pacing target between
    # cycles *inside* a session, not just the external trigger interval.
    agent_session_max_cycles: int = 30
    agent_session_max_minutes: int = 420

    toss_app_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("TOSS_API_KEY", "TOSS_APP_KEY"),
    )
    toss_app_secret: str | None = Field(
        default=None,
        validation_alias=AliasChoices("TOSS_SECRET_KEY", "TOSS_APP_SECRET"),
    )
    toss_account_id: str | None = None
    toss_base_url: str = "https://openapi.tossinvest.com"
    toss_token_path: str | None = Field(
        default="/oauth2/token",
        validation_alias=AliasChoices("TOSS_TOKEN_PATH", "TOSS_OAUTH_TOKEN_PATH"),
    )
    toss_accounts_path: str | None = Field(
        default="/api/v1/accounts",
        validation_alias=AliasChoices("TOSS_ACCOUNT_LIST_PATH", "TOSS_ACCOUNTS_PATH"),
    )
    toss_positions_path: str | None = Field(
        default="/api/v1/holdings",
        validation_alias=AliasChoices("TOSS_HOLDINGS_PATH", "TOSS_POSITIONS_PATH"),
    )
    toss_order_path: str | None = Field(
        default=None,
        validation_alias=AliasChoices("TOSS_ORDER_PATH", "TOSS_ORDERS_PATH"),
    )
    toss_order_status_path: str | None = Field(
        default=None,
        validation_alias=AliasChoices("TOSS_ORDER_STATUS_PATH", "TOSS_ORDER_DETAIL_PATH"),
    )
    toss_order_cancel_path: str | None = Field(
        default=None,
        validation_alias=AliasChoices("TOSS_ORDER_CANCEL_PATH", "TOSS_CANCEL_ORDER_PATH"),
    )
    toss_order_account_header_name: str = "X-Tossinvest-Account"
    toss_order_idempotency_header_name: str = "Idempotency-Key"
    toss_timeout_seconds: int = 8
    toss_read_cache_ttl_seconds: int = 15
    openai_api_key: str | None = None
    redis_enabled: bool = False
    redis_url: str | None = None
    redis_agent_run_lock_ttl_seconds: int = 300

    @staticmethod
    def _split_csv(value: str) -> list[str]:
        return [item.strip().upper() for item in value.split(",") if item.strip()]

    @staticmethod
    def _split_csv_preserve_case(value: str) -> list[str]:
        return [item.strip() for item in value.split(",") if item.strip()]

    @property
    def cors_allowed_origins(self) -> list[str]:
        return self._split_csv_preserve_case(self.cors_allowed_origins_csv)

    @property
    def allowed_symbols(self) -> list[str]:
        return self._split_csv(self.allowed_symbols_csv)

    @property
    def forbidden_keywords(self) -> list[str]:
        return [item.lower() for item in self._split_csv(self.forbidden_keywords_csv)]

    @property
    def protected_symbols(self) -> list[str]:
        return self._split_csv(self.protected_symbols_csv)

    @property
    def active_universe(self) -> list[str]:
        return self.allowed_symbols

    @property
    def llm_max_candidates_per_run_safe(self) -> int:
        return min(max(self.llm_max_candidates_per_run, 1), 3)

    @property
    def has_external_api_credentials(self) -> bool:
        return any(
            [
                self.toss_app_key,
                self.toss_app_secret,
                self.toss_account_id,
                self.openai_api_key,
            ]
        )

    @property
    def demo_mode_enabled(self) -> bool:
        return self.use_mock_data and not self.has_external_api_credentials

    @property
    def demo_mode_reason(self) -> str:
        if not self.use_mock_data:
            return "USE_MOCK_DATA is false."
        if self.has_external_api_credentials:
            return "External API credentials are configured."
        return "Demo mode is enabled because mock data is on and no external API credentials are configured."

    @property
    def real_llm_enabled(self) -> bool:
        return bool(
            not self.use_mock_data
            and self.openai_api_key
            and self.llm_model_decision
        )

    @property
    def llm_mode(self) -> str:
        if self.real_llm_enabled:
            return "real_openai"
        if self.use_mock_data:
            return "mock"
        return "unavailable"

    @property
    def llm_readiness_blockers(self) -> list[str]:
        blockers: list[str] = []
        if self.use_mock_data:
            blockers.append("USE_MOCK_DATA is true, so the agent uses mock LLM responses.")
        if not self.openai_api_key:
            blockers.append("OPENAI_API_KEY is not configured.")
        if not self.llm_model_decision:
            blockers.append("LLM_MODEL_DECISION is not configured.")
        return blockers

    @property
    def llm_readiness_next_actions(self) -> list[str]:
        if self.real_llm_enabled:
            return [
                "Run small DRY_RUN decisions first.",
                "Review LLM usage, reasoning, and generated order intent before live trading.",
            ]
        return [
            "Set USE_MOCK_DATA=false.",
            "Set OPENAI_API_KEY without committing it.",
            "Set LLM_MODEL_DECISION to the intended OpenAI model.",
        ]

    @property
    def agent_automation_mode_normalized(self) -> str:
        allowed_modes = {"manual_approval", "paper_auto", "live_requires_approval", "live_auto"}
        mode = self.agent_automation_mode.strip().lower()
        return mode if mode in allowed_modes else "manual_approval"

    @property
    def paper_auto_enabled(self) -> bool:
        return bool(
            self.agent_automation_enabled
            and self.agent_automation_mode_normalized == "paper_auto"
            and self.dry_run
            and not self.live_trading_enabled
        )

    @property
    def agent_scheduler_interval_minutes_safe(self) -> int:
        return max(self.agent_scheduler_interval_minutes, 1)

    @property
    def agent_session_max_cycles_safe(self) -> int:
        return max(self.agent_session_max_cycles, 1)

    @property
    def agent_session_max_minutes_safe(self) -> int:
        return max(self.agent_session_max_minutes, 1)

    @property
    def agent_session_lock_ttl_seconds(self) -> int:
        # Heartbeat lock must comfortably outlive one full inter-cycle pacing wait
        # (agent_scheduler_interval_minutes) so a normal cycle never loses the lock
        # before it renews. 2x interval + a fixed floor covers a slow cycle too.
        return max(self.agent_scheduler_interval_minutes_safe * 2 * 60, self.redis_agent_run_lock_ttl_seconds)

    @property
    def quantity_decimal_places_safe(self) -> int:
        return min(max(self.quantity_decimal_places, 0), 8)

    @property
    def order_sizing_mode_normalized(self) -> str:
        mode = self.order_sizing_mode.strip().lower()
        return mode if mode in {"notional", "quantity"} else "notional"

    @property
    def agent_market_closed_dates(self) -> list[str]:
        return self._split_csv_preserve_case(self.agent_market_closed_dates_csv)

    @property
    def toss_api_credentials_ready(self) -> bool:
        return bool(self.toss_app_key and self.toss_app_secret)

    @property
    def toss_credentials_ready(self) -> bool:
        return bool(self.toss_api_credentials_ready and self.toss_account_id)

    @property
    def toss_read_only_ready(self) -> bool:
        return bool(
            not self.use_mock_data
            and self.toss_credentials_ready
            and self.toss_token_path
            and self.toss_accounts_path
            and self.toss_positions_path
        )

    @property
    def toss_live_order_ready(self) -> bool:
        return bool(
            not self.use_mock_data
            and not self.dry_run
            and self.live_trading_enabled
            and self.toss_credentials_ready
            and self.toss_token_path
            and self.toss_order_path
        )

    @property
    def admin_api_key_configured(self) -> bool:
        return bool(self.admin_api_key and self.admin_api_key.strip())

    @property
    def admin_auth_enabled(self) -> bool:
        return bool(self.require_admin_api_key and self.admin_api_key_configured)


@lru_cache
def get_settings() -> Settings:
    return Settings()
