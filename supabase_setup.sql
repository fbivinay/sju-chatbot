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
alter table sju_knowledge_staging enable row level security;   -- no policies: public keys can't touch it
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
  delete from public.sju_knowledge;
  insert into public.sju_knowledge (content, source_url, page_name)
    select distinct on (md5(content)) content, source_url, page_name
      from public.sju_knowledge_staging
     where content <> ''
     order by md5(content), id;
  delete from public.sju_knowledge_staging;
  return new_count;
end $$;
revoke execute on function swap_sju_knowledge(real) from public, anon, authenticated;
grant execute on function swap_sju_knowledge(real) to service_role;
