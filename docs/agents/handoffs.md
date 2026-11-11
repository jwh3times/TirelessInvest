# Handoffs

## Map key

TirelessInvest

## Extra document content

- Production values (API keys, database URL, passwords) live in the 1Password vault
  `TirelessInvest`, item `TirelessInvest production`, never in `.env` files. Name them, never
  write their values.
- Local development env files (`api/.env`, `web/.env.local`) are recreated from the
  `.env.example` files beside them, pointing at local Supabase; see the README.
