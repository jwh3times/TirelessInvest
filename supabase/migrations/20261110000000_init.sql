-- TirelessInvest: initial schema.
--
-- Access model: the browser only talks to Supabase for sign-in. All data reads and writes go
-- through the Python API, which connects as the database owner and enforces permissions and
-- feature flags itself. Row-level security is enabled on every table with NO policies, so the
-- public anon/authenticated keys cannot read or write any of this data directly. That is
-- defense in depth: if someone calls Supabase's auto-generated REST API with a user token,
-- they get nothing.
--
-- Admin is NOT stored here. It lives in auth.users.raw_app_meta_data ->> 'role' = 'admin'
-- (app_metadata), which only the service role can change. Never use user_metadata for roles:
-- users can edit their own user_metadata.

-- ---------------------------------------------------------------------------
-- Permissions
-- ---------------------------------------------------------------------------
create table public.permissions (
  key text primary key,
  description text not null,
  granted_by_default boolean not null default false
);

create table public.user_permissions (
  user_id uuid not null references auth.users (id) on delete cascade,
  permission_key text not null references public.permissions (key) on delete cascade,
  granted_at timestamptz not null default now(),
  primary key (user_id, permission_key)
);

insert into public.permissions (key, description, granted_by_default) values
  ('backtest:run', 'Run backtests on preset universes', true),
  ('backtest:custom_universe', 'Run backtests on custom symbol lists', false);

-- New sign-ups receive the default permissions.
create function public.grant_default_permissions()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.user_permissions (user_id, permission_key)
  select new.id, p.key from public.permissions p where p.granted_by_default;
  return new;
end;
$$;

create trigger on_auth_user_created_grant_permissions
  after insert on auth.users
  for each row execute function public.grant_default_permissions();

-- ---------------------------------------------------------------------------
-- Feature flags: a global switch plus optional per-user overrides.
-- ---------------------------------------------------------------------------
create table public.feature_flags (
  key text primary key,
  description text not null,
  enabled boolean not null default false,
  updated_at timestamptz not null default now()
);

create table public.feature_flag_overrides (
  flag_key text not null references public.feature_flags (key) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  enabled boolean not null,
  updated_at timestamptz not null default now(),
  primary key (flag_key, user_id)
);

insert into public.feature_flags (key, description, enabled) values
  ('strategy.mean_reversion', 'Experimental short-term mean reversion strategy', false),
  ('live_trading', 'Real-money trading. Not implemented; also hard-blocked in code.', false);

-- ---------------------------------------------------------------------------
-- Admin audit log
-- ---------------------------------------------------------------------------
create table public.admin_audit_log (
  id bigint generated always as identity primary key,
  actor_id uuid not null,
  action text not null,
  target text not null,
  detail jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Market data (adjusted daily bars). Never exposed to clients directly: free data plans
-- are generally licensed for personal use, not redistribution.
-- ---------------------------------------------------------------------------
create table public.symbols (
  symbol text primary key,
  -- Earliest date a backfill has been attempted from; avoids re-fetching missing history.
  history_from date,
  last_synced_at timestamptz,
  created_at timestamptz not null default now()
);

create table public.prices_daily (
  symbol text not null references public.symbols (symbol) on delete cascade,
  date date not null,
  open double precision not null,
  high double precision not null,
  low double precision not null,
  close double precision not null,
  volume double precision not null default 0,
  primary key (symbol, date)
);

-- ---------------------------------------------------------------------------
-- Backtests
-- ---------------------------------------------------------------------------
create table public.backtests (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  name text,
  strategy text not null,
  request jsonb not null,
  summary jsonb not null,
  report jsonb not null,
  duration_ms integer not null,
  created_at timestamptz not null default now()
);

create index backtests_user_created_idx on public.backtests (user_id, created_at desc);

-- ---------------------------------------------------------------------------
-- Lock everything down for direct client access (see header).
-- ---------------------------------------------------------------------------
alter table public.permissions enable row level security;
alter table public.user_permissions enable row level security;
alter table public.feature_flags enable row level security;
alter table public.feature_flag_overrides enable row level security;
alter table public.admin_audit_log enable row level security;
alter table public.symbols enable row level security;
alter table public.prices_daily enable row level security;
alter table public.backtests enable row level security;

revoke all on all tables in schema public from anon, authenticated;
revoke execute on function public.grant_default_permissions() from anon, authenticated, public;
