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

    broker_provider: str = "toss_securities"
    dry_run: bool = True
    live_trading_enabled: bool = False
    use_mock_data: bool = True
    bot_capital_limit_usd: float = 250
    max_order_amount_usd: float = 100
    max_positions: int = 3
    max_daily_trades: int = 5
    min_cash_reserve_usd: float = 25
    allowed_sector: str = "semiconductor"
    allowed_symbols_csv: str = Field(
        default="NVDA,AMD,TSM,AVGO,ASML,QCOM,MU,ARM,INTC,AMAT",
        validation_alias="ALLOWED_SYMBOLS",
    )
    forbidden_keywords_csv: str = Field(
        default="leveraged,inverse,2x,3x,bull,bear,short",
        validation_alias="FORBIDDEN_KEYWORDS",
    )
    protected_symbols_csv: str = Field(
        default="SPACE_X",
        validation_alias="PROTECTED_SYMBOLS",
    )
    default_stop_mode: str = "agent_with_hard_guardrails"
    hard_max_position_loss_percent: float = 25
    hard_daily_loss_limit_percent: float = 10
    llm_daily_cost_limit_usd: float = 2
    llm_monthly_cost_limit_usd: float = 30
    llm_daily_token_limit: int = 100000
    llm_model_decision: str | None = None
    llm_model_evaluation: str | None = None
    llm_model_reflection: str | None = None
    llm_input_cost_per_1m_tokens_usd: float = 0
    llm_output_cost_per_1m_tokens_usd: float = 0
    openai_responses_url: str = "https://api.openai.com/v1/responses"
    openai_timeout_seconds: int = 30
    market_snapshot_max_age_minutes: int = 30

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
    toss_timeout_seconds: int = 30
    openai_api_key: str | None = None

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
