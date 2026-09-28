import json
import os
import pytest
from app import database as db
from app.main import app
from app.people import need_role

def test_each_write_route_has_a_role_check():
    expected={
      '/areas':{'admin'},'/areas/{area_id}':{'admin'},'/area-levels':{'admin'},
      '/asset-types':{'admin'},'/asset-types/{type_id}':{'admin'},'/users':{'admin'},'/users/{person_id}':{'admin'},'/settings':{'admin'},
      '/department-systems':{'admin'},'/department-systems/{system_id}':{'editor','admin'},
      '/imports':{'editor','admin'},'/imports/preview':{'editor','admin'},'/imports/from-web-address':{'editor','admin'},
      '/change-requests/approve-many':{'reviewer','admin'},'/change-requests/{request_id}/approve':{'reviewer','admin'},'/change-requests/{request_id}/reject':{'reviewer','admin'},
      '/contracts':{'editor','admin'},'/contracts/{contract_id}':{'editor','admin'},'/assets/{asset_id}/problems':{'editor','admin'},
      '/problems/{problem_id}/close':{'editor','reviewer','admin'},'/warranty-claims/{claim_id}/close':{'editor','reviewer','admin'},
      '/assets/{asset_id}/notes':{'editor','reviewer','admin'},'/assets/{asset_id}/photos':{'editor','admin'}}
    checked=set()
    for route in app.routes:
        if not getattr(route,'methods',set()) & {'POST','PUT','PATCH'} or route.path=='/auth/sign-in':continue
        dependencies=[d.call for d in route.dependant.dependencies]
        role_checks=[f for f in dependencies if f.__name__=='check']
        assert len(role_checks)==1,route.path
        for role in ['viewer','editor','reviewer','admin']:
            if role in expected[route.path]:role_checks[0]({'role':role})
            else:
                with pytest.raises(Exception) as error:role_checks[0]({'role':role})
                assert error.value.status_code==403
        checked.add(route.path)
    assert checked==set(expected)

def test_map_counts_match_active_assets(client):
    count=db.one('SELECT count(*) AS n FROM asset WHERE is_active')['n']
    assert all(row['n']==count for row in db.all('SELECT zoom,sum(asset_count) AS n FROM map_count GROUP BY zoom'))

def test_all_six_report_totals(client,sign_in):
    from app.settings import today
    data=client.get('/reports/summary',headers=sign_in('admin')).json()
    assert data['under_warranty']==db.one('SELECT count(*) AS n FROM asset WHERE is_active AND warranty_start<=%s AND warranty_end>=%s',(today(),today()))['n']
    assert data['warranty_ending']==db.one('SELECT count(*) AS n FROM asset WHERE is_active AND warranty_start<=%s AND warranty_end BETWEEN %s AND %s+90',(today(),today(),today()))['n']
    assert data['not_checked']==db.one('SELECT count(*) AS n FROM asset WHERE is_active AND (last_checked_at IS NULL OR last_checked_at<now()-make_interval(months=>%s))',(data['not_checked_months'],))['n']
    assert sum(r['count'] for r in client.get('/reports/by-area',headers=sign_in('admin')).json())==data['assets']

def test_sample_second_version_counts(client,sign_in):
    from scripts.load_demo_state import load_demo
    from scripts.make_sample_files import folder
    load_demo()
    system=db.one("SELECT id FROM department_system WHERE name='Roads Department road list'")['id']
    existing=db.one("SELECT id FROM import_batch WHERE department_system_id=%s AND file_name='roads_second_version.csv' AND status='done' ORDER BY id DESC LIMIT 1",(system,))
    if existing:
        batch=existing['id']
    else:
        result=client.post('/imports',headers=sign_in('editor'),data={'department_system_id':system},files={'file':('roads_second_version.csv',(folder/'roads_second_version.csv').read_bytes(),'text/csv')})
        batch=result.json()['id']
    kinds={r['kind']:r['n'] for r in db.all('SELECT kind,count(*) AS n FROM change_request WHERE batch_id=%s GROUP BY kind',(batch,))}
    assert kinds=={'add_asset':5,'update_asset':8,'mark_missing':2}
