SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS profiles (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  domain TEXT NOT NULL,
  profile_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS domain_packs (
  id TEXT PRIMARY KEY,
  domain TEXT NOT NULL,
  version TEXT NOT NULL,
  schema_version INTEGER NOT NULL,
  config_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sources (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  type TEXT NOT NULL,
  config_json TEXT NOT NULL,
  enabled INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS import_runs (
  id TEXT PRIMARY KEY,
  source_id TEXT,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL,
  items_seen INTEGER DEFAULT 0,
  items_created INTEGER DEFAULT 0,
  items_updated INTEGER DEFAULT 0,
  error_json TEXT
);

CREATE TABLE IF NOT EXISTS items (
  id TEXT PRIMARY KEY,
  domain TEXT NOT NULL,
  source_name TEXT,
  source_url TEXT,
  deduplication_hash TEXT,
  title TEXT,
  price INTEGER,
  currency TEXT,
  location TEXT,
  seller_type TEXT,
  attributes_json TEXT,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS item_snapshots (
  id TEXT PRIMARY KEY,
  item_id TEXT NOT NULL,
  import_run_id TEXT,
  observed_at TEXT NOT NULL,
  title TEXT,
  price INTEGER,
  currency TEXT,
  description TEXT,
  raw_data_json TEXT,
  content_hash TEXT,
  FOREIGN KEY (item_id) REFERENCES items(id)
);

CREATE TABLE IF NOT EXISTS ai_analysis_runs (
  id TEXT PRIMARY KEY,
  item_id TEXT NOT NULL,
  snapshot_id TEXT NOT NULL,
  profile_id TEXT NOT NULL,
  domain_pack_id TEXT NOT NULL,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  prompt_version TEXT NOT NULL,
  input_hash TEXT,
  output_json TEXT,
  validation_status TEXT NOT NULL,
  token_usage_json TEXT,
  estimated_cost REAL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (item_id) REFERENCES items(id),
  FOREIGN KEY (snapshot_id) REFERENCES item_snapshots(id),
  FOREIGN KEY (profile_id) REFERENCES profiles(id),
  FOREIGN KEY (domain_pack_id) REFERENCES domain_packs(id)
);

CREATE TABLE IF NOT EXISTS item_scores (
  id TEXT PRIMARY KEY,
  item_id TEXT NOT NULL,
  profile_id TEXT NOT NULL,
  analysis_run_id TEXT,
  fit_score INTEGER,
  value_score INTEGER,
  risk_score INTEGER,
  condition_score INTEGER,
  convenience_score INTEGER,
  overall_score INTEGER,
  explanation TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (item_id) REFERENCES items(id),
  FOREIGN KEY (profile_id) REFERENCES profiles(id)
);

CREATE TABLE IF NOT EXISTS feedback_events (
  id TEXT PRIMARY KEY,
  item_id TEXT NOT NULL,
  profile_id TEXT NOT NULL,
  feedback_type TEXT NOT NULL,
  reason TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (item_id) REFERENCES items(id),
  FOREIGN KEY (profile_id) REFERENCES profiles(id)
);
"""
