# Security Policy

This repository is designed to be safe by default, with DRY_RUN and mock data enabled unless the user explicitly changes the configuration.

## Do Not Commit

- API keys
- `.env` files
- Real brokerage account IDs
- Real account numbers
- Real holdings
- Real order history
- Real API responses
- Real logs or local database files

## Public Demo Mode

Use `USE_MOCK_DATA=true` for public demos. Mock mode must not call Toss Securities or OpenAI APIs.

## If A Secret Leaks

Rotate the key immediately, remove it from git history, and audit any systems that used the key.

## Live Trading

Live trading must remain opt-in. Keep `DRY_RUN=true` and `LIVE_TRADING_ENABLED=false` unless you have reviewed the code, configured credentials, and accepted responsibility for any resulting orders. Do not commit credentials, account data, real logs, or real API responses.
