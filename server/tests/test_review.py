import uuid
from concurrent.futures import ThreadPoolExecutor
import pytest
from app import database as db
from app.people import area_limit

@pytest.fixture
def bring(client,sign_in):
    editor = sign_in('editor')
    admin = sign_in('admin')
    area = db.one("SELECT id FROM area WHERE name='Sector 3'")['id']
    mapping = {'source_id':'id','name':'name','asset_type':{'fixed':'street_light'},'location':{'latitude':'lat','longitude':'lon'},'details':{'watts':'watts'}}
    def make(rows,system=None,full=False,headers=None):
        if system is None:
            response = client.post('/department-systems',headers=admin,json={'name':'Test '+uuid.uuid4().hex,'department_name':'Sample department','default_area_id':area,'column_mapping':mapping,'is_full_list':full})
            assert response.status_code==200,response.text
            system = response.json()['id']
        data = 'id,name,lat,lon,watts\n'+'\n'.join(rows)
        response = client.post('/imports',headers=headers or editor,data={'department_system_id':system},files={'file':('sample.csv',data,'text/csv')})
        batch = client.get('/imports/'+str(response.json()['id']),headers=editor).json()
        assert batch['status']=='done',batch
        requests = db.all('SELECT * FROM change_request WHERE batch_id=%s ORDER BY id',(batch['id'],))
        return system,batch,requests
    return make

def test_repeat_change_and_rejection(client,sign_in,bring):
    name = uuid.uuid4().hex
    system,batch,requests = bring([f'1,{name},23.23,72.66,40'])
    reviewer = sign_in('reviewer')
    request = requests[0]
    assert client.post(f"/change-requests/{request['id']}/approve",headers=reviewer,json={'choice':'different_asset'}).status_code==200
    _,batch,_ = bring([f'1,{name},23.23,72.66,40'],system)
    assert batch['rows_same']==1,batch
    _,batch,requests = bring([f'1,{name},23.23,72.66,50'],system)
    request = requests[0]
    assert request['current']['details']['watts']==40
    assert request['proposed']['details']['watts']==50
    assert client.post(f"/change-requests/{request['id']}/reject",headers=reviewer,json={}).status_code==400
    assert client.post(f"/change-requests/{request['id']}/reject",headers=reviewer,json={'note':'Check the value.'}).status_code==200
    _,batch,_ = bring([f'1,{name},23.23,72.66,50'],system)
    assert batch['rows_skipped_before']==1

def test_self_approval_and_concurrent_approval(client,sign_in,bring):
    admin = sign_in('admin')
    _,_,requests = bring([f'1,{uuid.uuid4().hex},23.24,72.67,40'],headers=admin)
    request_id = requests[0]['id']
    assert client.post(f'/change-requests/{request_id}/approve',headers=admin,json={}).status_code==403
    reviewer = sign_in('reviewer')
    def approve(_):
        return client.post(f'/change-requests/{request_id}/approve',headers=reviewer,json={'choice':'different_asset'}).status_code
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(approve,range(2)))==[200,409]
    assert db.one('SELECT count(*) AS n FROM history_entry WHERE change_request_id=%s',(request_id,))['n']==1

def test_possible_match_links_and_different_adds(client,sign_in,bring):
    name = uuid.uuid4().hex
    reviewer = sign_in('reviewer')
    _,_,requests = bring([f'1,{name},23.25,72.68,40'])
    response = client.post(f"/change-requests/{requests[0]['id']}/approve",headers=reviewer,json={'choice':'different_asset'})
    asset = response.json()['asset_id']
    _,_,requests = bring([f'2,{name},23.25009,72.68,40'])
    assert requests[0]['kind']=='link_asset'
    assert client.post(f"/change-requests/{requests[0]['id']}/approve",headers=reviewer,json={'choice':'same_asset','asset_id':asset}).status_code==200
    assert db.one('SELECT count(*) AS n FROM source_link WHERE asset_id=%s',(asset,))['n']==2
    _,_,requests = bring([f'3,{name},23.25009,72.68,40'])
    response = client.post(f"/change-requests/{requests[0]['id']}/approve",headers=reviewer,json={'choice':'different_asset'})
    assert response.status_code==200 and response.json()['asset_id']!=asset

def test_missing_limit(client,sign_in,bring):
    name = uuid.uuid4().hex
    rows = [f'{i},{name}-{i},{23+i/1000},72.7,40' for i in range(10)]
    system,_,requests = bring(rows,full=True)
    reviewer = sign_in('reviewer')
    for request in requests:
        assert client.post(f"/change-requests/{request['id']}/approve",headers=reviewer,json={'choice':'different_asset'}).status_code==200
    _,batch,_ = bring(rows[:8],system)
    assert batch['rows_missing']==2,batch
    _,batch,_ = bring(rows[:6],system)
    assert batch['rows_missing']==0 and '40%' in batch['message'],batch

def test_request_area_limit(client,sign_in,bring):
    _,_,requests = bring([f'1,{uuid.uuid4().hex},23.2,72.8,40'])
    original = db.one("SELECT area_id FROM app_user WHERE role='reviewer'")['area_id']
    other = db.one("SELECT id FROM area WHERE name='Sector 4'")['id']
    db.run("UPDATE app_user SET area_id=%s WHERE role='reviewer'",(other,))
    try:
        assert client.post(f"/change-requests/{requests[0]['id']}/approve",headers=sign_in('reviewer'),json={}).status_code==404
    finally:
        db.run("UPDATE app_user SET area_id=%s WHERE role='reviewer'",(original,))
