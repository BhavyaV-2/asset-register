from fastapi import APIRouter, Depends, HTTPException, Query
from app import database as db
from app.people import read_user, need_role, area_limit, check_asset, check_area
from app.apply_changes import write_history
from app.settings import today

router=APIRouter()

def asset_filter(user,q='',family_id=None,type_id=None,stage_key=None,area_id=None,under_warranty=None,has_open_problem=None,not_checked_months=None,is_active=True,warranty_ending=False):
    prefix=area_limit(user)
    if area_id:
        with db.transaction() as conn:
            prefix=check_area(conn,user,area_id)['path']
    conditions=['r.path LIKE %(path)s','(%(active)s::boolean IS NULL OR a.is_active=%(active)s)',
      '(%(family)s::int IS NULL OR t.family_id=%(family)s)','(%(type)s::int IS NULL OR a.asset_type_id=%(type)s)',
      '(%(stage)s::text IS NULL OR a.stage_key=%(stage)s)',
      '(%(warranty)s::boolean IS NULL OR COALESCE(a.warranty_start<=%(day)s AND a.warranty_end>=%(day)s,false)=%(warranty)s)',
      '(%(problem)s::boolean IS NULL OR (a.open_problem_count>0)=%(problem)s)',
      '(%(months)s::int IS NULL OR a.last_checked_at IS NULL OR a.last_checked_at < now()-make_interval(months=>%(months)s))',
      '(NOT %(ending)s OR (a.warranty_start<=%(day)s AND a.warranty_end BETWEEN %(day)s AND %(day)s + 90))',
      "(%(q)s='' OR a.name ILIKE %(search)s OR a.register_code ILIKE %(search)s OR EXISTS (SELECT 1 FROM source_link l WHERE l.asset_id=a.id AND l.source_id ILIKE %(search)s))"]
    return ' AND '.join(conditions),dict(path=prefix+'%',active=is_active,family=family_id,type=type_id,stage=stage_key,warranty=under_warranty,problem=has_open_problem,months=not_checked_months,day=today(),q=q,search='%'+q+'%',ending=warranty_ending)

@router.get('/assets')
def list_assets(q:str='',family_id:int|None=None,type_id:int|None=None,stage_key:str|None=None,area_id:int|None=None,under_warranty:bool|None=None,has_open_problem:bool|None=None,not_checked_months:int|None=Query(None,ge=1,le=120),is_active:bool|None=True,warranty_ending:bool=False,page:int=Query(1,ge=1),user=Depends(read_user)):
    where,values=asset_filter(user,q,family_id,type_id,stage_key,area_id,under_warranty,has_open_problem,not_checked_months,is_active,warranty_ending)
    values['offset']=(page-1)*50
    rows=db.all('SELECT a.id,a.register_code,a.name,a.stage_key,a.area_id,r.name AS area,t.name AS type,t.family_id,a.details,a.open_problem_count,a.warranty_start,a.warranty_end,a.repair_hold,a.last_checked_at,a.is_active,ST_AsGeoJSON(a.location)::json AS shape FROM asset a JOIN area r ON r.id=a.area_id JOIN asset_type t ON t.id=a.asset_type_id WHERE '+where+' ORDER BY a.register_code LIMIT 50 OFFSET %(offset)s',values)
    for row in rows:
        row['matched_field']='Name' if q.casefold() in (row['name'] or '').casefold() else 'Register code' if q.casefold() in row['register_code'].casefold() else 'Department ID'
    return rows

@router.get('/assets/{asset_id}')
def asset_page(asset_id:str,user=Depends(read_user)):
    with db.transaction() as conn:
        row=check_asset(conn,user,asset_id)
        row.pop('location')
        row['type']=conn.execute('SELECT * FROM asset_type WHERE id=%s',(row['asset_type_id'],)).fetchone()
        row['area']=conn.execute('SELECT name FROM area WHERE id=%s',(row['area_id'],)).fetchone()['name']
        row['links']=conn.execute('SELECT l.*,d.name AS system FROM source_link l JOIN department_system d ON d.id=l.department_system_id WHERE l.asset_id=%s ORDER BY l.is_main DESC,l.id',(asset_id,)).fetchall()
        row['contracts']=conn.execute('SELECT c.* FROM contract c JOIN contract_asset ca ON ca.contract_id=c.id WHERE ca.asset_id=%s',(asset_id,)).fetchall()
        row['problems']=conn.execute('SELECT * FROM problem_report WHERE asset_id=%s ORDER BY id DESC',(asset_id,)).fetchall()
        row['photos']=conn.execute('SELECT p.id,p.created_at,p.taken_lat,p.taken_lon,CASE WHEN p.taken_lat IS NOT NULL THEN round(ST_Distance(ST_SetSRID(ST_Point(p.taken_lon,p.taken_lat),4326)::geography,a.location::geography)) END AS distance_m FROM photo p JOIN asset a ON a.id=p.asset_id WHERE p.asset_id=%s ORDER BY p.id DESC',(asset_id,)).fetchall()
        row['notes']=conn.execute('SELECT n.*,u.full_name FROM asset_note n JOIN app_user u ON u.id=n.user_id WHERE n.asset_id=%s ORDER BY n.id DESC',(asset_id,)).fetchall()
        return row

@router.get('/assets/{asset_id}/history')
def asset_history(asset_id:str,page:int=Query(1,ge=1),user=Depends(read_user)):
    with db.transaction() as conn:
        check_asset(conn,user,asset_id)
        return conn.execute('SELECT h.*,u.full_name FROM history_entry h LEFT JOIN app_user u ON u.id=h.who_user_id WHERE h.asset_id=%s ORDER BY h.happened_at DESC,h.id DESC LIMIT 50 OFFSET %s',(asset_id,(page-1)*50)).fetchall()

@router.post('/assets/{asset_id}/notes')
def add_note(asset_id:str,body:dict,user=Depends(need_role('editor','reviewer','admin'))):
    if body.get('kind') not in ['note','correction_for_department'] or not body.get('body','').strip():
        raise HTTPException(400,'Write a note and choose its kind.')
    with db.transaction() as conn:
        check_asset(conn,user,asset_id)
        row=conn.execute('INSERT INTO asset_note(asset_id,user_id,kind,body) VALUES (%s,%s,%s,%s) RETURNING id',(asset_id,user['id'],body['kind'],body['body'])).fetchone()
        write_history(conn,asset_id,user,'note_added','Note added: '+body['body'])
        return row
