CREATE SEQUENCE project_number_seq;

CREATE TABLE project (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code text UNIQUE NOT NULL,
  name text NOT NULL,
  project_type text NOT NULL,
  department_system_id int REFERENCES department_system(id),
  owner_user_id int REFERENCES app_user(id),
  area_id int NOT NULL REFERENCES area(id),
  current_stage_key text NOT NULL DEFAULT 'need_identified',
  status text NOT NULL DEFAULT 'active',
  approved_budget numeric(14,2) DEFAULT 0,
  forecast_cost numeric(14,2) DEFAULT 0,
  actual_cost numeric(14,2) DEFAULT 0,
  target_start_date date,
  target_completion_date date,
  location geometry(Geometry, 4326),
  description text,
  details jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX project_area_idx ON project (area_id);
CREATE INDEX project_stage_idx ON project (current_stage_key);
CREATE INDEX project_status_idx ON project (status);

CREATE TABLE project_stage_history (
  id bigserial PRIMARY KEY,
  project_id uuid NOT NULL REFERENCES project(id) ON DELETE CASCADE,
  from_stage text,
  to_stage text NOT NULL,
  decision text NOT NULL DEFAULT 'advanced',
  who_user_id int NOT NULL REFERENCES app_user(id),
  reviewer_user_id int REFERENCES app_user(id),
  comments text,
  evidence_url text,
  happened_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX project_stage_history_project_idx ON project_stage_history (project_id, happened_at);

CREATE TABLE project_asset (
  project_id uuid NOT NULL REFERENCES project(id) ON DELETE CASCADE,
  asset_id uuid NOT NULL REFERENCES asset(id) ON DELETE CASCADE,
  relation_kind text NOT NULL DEFAULT 'creates',
  linked_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (project_id, asset_id)
);

CREATE INDEX project_asset_asset_idx ON project_asset (asset_id);

CREATE TABLE project_item (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES project(id) ON DELETE CASCADE,
  item_type text NOT NULL,
  title text NOT NULL,
  status text NOT NULL DEFAULT 'open',
  severity text,
  due_date date,
  owner_user_id int REFERENCES app_user(id),
  data jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX project_item_project_idx ON project_item (project_id, item_type);
