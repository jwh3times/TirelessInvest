from __future__ import annotations

from datetime import date
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Postgres connection string. On Supabase use the *session pooler* URL (IPv4-friendly).
    database_url: str = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"

    # Supabase project URL, e.g. https://abcd.supabase.co. Used to verify user JWTs via JWKS.
    supabase_url: str = "http://127.0.0.1:54321"
    # Only for projects still on the legacy shared HS256 secret. Leave empty to use JWKS.
    supabase_jwt_secret: str = ""

    # Comma-separated list of allowed browser origins.
    cors_origins: str = "http://localhost:5173"

    # Where backtests get prices: "db" (synced from Alpaca) or "synthetic" (offline demo).
    price_source: Literal["db", "synthetic"] = "db"

    alpaca_key_id: str = ""
    alpaca_secret_key: str = ""
    alpaca_data_url: str = "https://data.alpaca.markets"
    # "sip" = consolidated prices from all exchanges (official closes). If your plan rejects it,
    # the client falls back to "iex" (one exchange; closes can differ slightly).
    alpaca_feed: Literal["iex", "sip"] = "sip"
    # Fetch prices for unseen symbols on demand when a backtest needs them.
    backfill_on_demand: bool = True
    # Earliest date to fetch history from. Alpaca's history starts around 2016.
    backfill_floor: date = date(2016, 1, 1)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def alpaca_configured(self) -> bool:
        return bool(self.alpaca_key_id and self.alpaca_secret_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
