# Asset Register — Extras for the Builder

Use with `01_architecture.md` and `02_implementation.md`.

Sections: A Plain-words glossary · B Asset catalog (load as seed data) · C Default stages · D Sample data plan · E Website text · F Commit rules and plan · G Claims · H Environment variables · I Done checklist · J Demo script · K Templates

---

## A. Plain-words glossary (use these words everywhere)

| Say this | Not this | Meaning |
|---|---|---|
| asset | entity, resource | A physical thing the government owns or looks after |
| asset type | class, schema | The kind of asset (Road, Street Light) |
| family | category tree | A group of asset types |
| register | registry, master data | Our list of all assets |
| register code | canonical ID, UUID | The short code we give each asset, like AR-0000123 |
| department system | source system, upstream | A department's own list or database that holds the official record |
| official record | source of truth | What the department system says |
| bring in data / import | ingest, sync | Read a department's file or web address |
| column mapping | schema mapping | Which column in their file means what |
| change request | proposal, mutation, diff | A suggested addition or change waiting for a person |
| review | approval workflow | A person approves or rejects the request |
| history | audit log, event log, ledger | The list of everything that happened to an asset |
| area | jurisdiction, tenant, scope | A place in the tree: State, District, City, Ward |
| stage | lifecycle state, phase | Where the asset is in its life: Planned, In use, Retired |
| warranty period | DLP, defect liability period | Time after completion when the contractor must fix defects. Show "(defect liability period)" once on the contract page for people who know the term |
| warranty claim | DLP claim | A request that the contractor fixes a defect under warranty |
| problem report | issue, ticket, incident | A note that something is wrong with an asset |
| repair budget on hold | funds locked | Flag while a warranty claim is with the contractor |
| possible match | duplicate candidate, entity resolution | Two records that may be the same asset |
| map pieces | vector tiles, MVT | Small chunks of map data for the part of the map on screen |
| grouped dots | clusters | One dot standing for many nearby assets |
| second person | four-eyes, maker-checker | The person who approves must not be the one who made the request |

Name style: `asset`, `asset_type`, `department_system`, `change_request`, `history_entry`, `problem_report`, `warranty_claim`, `area`, `stage_key`, `register_code`. Short and clear beats clever. Function names start with a verb: `find_matches`, `approve_request`, `read_csv_file`.

---

## B. Asset catalog (load as `server/db/seed/asset_catalog.json`)

7 families, 37 types. Shape is the *usual* shape; imports may use any shape. Every detail field is optional. Kinds: `text`, `number`, `date`, `yes_no`, `choice[a|b|c]`. Field keys are the words before the colon; labels are the key with spaces and a capital letter (for example `width_m` → "Width (metres)"). Convert this block into JSON with keys `family`, `key`, `name`, `usual_shape`, `detail_fields[{key,label,kind,choices}]`.

Shared choice lists (write them out where used):
- MATERIAL = `cast iron|ductile iron|PVC|HDPE|steel|concrete|other`
- SURFACE = `asphalt|concrete|paving blocks|gravel|earth|other`

```text
FAMILY: Roads and Bridges
road | Road | line | road_class:choice[national highway|state highway|district road|city road|village road|lane]; surface:choice[SURFACE]; width_m:number; lanes:number; has_footpath:yes_no; has_divider:yes_no; year_built:number
bridge | Bridge or Flyover | line | bridge_kind:choice[bridge|flyover|underpass|foot overbridge]; length_m:number; span_count:number; material:choice[concrete|steel|stone|other]; load_limit_tons:number; year_built:number
culvert | Culvert | point | culvert_kind:choice[pipe|box|slab]; opening_width_m:number; material:choice[concrete|stone|steel|other]; year_built:number
footpath | Footpath or Cycle Track | line | track_kind:choice[footpath|cycle track|both]; surface:choice[SURFACE]; width_m:number
traffic_signal | Traffic Signal | point | arm_count:number; power_source:choice[grid|solar]; year_installed:number
bus_shelter | Bus Shelter | point | seats:number; has_lighting:yes_no; year_built:number

FAMILY: Transport and Logistics
transport_hub | Transport Station or Terminal | area | hub_kind:choice[bus station|railway station|metro station|ferry terminal|airport|port]; platforms_or_gates:number; year_built:number
storage_facility | Warehouse or Cold Store | area | storage_kind:choice[warehouse|cold store|container depot]; capacity_tonnes:number; year_built:number

FAMILY: Water and Sanitation
water_pipeline | Water Pipeline | line | pipe_kind:choice[main|distribution|service]; diameter_mm:number; material:choice[MATERIAL]; year_laid:number
water_treatment | Water Treatment Plant | point | capacity_mld:number; treatment_kind:choice[filtration|chlorination only|other]; year_built:number
water_tank | Water Tank | point | tank_kind:choice[overhead|ground level|underground sump]; capacity_litres:number; height_m:number; year_built:number
pump_station | Pumping Station or Borewell | point | pump_kind:choice[borewell|pumping station|booster station]; power_kw:number; year_installed:number
sewer_line | Sewer Line | line | diameter_mm:number; material:choice[MATERIAL]; year_laid:number
sewage_treatment | Sewage Treatment Plant | point | capacity_mld:number; treatment_kind:choice[primary|secondary|advanced|other]; year_built:number
storm_drain | Storm Water Drain | line | drain_kind:choice[open|covered|box]; width_m:number; depth_m:number; year_built:number
canal | Irrigation Canal | line | canal_kind:choice[main canal|branch canal|distributary|field channel]; lined:yes_no; width_m:number; year_built:number
dam_embankment | Dam or Embankment | area | structure_kind:choice[dam|embankment|check dam]; height_m:number; year_built:number
waste_facility | Solid Waste Facility | area | facility_kind:choice[transfer station|processing plant|landfill|compost site]; capacity_tonnes_per_day:number; year_started:number
public_toilet | Public Toilet | point | seat_count:number; has_water:yes_no; has_power:yes_no; year_built:number
waste_point | Waste Collection Point | point | point_kind:choice[bin|container|collection yard]; capacity_litres:number

FAMILY: Energy and Street Lighting
street_light | Street Light | point | pole_height_m:number; lamp_kind:choice[LED|sodium vapour|CFL|other]; watts:number; power_source:choice[grid|solar]; year_installed:number
substation | Substation or Transformer | point | equipment_kind:choice[substation|transformer]; capacity_kva:number; voltage_kv:number; year_installed:number
power_line | Power Line | line | voltage_kv:number; line_kind:choice[overhead|underground]; year_built:number
solar_plant | Solar Installation | area | capacity_kw:number; install_kind:choice[rooftop|ground mounted|street pole]; year_installed:number
fuel_pipeline | Oil or Gas Pipeline | line | fuel_kind:choice[oil|natural gas|LNG|other]; diameter_mm:number; year_laid:number

FAMILY: Communication
telecom_tower | Telecom Tower | point | tower_kind:choice[ground based|rooftop|pole]; height_m:number; year_built:number
cable_route | Communication Cable Route | line | cable_kind:choice[optical fibre|duct only|copper]; year_laid:number

FAMILY: Public Buildings and Social Facilities
government_building | Government Office Building | area | building_use:choice[office|court|police station|other]; floors:number; floor_area_sqm:number; year_built:number
school | School or College | area | education_level:choice[primary|secondary|higher secondary|college|training centre]; classrooms:number; year_built:number
hospital | Hospital or Health Centre | area | health_kind:choice[hospital|community health centre|primary health centre|clinic]; beds:number; year_built:number
housing | Housing Complex | area | housing_kind:choice[affordable housing|rental housing|staff quarters]; homes:number; year_built:number
sports_facility | Sports Facility | area | sports_kind:choice[stadium|playground|swimming pool|indoor hall]; year_built:number
market | Market or Shopping Complex | area | shops:number; year_built:number
community_hall | Community Hall or Centre | area | capacity_people:number; year_built:number

FAMILY: Public Spaces and Safety
park | Park or Garden | area | has_lighting:yes_no; has_play_equipment:yes_no; year_opened:number
fire_station | Fire Station | point | bays:number; year_built:number
burial_ground | Burial Ground or Crematorium | area | ground_kind:choice[burial ground|crematorium|both]; year_started:number
```

Source note (put it in `docs/OPEN_POINTS.md`): the five top-level categories follow the Government of India Harmonised Master List of Infrastructure Sub-sectors; municipal types follow common municipal asset lists (for example Ahmedabad Municipal Corporation's balance sheet). The exact 37-type split is our own and has not been checked against Gujarat's or Pravi's classification. Admins can edit it.

---

## C. Default stages (same for every type; admins can change per type)

| key | Label | is_end |
|---|---|---|
| planned | Planned | no |
| being_built | Being built | no |
| in_use | In use | no |
| needs_repair | Needs repair | no |
| under_repair | Under repair | no |
| retired | Retired | yes |

Stage colours (with a word label always shown): planned grey, being built blue, in use green, needs repair orange, under repair purple, retired dark grey.

---

## D. Sample data plan (all made up; label it "Sample data")

Location: around Gandhinagar (about 23.22 N, 72.65 E). Area tree: Gujarat > Gandhinagar district > Gandhinagar city > Sector 1 to 8. Use a fixed random seed so results repeat. Dates are made relative to the day the script runs.

**Sample department systems (created by seed, with saved column mappings)**

| Name | Connection | Type | Full list? | File |
|---|---|---|---|---|
| Roads Department road list | file | fixed: road | yes | `roads_first.csv` (60 road pieces as WKT lines; columns `road_id, road_name, width, surface_type, lanes, status, wkt`) |
| Municipal street light list | file | fixed: street_light | yes | `lights_first.csv` (400 lights along those roads; `light_no, place, lat, lon, lamp, watts, working`) |
| Ward electrical list | file | fixed: street_light | no | `lights_second.csv` (100 lights that are the same as 100 in the first list, moved 5–15 m, with different IDs and slightly different place names) |
| Water Board network | file (GeoJSON) | from a `kind` column: pipeline, tank, plant → water_pipeline, water_tank, water_treatment | yes | `water_network.geojson` (40 pipes, 6 tanks, 2 plants) |

**Second version file for the live demo (not approved in advance)**
`roads_second_version.csv`: the same 60 roads with 5 changed widths, 3 changed statuses, 2 roads removed, and 5 new roads. Expected result: 5 + 3 changed (a road can have both, count requests, not fields), 2 missing, 5 new.

**Demo state script** `scripts/load_demo_state.py`: imports the first four files as the editor and approves them as the reviewer **using the same server functions the website uses**, so history entries are real. Then it creates 3 contracts through the same request-and-approve path:
1. Completed about 8 months ago, warranty 36 months, covers 12 road pieces. (Inside warranty. Used for the warranty demo.)
2. Completed about 4 years ago, warranty 36 months, covers 8 road pieces. (Warranty ended.)
3. Completed about 34 months ago, warranty 36 months, covers 6 road pieces. (Warranty ends in about 60 days.)
It also adds 3 problem reports on ordinary roads and 1 on a road inside contract 1 **left un-decided** so the live demo shows the warranty request appear. It leaves `roads_second_version.csv` and `lights_second.csv` un-imported for the live demo.

**Load test data** `scripts/make_test_data.py`: made-up assets across Gujarat, at least 200,000 (option for 2,000,000), all marked `Sample data` in `details._sample = true`.

---

## E. Website text (keep in `web/src/text.ts`)

Tone: short sentences, everyday words, no slogans.

- App name: **Asset Register**
- Sign-in headline: "Sign in to the Asset Register"
- Sign-in line: "One place to see what public assets exist, where they are, who looks after them, and what has happened to them."
- Sign-in footer: "Sample data (made up) is shown in this demo."
- Menu: Map · Assets · Bring in data · Review · Contracts · Problems · Reports · Admin · How it works
- Empty list: "Nothing to show yet."
- Map, zoomed out: "Zoom in to see each asset. Dots show how many assets are close together."
- Official record heading: "Official record"
- Official record note: "Kept by {system}. Last checked {date}. To correct it, ask the department."
- Correction button: "Write a correction note for the department"
- Not checked recently badge: "Not checked in {months} months"
- Under warranty badge: "Under warranty until {date}"
- Repair on hold badge: "Repair budget on hold"
- Problem badge: "{n} open problem(s)"
- Review page headline: "Requests waiting for review"
- Review page rule: "Nothing changes in the register until a person approves it. You cannot approve a request you made."
- Approve many: "You are approving {n} items. Each one will be recorded under your name."
- Reject prompt: "Why are you rejecting this? Your reason is saved."
- Possible match: "These may be the same asset."; buttons "This is the same asset" · "This is a different asset"
- Warranty request: "This problem is on an asset that is still under warranty. Choose what caused it."
- Causes: "Bad workmanship" · "Damage by someone else" · "Normal wear" · "Not sure"
- Warranty letter footer: "Prepared by the Asset Register for a person to review and send. The register does not send anything."
- Import result: "{new} new · {changed} changed · {same} unchanged · {matches} possible matches · {missing} missing · {problems} rows with problems"
- Incomplete file warning: "This file may be incomplete: {percent}% of the known assets are not in it. No 'missing' requests were made."
- Server waking: "Waking the server. This can take up to a minute."
- Access message: "You can only see assets in {area} and the areas under it."
- How it works, three lines:
  1. "Departments keep the official records. The register reads them and never edits them."
  2. "Every addition or change waits for a second person to approve it."
  3. "Every step is saved in the history and cannot be changed."

---

## F. Commit rules and commit plan

Rules: one small change per commit; first line up to 60 characters; start with a verb (Add, Fix, Change, Remove); everyday words; no prefixes like `feat:` or scope brackets; no jargon; no "WIP".

Good: `Add tables for assets and history` · `Block changes to history in the database` · `Read CSV files for imports` · `Fix warranty check on the last day`
Not good: `feat(db): add DDL`, `refactor stuff`, `WIP`

Plan (adjust as needed, keep the order):
1. Add project folders and README
2. Add database runner and first tables
3. Add areas, users and department systems tables
4. Block changes to history in the database
5. Add asset catalog and seed script
6. Add server settings, database helpers and health check
7. Add sign-in, roles and area limit
8. Add tests for sign-in and area limit
9. Add area and asset type setup routes
10. Add department system routes and column mapping
11. Read CSV and GeoJSON files for imports
12. Read zipped Shapefiles
13. Fetch data from a web address safely
14. Compare imported rows with the register
15. Add tests for import comparing
16. Add the review queue routes
17. Apply approved requests to the register
18. Add tests for approving and rejecting
19. Add contracts and warranty dates
20. Add problem reports and warranty claims
21. Add the claim letter page
22. Add asset lists, one asset, history and notes
23. Add photos with two storage options
24. Add map pieces
25. Add reports
26. Add website base, sign-in and text file
27. Add assets list and asset page
28. Add map page
29. Add bring in data page and column mapping screen
30. Add review pages
31. Add contracts, problems and reports pages
32. Add admin pages
33. Add How it works page and picture
34. Add sample files and demo state script
35. Add load test scripts and results
36. Add Render and Vercel setup files
37. Add handover note and deploy steps

---

## G. Claims

**Allowed** (each has a test or check; keep the wording close):
- "Nothing is added to or changed in the register until a second person approves it."
- "Department systems stay the official source. The register does not edit their records."
- "History entries cannot be edited or deleted. The database blocks it."
- "Adding a department, an area or an asset type needs no new code."
- "Every screen shows only the areas a person is allowed to see."
- "Tested with {N} made-up assets: map pieces took {X} ms (median) and lists took {Y} ms (median) on {machine}." Only after the load test ran.
- "Designed to grow in steps: see the growth plan." (Not "handles" until tested.)

**Do not say:** "handles billions", "instant", "real time", "fraud-proof", "audit-approved", "photo proves location", "works offline", "AI-powered", "spoof-proof", "official Gujarat asset classification", "guaranteed".

---

## H. Environment variables

| Name | Where | Meaning |
|---|---|---|
| `DATABASE_URL` | server | Database address (Render fills it) |
| `SECRET_KEY` | server | Random secret for sign-in tokens (Render can generate) |
| `ALLOWED_ORIGINS` | server | Website address(es), comma separated |
| `DEMO_PASSWORD` | server | Password for the four demo users (required for seeding) |
| `PHOTO_STORAGE` | server | `database` (default) or `s3` |
| `S3_BUCKET`, `S3_ENDPOINT`, `S3_KEY`, `S3_SECRET`, `S3_REGION` | server | Only when `PHOTO_STORAGE=s3` |
| `MAX_UPLOAD_MB` | server | Default 25 |
| `TIME_ZONE` | server | Default `Asia/Kolkata` |
| `VITE_API_URL` | website | Server address |

Provide `.env.example` files with no real values.

---

## I. Done checklist (copy into HANDOVER with Yes / No / Reason)

**Rules and safety**
1. A request cannot be approved by the person who made it (test).
2. Approving the same request twice changes the register once (test).
3. History rows cannot be updated, deleted or wiped (test).
4. Each role can and cannot reach the routes listed (table test).
5. The area limit holds for lists, search, one asset, photos, map pieces, reports and requests (test).
6. No route deletes an asset.
7. The web-address fetch refuses private addresses (test).
8. No secrets or passwords in the repo (search).

**Imports and review**
9. First upload makes only requests; no assets before approval (test).
10. Same file after approval shows all unchanged (test).
11. A changed value makes an update request with a correct before and after (test).
12. Same asset in two lists gives a possible match; "same" links, "different" adds (test).
13. Missing detection works and the 30% safety rule works (tests).
14. A rejected row is not asked again (test).
15. Bad rows are listed with row numbers; good rows still load (test).

**Contracts and warranty**
16. Warranty edge days are right: completion today, last day, day after (tests).
17. A problem on an asset under warranty creates a warranty request; other problems do not.
18. Bad workmanship approval creates a claim and puts the repair budget on hold; other causes do not.
19. The claim letter opens and shows the right details.

**Map, reports, photos**
20. Map pieces decode, respect area limit and filters, zoom out shows grouped dots (tests).
21. The six report numbers match the lists they link to.
22. Photos upload, shrink, show, and respect the area limit.

**Website**
23. Every menu item opens for the right roles only.
24. All text comes from `text.ts`; no jargon (read-through).
25. Works at 360 px wide and on a large screen.
26. The "How it works" page shows the picture.

**Delivery**
27. `pytest`, type check and website build pass (summary lines pasted).
28. Load test run with the data size and machine written down; or "not run" with the reason.
29. Live addresses work and demo sign-ins work, or "not deployed" with the reason and the steps file.
30. `asset-register.zip` runs from the README on a clean machine (say how you checked).
31. Architecture picture saved as `.svg` and `.mmd`.
32. `docs/OPEN_POINTS.md` lists every choice made where the documents were silent.

---

## J. Demo script (about 6 minutes)

1. Open **How it works**. Say the three lines.
2. Open the **Map** as the viewer. Zoom from Gujarat down to a road; show grouped dots then real shapes. Click a street light.
3. Open the **asset page**: official record with "Kept by … last checked", history, contract and warranty.
4. Sign in as the editor. **Bring in data**: upload `roads_second_version.csv`. Show "5 new, changed, 2 missing".
5. Try to approve as the same editor: the request page shows "A different person must approve this request."
6. Sign in as the reviewer. Open **Review**. Approve one change (see before and after). Reject one with a reason.
7. Upload `lights_second.csv` as the editor; as the reviewer open a **possible match** and choose "This is the same asset". Show the asset now lists two departments.
8. As the editor, **report a problem** on a road inside contract 1. Show the "Under warranty" badge and the warranty request. As the reviewer choose "Bad workmanship", approve, open the claim letter, and show "Repair budget on hold".
9. Open **Reports** and click through one number to its list.
10. Show **Admin**: add a stage to one asset type and add a new detail field. Point out that no code was changed.

---

## K. Templates

**README.md sections:** What this is (3 lines) · Run it on your machine (Docker for the database, server, website: exact commands) · Demo sign-ins · Put it online (Render and Vercel steps, or link to DEPLOY_STEPS) · Run the tests · Run the load test · Folder guide · What is not in version 1.

**docs/OPEN_POINTS.md:** one line each: `Point — choice made — why — who to ask`.

**docs/HANDOVER.md sections:** Live addresses · Demo sign-ins · What was built · Test results (pasted lines) · Load test results · Done checklist (Yes / No / Reason) · Not done and why · Open points · How the zip was checked.
