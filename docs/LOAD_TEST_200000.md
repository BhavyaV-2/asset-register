# Load test results

Date: 2026-09-28T07:53:59.742267+00:00

Data size: 200,000 made-up assets.

Machine: Linux-6.6.87.2-microsoft-standard-WSL2-x86_64-with-glibc2.39; x86_64; 12 logical CPUs; 12th Gen Intel(R) Core(TM) i5-1235U. PostgreSQL 16 with PostGIS, local Ubuntu under Windows.

Method: fixed random seed 42; 30 requests per row, one request at a time, through FastAPI TestClient including authentication and database access. No internet round-trip. These are local measurements, not a hosted capacity claim. Map samples include empty tiles; their count is reported.

Targets set before the run: map median under 300 ms; list median under 500 ms.

| Request | Median ms | 95th percentile ms | Median bytes | Empty map pieces |
|---|---:|---:|---:|---:|
| Map zoom 6 | 301.01 | 584.42 | 1453 | 0 |
| Map zoom 9 | 12.37 | 20.16 | 2239 | 0 |
| Map zoom 12 | 6.71 | 13.14 | 4305 | 0 |
| Map zoom 15 | 8.35 | 11.49 | 152 | 3 |
| List | 14.25 | 42.71 | 23515 | 0 |
| Type filter | 32.45 | 54.45 | 22888 | 0 |
| Family filter | 57.45 | 92.12 | 23270 | 0 |
| Stage filter | 10.88 | 16.31 | 22982 | 0 |
| Warranty filter | 14.57 | 22.28 | 24109 | 0 |
| Problem filter | 15.26 | 54.7 | 24076 | 0 |
| Not checked filter | 28.01 | 66.75 | 23545 | 0 |
| Search | 57.71 | 171.27 | 23515 | 0 |
| Reports | 213.7 | 672.54 | 814 | 0 |
| Review queue | 2.14 | 2.68 | 2 | 0 |

Limits: no concurrent users, no hosted run, no import under load, and no proof of larger capacity than the recorded data size. Load rows are synthetic and bypass approval only in the separate guarded load-data script. Reports count the stored synthetic flags; this is a timing run, not the review demo.
