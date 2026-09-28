# Load test results

Date: 2026-09-28T08:09:26.611713+00:00

Data size: 2,000,000 made-up assets.

Machine: Linux-6.6.87.2-microsoft-standard-WSL2-x86_64-with-glibc2.39; x86_64; 12 logical CPUs; 12th Gen Intel(R) Core(TM) i5-1235U. PostgreSQL 16 with PostGIS, local Ubuntu under Windows.

Method: fixed random seed 42; 30 requests per row, one request at a time, through FastAPI TestClient including authentication and database access. No internet round-trip. These are local measurements, not a hosted capacity claim. Map samples include empty tiles; their count is reported.

Targets set before the run: map median under 300 ms; list median under 500 ms.

| Request | Median ms | 95th percentile ms | Median bytes | Empty map pieces |
|---|---:|---:|---:|---:|
| Map zoom 6 | 1146.45 | 1947.68 | 1441 | 0 |
| Map zoom 9 | 3689.78 | 4308.0 | 2277 | 0 |
| Map zoom 12 | 21.88 | 28.84 | 42180 | 0 |
| Map zoom 15 | 6.26 | 8.27 | 772 | 0 |
| List | 8.6 | 11.99 | 23515 | 0 |
| Type filter | 42.0 | 54.95 | 22888 | 0 |
| Family filter | 490.37 | 615.01 | 23270 | 0 |
| Stage filter | 7.94 | 10.37 | 22982 | 0 |
| Warranty filter | 8.43 | 11.29 | 24109 | 0 |
| Problem filter | 9.14 | 11.28 | 24076 | 0 |
| Not checked filter | 8.54 | 9.9 | 23545 | 0 |
| Search | 29.65 | 35.86 | 23515 | 0 |
| Reports | 1445.24 | 1880.7 | 831 | 0 |
| Review queue | 4.29 | 5.36 | 2 | 0 |

Limits: no concurrent users, no hosted run, no import under load, and no proof of larger capacity than the recorded data size. Load rows are synthetic and bypass approval only in the separate guarded load-data script. Reports count the stored synthetic flags; this is a timing run, not the review demo.
