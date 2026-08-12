# Realtime Intraday Signal Plan

## Goal

Replace the current daily-candle-only candidate input with a two-stage market pipeline:

1. Fetch current prices for the full active universe in one Toss `/api/v1/prices` request.
2. Fetch 1-minute candles and orderbook only for the deterministic shortlist.
3. Compute intraday signals in Python and call the LLM only when a meaningful signal exists.
4. Keep all existing paper-trading, capital, exposure, protected-symbol, and live-order guards.

## Ownership

### Claude CLI

- `backend/app/strategy/intraday_signal_selector.py` (new)
- `backend/tests/test_intraday_signal_selector.py` (new)

Claude owns only these two files. The module must be pure Python and must not read env, DB, network, or modify existing files.

### Codex

- `backend/app/clients/toss_client.py`
- `backend/app/clients/market_data_client.py`
- `backend/app/services/market_service.py`
- `backend/app/agents/market_agent.py`
- `backend/app/services/agent_service.py`
- `backend/app/services/agent_graph_service.py`
- configuration, schemas, frontend status surfaces, integration tests, and documentation

## Claude Module Contract

`IntradaySignalSelector(max_candidates=3)` stores a positive candidate limit.
`select(signals_by_symbol, candidates)` returns at most that many signals. `candidates`
is an ordered list of symbol strings and `signals_by_symbol` is keyed by symbol.
Each returned signal exposes:

- `symbol`
- `score`
- `reason`
- `return_5m_percent`
- `return_15m_percent`
- `volume_ratio`
- `vwap_deviation_percent`
- `spread_percent`
- `event_triggered`

Input signal payloads contain `candles` (newest or oldest order must both work), optional `bids`/`asks`, and a current `price`. Missing or malformed market data must fail closed without raising.

The deterministic trigger should require a measurable intraday move or volume expansion, reject excessive spread, and rank stronger liquid signals first. It must not make BUY/SELL decisions.

## Safety And Pacing

- Price collection can run every 5 minutes during the configured KRX session.
- LLM calls remain limited by a 30-minute cooldown and daily cost/token/call budgets.
- No qualifying intraday event means no OpenAI call and no order decision.
- Live trading remains disabled. A finite live order cap is still mandatory for live readiness.
