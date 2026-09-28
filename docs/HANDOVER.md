# Asset Register handover

## Live addresses

- Website published on Vercel: https://asset-register-pravi.vercel.app
- Server and database on Render: **not deployed**. No Render credential was available. The website needs `VITE_API_URL` set to the future Render server origin and a redeploy before hosted sign-in works.
- Follow [DEPLOY_STEPS.md](DEPLOY_STEPS.md). `render.yaml`, `server/Dockerfile` and `web/vercel.json` are included.

## Demo sign-ins

Viewer: `viewer@example.org`; Editor: `editor@example.org`; Reviewer: `reviewer@example.org`; Admin: `admin@example.org`.

The password is the operator's `DEMO_PASSWORD`, never a committed value. Local setup generates a random value. With `SHOW_DEMO_SIGN_INS=true`, selecting a role displays its demo credentials. The four accounts have separate saved roles; selecting another role does not change access. All demo data is made up. This credential display is for the sample deployment only.

## What was built

The full seven-family, 37-type catalog; editable areas, types, stages, departments and users; email/password sign-in; area checks; CSV, GeoJSON and zipped Shapefile reading; saved column mapping; private-address blocking for HTTPS fetches; request-only imports; review with a second-person check and one-time application; linked department records; missing-record safety rule; contracts and warranty reviews; draft claim letters; assets, history, notes, private photos; map pieces; six report groups; and the specified internal website pages.

History update, delete and wipe attempts are blocked by database triggers. Department records are never written back. Problems, photos and notes follow the architecture's explicit approval exception. Setup is admin-only. See [OPEN_POINTS.md](OPEN_POINTS.md) for conflicts and choices.

Sample loader: 508 assets, three contracts, four problems, one waiting warranty review. It uses the same import and approval functions as the website. The second road file and second light file remain un-imported in the demo.

## Test results

Tests used Python 3.12 with real PostgreSQL 16 and PostGIS in Ubuntu under Windows.

```text
59 passed, 1 warning in 27.65s
Test Files  1 passed (1)
Tests  17 passed (17)
```

The warning is a dependency's deprecated test-client alias. Website type-check and Vite production build passed. Vite warns that the map-containing JavaScript bundle exceeds 500 KB; this is not a failed build.

Browser checks used headless Chrome against the local app: viewer pages opened, 360-pixel layout had no page overflow, four role menus and editor/admin pages opened, and both SVG pictures loaded. The published Vercel sign-in page opened. Its first deployment had a failed health fetch because no Render address was configured; the final website explicitly shows the pending-server status and catches failed health requests.

The final package includes the load-measurement report and both architecture pictures.

## Load test results

**2,000,000 made-up assets**. Median map times: zoom 6 **236.51 ms**, zoom 9 **88.35 ms**, zoom 12 **18.27 ms**, zoom 15 **5.93 ms**. First list page **9.19 ms**; reports **1,489.15 ms**.

These were 30 sequential requests per group through the server and database locally, with no internet round trip. Map and list medians met the declared targets; report time remains a limitation. No concurrent-user or hosted capacity claim is made. Machine details, 95th percentiles, payload sizes and earlier runs are in [LOAD_TEST_RESULTS.md](LOAD_TEST_RESULTS.md). [SCALING.md](SCALING.md) explains why the measured design remains three parts and what the evidence does not prove.

## Done checklist

| # | Check | Result and evidence |
|---|---|---|
|1|Maker cannot approve|Yes — self-approval test, including admin.|
|2|Two approvals apply once|Yes — two concurrent approvals return one success and one already-decided response; one history entry.|
|3|History cannot be changed or wiped|Yes — database update, delete and truncate tests. Database owners can alter protections themselves.|
|4|Role access on routes|Yes — table check covers every write route's server role dependency; sign-in and selected endpoint checks also ran.|
|5|Area limits|Yes for tested lists, search, asset, history, photo, map, report and request decisions. Not every setup-move/contract combination was independently tested.|
|6|No asset delete route|Yes — route inspection test.|
|7|Private fetch addresses refused|Yes — local, private, link-local and IPv6 loopback tests. Actual external department endpoints were not available.|
|8|No committed secrets|Checked in final package; environment values are generated or supplied outside Git.|
|9|First import only creates requests|Yes — count stays unchanged until review.|
|10|Same approved file unchanged|Yes — integration test.|
|11|Correct before/after|Yes — changed detail integration test.|
|12|Match links or adds|Yes — nearby point tests for both choices. Line/area matching is implemented but not separately covered by shape-overlap fixtures.|
|13|Missing and 30% guard|Yes — 20% missing makes requests, 40% warns; sample file yields 5 new, 8 changed and 2 missing.|
|14|Rejected row not re-asked|Yes — rejected fingerprint test.|
|15|Bad rows reported; good continue|Yes — invalid latitude and row-number test.|
|16|Warranty edge days|Yes — completion day, last day, next day and zero-month tests.|
|17|Problem creates warranty request|Yes for under-warranty flow; ordinary sample problems also loaded without claims.|
|18|Cause controls claim and repair hold|Yes — four causes tested; bad workmanship creates claim and hold.|
|19|Claim letter details|Yes — HTML response includes the selected contract; closes only after outcome is recorded.|
|20|Map decoding, scope, filters, groups|Yes — decoded low/high zoom pieces, empty filter, area restriction and 20,000-feature cap tests.|
|21|Six reports agree|Yes — report totals checked against database queries; linked area filters implemented.|
|22|Photos|Partial verification — database upload/read/access tests pass. Browser shrinking, optional device position and database-computed distance hints are implemented. Remote S3 storage and physical-phone positioning were not tested.|
|23|Role menus|Yes — four-role browser checks; server remains authoritative.|
|24|All text in text.ts/plain words|Partial — primary screen words are centralized; some Admin mapping structure and saved field names remain visible.|
|25|360 px and desktop|Yes — headless Chrome screenshots inspected, no page overflow at 360 px. Not tested on a physical phone.|
|26|How it works pictures|Yes — both SVGs loaded in browser checks.|
|27|Server tests, type-check, build|Yes — real summary lines above; final rerun recorded below if changed.|
|28|Load test|Yes — 200,000 and 2,000,000 local made-up assets; measurements and limits saved.|
|29|Hosted deployment|Partial — Vercel published; Render not deployed. Steps provided, no invented server address.|
|30|ZIP runs fresh|Yes for fresh extraction and an empty real PostGIS database: sample loading, health, four sign-ins, lists and reports passed. Docker execution itself was unavailable here.|
|31|SVG and source|Yes — architecture-diagram.svg/.mmd and change-flow.svg/.mmd; SVG has no pages, so the flow is a separate picture.|
|32|Open choices|Yes — OPEN_POINTS.md records known choices, conflicts and limits.|

## Not done and why

- Render deployment and connected hosted demo checks: account access is required.
- Remote S3 storage check: no bucket credentials supplied; database storage is the tested demo option.
- Admin department column mapping still permits structured-text editing; the import mapping screen uses column pickers and plain value-pair controls. Primary type/stage setup uses forms. A full translation-ready screen-text audit is not complete.
- Real-data, concurrent-user, import-under-load, backup and restore, and physical-phone tests: not run.
- A Docker build/run on this machine: Docker's Linux integration was unavailable. Fresh-extraction verification uses real PostgreSQL/PostGIS directly instead.

## Open points

Read [OPEN_POINTS.md](OPEN_POINTS.md). In particular, self-approval is always refused despite the implementation document's optional off switch, and the second lights file is reserved for the live demo despite the contradictory sample-plan sentence.

## How the ZIP was checked

The package excludes dependencies, build output, private settings, local test environments and Git metadata. The final verification below records integrity, fresh extraction, clean database setup and the extracted website build. No claim of a Docker run or a second physical machine is made.

```text
ZIP integrity passed: 101 files; 176 KB; no local settings or dependencies.
Extracted ZIP check passed: clean database, 508 sample assets, health, four sign-ins, asset pages and reports.
```

That extraction was checked before the last map-display refinements; the archive is regenerated from the final sources. No dependency folders or environment secrets are included.

The extracted website passed `npm ci` and `npm run build` (`✓ built in 8.77s`). Its install reported dependency advisories; the already-required libraries were updated before the final package. Final checks:

```text
found 0 vulnerabilities
✓ built in 3.91s
Test Files  1 passed (1)
Tests  17 passed (17)
11 role/menu/page checks passed; both diagrams loaded; browser errors: 0.
```
