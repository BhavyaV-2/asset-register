from fastapi import HTTPException
from psycopg.types.json import Jsonb
from app.people import check_asset

def write_history(conn,asset_id,user,what,summary,before=None,after=None,request_id=None):
    conn.execute('INSERT INTO history_entry(asset_id,who_user_id,what,summary,before_value,after_value,change_request_id) VALUES (%s,%s,%s,%s,%s,%s,%s)',(asset_id,user['id'],what,summary,Jsonb(before) if before else None,Jsonb(after) if after else None,request_id))

def add_asset(conn,request,user):
    row = request['proposed']
    conn.execute('SELECT id FROM asset_type WHERE id=%s FOR SHARE',(row['asset_type_id'],))
    if not conn.execute('SELECT id FROM asset_type WHERE id=%s AND EXISTS (SELECT 1 FROM jsonb_array_elements(stages) s WHERE s->>\'key\'=%s)',(row['asset_type_id'],row['stage_key'])).fetchone():
        raise HTTPException(409,'The asset type stages changed. Import this row again.')
    asset = conn.execute("INSERT INTO asset(register_code,asset_type_id,area_id,name,location,stage_key,details,last_checked_at) VALUES ('AR-'||lpad(nextval('asset_number_seq')::text,7,'0'),%s,%s,%s,ST_GeomFromText(%s,4326),%s,%s,now()) RETURNING id",(row['asset_type_id'],request['area_id'],row['name'],row['geometry_wkt'],row['stage_key'],Jsonb(row['details']))).fetchone()['id']
    link = conn.execute('INSERT INTO source_link(asset_id,department_system_id,source_id,is_main,official_record) VALUES (%s,%s,%s,true,%s) RETURNING id',(asset,request['department_system_id'],row['source_id'],Jsonb(row))).fetchone()['id']
    conn.execute('UPDATE asset SET main_link_id=%s WHERE id=%s',(link,asset))
    conn.execute('UPDATE change_request SET asset_id=%s WHERE id=%s',(asset,request['id']))
    write_history(conn,asset,user,'added','Added to the register from the department system.',after=row,request_id=request['id'])
    return asset

def update_asset(conn,request,user):
    row = request['proposed']
    asset = check_asset(conn,user,request['asset_id'],True)
    link = conn.execute('SELECT * FROM source_link WHERE id=%s FOR UPDATE',(row['link_id'],)).fetchone()
    if link['official_record']!=request['current']:
        raise HTTPException(409,'This record changed after the request was made. Import the latest file again.')
    if link['id']==asset['main_link_id']:
        conn.execute('UPDATE asset SET name=%s,asset_type_id=%s,stage_key=%s,details=%s,location=ST_GeomFromText(%s,4326),is_active=true,updated_at=now() WHERE id=%s',(row['name'],row['asset_type_id'],row['stage_key'],Jsonb(row['details']),row['geometry_wkt'],asset['id']))
    conn.execute('UPDATE source_link SET official_record=%s WHERE id=%s',(Jsonb(row),link['id']))
    write_history(conn,asset['id'],user,'changed','Accepted a newer department record.',request['current'],row,request['id'])
    return asset['id']

def link_asset(conn,request,user,body):
    if body.get('choice')=='different_asset':
        return add_asset(conn,request,user)
    if body.get('choice')!='same_asset' or body.get('asset_id') not in [r['asset_id'] for r in request['match_candidates']]:
        raise HTTPException(400,'Choose one of the suggested assets, or choose a different asset.')
    asset = check_asset(conn,user,body['asset_id'],True)
    row = request['proposed']
    conn.execute('INSERT INTO source_link(asset_id,department_system_id,source_id,official_record) VALUES (%s,%s,%s,%s)',(asset['id'],request['department_system_id'],row['source_id'],Jsonb(row)))
    conn.execute('UPDATE change_request SET asset_id=%s WHERE id=%s',(asset['id'],request['id']))
    write_history(conn,asset['id'],user,'linked','Linked another department record.',after=row,request_id=request['id'])
    return asset['id']

def mark_missing(conn,request,user):
    asset = check_asset(conn,user,request['asset_id'],True)
    link = conn.execute('SELECT last_seen_at FROM source_link WHERE id=%s',(asset['main_link_id'],)).fetchone()
    if link['last_seen_at']>request['created_at']:
        raise HTTPException(409,'A newer file lists this asset. It cannot be marked missing from this request.')
    conn.execute('UPDATE asset SET is_active=false,updated_at=now() WHERE id=%s',(asset['id'],))
    write_history(conn,asset['id'],user,'marked_missing','No longer listed by the department; approved as missing.',request_id=request['id'])
    return asset['id']

def apply_request(conn,request,user,body):
    kind = request['kind']
    if kind=='add_asset':
        return add_asset(conn,request,user)
    if kind=='update_asset':
        return update_asset(conn,request,user)
    if kind=='link_asset':
        return link_asset(conn,request,user,body)
    if kind=='mark_missing':
        return mark_missing(conn,request,user)
    if kind in ['add_contract','update_contract']:
        from app.contracts import apply_contract
        return apply_contract(conn,request,user)
    if kind=='warranty_claim':
        from app.problems import apply_claim
        return apply_claim(conn,request,user,body)
    raise HTTPException(400,'This request kind is not supported.')
