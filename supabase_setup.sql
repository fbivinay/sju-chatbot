-- Run this once in the Supabase SQL Editor before running scrape_playwright.py.
-- Sets up Postgres full-text search over the sju_knowledge table (no embeddings).

-- GIN index makes full-text search fast.
create index if not exists sju_knowledge_fts_idx
  on sju_knowledge using gin (to_tsvector('english', content));

-- Keyword search used by main.py's search_supabase().
-- websearch_to_tsquery lets users type natural queries ("bba fees", "phd admission").
drop function if exists match_sju_knowledge(vector, integer);

create or replace function match_sju_knowledge(query text, match_count int default 6)
returns table (content text, page_name text, source_url text, rank real)
language sql stable
as $$
  select content, page_name, source_url,
         ts_rank(to_tsvector('english', content), websearch_to_tsquery('english', query)) as rank
  from sju_knowledge
  where to_tsvector('english', content) @@ websearch_to_tsquery('english', query)
  order by rank desc
  limit match_count;
$$;
