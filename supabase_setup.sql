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
drop function if exists match_sju_knowledge(vector, integer);

create or replace function match_sju_knowledge(query text, match_count int default 6)
returns table (content text, page_name text, source_url text, rank real)
language sql stable
as $$
  with q as (
    select nullif(replace(plainto_tsquery('english', query)::text, '&', '|'), '')::tsquery as tsq
  )
  select k.content, k.page_name, k.source_url,
         ts_rank(to_tsvector('english', k.content), q.tsq) as rank
  from sju_knowledge k, q
  where q.tsq is not null
    and to_tsvector('english', k.content) @@ q.tsq
  order by rank desc
  limit match_count;
$$;
