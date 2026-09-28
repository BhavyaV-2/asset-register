# Load test results

Date: 2026-09-28T08:12:10.426063+00:00

Data size: 2,000,000 made-up assets.

Machine: Linux-6.6.87.2-microsoft-standard-WSL2-x86_64-with-glibc2.39; x86_64; 12 logical CPUs; 12th Gen Intel(R) Core(TM) i5-1235U. PostgreSQL 16 with PostGIS, local Ubuntu under Windows.

Method: fixed random seed 42; 30 requests per row, one request at a time, through FastAPI TestClient including authentication and database access. No internet round-trip. These are local measurements, not a hosted capacity claim. Map samples include empty tiles; their count is reported.

Targets set before the run: map median under 300 ms; list median under 500 ms.

| Request | Median ms | 95th percentile ms | Median bytes | Empty map pieces |
|---|---:|---:|---:|---:|
| Map zoom 6 | 236.51 | 320.16 | 1441 | 0 |
| Map zoom 9 | 88.35 | 127.33 | 2277 | 0 |
| Map zoom 12 | 18.27 | 24.84 | 42180 | 0 |
| Map zoom 15 | 5.93 | 7.37 | 772 | 0 |
| List | 9.19 | 11.4 | 23515 | 0 |
| Type filter | 23.89 | 27.1 | 22888 | 0 |
| Family filter | 366.68 | 441.13 | 23270 | 0 |
| Stage filter | 10.76 | 18.22 | 22982 | 0 |
| Warranty filter | 12.3 | 19.7 | 24109 | 0 |
| Problem filter | 11.77 | 17.07 | 24076 | 0 |
| Not checked filter | 9.68 | 13.33 | 23545 | 0 |
| Search | 30.28 | 52.96 | 23515 | 0 |
| Reports | 1489.15 | 1837.11 | 831 | 0 |
| Review queue | 6.52 | 10.3 | 2 | 0 |

Limits: no concurrent users, no hosted run, no import under load, and no proof of larger capacity than the recorded data size. Load rows are synthetic and bypass approval only in the separate guarded load-data script. Reports count the stored synthetic flags; this is a timing run, not the review demo.
