# Asset Register

An internal tool for viewers, editors, reviewers and admins.
Department systems keep the official records.
The register reads them and never edits them.

## Run locally

Install Python 3.12, Node.js 22+ and Docker with Compose. Start Docker. From this folder:

```sh
python server/scripts/setup_local.py
docker compose up -d db
python -m venv .venv
```

Activate Python: `.\.venv\Scripts\Activate.ps1` in Windows PowerShell, or `source .venv/bin/activate` on macOS/Linux. Then:

```sh
python -m pip install -r server/requirements.txt
python server/scripts/run.py start_server
```

Leave it running. In a second terminal:

```sh
cd web
npm ci
npm run dev
```

Open [the local website](http://localhost:5173). Server health: [localhost:8000/health](http://localhost:8000/health). First start loads 508 made-up assets, three contracts and four problems through imports and approvals. Repeated starts keep existing data. The map's OpenStreetMap background needs internet access.

## Demo sign-ins

Select Viewer, Editor, Reviewer or Admin. Their emails are `viewer@example.org`, `editor@example.org`, `reviewer@example.org` and `admin@example.org`. The randomly generated password comes from `DEMO_PASSWORD` in ignored `server/.env`. It appears after selecting a role when `SHOW_DEMO_SIGN_INS=true`; the server still checks the actual account role. Disable that setting before adding real records. No password is committed.

Viewer, editor and reviewer cover Gandhinagar city; admin covers all areas. All demo data is made up. Files for the live demo are `server/db/seed/samples/roads_second_version.csv` and `lights_second.csv`; the loader leaves them un-imported.

## Put it online

Website: [Asset Register on Vercel](https://asset-register-pravi.vercel.app). The Render server must still be connected. 

## Run tests

With Docker running and Python activated, create the separate test database once:

```sh
docker compose exec db createdb -U asset_register asset_register_test
python server/scripts/run.py test
cd web
npm test
npm run typecheck
npm run build
```

Tests require real PostgreSQL/PostGIS and refuse other database names. They add made-up test records.

## Run the load test

From the project folder, create a separate local load database once:

```sh
docker compose exec db createdb -U asset_register asset_register_load
python server/scripts/run.py make_test_data --count 200000 --yes-this-is-a-test-database
python server/scripts/run.py time_the_map
```

Repeat with `--count 2000000` for the stretch run. The generator adds rows up to that count and refuses other database names and non-local addresses. It never removes records. 
## Folder guide

- `server/app`: rules, imports, review, assets, contracts, photos, map pieces and reports.
- `server/db`: database changes, all 37 asset types, and made-up samples.
- `server/tests`: tests against PostGIS.
- `web/src`: React pages, shared words and plain CSS.
- `docs`: specifications, diagrams, results, choices and handover.

## Not in version 1

No write-back to department systems, two-way updates, offline use, state single sign-on, public complaint form, mobile app, movable assets, or automatic matching decisions. Real Pravi data has not been tested. Database photo storage is for the demo; bucket storage needs operator-provided S3 settings.

Database triggers block updates, deletion and wiping of history. A database owner can change database protections; operational permissions and backups remain the operator's responsibility.
