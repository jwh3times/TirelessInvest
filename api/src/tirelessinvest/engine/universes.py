"""Preset symbol universes.

ETF universes are the honest default: an index ETF's history already includes the companies
that failed. Lists of individual stocks picked today are survivorship-biased: they contain
only companies that grew big enough to be on today's list, which flatters any backtest.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Universe:
    key: str
    label: str
    description: str
    symbols: tuple[str, ...]
    survivorship_biased: bool = False


UNIVERSES: dict[str, Universe] = {
    u.key: u
    for u in (
        Universe(
            "us_index",
            "S&P 500 index fund",
            "A single S&P 500 ETF. The baseline every other strategy has to beat.",
            ("SPY",),
        ),
        Universe(
            "us_size",
            "US large / mid / small cap",
            "S&P 500 (large), S&P MidCap 400 (mid) and Russell 2000 (small) ETFs.",
            ("SPY", "MDY", "IWM"),
        ),
        Universe(
            "multi_asset",
            "Multi-asset",
            "US and international stocks, Treasuries, gold and real estate.",
            ("SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "IEF", "GLD", "VNQ"),
        ),
        Universe(
            "us_sectors",
            "US sectors",
            "The S&P 500 sector ETFs. XLRE and XLC start later than the others.",
            ("XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY", "XLRE", "XLC"),
        ),
        Universe(
            "mega_caps_today",
            "Today's mega-cap stocks",
            "Large US companies as of 2026. Survivorship-biased: expect inflated results.",
            (
                "AAPL",
                "MSFT",
                "NVDA",
                "AMZN",
                "GOOGL",
                "META",
                "BRK.B",
                "JPM",
                "LLY",
                "AVGO",
                "XOM",
                "UNH",
                "V",
                "JNJ",
                "WMT",
            ),
            survivorship_biased=True,
        ),
    )
}
