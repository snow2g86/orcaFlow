-- OrcaFlow SQLite schema v1 (schema.md §7.3)
-- Applied when PRAGMA user_version == 0, then user_version := 1.

CREATE TABLE IF NOT EXISTS workflows (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  version INTEGER NOT NULL,
  yaml TEXT NOT NULL,
  policy_id TEXT REFERENCES policies(id),
  default_llm_profile_id TEXT REFERENCES llm_profiles(id),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS providers (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  kind TEXT NOT NULL,
  base_url TEXT NOT NULL,
  api_key_ref TEXT,
  headers_json TEXT,
  timeout_ms INTEGER DEFAULT 30000,
  health_url TEXT
);

CREATE TABLE IF NOT EXISTS llm_profiles (
  id TEXT PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  provider_id TEXT NOT NULL REFERENCES providers(id) ON DELETE RESTRICT,
  model TEXT NOT NULL,
  params_json TEXT NOT NULL,
  context_window INTEGER,
  is_tool_capable INTEGER NOT NULL DEFAULT 1,
  is_planner INTEGER NOT NULL DEFAULT 0,
  is_default INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS agent_roles (
  id TEXT PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  display_name TEXT,
  role_type TEXT NOT NULL CHECK(role_type IN ('worker','planner','supervisor','critic')),
  system_prompt TEXT NOT NULL,
  goal TEXT,
  tools_json TEXT NOT NULL,
  llm_profile_id TEXT NOT NULL REFERENCES llm_profiles(id) ON DELETE RESTRICT,
  max_steps INTEGER DEFAULT 10,
  temperature_override REAL,
  tags_json TEXT
);

CREATE TABLE IF NOT EXISTS policies (
  id TEXT PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  mode TEXT NOT NULL CHECK(mode IN ('strict','ask','trusted')),
  yaml TEXT NOT NULL,
  require_dry_run_for_json TEXT,
  auto_approve_reversible INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS policy_rules (
  id TEXT PRIMARY KEY,
  policy_id TEXT NOT NULL REFERENCES policies(id) ON DELETE CASCADE,
  priority INTEGER NOT NULL,
  scope TEXT NOT NULL,
  matcher TEXT NOT NULL,
  effect TEXT NOT NULL CHECK(effect IN ('allow','deny','ask','dry_run_only')),
  reason TEXT
);

CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY,
  workflow_id TEXT NOT NULL REFERENCES workflows(id),
  workflow_snapshot TEXT NOT NULL,
  trigger TEXT NOT NULL,
  status TEXT NOT NULL,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  stats_json TEXT,
  error_json TEXT,
  parent_run_id TEXT REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS run_steps (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  parent_step_id TEXT REFERENCES run_steps(id),
  node_id TEXT,
  kind TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  result_json TEXT,
  status TEXT NOT NULL,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  duration_ms INTEGER,
  tokens_in INTEGER,
  tokens_out INTEGER
);

CREATE TABLE IF NOT EXISTS tool_calls (
  id TEXT PRIMARY KEY,
  run_step_id TEXT NOT NULL REFERENCES run_steps(id) ON DELETE CASCADE,
  tool_id TEXT NOT NULL,
  args_json TEXT NOT NULL,
  result_json TEXT,
  error_json TEXT,
  dry_run INTEGER NOT NULL DEFAULT 0,
  policy_decision TEXT NOT NULL,
  audit_log_id TEXT,
  duration_ms INTEGER
);

CREATE TABLE IF NOT EXISTS approval_requests (
  id TEXT PRIMARY KEY,
  run_step_id TEXT NOT NULL REFERENCES run_steps(id) ON DELETE CASCADE,
  tool_call_id TEXT REFERENCES tool_calls(id),
  reason TEXT NOT NULL,
  diff_preview_json TEXT,
  state TEXT NOT NULL,
  decided_at TEXT,
  decided_by TEXT,
  ttl_seconds INTEGER DEFAULT 300
);

CREATE TABLE IF NOT EXISTS audit_logs (
  id TEXT PRIMARY KEY,
  at TEXT NOT NULL,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  target TEXT NOT NULL,
  status TEXT NOT NULL,
  policy_decision TEXT NOT NULL,
  run_id TEXT NOT NULL,
  run_step_id TEXT NOT NULL,
  hash_prev TEXT,
  hash_self TEXT
);
-- Application layer enforces append-only. No UPDATE/DELETE paths exposed.

CREATE TABLE IF NOT EXISTS journal_entries (
  id TEXT PRIMARY KEY,
  run_step_id TEXT NOT NULL REFERENCES run_steps(id) ON DELETE CASCADE,
  tool_call_id TEXT NOT NULL REFERENCES tool_calls(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,
  before_json TEXT,
  after_json TEXT,
  before_storage_ref TEXT,
  after_storage_ref TEXT,
  reversible INTEGER NOT NULL,
  restored_at TEXT,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_run_steps_run ON run_steps(run_id);
CREATE INDEX IF NOT EXISTS idx_tool_calls_step ON tool_calls(run_step_id);
CREATE INDEX IF NOT EXISTS idx_audit_run ON audit_logs(run_id);
CREATE INDEX IF NOT EXISTS idx_audit_at ON audit_logs(at);
CREATE INDEX IF NOT EXISTS idx_journal_run_step ON journal_entries(run_step_id);
