-- Run this once in the Supabase SQL Editor before running scrape_playwright.py.
-- Sets up Postgres full-text search over the sju_knowledge table (no embeddings).

-- GIN index makes full-text search fast.
create index if not exists sju_knowledge_fts_idx
  on sju_knowledge using gin (to_tsvector('english', content));

-- Keyword search used by main.py's search_supabase().
-- OR semantics (not websearch_to_tsquery's AND): natural-language questions like
-- "who are the professors in advanced computing" match on ANY term, ranked by
-- ts_rank so the most relevant chunks come first. AND semantics returned nothing
-- when a query contained a word absent from every chunk (e.g. "list").
-- search_path is pinned (Supabase lint 0011), so the table is schema-qualified.
create or replace function match_sju_knowledge(query text, match_count int default 6)
returns table (content text, page_name text, source_url text, rank real)
language sql stable
set search_path = ''
as $$
  with q as (
    select nullif(replace(plainto_tsquery('english', query)::text, '&', '|'), '')::tsquery as tsq
  )
  select k.content, k.page_name, k.source_url,
         ts_rank(to_tsvector('english', k.content), q.tsq) as rank
  from public.sju_knowledge k, q
  where q.tsq is not null
    and to_tsvector('english', k.content) @@ q.tsq
  order by rank desc
  limit match_count;
$$;

-- Anyone holding the publishable key may only read. The scraper writes with a
-- secret key, which bypasses RLS.
alter table sju_knowledge enable row level security;
drop policy if exists "Allow public read" on sju_knowledge;
create policy "Allow public read" on sju_knowledge for select using (true);
revoke insert, update, delete, truncate on sju_knowledge from anon, authenticated;

-- The same text can never be stored twice, whatever writes to the table.
create unique index if not exists sju_knowledge_content_key on sju_knowledge (md5(content));

-- The daily refresh loads here first; the live table only changes in swap_sju_knowledge().
create table if not exists sju_knowledge_staging (
  id bigint generated always as identity primary key,
  content text not null,
  source_url text,
  page_name text
);
alter table sju_knowledge_staging enable row level security;
drop policy if exists "No public access" on sju_knowledge_staging;
create policy "No public access" on sju_knowledge_staging
  for all to anon, authenticated using (false) with check (false);   -- only the secret key (bypasses RLS)
revoke all on sju_knowledge_staging from anon, authenticated;

-- Replace the live knowledge base with the staged scrape in one transaction, so the bot
-- sees either the old set or the new one, never a half-loaded or doubled table. Refuses
-- a scrape that came back much smaller than what's live (site down, layout change).
create or replace function swap_sju_knowledge(min_ratio real default 0.6)
returns integer
language plpgsql
set search_path = ''
as $$
declare
  new_count integer;
  old_count integer;
begin
  perform pg_advisory_xact_lock(hashtext('swap_sju_knowledge'));
  select count(distinct md5(content)) into new_count from public.sju_knowledge_staging where content <> '';
  select count(*) into old_count from public.sju_knowledge;
  if new_count < greatest(50, old_count * min_ratio) then
    raise exception 'refusing to swap: scrape has % chunks, live table has %', new_count, old_count;
  end if;
  delete from public.sju_knowledge where true;   -- API sessions reject a bare DELETE (pg-safeupdate)
  insert into public.sju_knowledge (content, source_url, page_name)
    select distinct on (md5(content)) content, source_url, page_name
      from public.sju_knowledge_staging
     where content <> ''
     order by md5(content), id;
  delete from public.sju_knowledge_staging where true;
  return new_count;
end $$;
revoke execute on function swap_sju_knowledge(real) from public, anon, authenticated;
grant execute on function swap_sju_knowledge(real) to service_role;

-- ── Global per-IP rate limit for the chat API ──────────────────────────────────
-- The app also limits per instance in memory, but Vercel runs several instances, so
-- that caps at 15/min x instances. This table is the shared, authoritative counter.
-- Written only by the SECURITY DEFINER function below; direct access is denied.
create table if not exists public.sju_rate_limit (
  ip           text primary key,
  minute_start timestamptz not null default now(),
  minute_count int not null default 0,
  day          date not null default (now() at time zone 'utc')::date,
  day_count    int not null default 0
);
alter table public.sju_rate_limit enable row level security;
revoke all on public.sju_rate_limit from anon, authenticated;

-- Atomically roll the minute/day windows, count this hit, and say whether it's allowed.
-- One row locked per IP (distinct IPs never contend). SECURITY DEFINER so the bot's
-- publishable key can run it without direct table access.
--
-- The limits are CONSTANTS here, not parameters: a caller (anyone holding the
-- publishable key) must not be able to pass its own huge cap and bypass the limit.
-- p_ip is validated to an IP/CIDR shape so a stray caller can't fill the table with
-- junk keys. Malformed input is treated as blocked (safe default; the app never
-- sends it). This keeps the function callable by the app's publishable key. For a
-- stricter posture, restrict the grant to service_role and call it with the secret key.
drop function if exists public.sju_rate_check(text, int, int);
create or replace function public.sju_rate_check(p_ip text)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  max_min constant int := 15;    -- keep in sync with RATE_MAX in main.py
  max_day constant int := 300;   -- keep in sync with RATE_DAY_MAX in main.py
  key    text;
  r      public.sju_rate_limit%rowtype;
  now_ts timestamptz := now();
  today  date := (now() at time zone 'utc')::date;
  ok     boolean;
begin
  if p_ip is null or length(p_ip) > 64 then
    return false;
  elsif p_ip in ('invalid', 'unknown') then
    key := p_ip;                 -- the app's two sentinels for a missing/unparseable IP
  else
    begin
      key := text(p_ip::inet);   -- real IP/CIDR parse; canonical form dedupes spellings
    exception when others then
      return false;              -- not a valid address: reject without creating a row
    end;
  end if;
  insert into public.sju_rate_limit(ip) values (key) on conflict (ip) do nothing;
  select * into r from public.sju_rate_limit where ip = key for update;
  if now_ts - r.minute_start >= interval '60 seconds' then
    r.minute_start := now_ts; r.minute_count := 0;
  end if;
  if r.day <> today then
    r.day := today; r.day_count := 0;
  end if;
  ok := r.minute_count < max_min and r.day_count < max_day;
  if ok then
    r.minute_count := r.minute_count + 1;
    r.day_count := r.day_count + 1;
  end if;
  update public.sju_rate_limit
     set minute_start = r.minute_start, minute_count = r.minute_count,
         day = r.day, day_count = r.day_count
   where ip = key;
  -- occasionally sweep rows idle for over a day, so the table can't grow forever.
  -- ponytail: random sweep; a scheduled job (pg_cron) would be tidier if it ever matters.
  if random() < 0.005 then
    delete from public.sju_rate_limit
     where day < today and minute_start < now_ts - interval '1 day';
  end if;
  return ok;
end $$;
revoke execute on function public.sju_rate_check(text) from public;
grant  execute on function public.sju_rate_check(text) to anon, authenticated, service_role;

-- Heartbeat for .github/workflows/refresh-knowledge.yml. Supabase pauses a free
-- project after 7 days without activity; the daily scrape writes nothing when it
-- captures nothing (site down), so this writes one timestamp twice a day regardless.
create table if not exists public.keepalive (
  id int primary key,
  pinged_at timestamptz not null default now()
);
alter table public.keepalive enable row level security;
revoke all on public.keepalive from anon, authenticated;

create or replace function public.keepalive()
returns timestamptz
language sql
set search_path = ''
as $$
  insert into public.keepalive (id, pinged_at) values (1, now())
  on conflict (id) do update set pinged_at = now()
  returning pinged_at;
$$;
revoke execute on function public.keepalive() from public, anon, authenticated;
grant  execute on function public.keepalive() to service_role;
