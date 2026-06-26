# Security Policy

This repository is designed for public demo and paper-trading research only.

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

Live trading implementation should stay in a private branch or private repository. The public main branch should remain DRY_RUN-only.
