import math
import os
import platform
import random
import statistics
import time
from pathlib import Path
from datetime import datetime,timezone
from fastapi.testclient import TestClient
from app.main import app
from app import database as db

def time_routes():
    random.seed(42)
    with TestClient(app) as client:
        token=client.post('/auth/sign-in',json={'email':'viewer@example.org','password':os.environ['DEMO_PASSWORD']}).json()['token']
        headers={'Authorization':'Bearer '+token}
        count=db.one('SELECT count(*) AS n FROM asset')['n']
        results=[]
        for z in [6,9,12,15]:
            routes=[]
            for _ in range(30):
                lon,lat=random.uniform(68.5,73.5),random.uniform(20.2,24.7)
                x=int((lon+180)/360*2**z);y=int((1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*2**z)
                routes.append(f'/map/{z}/{x}/{y}.pbf')
            results.append((f'Map zoom {z}',routes))
        for name,path in [('List','/assets'),('Type filter','/assets?type_id=1'),('Family filter','/assets?family_id=1'),('Stage filter','/assets?stage_key=in_use'),('Warranty filter','/assets?under_warranty=true'),('Problem filter','/assets?has_open_problem=true'),('Not checked filter','/assets?not_checked_months=12'),('Search','/assets?q=Sample'),('Reports','/reports/summary'),('Review queue','/change-requests')]:
            results.append((name,[path]*30))
        rows=[]
        for name,routes in results:
            times=[];sizes=[];empty=0
            for path in routes:
                started=time.perf_counter()
                response=client.get(path,headers=headers)
                times.append((time.perf_counter()-started)*1000)
                assert response.status_code in [200,204],response.text
                sizes.append(len(response.content));empty+=response.status_code==204
            rows.append((name,round(statistics.median(times),2),round(sorted(times)[math.ceil(len(times)*.95)-1],2),round(statistics.median(sizes)),empty))
            print(name,rows[-1][1:])
    machine=platform.platform()+'; '+platform.machine()+f'; {os.cpu_count()} logical CPUs'
    cpu=Path('/proc/cpuinfo')
    if cpu.exists():
        machine+='; '+next((line.split(':',1)[1].strip() for line in cpu.read_text().splitlines() if line.startswith('model name')),'')
    body=f'# Load test results\n\nDate: {datetime.now(timezone.utc).isoformat()}\n\nData size: {count:,} made-up assets.\n\nMachine: {machine}. PostgreSQL 16 with PostGIS, local Ubuntu under Windows.\n\nMethod: fixed random seed 42; 30 requests per row, one request at a time, through FastAPI TestClient including authentication and database access. No internet round-trip. These are local measurements, not a hosted capacity claim. Map samples include empty tiles; their count is reported.\n\nTargets set before the run: map median under 300 ms; list median under 500 ms.\n\n| Request | Median ms | 95th percentile ms | Median bytes | Empty map pieces |\n|---|---:|---:|---:|---:|\n'
    body+='\n'.join('| '+' | '.join(map(str,row))+' |' for row in rows)
    body+='\n\nLimits: no concurrent users, no hosted run, no import under load, and no proof of larger capacity than the recorded data size. Load rows are synthetic and bypass approval only in the separate guarded load-data script. Reports count the stored synthetic flags; this is a timing run, not the review demo.\n'
    folder=Path(__file__).resolve().parents[2]/'docs'
    (folder/f'LOAD_TEST_{count}.md').write_text(body)
    (folder/'LOAD_TEST_RESULTS.md').write_text(body)

if __name__=='__main__':time_routes()
