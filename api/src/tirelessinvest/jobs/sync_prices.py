"""Scheduled job: refresh stored prices. Run with `python -m tirelessinvest.jobs.sync_prices`.

Railway runs this on a cron schedule (see railway.sync.toml). It must exit when done.
"""

from __future__ import annotations

import logging
import sys

from ..config import get_settings
from ..db import close_pool
from ..engine.universes import UNIVERSES
from ..market.alpaca import AlpacaClient
from ..market.store import PostgresPriceStore


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()
    if not settings.alpaca_configured:
        logging.error("ALPACA_KEY_ID / ALPACA_SECRET_KEY are not set")
        return 1
    alpaca = AlpacaClient(
        settings.alpaca_key_id,
        settings.alpaca_secret_key,
        base_url=settings.alpaca_data_url,
        feed=settings.alpaca_feed,
    )
    store = PostgresPriceStore(alpaca, settings.backfill_floor)
    try:
        # Make sure every preset universe is tracked, then refresh everything tracked.
        presets = sorted({s for u in UNIVERSES.values() for s in u.symbols})
        store.ensure_history(presets, settings.backfill_floor)
        result = store.refresh_all()
        logging.info("price sync complete: %s", result)
        return 0
    finally:
        close_pool()


if __name__ == "__main__":
    sys.exit(main())
