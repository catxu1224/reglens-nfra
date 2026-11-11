CREATE TABLE IF NOT EXISTS nfra_penalties (
  source_key TEXT PRIMARY KEY CHECK (length(source_key) = 64),
  source_row_number INTEGER NOT NULL,
  content_hash TEXT NOT NULL CHECK (length(content_hash) = 64),
  company TEXT,
  branch TEXT,
  person TEXT,
  institution_type TEXT,
  institution_sector TEXT NOT NULL CHECK (institution_sector IN ('银行', '保险', '其他')),
  decision_no TEXT,
  region TEXT,
  agency TEXT,
  violation TEXT,
  decision_text TEXT,
  penalty_subject TEXT CHECK (penalty_subject IN ('机构', '个人')),
  legal_basis TEXT,
  amount_raw TEXT,
  amount_yuan NUMERIC(20, 2),
  published_date DATE NOT NULL,
  risk_points TEXT,
  penalty_types TEXT,
  causes TEXT,
  penalty_authority TEXT,
  notice_url TEXT,
  source_update_time TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS nfra_penalties_published_idx ON nfra_penalties (published_date DESC);
CREATE INDEX IF NOT EXISTS nfra_penalties_sector_date_idx ON nfra_penalties (institution_sector, published_date DESC);
CREATE INDEX IF NOT EXISTS nfra_penalties_institution_type_idx ON nfra_penalties (institution_type);
CREATE INDEX IF NOT EXISTS nfra_penalties_region_idx ON nfra_penalties (region);
CREATE INDEX IF NOT EXISTS nfra_penalties_notice_url_idx ON nfra_penalties (notice_url);
