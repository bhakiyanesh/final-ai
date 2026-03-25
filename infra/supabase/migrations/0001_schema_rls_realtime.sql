-- Remittance Optimization MVP schema
-- Includes: tables, indexes, audit timestamps, RLS policies, and Supabase realtime publication config.

begin;

create extension if not exists pgcrypto;

-- Generic updated_at trigger
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- Admin helper for RLS policies
create or replace function public.is_admin()
returns boolean
language sql
stable
as $$
  select exists (
    select 1
    from public.users u
    where u.id = auth.uid()
      and u.is_admin = true
  );
$$;

create table if not exists public.users (
  id uuid primary key references auth.users(id) on delete cascade,
  email text,
  is_admin boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists trg_users_updated_at on public.users;
create trigger trg_users_updated_at
before update on public.users
for each row
execute function public.set_updated_at();

alter table public.users enable row level security;

drop policy if exists users_select_own on public.users;
create policy users_select_own
on public.users
for select
using (id = auth.uid() or public.is_admin());

drop policy if exists users_update_own on public.users;
create policy users_update_own
on public.users
for update
using (id = auth.uid() or public.is_admin())
with check (id = auth.uid() or public.is_admin());

drop policy if exists users_insert_own on public.users;
create policy users_insert_own
on public.users
for insert
with check (id = auth.uid() or public.is_admin());

create table if not exists public.transactions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete restrict,
  idempotency_key text not null,

  sender_country char(2) not null,
  receiver_country char(2) not null,
  amount numeric(20, 8) not null check (amount > 0),
  currency char(3) not null,
  speed_preference text not null check (speed_preference in ('fastest', 'balanced', 'cheapest')),

  payout_preference text not null check (payout_preference in ('bank', 'mobile', 'cash', 'stablecoin')),
  recipient_identifier text,

  status text not null default 'created'
    check (status in ('created', 'quoted', 'executing', 'sent', 'failed', 'cancelled')),

  -- Pricing + decision outputs (persisted for transparency)
  quote_payload jsonb,
  selected_route_id uuid,
  total_fee numeric(20, 8),
  fx_rate numeric(30, 12),
  fx_spread numeric(20, 8),
  all_in_total numeric(30, 8),
  delivery_eta_seconds integer,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists trg_transactions_updated_at on public.transactions;
create trigger trg_transactions_updated_at
before update on public.transactions
for each row
execute function public.set_updated_at();

create unique index if not exists transactions_user_id_idempotency_key_key
  on public.transactions(user_id, idempotency_key);
create index if not exists transactions_user_id_status_idx
  on public.transactions(user_id, status);
create index if not exists transactions_receiver_country_idx
  on public.transactions(receiver_country);

alter table public.transactions enable row level security;

drop policy if exists transactions_select_own on public.transactions;
create policy transactions_select_own
on public.transactions
for select
using (user_id = auth.uid() or public.is_admin());

drop policy if exists transactions_insert_own on public.transactions;
create policy transactions_insert_own
on public.transactions
for insert
with check (user_id = auth.uid() or public.is_admin());

drop policy if exists transactions_update_own on public.transactions;
create policy transactions_update_own
on public.transactions
for update
using (user_id = auth.uid() or public.is_admin())
with check (user_id = auth.uid() or public.is_admin());

create table if not exists public.routes (
  id uuid primary key default gen_random_uuid(),
  transaction_id uuid not null references public.transactions(id) on delete cascade,
  corridor_key text not null, -- e.g. "US->NG"

  -- rail_type is the final rail that delivers liquidity (stablecoin/ach/mobile_money)
  rail_type text not null check (rail_type in ('stablecoin', 'ach', 'mobile_money')),

  provider_path jsonb not null default '[]'::jsonb,

  fee_total numeric(20, 8) not null default 0,
  fx_rate numeric(30, 12),
  fx_spread numeric(20, 8) not null default 0,

  eta_seconds integer,
  cost_vs_speed_score numeric(20, 8),
  confidence numeric(20, 8),
  is_recommended boolean not null default false,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists trg_routes_updated_at on public.routes;
create trigger trg_routes_updated_at
before update on public.routes
for each row
execute function public.set_updated_at();

create index if not exists routes_transaction_id_idx on public.routes(transaction_id);
create index if not exists routes_is_recommended_idx on public.routes(transaction_id, is_recommended);

alter table public.routes enable row level security;

drop policy if exists routes_select_own on public.routes;
create policy routes_select_own
on public.routes
for select
using (
  public.is_admin() OR
  transaction_id in (
    select t.id
    from public.transactions t
    where t.user_id = auth.uid()
  )
);

drop policy if exists routes_insert_own on public.routes;
create policy routes_insert_own
on public.routes
for insert
with check (
  public.is_admin() OR
  transaction_id in (
    select t.id
    from public.transactions t
    where t.user_id = auth.uid()
  )
);

drop policy if exists routes_update_own on public.routes;
create policy routes_update_own
on public.routes
for update
using (
  public.is_admin() OR
  transaction_id in (
    select t.id
    from public.transactions t
    where t.user_id = auth.uid()
  )
)
with check (
  public.is_admin() OR
  transaction_id in (
    select t.id
    from public.transactions t
    where t.user_id = auth.uid()
  )
);

create table if not exists public.fx_rates (
  id uuid primary key default gen_random_uuid(),
  transaction_id uuid references public.transactions(id) on delete set null,

  base_currency char(3) not null,
  quote_currency char(3) not null,
  source text not null,
  rate numeric(30, 12) not null,
  spread numeric(20, 8) not null default 0,

  captured_at timestamptz not null default now(),
  valid_until timestamptz,
  metadata jsonb,

  created_at timestamptz not null default now()
);

create index if not exists fx_rates_transaction_id_idx on public.fx_rates(transaction_id);
create index if not exists fx_rates_currency_pair_idx on public.fx_rates(base_currency, quote_currency, captured_at desc);

alter table public.fx_rates enable row level security;

drop policy if exists fx_rates_select_own on public.fx_rates;
create policy fx_rates_select_own
on public.fx_rates
for select
using (
  public.is_admin() OR
  (
    transaction_id is not null AND
    transaction_id in (
      select t.id
      from public.transactions t
      where t.user_id = auth.uid()
    )
  )
);

drop policy if exists fx_rates_insert_own on public.fx_rates;
create policy fx_rates_insert_own
on public.fx_rates
for insert
with check (
  public.is_admin() OR
  (
    transaction_id is not null AND
    transaction_id in (
      select t.id
      from public.transactions t
      where t.user_id = auth.uid()
    )
  )
);

create table if not exists public.agents_logs (
  id uuid primary key default gen_random_uuid(),
  transaction_id uuid references public.transactions(id) on delete cascade,
  user_id uuid not null references public.users(id) on delete cascade,

  agent_name text not null,
  step_name text not null,
  trace_id text,
  input_json jsonb,
  output_json jsonb,
  confidence numeric(20, 8),
  error_json jsonb,

  created_at timestamptz not null default now()
);

create index if not exists agents_logs_transaction_id_idx on public.agents_logs(transaction_id);
create index if not exists agents_logs_user_id_agent_step_idx on public.agents_logs(user_id, agent_name, step_name, created_at desc);

alter table public.agents_logs enable row level security;

drop policy if exists agents_logs_select_own on public.agents_logs;
create policy agents_logs_select_own
on public.agents_logs
for select
using (public.is_admin() OR user_id = auth.uid());

drop policy if exists agents_logs_insert_own on public.agents_logs;
create policy agents_logs_insert_own
on public.agents_logs
for insert
with check (public.is_admin() OR user_id = auth.uid());

drop policy if exists agents_logs_update_own on public.agents_logs;
create policy agents_logs_update_own
on public.agents_logs
for update
using (public.is_admin() OR user_id = auth.uid())
with check (public.is_admin() OR user_id = auth.uid());

-- Realtime config for transaction tracking
alter table public.transactions replica identity full;
alter table public.routes replica identity full;

do $$
begin
  if not exists (
    select 1
    from pg_publication_tables
    where schemaname = 'public'
      and tablename in ('transactions', 'routes')
      and pubname = 'supabase_realtime'
  ) then
    -- If supabase_realtime exists but tables are not added, add them individually.
    begin
      execute 'alter publication supabase_realtime add table public.transactions';
    exception when others then
      null;
    end;

    begin
      execute 'alter publication supabase_realtime add table public.routes';
    exception when others then
      null;
    end;
  end if;
end;
$$;

commit;

