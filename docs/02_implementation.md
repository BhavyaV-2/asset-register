# Asset Register — Implementation Details

Read `01_architecture.md` first. This document says exactly how to build it, **from the bottom up**: database, then server, then website, then test data, then hosting.
Read `04_extras.md` for the asset catalog, plain-words glossary, sample data plan, website text, commit rules and checklist.

Rules for the builder
- Use plain words in code names, screen text, comments and commit messages (see the glossary in `04_extras.md`).
- Build only what these documents ask for. When something is unclear, choose the simplest option and write it in `docs/OPEN_POINTS.md`.
- Never claim something works unless you ran it. Say what you ran in the handover note.

---

## 1. Stack (kept small on purpose)

| Part | Choice | Notes |
|---|---|---|
| Server | Python 3.12, FastAPI, Uvicorn | One app, no worker process |
| Database access | `psycopg` 3 with a connection pool, plain SQL | No ORM. SQL is readable and map functions are easier |
| Database | PostgreSQL 16+ with `postgis` and `pg_trgm` | Render Postgres supports both [H] |
| Passwords and sign-in | `bcrypt`, signed tokens (PyJWT) | Token lasts 8 hours |
| Website | React 18, TypeScript, Vite, React Router | Plain CSS, no UI kit |
| Map | MapLibre GL JS | Base map: OpenStreetMap raster tiles for the demo |
| File reading | Python `csv`, `json`; `pyshp` for zipped Shapefile | Shapefile only if in WGS84 latitude/longitude |
| Tests | `pytest` (server, against a real PostGIS test database), `vitest` (website), `tsc` type check | |

Repo layout

```
asset-register/
  README.md
  render.yaml                 # Render setup: server + database
  docs/
    01_architecture.md
    02_implementation.md
    architecture-diagram.svg  # exported picture
    architecture-diagram.mmd  # source
    OPEN_POINTS.md
    LOAD_TEST_RESULTS.md      # written by the load test
    HANDOVER.md
  server/
    Dockerfile
    requirements.txt
    app/
      main.py                 # starts the app, adds routes
      settings.py             # reads environment variables
      database.py             # connection pool, small helper functions
      people.py               # sign-in, roles, area limit
      areas.py
      asset_types.py
      department_systems.py
      imports/
        read_files.py         # CSV, GeoJSON, Shapefile -> plain rows
        map_columns.py        # apply a department system's column mapping
        compare.py            # compare rows with the register, make requests
      review.py               # list, approve, reject
      apply_changes.py        # what each kind of approved request does
      assets.py               # lists, one asset, history, notes
      contracts.py
      problems.py             # problem reports and warranty claims
      photos.py
      map_pieces.py           # map tiles
      reports.py
      file_store.py           # photo storage: database or S3
    db/
      migrations/0001_tables.sql ... (numbered)
      seed/asset_catalog.json
      seed/make_seed.py
    scripts/
      make_sample_files.py
      make_test_data.py
      time_the_map.py
    tests/
  web/
    package.json, vite.config.ts, vercel.json
    src/
      main.tsx, api.ts, text.ts, styles.css
      pages/ (SignIn, MapPage, AssetList, AssetPage, BringInData, ReviewQueue,
              ReviewItem, Contracts, ContractPage, Problems, Reports, Admin, HowItWorks)
      components/
```

---

## 2. Step 1 — Database (build this first)

Migrations are numbered `.sql` files. A tiny runner (`server/app/database.py`) applies missing ones in order and records them in a `schema_version` table. It runs at server start.

### 2.1 Extensions

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

### 2.2 Tables

Use plain names. All times are `timestamptz`. Dates for contracts are `date` and "today" always means today in `Asia/Kolkata`.

```sql
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
```

### 2.3 History cannot be changed (enforced in the database)

```sql
CREATE FUNCTION stop_history_changes() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION 'History entries cannot be changed or deleted'; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER history_no_change BEFORE UPDATE OR DELETE ON history_entry
  FOR EACH ROW EXECUTE FUNCTION stop_history_changes();
CREATE TRIGGER history_no_wipe BEFORE TRUNCATE ON history_entry
  FOR EACH STATEMENT EXECUTE FUNCTION stop_history_changes();
```

No endpoint deletes an asset. Assets are marked not active by an approved request.

### 2.4 Seed data (`server/db/seed/make_seed.py`)

Run once at first start, safe to run again.
1. Area levels: State, District, City, Zone or Ward (names are editable in Admin).
2. Sample areas: Gujarat > Gandhinagar district > Gandhinagar city > Sector 1 to Sector 8 (sample tree, editable).
3. Asset families, types, detail fields and default stages from `asset_catalog.json` (spec in `04_extras.md`).
4. Four demo users with `DEMO_PASSWORD` from the environment: `viewer@example.org`, `editor@example.org`, `reviewer@example.org`, `admin@example.org`. Refuse to start seeding if `DEMO_PASSWORD` is empty.
5. Sample department systems with saved column mappings (see `04_extras.md`, sample data plan).

### 2.5 Database tests (write now)
- History row cannot be updated, deleted or truncated.
- Two department records with the same `(department_system_id, source_id)` are rejected.
- Migrations run twice without error.

---

## 3. Step 2 — Server foundation

1. **`settings.py`**: reads `DATABASE_URL`, `SECRET_KEY`, `ALLOWED_ORIGINS` (comma list), `DEMO_PASSWORD`, `PHOTO_STORAGE`, `S3_*`, `MAX_UPLOAD_MB` (default 25), `TIME_ZONE` (default `Asia/Kolkata`). Change a `postgresql://` URL to `postgresql+psycopg://`-style only if the driver needs it; psycopg 3 accepts `postgresql://` directly.
2. **`database.py`**: pool (small: 5 to 10), helpers `one()`, `all()`, `run()`, and a `transaction()` context. Only parameterised queries. Never build SQL from user text.
3. **`main.py`**: creates the app, adds CORS for `ALLOWED_ORIGINS`, runs migrations at start, adds routes, `GET /health` (returns `{"ok": true}` and checks the database).
4. **Errors**: every error returns `{"message": "plain sentence"}` with a fitting status. Messages are written for people (for example "You can only see assets in Gandhinagar and the areas under it.").
5. **`people.py`**
   - `POST /auth/sign-in` with email and password. Wrong password gives one generic message. After 10 failed tries in 15 minutes for the same email and address, wait 15 minutes (kept in memory; note it in OPEN_POINTS that this resets on restart).
   - Password rule: at least 10 characters.
   - Token has user id and role, expires in 8 hours. `GET /me` returns name, role, area.
   - Dependencies: `need_role(...)` and `area_limit(user)` which returns the user's area path (or none = all). **Every query that returns assets, requests, contracts, problems, photos, reports or map pieces must apply the area limit.**

### Server foundation tests
- Wrong password, expired token, disabled user.
- Each role can and cannot reach each route (build a table-driven test from the route list in section 8).
- Area limit: a Sector 3 user cannot see Sector 4 assets by list, search, id, photo, map piece or report.

---

## 4. Step 3 — Setup screens' APIs (admin)

- `GET /areas` (tree), `POST /areas`, `PATCH /areas/{id}` (rename, move). Maintain `path` on create and move (update all children). Levels: `GET/PUT /area-levels`.
- `GET /asset-types` (families with types), `PATCH /asset-types/{id}` (name, detail fields, stages), `POST /asset-types`.
  - Stage rules: at least one stage; keys are lowercase words with underscores; the **last** stage marked `is_end` is shown as finished; a stage cannot be removed while assets use it (message names the count).
  - Detail field kinds: `text`, `number`, `date`, `choice` (with choices), `yes_no`.
- `GET/POST/PATCH /department-systems`. Includes column mapping (section 5.3), full-list flag, default area, default stage.
- `GET/PATCH /settings` (admin).
- Users: `GET/POST/PATCH /users` (admin): create, change role or area, deactivate. No delete.

---

## 5. Step 4 — Bringing data in (the heart of the system)

### 5.1 Steps for one import

1. `POST /imports` (multipart: `department_system_id`, `file`, optional `area_id`) or `POST /imports/from-web-address` (body: `department_system_id`). Editor or admin. Creates an `import_batch` (status waiting) and returns its id right away.
2. A background task processes it (FastAPI background task, same process). The website polls `GET /imports/{id}` every 2 seconds to show progress and counts.
3. Reading (`read_files.py`) turns the file into a list of plain rows (dictionary of column name to text). Limits: `MAX_UPLOAD_MB`, at most 200,000 rows per file. Rows are handled in groups of 500 in one database transaction each.
4. Column mapping (`map_columns.py`) turns each row into a standard row:

```
{ source_id, name, type_key, stage_key, geometry_wkt, details{}, raw{} }
```

5. Comparing (`compare.py`) decides what each standard row means (5.4) and writes requests.
6. When finished: set counts, `status='done'`, `finished_at`, and `department_system.last_imported_at`.

Failure rules: a bad row never stops the file. It is written to `import_problem_row` with its row number and a plain message. The batch is `failed` only if the file cannot be read at all, and then `message` says why.

### 5.2 Reading files
- **CSV**: detect the comma or semicolon separator; UTF-8 (also accept UTF-8 with a starting mark). Location from two columns (latitude, longitude) or one column of WKT text.
- **GeoJSON**: a FeatureCollection. Each feature's properties become the row; its geometry is the location.
- **Zipped Shapefile** (second priority): read with `pyshp`; if the `.prj` file says anything other than WGS84 latitude/longitude, stop with: "This Shapefile is not in latitude/longitude. Please convert it to WGS84 and upload again."
- **Web address**: fetch with a 30 second limit and 25 MB limit; treat the content by its type (CSV or GeoJSON). Only `https` addresses. Block private and local network addresses (`localhost`, `10.*`, `192.168.*`, `172.16–31.*`, `169.254.*`) so the server cannot be pointed at internal services.
- Location check: latitude −90 to 90, longitude −180 to 180, geometry not empty and valid (`ST_IsValid`; try `ST_MakeValid` once). Otherwise a problem row.

### 5.3 Saved column mapping (per department system)

```json
{
  "source_id": "road_id",
  "name": "road_name",
  "asset_type": { "fixed": "road" }
      // or { "column": "kind", "values": { "STL": "street_light", "Lamp": "street_light" } },
  "stage": { "column": "status", "values": { "Working": "in_use", "Broken": "needs_repair" } },
      // or omit: use the system's default stage
  "location": { "latitude": "lat", "longitude": "lon" }
      // or { "wkt": "geometry" } or { "geojson": true },
  "details": { "width_m": "width", "surface": "surface_type" }
      // optional; columns whose header matches a detail field's key or label are matched automatically
}
```

- A **mapping screen** on the Bring in Data page lets an editor or admin pick columns from lists after reading the first 20 rows of a sample file. It guesses by header words (id, name, lat, lon, type, status). It saves to the department system.
- Values that have no match in `asset_type.values` or `stage.values` become problem rows ("The type 'XYZ' is not in the mapping"). The screen shows the list of unmapped values so they can be mapped in one go.
- Details: coerce to the type's field kinds. If a value does not fit (for example "abc" in a number field), keep it in `details._not_understood` and add a warning to the batch; do not drop the row.
- Nothing is required except `source_id`, a type, and a valid location. Government data is messy; we keep what we can.

### 5.4 Comparing a row with the register (`compare.py`)

For each standard row:

1. **Find the department's own record**: `source_link` with same `(department_system_id, source_id)`.
   - **Found**:
     - Set `last_seen_at = now()` on the link. If it is the main link, set `asset.last_checked_at = now()`.
     - Compare with `official_record`: name, stage, details (after tidying text and numbers), and location (equal when the Hausdorff distance between the two shapes is under 1 metre, or both are equal after rounding to 6 decimals).
     - **Nothing different** → count as `same`.
     - **Different** → make an `update_asset` request with `current` (old) and `proposed` (new). If a waiting request for this asset with the same fingerprint exists, skip. If a rejected one with the same fingerprint exists, count as `skipped_before`.
   - **Not found**:
     2. **Look for the same asset from another record** (`link_asset` search): among **active assets of the same type, in the same area tree**, where:
        - points: within `match_distance_metres` (default 25);
        - lines: at least 80% of the shorter line lies within that distance of the other line;
        - areas: overlap is at least 60% of the smaller area;
        - and, when both have names, `similarity(name_a, name_b) >= name_match_score` (default 0.5, from `pg_trgm`).
        Keep the best 3 by closeness. These matches are **suggestions only**.
     3. Matches found → `link_asset` request with `match_candidates`. No match → `add_asset` request.
2. **After the last row** (only if `is_full_list` is true and the file was read completely): for every active asset whose main link belongs to this department system and has `last_seen_at < batch started_at`, make a `mark_missing` request. **Safety check**: if the missing ones are more than `missing_share_limit` (default 30%) of the assets from this system, make no missing requests and put a warning in `message`: "This file may be incomplete: 42% of the known assets are not in it. No 'missing' requests were made."
3. **Fingerprint** = hash of (department system id, source id, kind, normalised proposed content). Skipping by fingerprint means the same question is not asked twice, and a rejected request stays rejected unless the department's record changes again.
4. **Sentence for people** in `summary`, for example: "New street light in the Municipal lights list (ID L-2041), Sector 3." or "Width of Road R-18 changed from 6 m to 7.5 m in the Roads list."

The request's `area_id` is the batch's area (from the file, or the department system's default area).

Tests to write for this step (each with a tiny file)
- A first upload makes only `add_asset` requests; assets do not exist yet.
- The same file after approval → all `same`, and `last_checked_at` moves.
- A changed width makes one `update_asset` with a correct before/after.
- Two department lists with the same street light 10 m apart → `link_asset` with candidate.
- A full list missing 2 of 100 → 2 `mark_missing`; missing 40 of 100 → none and a warning.
- The same rejected row uploaded again → `skipped_before`.
- A bad latitude → problem row, other rows still processed.
- Web address to a private address is refused.

---

## 6. Step 5 — Review queue and what approval does

**APIs**
- `GET /change-requests?status=waiting&kind=&batch_id=&area_id=&q=` (reviewer, admin; viewers and editors can read but not decide; area limit applies).
- `GET /change-requests/{id}`
- `POST /change-requests/{id}/approve` body `{ "choice": "...", "note": "..." }`
- `POST /change-requests/{id}/reject` body `{ "note": "..." }` (note required)
- `POST /change-requests/approve-many` body `{ "ids": [...] }` (max 200; only `add_asset` and `update_asset`; each is still recorded under the reviewer's name; the screen asks "You are approving N items. Each will be recorded under your name.")

**Rules on every decision**
1. Reviewer or admin only.
2. If setting `second_person_must_approve` is true: `decided_by` must differ from `created_by`, else message "A different person must approve this request."
3. In one transaction: lock the request row (`SELECT ... FOR UPDATE`); if it is no longer `waiting`, message "This request was already decided."; apply; update status, `decided_by`, `decided_at`, note, choice; write history.
4. The person must have the request's area inside their area limit.

**What each kind does when approved** (`apply_changes.py`, each in its own function)

| Kind | Effect |
|---|---|
| `add_asset` | Create asset with the next `AR-` code (`'AR-' || lpad(nextval('asset_number_seq')::text, 7, '0')`), area, type, name, location, stage, details. Create the main `source_link`. `last_checked_at = now()`. History: "Added to the register from [system]." |
| `update_asset` | If the link is the asset's main link: update name, stage, location, details, `updated_at`; update the link's `official_record`. If not the main link: update only the link's record. History with before and after. |
| `link_asset` | Choice `same_asset` (with `asset_id` from the candidates): add a non-main `source_link` to that asset. Choice `different_asset`: behave as `add_asset`. History for the asset. |
| `mark_missing` | Set `is_active = false`. History: "No longer listed by [system]; approved as missing by [name]." (An import that lists it again makes an `update_asset`-style request that can turn it active again — see note below.) |
| `add_contract` / `update_contract` | Create or update the contract, compute `warranty_end_date = completion_date + warranty_months months`, replace `contract_asset` rows, then refresh warranty fields on all affected assets (section 7). History "Contract linked" on each asset. |
| `warranty_claim` | Choice `bad_workmanship`: create `warranty_claim` (status sent), set `problem_report.status = 'with_contractor'`, set `asset.repair_hold = true`. Any other choice (`damage_by_others`, `normal_wear`, `not_sure`): problem stays open; the choice and note are saved. History either way. |

Note on coming back: if an import row matches an existing link whose asset is not active, the comparison makes an `update_asset` request with `proposed.is_active = true`. Approving turns it active again.

Tests
- Approving twice at the same time changes the register once.
- The person who made a request cannot approve it (and can when the setting is off).
- A reviewer cannot decide a request outside their area.
- Each kind produces the right rows and history.
- Reject requires a note.

---

## 7. Step 6 — Contracts, problems and warranty

**Contracts**
- `POST /contracts` (editor, admin): body has contract fields plus `asset_ids` (or `import_batch_id` to include all assets created from that import). It creates a `change_request` of kind `add_contract` (nothing is in `contract` yet). Same for `PATCH /contracts/{id}` → `update_contract`.
- `GET /contracts`, `GET /contracts/{id}` (with linked assets, area limit applies through the assets).
- The contract page shows: warranty start, end, days left (or "ended").

**Warranty fields on assets**
`refresh_asset_warranty(asset_ids)`: for each asset, choose the linked contract with the latest `warranty_end_date`; set `warranty_start = contract.completion_date`, `warranty_end = contract.warranty_end_date`; if none, set both to null. Called after a contract is applied.
"Under warranty on day D" means `warranty_start <= D <= warranty_end` (both days included), with D taken in `Asia/Kolkata`.
Edge cases to test: completion date is today; last warranty day is today; day after warranty ends; asset in two contracts; contract with 0 months (never under warranty).

**Problem reports**
- `POST /assets/{id}/problems` body `{ description, urgency }` (editor, admin). Steps in one transaction:
  1. Create `problem_report`, add 1 to `asset.open_problem_count`.
  2. If the asset is under warranty today, set `under_warranty = true` and `contract_id` (the contract used for the field), and create a `change_request` of kind `warranty_claim` (`created_by` = reporter) with `proposed` containing the problem, contract and days left.
  3. Write history "Problem reported".
- `POST /problems/{id}/close` body `{ note }` (editor, admin, reviewer): sets closed, subtracts from `open_problem_count`. If a warranty claim exists in status `sent`, it must be closed first with an outcome (`fixed_by_contractor` or `closed_without_fix`) using `POST /warranty-claims/{id}/close`; closing the claim clears `repair_hold` if no other sent claim exists on that asset.
- `GET /problems`, `GET /warranty-claims`.
- `GET /warranty-claims/{id}/letter`: returns a simple printable HTML page (no styling library) with contract number, contractor, asset code and name, location, problem description, dates, and a plain request to repair under warranty. The letter says "Prepared by the Asset Register for review by [reviewer name]". It is a draft for a person to send; the register does not send anything.

---

## 8. Step 7 — Assets, photos, notes, map, reports

**Routes and roles** (viewer = V, editor = E, reviewer = R, admin = A; area limit on all)

| Route | Who |
|---|---|
| `GET /assets` filters: `q`, `family_id`, `type_id`, `stage_key`, `area_id` (includes below), `under_warranty`, `has_open_problem`, `not_checked_months`, `is_active`; paging 50 per page | V E R A |
| `GET /assets/{id}` (with links, contracts, problems, photos list, notes) | V E R A |
| `GET /assets/{id}/history` (paging) | V E R A |
| `POST /assets/{id}/notes` (`note` or `correction_for_department`) | E R A |
| `POST /assets/{id}/photos` (multipart; optional `taken_lat`, `taken_lon`, `problem_id`) / `GET /photos/{id}/file` | upload E A; view all |
| `POST /assets/{id}/problems` | E A |
| Imports, department mapping | E A (mapping edit: A, and E for their systems' mapping) |
| Decide requests | R A |
| Setup (areas, types, users, settings) | A |

**Search** `q`: matches register code, name (trigram), and department IDs (`source_link.source_id`). Results show the matched field.

**Photos**
- The website shrinks a picture to at most 1600 pixels on the long side (JPEG, quality about 0.8) before uploading. The server refuses anything over 5 MB or not JPEG/PNG/WebP.
- `file_store.py` has two backends chosen by `PHOTO_STORAGE`: `database` (bytes in the `photo` table) and `s3` (any S3-compatible bucket; save only the key). Tell the reader in the handover note that database storage is for the demo. [M]
- The asset page shows "Taken about 12 m from the asset" when the phone gave a position. Wording must say it is a hint.
- Images are fetched with the sign-in token and shown from a temporary browser address (not a public link).

**Map pieces** (`map_pieces.py`), route `GET /map/{z}/{x}/{y}.pbf` with optional `type_id`, `family_id`, `stage_key`, `under_warranty`, `has_open_problem`
- Needs sign-in (the website adds the token to map requests using MapLibre's request hook). Applies the area limit and `is_active`.
- Response header `Cache-Control: private, max-age=60`. Empty tile returns an empty response with 204.
- **Zoom 0 to 9**: grouped dots. Group by snapping each asset's centre to a grid whose cell size is (tile width in degrees ÷ 12); return one dot per cell with `count`.
- **Zoom 10 and above**: real shapes.

```sql
WITH env AS (SELECT ST_TileEnvelope(%(z)s, %(x)s, %(y)s) AS box)
SELECT ST_AsMVT(t, 'assets', 4096, 'geom') FROM (
  SELECT a.id::text AS id, a.register_code AS code, a.asset_type_id AS type_id,
         a.stage_key AS stage, (a.open_problem_count > 0) AS has_problem,
         (a.warranty_start <= (now() AT TIME ZONE 'Asia/Kolkata')::date
          AND (now() AT TIME ZONE 'Asia/Kolkata')::date <= a.warranty_end) AS under_warranty,
         ST_AsMVTGeom(ST_Transform(a.location, 3857), env.box, 4096, 64, true) AS geom
  FROM asset a, env
  WHERE a.is_active
    AND a.location && ST_Transform(env.box, 4326)
    AND ( -- area limit and filters go here as parameters
          TRUE )
) t WHERE t.geom IS NOT NULL;
```

Line and area shapes are simplified before packing when zoom is under 14 (use `ST_Simplify` with a tolerance that shrinks as zoom grows). Cap each tile at 20,000 features; if more, keep the largest by length or area and set a header `X-Tile-Trimmed: yes`.
Tile tests: valid response (decode it), area limit respected, filters respected, trimmed header works, response time recorded in the load test.

**Reports** (`reports.py`, `GET /reports/summary?area_id=`, `GET /reports/by-area?area_id=`)
Numbers for the Reports page (all clickable to a filtered list or map):
1. Requests waiting for review (with oldest waiting date).
2. Assets by family and by stage.
3. Open problems (with how many under warranty).
4. Assets under warranty now, and warranty ending in the next 90 days.
5. Assets not checked by a department system in `not_checked_months` (default 12) months.
6. Assets by area with one level of drill-down (uses `area.path LIKE prefix%`).
Use plain queries with indexes first. If slow in the load test, add a summary table refreshed after imports and approvals.

---

## 9. Step 8 — Website

**Foundation (build first)**
- `api.ts`: one small function per server route; adds the token; on a 401, go to sign-in with the message "Please sign in again."
- `text.ts`: **all screen words in one file** (easy to translate later; see `04_extras.md` for the wording).
- `styles.css`: system font, body text 17 px, high contrast, buttons with words (no icon-only buttons), visible keyboard focus, layouts that work from 360 px wide to a large screen. One accent colour. Stage colours have a fixed set plus a word label (never colour alone).
- On load, call `GET /health` once to wake the server (shows a small "Waking the server, this can take up to a minute" note if it takes over 3 seconds).
- Role-based menu: viewers do not see Bring in Data; only reviewers and admins see the decision buttons; only admins see Admin.

**Pages, in build order**
1. **Sign in.** Email, password, one button. Under it, one line: what the register is.
2. **Assets list.** Search box, filters (family, type, stage, area, "Under warranty", "Has open problem", "Not checked recently"), table with code, name, type, area, stage, badges. Click opens the asset.
3. **Asset page.** Top: name, code, type, area, stage, badges. Sections: *Official record* (read-only details with "Kept by [system], last checked [date]" and a "Write a correction note for the department" button), *Also recorded by*, *Contracts and warranty*, *Problems* (with "Report a problem"), *Photos* (with "Add a photo"), *Notes*, *History* (newest first). A small map at the top right.
4. **Map page.** Full-screen map, filter bar, search box (jumps to an asset), click an asset for a side panel with a short summary and "Open full page". A note explains "Zoom in to see individual assets" when showing dots.
5. **Bring in data.** Choose a department system (or create one, admin), upload a file or press "Fetch from web address", column mapping screen (first time), progress bar and results ("120 new, 8 changed, 3 possible matches, 2 with problems"), link "Go to these requests", link "Download problem rows".
6. **Review queue.** Tabs Waiting, Approved, Rejected. Filters by kind, area, batch. Each row is a plain sentence. Buttons per row: Look. Checkbox and "Approve selected" only for add and update.
7. **Request page.** Shows a sentence, who made it and when, then by kind: a before/after table for updates; a small map and a side-by-side table for possible matches with the buttons "This is the same asset" and "This is a different asset"; for warranty claims the contract, contractor, days left, problem text, photos, and a list of causes to pick from. Buttons: Approve, Reject (asks for a reason).
8. **Contracts.** List and a form: number, title, contractor, dates, warranty months, cost (optional), assets (search and pick, or "all assets from import #N"). Contract page shows warranty dates and days left.
9. **Problems.** List with filters (open, under warranty), close with a note; warranty claims tab with the letter link and "Close claim".
10. **Reports.** The six numbers, each linking to a filtered view.
11. **Admin.** Tabs: Areas (tree editor), Asset types (edit fields and stages), Department systems, Users, Settings.
12. **How it works.** Shows the architecture diagram and the "how a change gets in" diagram with 6 lines of plain explanation. Uses the exported SVG.

**Website tests**: type check passes; build passes; a smoke test opens each page with mocked data; text file has no missing keys.

---

## 10. Step 9 — Sample data and load test

Read the sample data plan in `04_extras.md`. All sample data is made up and must be labelled so on the sign-in page footer and in a "Sample data" badge on assets created by the sample scripts.

- `scripts/make_sample_files.py` writes the sample department files into `server/db/seed/samples/`.
- `scripts/make_test_data.py --count 200000` fills the database directly with synthetic assets (points and lines scattered across Gujarat, mixed types, mixed stages, some warranty and problems) in batches of 10,000 using `INSERT ... SELECT` with `generate_series`. It must never run against a database whose name or address is not on a short allow list, or without `--yes-this-is-a-test-database`.
- `scripts/time_the_map.py` measures, for the current data size: map piece time at zoom 6, 9, 12, 15 for 30 random places each; list page 1 with each filter; search; the reports summary; a review-queue page. It writes median and 95th-percentile times, the row count, machine description and date into `docs/LOAD_TEST_RESULTS.md`. Compare to the targets (map piece under 300 ms and list under 500 ms median on a normal laptop). [M, targets are ours and can be changed]
- Run at 200,000 on the real Render database if the plan allows, and at 2 million locally in Docker. Report what was really run.

---

## 11. Step 10 — Hosting

**Server on Render** (`render.yaml` in the repo root; check current field names in Render's docs before use [M])

```yaml
databases:
  - name: asset-register-db
    plan: free            # change to a paid plan before judging (free databases expire after 30 days)
services:
  - type: web
    name: asset-register-server
    runtime: docker
    dockerfilePath: ./server/Dockerfile
    dockerContext: ./server
    plan: free            # free servers sleep when idle; use a paid plan for judging
    healthCheckPath: /health
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: asset-register-db
          property: connectionString
      - key: SECRET_KEY
        generateValue: true
      - key: ALLOWED_ORIGINS
        sync: false       # set by hand to the Vercel website address
      - key: DEMO_PASSWORD
        sync: false
      - key: PHOTO_STORAGE
        value: database
```

The Dockerfile starts with `python:3.12-slim`, installs requirements, and runs `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Migrations and seed run at start (seed only if the database is empty).

**Website on Vercel**
- Project root `web/`. Build: `npm run build`. Output: `dist`. Environment: `VITE_API_URL` = the Render server address.
- `web/vercel.json`: send all paths to `index.html` (so page addresses work when refreshed).
- After both are up, set Render's `ALLOWED_ORIGINS` to the Vercel address (and any preview address if needed) and redeploy the server.

**If you cannot deploy** (no account access): do not invent addresses. Deliver the two config files and a click-by-click guide `docs/DEPLOY_STEPS.md` (create the database, create the server from `render.yaml`, set the three secret values, create the Vercel project, set the one variable, set `ALLOWED_ORIGINS`), and say in the handover note that it was not deployed.

**After deploying**: run the check list in `04_extras.md` against the live addresses and paste results into `docs/HANDOVER.md`.

---

## 12. Step 11 — The architecture picture

Make one clean picture from the first diagram in `01_architecture.md`, plus the second diagram on a second page, as `docs/architecture-diagram.svg` (and `.mmd` source, and a PNG if easy). Rules:
- Three main boxes and one dotted box for department systems. Nothing else on the first picture.
- Every label is a plain word. No brand-new jargon. Put the hosting names (Vercel, Render) in small text.
- Under the picture, three plain sentences: what each part does, who is official, and what needs approval.
- Show the same picture on the website's "How it works" page.

---

## 13. Final checks before you stop

1. Every item in `04_extras.md` "Done checklist" is ticked or listed in HANDOVER as not done, with the reason.
2. `pytest`, type check and build pass. Paste the summary lines in HANDOVER.
3. Read all screen text once for jargon. Read all commit messages once for jargon.
4. Search the code for `TODO`, hard-coded passwords, and secrets. There must be none.
5. Zip the repo without `node_modules`, `.env`, caches and virtual environments: `asset-register.zip`.
