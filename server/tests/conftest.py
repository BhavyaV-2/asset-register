import os
from urllib.parse import urlparse
import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture(scope='session',autouse=True)
def safe_database():
    if urlparse(os.environ['DATABASE_URL']).path != '/asset_register_test':
        raise RuntimeError('Tests require the dedicated asset_register_test database.')

@pytest.fixture(scope='session')
def client():
    with TestClient(app) as current:
        # Give read-route tests one approved record even on a fresh test database.
        from app import database as db
        from app.imports.compare import process_import
        from app.imports.routes import start_batch
        from app.review import decide_request
        from psycopg.types.json import Jsonb
        import uuid
        if not db.one('SELECT id FROM asset LIMIT 1'):
            editor=db.one("SELECT u.*,a.path AS area_path FROM app_user u JOIN area a ON a.id=u.area_id WHERE role='editor'")
            reviewer=db.one("SELECT u.*,a.path AS area_path FROM app_user u JOIN area a ON a.id=u.area_id WHERE role='reviewer'")
            area=db.one("SELECT id FROM area WHERE name='Sector 3'")['id']
            with db.transaction() as conn:
                system=conn.execute("INSERT INTO department_system(name,department_name,connection,default_area_id,column_mapping) VALUES (%s,'Sample','file',%s,%s) RETURNING id",('Test '+uuid.uuid4().hex,area,Jsonb({'source_id':'id','name':'name','asset_type':{'fixed':'street_light'},'location':{'latitude':'lat','longitude':'lon'}}))).fetchone()['id']
            batch=start_batch(editor,system,'sample.csv')
            process_import(batch['id'],'sample.csv',b'id,name,lat,lon\n1,Sample light,23.25,72.68',editor)
            request=db.one('SELECT id FROM change_request WHERE batch_id=%s',(batch['id'],))
            decide_request(request['id'],{},reviewer)
        yield current

@pytest.fixture
def sign_in(client):
    def make(role):
        response = client.post('/auth/sign-in',json={'email':role+'@example.org','password':os.environ['DEMO_PASSWORD'],'role':role})
        assert response.status_code == 200, response.text
        return {'Authorization':'Bearer '+response.json()['token']}
    return make
