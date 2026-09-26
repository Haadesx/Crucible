from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "DarwinGuard"
    app_env: Literal["development", "test", "production"] = "development"
    run_mode: Literal["REAL", "DEV", "TEST"] = "DEV"
    # Persistence reality until Atlas is available (§27, §35). "dev" is the explicitly
    # labelled local DEV backend (in-memory, optionally snapshot-backed); "atlas"
    # enforces a live MongoDB + Atlas Vector Search for REAL runs.
    persistence: Literal["dev", "atlas"] = "dev"
    log_level: str = "INFO"

    openai_api_key: SecretStr = SecretStr("")
    openrouter_api_key: SecretStr = SecretStr("")
    openai_model: str = "gpt-4.1-mini"
    openai_mutation_model: str = "gpt-4.1"
    agent_provider: Literal["fake", "openai"] = "fake"
    mutation_provider: Literal["deterministic", "openai"] = "deterministic"

    # --- Real co-evolution model endpoints (BuildProduct.md §6, §7) ---
    # RED: the attacking agent; typically a local uncensored OpenAI-compatible server.
    red_provider: Literal["openai", "openai_compatible"] = "openai_compatible"
    # §23: what Red is allowed to know about the harness it attacks. BLACK_BOX is the
    # spec's default; GRAY_BOX additionally tells Red the harness's capabilities.
    red_team_mode: Literal["BLACK_BOX", "GRAY_BOX"] = "BLACK_BOX"
    red_base_url: str = ""
    red_api_key: str = "local"
    red_model: str = ""

    # BLUE: the defending agent; may be OpenAI or any OpenAI-compatible endpoint.
    blue_provider: Literal["openai", "openai_compatible", "openrouter"] = "openai"
    blue_base_url: str = ""
    blue_api_key: str = ""
    blue_model: str = "gpt-4.1-mini"
    # The harness-patch engineer is a separate role from the executor: the bake-off chose
    # Nimotron 3 Super for first-pass reliability and native JSON mode, with Ling Fin as
    # the explicit fallback. Empty means "use blue_model"; an empty fallback means none.
    blue_engineer_model: str = ""
    blue_fallback_model: str = ""

    # When true, deterministic stand-ins are allowed (tests / offline demos only).
    # Real runs MUST leave this false; audit_runtime reports it loudly.
    test_mode: bool = False

    mongodb_uri: str = ""
    mongodb_database: str = "darwinguard"
    dev_state_path: str = ""
    # An observer serving a DEV snapshot is read-only by default so evidence cannot be
    # written or wiped through the API. Set ALLOW_SNAPSHOT_WRITES=true only for a
    # dedicated live-demo snapshot that is safe to write.
    allow_snapshot_writes: bool = False
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = Field(default=1536, ge=64, le=4096)

    red_population: int = Field(default=6, ge=4, le=24)
    blue_population: int = Field(default=6, ge=4, le=24)
    generations: int = Field(default=5, ge=2, le=12)
    matchups_per_genome: int = Field(default=3, ge=2, le=8)
    max_parallel_episodes: int = Field(default=4, ge=1, le=16)

    use_vector_search: bool = True
    use_change_streams: bool = True
    use_secondary_verifier: bool = False
    use_openrouter: bool = False
    use_voice: bool = False
    demo_mode: bool = False
    export_dir: str = "exports"

    @property
    def has_openai(self) -> bool:
        return bool(self.openai_api_key.get_secret_value())

    @property
    def has_blue(self) -> bool:
        if self.blue_provider == "openai":
            return bool(self.blue_api_key or self.openai_api_key.get_secret_value())
        if self.blue_provider == "openrouter":
            return bool(self.openrouter_api_key.get_secret_value())
        return True  # local compatible endpoints need no key

    @property
    def real_models_available(self) -> bool:
        return not self.test_mode and self.has_blue

    @property
    def has_mongodb(self) -> bool:
        return bool(self.mongodb_uri)

    @property
    def effective_run_mode(self) -> Literal["REAL", "DEV", "TEST"]:
        return "TEST" if self.test_mode else self.run_mode


@lru_cache
def get_settings() -> Settings:
    return Settings()
