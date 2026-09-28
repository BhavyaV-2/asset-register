import pytest
from app import database as db

@pytest.mark.parametrize('role',['viewer','editor','reviewer','admin'])
@pytest.mark.parametrize('route',['/users','/settings'])
def test_setup_roles(client,sign_in,role,route):
    assert client.get(route,headers=sign_in(role)).status_code == (200 if role=='admin' else 403)

def test_catalog_complete(client,sign_in):
    rows = client.get('/asset-types',headers=sign_in('viewer')).json()
    assert len(rows)==37
    assert len({r['family'] for r in rows})==7

def test_second_person_setting_cannot_be_disabled(client,sign_in):
    assert client.patch('/settings',headers=sign_in('admin'),json={'second_person_must_approve':'false'}).status_code == 400

def test_area_limit_for_setup(client,sign_in):
    sector = db.one("SELECT id FROM area WHERE name='Sector 3'")['id']
    original = db.one("SELECT area_id FROM app_user WHERE role='viewer'")['area_id']
    db.run("UPDATE app_user SET area_id=%s WHERE role='viewer'",(sector,))
    try:
        rows = client.get('/areas',headers=sign_in('viewer')).json()
        assert [r['name'] for r in rows] == ['Sector 3']
        assert client.get('/department-systems',headers=sign_in('viewer')).json() == []
    finally:
        db.run("UPDATE app_user SET area_id=%s WHERE role='viewer'",(original,))

def test_area_move_cannot_make_loop(client,sign_in):
    city = db.one("SELECT id FROM area WHERE name='Gandhinagar city'")['id']
    child = db.one("SELECT id FROM area WHERE name='Sector 1'")['id']
    assert client.patch(f'/areas/{city}',headers=sign_in('admin'),json={'parent_id':child}).status_code == 400
