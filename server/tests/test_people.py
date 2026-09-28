import os
import jwt
import pytest
from app import database as db
from app.people import attempts

def test_wrong_password(client):
    assert client.post('/auth/sign-in',json={'email':'viewer@example.org','password':'wrong'}).status_code == 401

@pytest.mark.parametrize('role',['viewer','editor','reviewer','admin'])
def test_role_sign_in(client,sign_in,role):
    assert client.get('/me',headers=sign_in(role)).json()['role'] == role

def test_expired_token(client):
    token = jwt.encode({'sub':'1','exp':1},os.environ['SECRET_KEY'],algorithm='HS256')
    assert client.get('/me',headers={'Authorization':'Bearer '+token}).status_code == 401

def test_disabled_user(client,sign_in):
    headers = sign_in('viewer')
    db.run("UPDATE app_user SET is_active=false WHERE role='viewer'")
    try:
        assert client.get('/me',headers=headers).status_code == 401
    finally:
        db.run("UPDATE app_user SET is_active=true WHERE role='viewer'")

def test_limit_tries(client):
    attempts.clear()
    for _ in range(10):
        assert client.post('/auth/sign-in',json={'email':'unknown@example.org','password':'wrong'}).status_code == 401
    assert client.post('/auth/sign-in',json={'email':'unknown@example.org','password':'wrong'}).status_code == 429

def test_selected_role_does_not_grant_access(client):
    assert client.post('/auth/sign-in',json={'email':'viewer@example.org','password':os.environ['DEMO_PASSWORD'],'role':'admin'}).status_code == 401
