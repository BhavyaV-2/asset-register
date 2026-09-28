from fastapi import APIRouter, Depends, HTTPException
from psycopg.types.json import Jsonb
from app import database as db
from app.people import read_user, need_role, area_limit, check_area
from app.areas import save_fields

router = APIRouter()

def get_system(conn,user,system_id):
    row = conn.execute('SELECT d.* FROM department_system d JOIN area a ON a.id=d.default_area_id WHERE d.id=%s AND a.path LIKE %s',(system_id,area_limit(user)+'%')).fetchone()
    if not row:
        raise HTTPException(404,'This department system is not available to you.')
    return row

@router.get('/department-systems')
def list_systems(user=Depends(read_user)):
    return db.all('SELECT d.* FROM department_system d JOIN area a ON a.id=d.default_area_id WHERE a.path LIKE %s ORDER BY d.id',(area_limit(user)+'%',))

@router.post('/department-systems')
def add_system(body:dict,user=Depends(need_role('admin'))):
    with db.transaction() as conn:
        check_area(conn,user,body['default_area_id'])
        return conn.execute('INSERT INTO department_system(name,department_name,connection,web_address,default_area_id,fixed_asset_type_id,column_mapping,is_full_list,default_stage_key) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *',(body['name'],body['department_name'],body.get('connection','file'),body.get('web_address'),body['default_area_id'],body.get('fixed_asset_type_id'),Jsonb(body.get('column_mapping',{})),body.get('is_full_list',False),body.get('default_stage_key','in_use'))).fetchone()

@router.patch('/department-systems/{system_id}')
def change_system(system_id:int,body:dict,user=Depends(need_role('editor','admin'))):
    with db.transaction() as conn:
        get_system(conn,user,system_id)
        if user['role']=='editor' and set(body) != {'column_mapping'}:
            raise HTTPException(403,'Editors can only change the column mapping.')
        if 'default_area_id' in body:
            check_area(conn,user,body['default_area_id'])
        return save_fields(conn,'department_system',system_id,body,['name','department_name','connection','web_address','default_area_id','fixed_asset_type_id','column_mapping','is_full_list','default_stage_key'],['column_mapping'])
