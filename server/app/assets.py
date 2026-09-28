from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg.types.json import Jsonb
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
        row['projects']=conn.execute('SELECT p.id,p.code,p.name,p.current_stage_key,pa.relation_kind FROM project_asset pa JOIN project p ON p.id=pa.project_id WHERE pa.asset_id=%s ORDER BY pa.linked_at DESC',(asset_id,)).fetchall() if conn.execute("SELECT to_regclass('public.project_asset')").fetchone()['to_regclass'] else []
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

@router.post('/assets')
def create_asset(body:dict,user=Depends(need_role('admin'))):
    asset_type_id=body.get('asset_type_id')
    area_id=body.get('area_id')
    name=(body.get('name') or '').strip()
    stage_key=body.get('stage_key')
    details=body.get('details') or {}
    wkt=body.get('geometry_wkt') or body.get('location')
    lat=body.get('latitude')
    lon=body.get('longitude')
    if not asset_type_id or not area_id or not stage_key:
        raise HTTPException(400,'Asset type, area, and stage are required.')
    if not wkt and lat is not None and lon is not None:
        try:
            wkt=f'POINT({float(lon)} {float(lat)})'
        except (ValueError,TypeError):
            raise HTTPException(400,'Invalid coordinates.')
    if not wkt:
        wkt='POINT(72.65 23.22)'
    with db.transaction() as conn:
        check_area(conn,user,area_id)
        type_row=conn.execute('SELECT stages FROM asset_type WHERE id=%s',(asset_type_id,)).fetchone()
        if not type_row:
            raise HTTPException(404,'Asset type not found.')
        valid_stages=[s.get('key') for s in type_row['stages']] if isinstance(type_row['stages'],list) else []
        if valid_stages and stage_key not in valid_stages:
            stage_key=valid_stages[0]
        row=conn.execute("INSERT INTO asset(register_code,asset_type_id,area_id,name,location,stage_key,details) VALUES ('AR-'||lpad(nextval('asset_number_seq')::text,7,'0'),%s,%s,%s,ST_GeomFromText(%s,4326),%s,%s) RETURNING id,register_code,name,stage_key,area_id,asset_type_id,is_active",(asset_type_id,area_id,name,wkt,stage_key,Jsonb(details))).fetchone()
        write_history(conn,row['id'],user,'admin_created','Created directly by administrator.',after=dict(name=name,stage=stage_key))
        return row

@router.patch('/assets/{asset_id}')
def update_asset(asset_id:str,body:dict,user=Depends(need_role('admin'))):
    with db.transaction() as conn:
        current=check_asset(conn,user,asset_id,lock=True)
        updates=[]
        values=[]
        if 'name' in body:
            updates.append('name = %s')
            values.append((body['name'] or '').strip())
        if 'stage_key' in body and body['stage_key']:
            updates.append('stage_key = %s')
            values.append(body['stage_key'])
        if 'area_id' in body and body['area_id']:
            check_area(conn,user,body['area_id'])
            updates.append('area_id = %s')
            values.append(body['area_id'])
        if 'asset_type_id' in body and body['asset_type_id']:
            updates.append('asset_type_id = %s')
            values.append(body['asset_type_id'])
        if 'details' in body and isinstance(body['details'],dict):
            updates.append('details = %s')
            values.append(Jsonb(body['details']))
        if 'is_active' in body:
            updates.append('is_active = %s')
            values.append(bool(body['is_active']))
        if 'geometry_wkt' in body and body['geometry_wkt']:
            updates.append('location = ST_GeomFromText(%s,4326)')
            values.append(body['geometry_wkt'])
        elif 'latitude' in body and 'longitude' in body and body['latitude'] is not None and body['longitude'] is not None:
            updates.append('location = ST_SetSRID(ST_Point(%s,%s),4326)')
            values.extend([float(body['longitude']),float(body['latitude'])])
        if not updates:
            return current
        updates.append('updated_at = now()')
        values.append(asset_id)
        updated=conn.execute(f"UPDATE asset SET {', '.join(updates)} WHERE id = %s RETURNING id,register_code,name,stage_key,area_id,asset_type_id,is_active",values).fetchone()
        write_history(conn,asset_id,user,'admin_updated','Updated directly by administrator.',before={'name':current['name'],'stage':current['stage_key']},after={'name':updated['name'],'stage':updated['stage_key']})
        return updated

@router.delete('/assets/{asset_id}')
def delete_asset(asset_id:str,user=Depends(need_role('admin'))):
    with db.transaction() as conn:
        check_asset(conn,user,asset_id,lock=True)
        conn.execute('UPDATE asset SET is_active=false,updated_at=now() WHERE id=%s',(asset_id,))
        write_history(conn,asset_id,user,'admin_deactivated','Deactivated directly by administrator.')
        return {'ok':True,'id':asset_id,'is_active':False}
