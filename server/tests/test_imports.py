import socket
import uuid
import pytest
from app import database as db
from app.imports.read_files import public_address,read_file

@pytest.mark.parametrize('address',['http://example.org','https://127.0.0.1','https://10.0.0.1','https://192.168.1.1','https://169.254.169.254','https://[::1]'])
def test_private_addresses(address):
    with pytest.raises(ValueError):
        public_address(address)

def test_csv_semicolon():
    assert read_file('a.csv',b'\xef\xbb\xbfid;name\n1;One')[0]['name']=='One'

def test_first_upload_and_bad_row(client,sign_in):
    system = db.one("SELECT id FROM department_system WHERE name='Municipal street light list'")['id']
    before = db.one('SELECT count(*) AS n FROM asset')['n']
    value = uuid.uuid4().hex
    content = f'light_no,place,lat,lon,lamp,watts,working\n{value},Sample,23.2,72.6,LED,50,yes\nbad,Sample,999,72,LED,50,yes'
    response = client.post('/imports',headers=sign_in('editor'),data={'department_system_id':system},files={'file':('test.csv',content,'text/csv')})
    assert response.status_code==200,response.text
    batch = client.get('/imports/'+str(response.json()['id']),headers=sign_in('editor')).json()
    assert batch['status']=='done',batch
    assert batch['rows_new']==1 and batch['rows_with_problems']==1,batch
    assert batch['problems'][0]['row_number']==2
    assert db.one('SELECT count(*) AS n FROM asset')['n']==before

@pytest.mark.parametrize('role',['viewer','reviewer'])
def test_import_role(client,sign_in,role):
    assert client.post('/imports',headers=sign_in(role),data={'department_system_id':1},files={'file':('a.csv','id\n1','text/csv')}).status_code==403
