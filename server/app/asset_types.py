import re
from fastapi import APIRouter, Depends, HTTPException
from psycopg.types.json import Jsonb
from app import database as db
from app.people import read_user, need_role
from app.areas import global_admin, save_fields

router = APIRouter()

def check_type(body):
    stages = body.get('stages')
    if stages is not None:
        keys = [s['key'] for s in stages]
        if not keys or len(set(keys)) != len(keys) or any(not re.fullmatch('[a-z]+(?:_[a-z]+)*',k) for k in keys):
            raise HTTPException(400,'Give each stage a different lowercase key, using underscores between words.')
    for field in body.get('detail_fields',[]):
        if field['kind'] not in ['text','number','date','choice','yes_no'] or (field['kind']=='choice' and not field.get('choices')):
            raise HTTPException(400,'Choose a supported field kind and give choices where needed.')

@router.get('/asset-types')
def list_types(user=Depends(read_user)):
    return db.all('SELECT t.*,f.name AS family FROM asset_type t JOIN asset_family f ON f.id=t.family_id ORDER BY f.sort_order,t.id')

@router.post('/asset-types')
def add_type(body:dict,user=Depends(need_role('admin'))):
    global_admin(user)
    check_type(body)
    with db.transaction() as conn:
        return conn.execute('INSERT INTO asset_type(family_id,key,name,usual_shape,detail_fields,stages) VALUES (%s,%s,%s,%s,%s,%s) RETURNING *',(body['family_id'],body['key'],body['name'],body['usual_shape'],Jsonb(body.get('detail_fields',[])),Jsonb(body['stages']))).fetchone()

@router.patch('/asset-types/{type_id}')
def change_type(type_id:int,body:dict,user=Depends(need_role('admin'))):
    global_admin(user)
    check_type(body)
    with db.transaction() as conn:
        conn.execute('SELECT id FROM asset_type WHERE id=%s FOR UPDATE',(type_id,))
        if 'stages' in body:
            count = conn.execute('SELECT count(*) AS n FROM asset WHERE asset_type_id=%s AND NOT stage_key=ANY(%s)',(type_id,[s['key'] for s in body['stages']])).fetchone()['n']
            if count:
                raise HTTPException(400,f'{count} assets still use a stage you removed.')
        return save_fields(conn,'asset_type',type_id,body,['name','detail_fields','stages'],['detail_fields','stages'])
