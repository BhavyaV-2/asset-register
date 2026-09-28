from fastapi import APIRouter, Depends, HTTPException
from psycopg import sql
from psycopg.types.json import Jsonb
from app import database as db
from app.people import read_user, need_role, area_limit, check_area, hash_password

router = APIRouter()
admin = need_role('admin')

def global_admin(user):
    if user['area_id'] is not None:
        raise HTTPException(403,'An admin for all areas must change shared setup.')

def save_fields(conn, table, row_id, body, allowed, json_fields=()):
    fields = [key for key in body if key in allowed]
    if not fields:
        raise HTTPException(400,'Choose a field to change.')
    query = sql.SQL('UPDATE {} SET {} WHERE id=%s RETURNING *').format(sql.Identifier(table),sql.SQL(',').join(sql.SQL('{}=%s').format(sql.Identifier(key)) for key in fields))
    values = [Jsonb(body[key]) if key in json_fields else body[key] for key in fields]
    return conn.execute(query,values+[row_id]).fetchone()

@router.get('/areas')
def list_areas(user=Depends(read_user)):
    return db.all('SELECT * FROM area WHERE path LIKE %s ORDER BY path',(area_limit(user)+'%',))

@router.post('/areas')
def add_area(body:dict,user=Depends(admin)):
    with db.transaction() as conn:
        parent = check_area(conn,user,body['parent_id']) if body.get('parent_id') else None
        if not parent:
            global_admin(user)
        rank = int(body['level_rank'])
        if parent and rank <= parent['level_rank']:
            raise HTTPException(400,'Choose a level below the parent area.')
        row = conn.execute('INSERT INTO area(parent_id,name,level_rank,path) VALUES (%s,%s,%s,%s) RETURNING id',(body.get('parent_id'),body['name'],rank,'/')).fetchone()
        return conn.execute('UPDATE area SET path=%s WHERE id=%s RETURNING *',((parent['path'] if parent else '/')+str(row['id'])+'/',row['id'])).fetchone()

@router.patch('/areas/{area_id}')
def change_area(area_id:int,body:dict,user=Depends(admin)):
    with db.transaction() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(731206)')
        old = check_area(conn,user,area_id)
        if 'parent_id' in body:
            parent = check_area(conn,user,body['parent_id']) if body['parent_id'] else None
            if not parent:
                global_admin(user)
            if parent and (parent['path'].startswith(old['path']) or parent['level_rank'] >= old['level_rank']):
                raise HTTPException(400,'Choose a parent above this area, outside its children.')
            path = (parent['path'] if parent else '/')+str(area_id)+'/'
            conn.execute('UPDATE area SET path=%s || substring(path from %s) WHERE path LIKE %s',(path,len(old['path'])+1,old['path']+'%'))
        return save_fields(conn,'area',area_id,body,['name','parent_id'])

@router.get('/area-levels')
def list_levels(user=Depends(read_user)):
    return db.all('SELECT * FROM area_level ORDER BY rank')

@router.put('/area-levels')
def save_levels(body:list[dict],user=Depends(admin)):
    global_admin(user)
    with db.transaction() as conn:
        for row in body:
            conn.execute('INSERT INTO area_level VALUES (%s,%s) ON CONFLICT(rank) DO UPDATE SET name=EXCLUDED.name',(row['rank'],row['name']))
    return {'saved':True}

@router.get('/settings')
def list_settings(user=Depends(admin)):
    return db.all('SELECT * FROM app_setting ORDER BY key')

@router.patch('/settings')
def change_settings(body:dict,user=Depends(admin)):
    global_admin(user)
    allowed = {'match_distance_metres':(1,500),'name_match_score':(0,1),'missing_share_limit':(0,.3),'not_checked_months':(1,120)}
    with db.transaction() as conn:
        for key,value in body.items():
            if key=='second_person_must_approve' and str(value).lower()=='true':
                continue
            if key not in allowed or not allowed[key][0] <= float(value) <= allowed[key][1]:
                raise HTTPException(400,'This setting is outside its allowed range.')
            conn.execute('UPDATE app_setting SET value=%s WHERE key=%s',(str(value),key))
    return {'saved':True}

@router.get('/users')
def list_users(user=Depends(admin)):
    return db.all('SELECT u.id,u.email,u.full_name,u.role,u.area_id,u.is_active FROM app_user u LEFT JOIN area a ON a.id=u.area_id WHERE %s OR a.path LIKE %s ORDER BY u.id',(user['area_id'] is None,area_limit(user)+'%'))

@router.post('/users')
def add_user(body:dict,user=Depends(admin)):
    with db.transaction() as conn:
        if body.get('area_id'):
            check_area(conn,user,body['area_id'])
        else:
            global_admin(user)
        return conn.execute('INSERT INTO app_user(email,full_name,password_hash,role,area_id) VALUES (%s,%s,%s,%s,%s) RETURNING id',(body['email'].strip().lower(),body['full_name'],hash_password(body['password']),body['role'],body.get('area_id'))).fetchone()

@router.patch('/users/{person_id}')
def change_user(person_id:int,body:dict,user=Depends(admin)):
    with db.transaction() as conn:
        current = conn.execute('SELECT area_id FROM app_user WHERE id=%s',(person_id,)).fetchone()
        if not current:
            raise HTTPException(404,'This person was not found.')
        for area in [current['area_id'],body.get('area_id',current['area_id'])]:
            check_area(conn,user,area) if area else global_admin(user)
        if 'password' in body:
            body['password_hash'] = hash_password(body.pop('password'))
        row = save_fields(conn,'app_user',person_id,body,['full_name','role','area_id','is_active','password_hash'])
        row.pop('password_hash')
        return row
