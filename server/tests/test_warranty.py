from datetime import date,timedelta
import uuid
import pytest
from app import database as db
from app.contracts import warranty_end,under_warranty
from app.settings import today

@pytest.mark.parametrize('day,expected',[(date(2024,1,31),True),(date(2024,2,29),True),(date(2024,3,1),False)])
def test_warranty_edge_days(day,expected):
    start=date(2024,1,31)
    assert under_warranty(start,warranty_end(start,1),1,day)==expected

def test_zero_months():
    assert not under_warranty(today(),today(),0,today())

@pytest.mark.parametrize('choice',['bad_workmanship','damage_by_others','normal_wear','not_sure'])
def test_contract_problem_claim_letter(client,sign_in,choice):
    asset = db.one('SELECT id FROM asset ORDER BY created_at LIMIT 1')['id']
    editor,reviewer = sign_in('editor'),sign_in('reviewer')
    body={'contract_number':'SAMPLE-'+uuid.uuid4().hex,'title':'Sample repair','contractor_name':'Sample contractor','completion_date':today().isoformat(),'warranty_months':12,'asset_ids':[str(asset)]}
    response=client.post('/contracts',headers=editor,json=body)
    assert response.status_code==200,response.text
    request_id=response.json()['id']
    assert not db.one('SELECT id FROM contract WHERE contract_number=%s',(body['contract_number'],))
    assert client.post(f'/change-requests/{request_id}/approve',headers=reviewer,json={}).status_code==200
    problem=client.post(f'/assets/{asset}/problems',headers=editor,json={'description':'Sample broken surface','urgency':'major'})
    assert problem.status_code==200,problem.text
    assert problem.json()['under_warranty']
    request=db.one("SELECT id FROM change_request WHERE kind='warranty_claim' ORDER BY id DESC LIMIT 1")
    response=client.post(f"/change-requests/{request['id']}/approve",headers=reviewer,json={'choice':choice})
    assert response.status_code==200,response.text
    claim=db.one('SELECT * FROM warranty_claim WHERE problem_report_id=%s',(problem.json()['id'],))
    if choice=='bad_workmanship':
        assert claim
        assert db.one('SELECT repair_hold FROM asset WHERE id=%s',(asset,))['repair_hold']
        letter=client.get(f"/warranty-claims/{claim['id']}/letter",headers=reviewer)
        assert letter.status_code==200 and body['contract_number'] in letter.text
        assert client.post(f"/problems/{problem.json()['id']}/close",headers=editor,json={'note':'Finished'}).status_code==409
        assert client.post(f"/warranty-claims/{claim['id']}/close",headers=reviewer,json={'note':'Sample fixed','outcome':'fixed_by_contractor'}).status_code==200
    else:
        assert not claim
        assert response.json()['status']=='rejected'
    assert client.post(f"/problems/{problem.json()['id']}/close",headers=editor,json={'note':'Sample closed'}).status_code==200
