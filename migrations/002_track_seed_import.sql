ALTER TABLE nfra_penalties
  ADD COLUMN IF NOT EXISTS seed_origin TEXT NOT NULL DEFAULT 'snapshot';

CREATE TABLE IF NOT EXISTS nfra_seed_imports (
  name TEXT PRIMARY KEY,
  content_hash TEXT NOT NULL,
  imported_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
