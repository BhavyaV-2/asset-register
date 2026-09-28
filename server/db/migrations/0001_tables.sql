CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE area_level (
  rank int PRIMARY KEY,               -- 1 = top
  name text NOT NULL                  -- State, District, City, Ward ... (admin can change)
);

CREATE TABLE area (
  id serial PRIMARY KEY,
  parent_id int REFERENCES area(id),
  name text NOT NULL,
  level_rank int NOT NULL REFERENCES area_level(rank),
  path text NOT NULL,                 -- e.g. '/1/4/9/'  (ids of all parents and itself)
  UNIQUE (parent_id, name)
);
CREATE INDEX area_path_idx ON area (path text_pattern_ops);

CREATE TABLE app_user (
  id serial PRIMARY KEY,
  email text UNIQUE NOT NULL,
  full_name text NOT NULL,
  password_hash text NOT NULL,
  role text NOT NULL CHECK (role IN ('viewer','editor','reviewer','admin')),
  area_id int REFERENCES area(id),    -- NULL = all areas
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE asset_family (
  id serial PRIMARY KEY,
  name text UNIQUE NOT NULL,
  sort_order int NOT NULL
);

CREATE TABLE asset_type (
  id serial PRIMARY KEY,
  family_id int NOT NULL REFERENCES asset_family(id),
  key text UNIQUE NOT NULL,           -- 'road', 'street_light' ...
  name text NOT NULL,
  usual_shape text NOT NULL CHECK (usual_shape IN ('point','line','area')),
  detail_fields jsonb NOT NULL DEFAULT '[]',   -- [{key,label,kind,choices?}]
  stages jsonb NOT NULL                          -- [{key,label,is_end}]
);

CREATE TABLE department_system (
  id serial PRIMARY KEY,
  name text UNIQUE NOT NULL,          -- 'Roads Department road list'
  department_name text NOT NULL,
  connection text NOT NULL CHECK (connection IN ('file','web_address')),
  web_address text,
  default_area_id int REFERENCES area(id),
  fixed_asset_type_id int REFERENCES asset_type(id),  -- whole system is one type, OR
  column_mapping jsonb NOT NULL DEFAULT '{}',          -- see 5.3
  is_full_list boolean NOT NULL DEFAULT false,         -- can "missing" be detected?
  default_stage_key text NOT NULL DEFAULT 'in_use',
  last_imported_at timestamptz
);

CREATE SEQUENCE asset_number_seq;

CREATE TABLE asset (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  register_code text UNIQUE NOT NULL,             -- 'AR-0000123'
  asset_type_id int NOT NULL REFERENCES asset_type(id),
  area_id int NOT NULL REFERENCES area(id),
  name text,
  location geometry(Geometry, 4326) NOT NULL,
  stage_key text NOT NULL,
  details jsonb NOT NULL DEFAULT '{}',            -- official details, from main department record
  main_link_id bigint,                            -- set after first link is created
  is_active boolean NOT NULL DEFAULT true,        -- false = approved as missing/removed
  last_checked_at timestamptz,                    -- last time a department file confirmed it
  open_problem_count int NOT NULL DEFAULT 0,      -- kept up to date by the server
  warranty_start date,                            -- from the linked contract with the latest end
  warranty_end date,
  repair_hold boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX asset_location_idx ON asset USING gist (location);
CREATE INDEX asset_location_geog_idx ON asset USING gist ((location::geography));
CREATE INDEX asset_area_type_idx ON asset (area_id, asset_type_id);
CREATE INDEX asset_name_idx ON asset USING gin (name gin_trgm_ops);
CREATE INDEX asset_checked_idx ON asset (last_checked_at);

CREATE TABLE source_link (                        -- one department's record of an asset
  id bigserial PRIMARY KEY,
  asset_id uuid NOT NULL REFERENCES asset(id),
  department_system_id int NOT NULL REFERENCES department_system(id),
  source_id text NOT NULL,                        -- the department's own ID for it
  is_main boolean NOT NULL DEFAULT false,
  official_record jsonb NOT NULL,                 -- the row as last accepted (name, stage, details, raw)
  last_seen_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (department_system_id, source_id)
);
CREATE INDEX source_link_asset_idx ON source_link (asset_id);
ALTER TABLE asset ADD FOREIGN KEY (main_link_id) REFERENCES source_link(id);

CREATE TABLE import_batch (
  id bigserial PRIMARY KEY,
  department_system_id int NOT NULL REFERENCES department_system(id),
  started_by int NOT NULL REFERENCES app_user(id),
  file_name text,
  status text NOT NULL DEFAULT 'waiting' CHECK (status IN ('waiting','running','done','failed')),
  rows_total int NOT NULL DEFAULT 0,
  rows_same int NOT NULL DEFAULT 0,
  rows_new int NOT NULL DEFAULT 0,
  rows_changed int NOT NULL DEFAULT 0,
  rows_possible_match int NOT NULL DEFAULT 0,
  rows_missing int NOT NULL DEFAULT 0,
  rows_skipped_before int NOT NULL DEFAULT 0,     -- already asked and rejected earlier
  rows_with_problems int NOT NULL DEFAULT 0,
  message text,
  started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz
);

CREATE TABLE import_problem_row (
  id bigserial PRIMARY KEY,
  batch_id bigint NOT NULL REFERENCES import_batch(id),
  row_number int NOT NULL,
  message text NOT NULL,
  row_text text
);

CREATE TABLE change_request (
  id bigserial PRIMARY KEY,
  kind text NOT NULL CHECK (kind IN
    ('add_asset','update_asset','link_asset','mark_missing','add_contract','update_contract','warranty_claim')),
  status text NOT NULL DEFAULT 'waiting' CHECK (status IN ('waiting','approved','rejected')),
  asset_id uuid REFERENCES asset(id),
  area_id int NOT NULL REFERENCES area(id),       -- used for access limits
  batch_id bigint REFERENCES import_batch(id),
  department_system_id int REFERENCES department_system(id),
  summary text NOT NULL,                          -- one plain sentence
  proposed jsonb NOT NULL,                        -- what will be applied
  current jsonb,                                  -- what it looks like now (for before/after)
  match_candidates jsonb,                         -- for link_asset: [{asset_id, reason, distance_m}]
  fingerprint text,                               -- stops asking the same question twice
  created_by int NOT NULL REFERENCES app_user(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  decided_by int REFERENCES app_user(id),
  decided_at timestamptz,
  decision_note text,
  decision_choice text                            -- e.g. 'same_asset', 'different_asset', 'bad_workmanship'
);
CREATE INDEX change_request_status_idx ON change_request (status, kind, area_id);
CREATE INDEX change_request_fingerprint_idx ON change_request (fingerprint);

CREATE TABLE contract (
  id serial PRIMARY KEY,
  contract_number text UNIQUE NOT NULL,
  title text NOT NULL,
  contractor_name text NOT NULL,
  start_date date,
  completion_date date NOT NULL,
  warranty_months int NOT NULL CHECK (warranty_months >= 0),
  warranty_end_date date NOT NULL,                -- set by the server
  cost_amount numeric(15,2),
  notes text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE contract_asset (
  contract_id int NOT NULL REFERENCES contract(id),
  asset_id uuid NOT NULL REFERENCES asset(id),
  PRIMARY KEY (contract_id, asset_id)
);
CREATE INDEX contract_asset_asset_idx ON contract_asset (asset_id);

CREATE TABLE problem_report (
  id bigserial PRIMARY KEY,
  asset_id uuid NOT NULL REFERENCES asset(id),
  reported_by int NOT NULL REFERENCES app_user(id),
  description text NOT NULL,
  urgency text NOT NULL CHECK (urgency IN ('minor','major','urgent')),
  status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','with_contractor','closed')),
  under_warranty boolean NOT NULL DEFAULT false,
  contract_id int REFERENCES contract(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  closed_at timestamptz,
  closing_note text
);

CREATE TABLE warranty_claim (
  id bigserial PRIMARY KEY,
  problem_report_id bigint NOT NULL REFERENCES problem_report(id),
  contract_id int NOT NULL REFERENCES contract(id),
  approved_by int NOT NULL REFERENCES app_user(id),
  status text NOT NULL DEFAULT 'sent' CHECK (status IN ('sent','fixed_by_contractor','closed_without_fix')),
  sent_at timestamptz NOT NULL DEFAULT now(),
  closed_at timestamptz,
  closing_note text
);

CREATE TABLE photo (
  id bigserial PRIMARY KEY,
  asset_id uuid NOT NULL REFERENCES asset(id),
  problem_report_id bigint REFERENCES problem_report(id),
  uploaded_by int NOT NULL REFERENCES app_user(id),
  content_type text NOT NULL,
  file_bytes bytea,                                -- used when PHOTO_STORAGE=database
  file_key text,                                   -- used when PHOTO_STORAGE=s3
  taken_lat double precision,                      -- from the phone, if allowed; a hint only
  taken_lon double precision,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE asset_note (
  id bigserial PRIMARY KEY,
  asset_id uuid NOT NULL REFERENCES asset(id),
  user_id int NOT NULL REFERENCES app_user(id),
  kind text NOT NULL CHECK (kind IN ('note','correction_for_department')),
  body text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE history_entry (
  id bigserial PRIMARY KEY,
  asset_id uuid NOT NULL REFERENCES asset(id),
  happened_at timestamptz NOT NULL DEFAULT now(),
  who_user_id int REFERENCES app_user(id),
  what text NOT NULL,             -- 'added','changed','linked','marked_missing','problem_reported',
                                  -- 'warranty_claim_sent','photo_added','note_added','contract_linked', ...
  summary text NOT NULL,          -- plain sentence
  before_value jsonb,
  after_value jsonb,
  change_request_id bigint REFERENCES change_request(id)
);
CREATE INDEX history_asset_idx ON history_entry (asset_id, happened_at DESC);

CREATE TABLE app_setting (key text PRIMARY KEY, value text NOT NULL);
INSERT INTO app_setting VALUES
  ('second_person_must_approve','true'),
  ('match_distance_metres','25'),
  ('name_match_score','0.5'),
  ('missing_share_limit','0.3'),
  ('not_checked_months','12');
