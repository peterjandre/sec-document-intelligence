create extension if not exists vector;

-- Prefixed so these objects stay distinct from other projects in the same Supabase.
create table if not exists sec_document_intelligence_documents (
  document_id text primary key,
  ticker text,
  filing_year int not null default 2025
);

create table if not exists sec_document_intelligence_chunks (
  chunk_id text primary key,
  document_id text not null references sec_document_intelligence_documents(document_id) on delete cascade,
  section text not null,
  text text not null,
  char_range_start int not null,
  char_range_end int not null
);

create table if not exists sec_document_intelligence_chunk_embeddings (
  chunk_id text primary key references sec_document_intelligence_chunks(chunk_id) on delete cascade,
  embedding vector(1536),
  metadata jsonb default '{}'::jsonb
);

create index if not exists idx_sec_document_intelligence_chunks_document_id
  on sec_document_intelligence_chunks(document_id);
create index if not exists idx_sec_document_intelligence_documents_filing_year
  on sec_document_intelligence_documents(filing_year);
create index if not exists idx_sec_document_intelligence_documents_ticker
  on sec_document_intelligence_documents(ticker);
create index if not exists idx_sec_document_intelligence_chunk_embeddings_vector
  on sec_document_intelligence_chunk_embeddings using ivfflat (embedding vector_cosine_ops);

create or replace function sec_document_intelligence_match_chunks(
  query_embedding vector(1536),
  match_count int,
  filter jsonb default '{}'::jsonb
)
returns table (
  chunk_id text,
  document_id text,
  section text,
  text text,
  similarity float
)
language sql
as $$
  select c.chunk_id, c.document_id, c.section, c.text,
         1 - (ce.embedding <=> query_embedding) as similarity
  from sec_document_intelligence_chunk_embeddings ce
  join sec_document_intelligence_chunks c on c.chunk_id = ce.chunk_id
  join sec_document_intelligence_documents d on d.document_id = c.document_id
  where
    (
      case
        when coalesce(filter, '{}'::jsonb) ? 'filing_years' then
          d.filing_year in (
            select jsonb_array_elements_text(filter->'filing_years')::int
          )
        when coalesce(filter, '{}'::jsonb) ? 'filing_year' then
          d.filing_year = (filter->>'filing_year')::int
        else true
      end
    )
    and (
      case
        when coalesce(filter, '{}'::jsonb) ? 'tickers' then
          upper(d.ticker) in (
            select upper(jsonb_array_elements_text(filter->'tickers'))
          )
        when coalesce(filter, '{}'::jsonb) ? 'ticker' then
          upper(d.ticker) = upper(filter->>'ticker')
        else true
      end
    )
  order by ce.embedding <=> query_embedding
  limit match_count;
$$;
