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
        yield current

@pytest.fixture
def sign_in(client):
    def make(role):
        response = client.post('/auth/sign-in',json={'email':role+'@example.org','password':os.environ['DEMO_PASSWORD'],'role':role})
        assert response.status_code == 200, response.text
        return {'Authorization':'Bearer '+response.json()['token']}
    return make
