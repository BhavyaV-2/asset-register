# Why the design stays small as the data grows

The same three parts were used for the 508-asset demo and the 2,000,000-asset load run: one React website, one FastAPI server and one PostgreSQL/PostGIS database. No cache server, message service, import worker or second database was added.

## What was measured

The final local run used **2,000,000 made-up assets**, 30 sequential requests per group, fixed random seed 42, and the machine recorded in `LOAD_TEST_RESULTS.md`.

| Request | Median | 95th percentile |
|---|---:|---:|
| Map at zoom 6 | 236.51 ms | 320.16 ms |
| Map at zoom 9 | 88.35 ms | 127.33 ms |
| Map at zoom 12 | 18.27 ms | 24.84 ms |
| Map at zoom 15 | 5.93 ms | 7.37 ms |
| First asset-list page | 9.19 ms | 11.40 ms |
| Family-filtered list | 366.68 ms | 441.13 ms |
| Reports | 1,489.15 ms | 1,837.11 ms |

The predeclared median targets were 300 ms for map pieces and 500 ms for lists. The recorded map and list groups met those median targets. Zoom-6's 95th percentile exceeded 300 ms. Reports remain the clearest measured next improvement.

The earlier 200,000-row run missed the zoom-6 median target at 301.01 ms. Following the documented growth plan, saved low-zoom counts were added inside the same database. An initial two-million-row run exposed a query that failed to use the count index efficiently. Computing integer map bounds before the query reduced zoom-9 median time from 3,689.78 ms to 88.35 ms in these runs. Both earlier results are retained; this is an observed comparison, not a controlled hardware benchmark.

## Why these results are explainable

1. A map request asks for one visible piece, not the whole register. Location indexes narrow the high-zoom reads; each piece has a 20,000-feature cap.
2. Zoomed-out map requests read saved counts. Database triggers adjust those counts inside the same transaction as an asset change, preserving area, type, stage, problem and warranty filters.
3. Lists return 50 records. Fields and stages are saved data, so all 37 catalog types use the same code path.
4. Imports group 500 rows into each transaction. Approval locks a single request and applies its change and history together.
5. Adding an area, department or asset type changes saved setup; it does not require another service or a separate table for that type.

## What this does not establish

No concurrent-user capacity was measured. No Render performance run was made. Internet latency, multiple server instances, imports under load, bucket photos, backup recovery and larger data sizes were not measured. The load rows have synthetic stored flags and are not a full-size history/contract workload. Two-million-row generation directly fills only the separate guarded load database; the demo uses approval.

The evidence supports **designed to grow in steps** and the specific measured results above. It does not justify an unlimited or universal scalability claim. Next, measure reports while editing before deciding whether saved report counts or a read-only database copy are needed.
