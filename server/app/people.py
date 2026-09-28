import os
import time
from datetime import datetime, timedelta, timezone
from threading import Lock
import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from app import database as db
from app.settings import secret

router = APIRouter()
bearer = HTTPBearer(auto_error=False)
attempts = {}
attempt_lock = Lock()

class SignIn(BaseModel):
    email: str
    password: str
    role: str | None = None

def read_user(token: HTTPAuthorizationCredentials | None = Depends(bearer)):
    try:
        content = jwt.decode(token.credentials,secret(),algorithms=['HS256'])
        user = db.one('SELECT u.id,u.email,u.full_name,u.role,u.area_id,a.path AS area_path,a.name AS area_name FROM app_user u LEFT JOIN area a ON a.id=u.area_id WHERE u.id=%s AND u.is_active',(int(content['sub']),))
        if not user:
            raise ValueError()
        return user
    except (jwt.PyJWTError, ValueError, AttributeError, KeyError):
        raise HTTPException(401,'Please sign in again.')

def need_role(*roles):
    def check(user=Depends(read_user)):
        if user['role'] not in roles:
            raise HTTPException(403,'Your role cannot do this.')
        return user
    return check

def area_limit(user):
    return user.get('area_path') or '/'

def check_area(conn, user, area_id):
    row = conn.execute('SELECT * FROM area WHERE id=%s AND path LIKE %s',(area_id,area_limit(user)+'%')).fetchone()
    if not row:
        raise HTTPException(404,'This area is not available to you.')
    return row

def check_asset(conn, user, asset_id, lock=False):
    sql = 'SELECT a.*,ST_AsGeoJSON(a.location)::json AS shape FROM asset a JOIN area r ON r.id=a.area_id WHERE a.id=%s AND r.path LIKE %s'
    if lock:
        sql += ' FOR UPDATE OF a'
    row = conn.execute(sql,(asset_id,area_limit(user)+'%')).fetchone()
    if not row:
        raise HTTPException(404,'This asset is not available to you.')
    return row

def hash_password(password):
    if not 10 <= len(password.encode()) <= 72:
        raise HTTPException(400,'Use a password from 10 to 72 bytes long.')
    return bcrypt.hashpw(password.encode(),bcrypt.gensalt()).decode()

@router.post('/auth/sign-in')
def sign_in(body: SignIn, request: Request):
    email = body.email.strip().lower()
    key = (email,request.client.host)
    now = time.monotonic()
    with attempt_lock:
        recent = [t for t in attempts.get(key,[]) if t > now-900]
        attempts[key] = recent
        if len(recent) >= 10:
            raise HTTPException(429,'Please wait 15 minutes before trying again.')
        # Count before checking so simultaneous tries cannot bypass the limit.
        recent.append(now)
    user = db.one('SELECT * FROM app_user WHERE email=%s AND is_active',(email,))
    valid = user and len(body.password.encode()) <= 72 and bcrypt.checkpw(body.password.encode(),user['password_hash'].encode())
    if not valid or (body.role and body.role != user['role']):
        raise HTTPException(401,'The sign-in details do not match.')
    with attempt_lock:
        attempts.pop(key,None)
    token = jwt.encode({'sub':str(user['id']),'role':user['role'],'exp':datetime.now(timezone.utc)+timedelta(hours=8)},secret(),algorithm='HS256')
    return {'token':token}

@router.get('/auth/demo/{role}')
def demo_sign_in(role: str):
    if os.getenv('SHOW_DEMO_SIGN_INS','false').lower() != 'true' or role not in ['viewer','editor','reviewer','admin']:
        raise HTTPException(404,'Demo sign-ins are not shown.')
    return {'email':role+'@example.org','password':os.environ.get('DEMO_PASSWORD','')}

@router.get('/me')
def me(user=Depends(read_user)):
    return user
