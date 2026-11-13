"""Fake CryptoGames casino for tests (E0-S2). Dice only.

Speaks the REST shape the clients parse (cryptogames.py `api_place_bet` /
`betting_loop`, tg/engine.py `_api_place_bet` / `start`). Key in the path:

    POST https://api.crypto.games/v1/placebet/{coin}/{key}
        {Bet, Payout, UnderOver (true = under), ClientSeed}
        200 {BetId, Roll, Target, UnderOver, Bet, Payout, Profit, Balance,
             ClientSeed, ServerSeed, NextServerSeedHash}
        errors arrive as HTTP 200 with a Message and no Roll
    GET  /v1/balance/{coin}/{key}  -> {"Balance": x}
    GET  /v1/settings/{coin}       -> {"MinBet", "MinimumBet", "MaxWin", "Edge"}
Read-only GETs never consume the script.

Script outcomes: win, loss, insufficient_balance, http_429, timeout.
429 carries `Retry-After: 3` (the TG loop honours it).
An empty script answers insufficient_balance and sets `exhausted`.
"""

import json
from collections import deque

import httpx
import requests

API_BASE = "https://api.crypto.games"
OUTCOMES = {"win", "loss", "insufficient_balance", "http_429", "timeout"}
RETRY_AFTER = "3"


class UnexpectedRequest(BaseException):
    """A request the fake has no route for. BaseException on purpose: the bet
    loops catch Exception and retry forever, which would hang the test."""


class FakeTimeout(Exception):
    """Raised by FakeCasino.handle; adapters map it to the client's timeout."""


class FakeCasino:
    def __init__(self, balance: float = 10.0, coin: str = "doge", api_key: str = "test-key",
                 script=()):
        self.balance = float(balance)
        self.coin = coin
        self.api_key = api_key
        self.min_bet = 0.0001
        self.script = deque()
        self.calls = []        # (method, url, body) for every request
        self.bets = []         # {"outcome", "amount", "payout", "profit", "balance", "seed"}
        self.exhausted = False
        self.queue(*script)

    def queue(self, *outcomes):
        for o in outcomes:
            if o not in OUTCOMES:
                raise ValueError(f"unknown outcome {o!r}")
            self.script.append(o)

    @property
    def bet_posts(self) -> int:
        return sum(1 for m, _, _ in self.calls if m == "POST")

    @property
    def profit(self) -> float:
        return sum(b["profit"] for b in self.bets)

    def handle(self, method: str, url: str, body: dict):
        """Return (status, json_body, headers) or raise FakeTimeout."""
        self.calls.append((method, url, body))
        key, coin = self.api_key, self.coin
        if method == "GET" and url == f"{API_BASE}/v1/balance/{coin}/{key}":
            return 200, {"Balance": self.balance}, {}
        if method == "GET" and url == f"{API_BASE}/v1/settings/{coin}":
            return 200, {"MinBet": self.min_bet, "MinimumBet": self.min_bet,
                         "MaxWin": 1000.0, "Edge": 0.8}, {}
        if method != "POST" or url != f"{API_BASE}/v1/placebet/{coin}/{key}":
            raise UnexpectedRequest(f"unexpected request {method} {url}")

        amount = float(body["Bet"])
        outcome = self.script.popleft() if self.script else None
        if outcome is None:
            self.exhausted = True
            outcome = "insufficient_balance"
        if outcome == "timeout":
            raise FakeTimeout()
        if outcome == "http_429":
            return 429, {"Message": "Too many requests"}, {"Retry-After": RETRY_AFTER}
        if outcome == "insufficient_balance" or amount > self.balance:
            return 200, {"Message": "Insufficient balance"}, {}

        win = outcome == "win"
        payout_mult = float(body["Payout"])
        under = bool(body["UnderOver"])
        target = round(99.2 / payout_mult, 2) if under else round(100 - 99.2 / payout_mult, 2)
        roll = round(target - 1 if under == win else target + 1, 2)
        profit = round(amount * (payout_mult - 1), 8) if win else -amount
        self.balance = round(self.balance + profit, 8)
        self.bets.append({"outcome": outcome, "amount": amount, "payout": amount + profit,
                          "profit": profit, "balance": self.balance, "roll": roll,
                          "seed": body["ClientSeed"]})
        return 200, {
            "BetId": len(self.bets), "Roll": roll, "Target": target, "UnderOver": under,
            "Bet": amount, "Payout": payout_mult, "Profit": profit, "Balance": self.balance,
            "ClientSeed": body["ClientSeed"], "ServerSeed": "s" * 64,
            "NextServerSeedHash": "h" * 64,
        }, {}

    # ── adapters ─────────────────────────────────────────
    def requests_api(self) -> "RequestsAPI":
        return RequestsAPI(self)

    def async_client(self) -> httpx.AsyncClient:
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content) if request.content else {}
            try:
                status, payload, headers = self.handle(request.method, str(request.url), body)
            except FakeTimeout:
                raise httpx.ReadTimeout("fake timeout", request=request)
            return httpx.Response(status, json=payload, headers=headers)
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))


class FakeResponse:
    def __init__(self, status: int, payload, headers=None):
        self.status_code = status
        self._payload = payload
        self.text = json.dumps(payload)
        self.headers = headers or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class RequestsAPI:
    """Stands in for the module-level `requests.get` / `requests.post` the CLI calls."""

    def __init__(self, casino: FakeCasino):
        self.casino = casino

    def _call(self, method, url, body):
        try:
            return FakeResponse(*self.casino.handle(method, url, body or {}))
        except FakeTimeout:
            raise requests.exceptions.Timeout("fake timeout")

    def get(self, url, timeout=None, **_):
        return self._call("GET", url, None)

    def post(self, url, json=None, timeout=None, **_):
        return self._call("POST", url, json)
