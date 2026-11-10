from datetime import date

import httpx

from tirelessinvest.market.alpaca import AlpacaClient


def test_paginates_parses_dates_and_falls_back_from_sip():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        seen.append(params)
        assert request.headers["APCA-API-KEY-ID"] == "k"
        assert params["adjustment"] == "all"
        if params["feed"] == "sip":
            return httpx.Response(403, json={"message": "subscription does not permit"})
        if "page_token" not in params:
            return httpx.Response(
                200,
                json={
                    "bars": {
                        "SPY": [
                            {
                                "t": "2024-01-02T05:00:00Z",
                                "o": 1,
                                "h": 2,
                                "l": 0.5,
                                "c": 1.5,
                                "v": 100,
                            }
                        ]
                    },
                    "next_page_token": "abc",
                },
            )
        return httpx.Response(
            200,
            json={
                "bars": {
                    "SPY": [
                        {"t": "2024-07-01T04:00:00Z", "o": 2, "h": 3, "l": 1, "c": 2.5, "v": 200}
                    ]
                },
                "next_page_token": None,
            },
        )

    client = AlpacaClient("k", "s", http=httpx.Client(transport=httpx.MockTransport(handler)))
    df = client.daily_bars(["SPY"], date(2024, 1, 1), date(2024, 12, 31))
    # Midnight New York in winter (05:00Z) and summer (04:00Z) both map to the right day.
    assert list(df["date"]) == [date(2024, 1, 2), date(2024, 7, 1)]
    assert list(df["close"]) == [1.5, 2.5]
    assert client.feed == "iex"
    assert [p["feed"] for p in seen] == ["sip", "iex", "iex"]
