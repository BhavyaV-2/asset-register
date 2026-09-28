"""Load made-up records through the normal server functions. No direct asset inserts."""
from app import database as db
from db.seed.make_seed import make_seed
from app.imports.routes import start_batch
from app.imports.compare import process_import
from app.review import decide_request
from app.contracts import propose_contract,warranty_end
from app.problems import report_problem
from app.settings import today
from scripts.make_sample_files import make_sample_files,folder

def load_demo():
    db.migrate();make_seed();make_sample_files()
    editor=db.one("SELECT u.*,a.path AS area_path FROM app_user u JOIN area a ON a.id=u.area_id WHERE email='editor@example.org'")
    reviewer=db.one("SELECT u.*,a.path AS area_path FROM app_user u JOIN area a ON a.id=u.area_id WHERE email='reviewer@example.org'")
    for name,filename in [('Roads Department road list','roads_first.csv'),('Municipal street light list','lights_first.csv'),('Water Board network','water_network.geojson')]:
        system=db.one('SELECT id FROM department_system WHERE name=%s',(name,))['id']
        if db.one('SELECT id FROM source_link WHERE department_system_id=%s LIMIT 1',(system,)):
            continue
        batch=start_batch(editor,system,filename)
        process_import(batch['id'],filename,(folder/filename).read_bytes(),editor)
        requests=db.all("SELECT id,kind FROM change_request WHERE batch_id=%s AND status='waiting' ORDER BY id",(batch['id'],))
        for request in requests:
            decide_request(request['id'],{'choice':'different_asset'},reviewer)
        result=db.one('SELECT status,rows_with_problems FROM import_batch WHERE id=%s',(batch['id'],))
        if result['status']!='done' or result['rows_with_problems']:
            raise RuntimeError('The sample import did not finish cleanly.')
    roads=db.all("SELECT a.id FROM asset a JOIN asset_type t ON t.id=a.asset_type_id WHERE t.key='road' AND a.details->>'_sample'='true' ORDER BY a.register_code")
    if len(roads)<60:
        raise RuntimeError('The demo needs 60 sample roads.')
    for number,months_back,start,end in [(1,8,0,12),(2,48,12,20),(3,34,20,26)]:
        code=f'SAMPLE-CONTRACT-{number}'
        if not db.one('SELECT id FROM contract WHERE contract_number=%s',(code,)):
            completion=warranty_end(today(),-months_back)
            request=propose_contract({'contract_number':code,'title':f'Sample road contract {number}','contractor_name':f'Sample contractor {number}','completion_date':completion.isoformat(),'warranty_months':36,'asset_ids':[str(a['id']) for a in roads[start:end]]},editor)
            decide_request(request['id'],{},reviewer)
    for number in [0,30,31,32]:
        asset_id=str(roads[number]['id'])
        if not db.one('SELECT id FROM problem_report WHERE asset_id=%s',(asset_id,)):
            report_problem(asset_id,{'description':'Sample broken road surface','urgency':'major'},editor)
    print('Demo state loaded through imports and review: 508 assets, 3 contracts, 4 problems. One warranty request waits for review.')

if __name__=='__main__':load_demo()
