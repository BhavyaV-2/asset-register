import hashlib
import json
from psycopg.types.json import Jsonb
from app import database as db
from app.people import check_area
from app.department_systems import get_system
from app.imports.read_files import read_file
from app.imports.map_columns import map_row

def normalize_shape(conn,row):
    if isinstance(row['geometry'],dict):
        shape = conn.execute('SELECT ST_AsText(ST_SetSRID(ST_GeomFromGeoJSON(%s),4326)) AS wkt',(json.dumps(row['geometry']),)).fetchone()['wkt']
    else:
        shape = row['geometry']
    value = conn.execute('WITH g AS (SELECT ST_MakeValid(ST_GeomFromText(%s,4326)) AS shape) SELECT ST_AsText(shape) AS wkt,NOT ST_IsEmpty(shape) AND ST_IsValid(shape) AND ST_XMin(Box3D(shape))>=-180 AND ST_XMax(Box3D(shape))<=180 AND ST_YMin(Box3D(shape))>=-90 AND ST_YMax(Box3D(shape))<=90 AS valid FROM g',(shape,)).fetchone()
    if not value or not value['valid']:
        raise ValueError('The location is empty or outside latitude and longitude limits.')
    row['geometry_wkt'] = value['wkt']
    row.pop('geometry',None)
    return row

def make_request(conn,kind,row,system,area,user,batch=None,asset=None,current=None,candidates=None):
    content = {key:value for key,value in row.items() if key!='raw'}
    fingerprint = hashlib.sha256(json.dumps([system,kind,content],sort_keys=True,default=str).encode()).hexdigest()
    previous = conn.execute('SELECT status FROM change_request WHERE fingerprint=%s ORDER BY id DESC LIMIT 1',(fingerprint,)).fetchone()
    if previous and previous['status'] in ['waiting','rejected']:
        return 'skipped_before' if previous['status']=='rejected' else 'same'
    conn.execute('INSERT INTO change_request(kind,asset_id,area_id,batch_id,department_system_id,summary,proposed,current,match_candidates,fingerprint,created_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',(kind,asset,area,batch,system,{'add_asset':'Add asset','update_asset':'Change asset','link_asset':'These may be the same asset','mark_missing':'Mark asset as missing'}[kind]+': '+str(row.get('name') or row.get('source_id','')),Jsonb(row),Jsonb(current) if current else None,Jsonb(candidates) if candidates else None,fingerprint,user['id']))
    return {'add_asset':'new','update_asset':'changed','link_asset':'possible_match','mark_missing':'missing'}[kind]

def compare_row(conn,row,system,area,user,batch):
    # Serialize imports for a department, including the fingerprint check.
    conn.execute('SELECT pg_advisory_xact_lock(%s)',(system['id'],))
    link = conn.execute('SELECT l.*,a.main_link_id,a.is_active,a.area_id FROM source_link l JOIN asset a ON a.id=l.asset_id WHERE l.department_system_id=%s AND l.source_id=%s',(system['id'],row['source_id'])).fetchone()
    if link:
        check_area(conn,user,link['area_id'])
        conn.execute('UPDATE source_link SET last_seen_at=now() WHERE id=%s',(link['id'],))
        conn.execute('UPDATE asset SET last_checked_at=now() WHERE main_link_id=%s',(link['id'],))
        before = link['official_record']
        shape_same = conn.execute('SELECT ST_Equals(ST_SnapToGrid(ST_GeomFromText(%s,4326),0.000001),ST_SnapToGrid(ST_GeomFromText(%s,4326),0.000001)) OR ST_HausdorffDistance(ST_Transform(ST_GeomFromText(%s,4326),32643),ST_Transform(ST_GeomFromText(%s,4326),32643))<1 AS same',(before['geometry_wkt'],row['geometry_wkt'],before['geometry_wkt'],row['geometry_wkt'])).fetchone()['same']
        if link['is_active'] and shape_same and all(before.get(k)==row.get(k) for k in ['name','stage_key','details','type_key']):
            return 'same'
        row['link_id'] = link['id']
        row['is_active'] = True
        return make_request(conn,'update_asset',row,system['id'],link['area_id'],user,batch,link['asset_id'],before)
    settings = {r['key']:float(r['value']) for r in conn.execute("SELECT * FROM app_setting WHERE key IN ('match_distance_metres','name_match_score')").fetchall()}
    area_row = check_area(conn,user,area)
    matches = conn.execute('''WITH shape AS (SELECT ST_GeomFromText(%s,4326) AS g)
      SELECT a.id::text AS asset_id,a.name,ST_Distance(a.location::geography,g::geography) AS distance_m
      FROM asset a JOIN area r ON r.id=a.area_id,shape
      WHERE a.is_active AND a.asset_type_id=%s AND r.path LIKE %s
      AND ST_DWithin(a.location::geography,g::geography,%s)
      AND (%s::text IS NULL OR a.name IS NULL OR similarity(a.name,%s)>=%s)
      AND CASE WHEN ST_Dimension(g)=0 THEN ST_Dimension(a.location)=0
       WHEN ST_Dimension(g)=1 AND ST_Dimension(a.location)=1 THEN
        ST_Length(ST_Intersection(ST_Transform(g,32643),ST_Buffer(ST_Transform(a.location,32643),%s))) >= .8*LEAST(ST_Length(ST_Transform(g,32643)),ST_Length(ST_Transform(a.location,32643)))
       WHEN ST_Dimension(g)=2 AND ST_Dimension(a.location)=2 THEN
        ST_Area(ST_Intersection(g,a.location)) >= .6*LEAST(ST_Area(g),ST_Area(a.location))
       ELSE false END
      ORDER BY distance_m,a.id LIMIT 3''',(row['geometry_wkt'],row['asset_type_id'],area_row['path']+'%',settings['match_distance_metres'],row['name'],row['name'],settings['name_match_score'],settings['match_distance_metres'])).fetchall()
    for match in matches:
        match['reason'] = 'Same type, nearby location and similar name.'
    return make_request(conn,'link_asset' if matches else 'add_asset',row,system['id'],area,user,batch,candidates=matches)

def process_import(batch_id,name,data,user,area_id=None):
    try:
        rows = read_file(name,data)
        with db.transaction() as conn:
            batch = conn.execute('SELECT * FROM import_batch WHERE id=%s',(batch_id,)).fetchone()
            system = get_system(conn,user,batch['department_system_id'])
            area_id = area_id or system['default_area_id']
            check_area(conn,user,area_id)
            types = {r['key']:r for r in conn.execute('SELECT * FROM asset_type').fetchall()}
            conn.execute("UPDATE import_batch SET status='running',rows_total=%s WHERE id=%s",(len(rows),batch_id))
        counts = {k:0 for k in ['new','changed','same','possible_match','missing','skipped_before','with_problems']}
        for start in range(0,len(rows),500):
            with db.transaction() as conn:
                for number,raw in enumerate(rows[start:start+500],start+1):
                    try:
                        with conn.transaction():
                            row = normalize_shape(conn,map_row(raw,system,types))
                            result = compare_row(conn,row,system,area_id,user,batch_id)
                            if row['details'].get('_not_understood'):
                                conn.execute('INSERT INTO import_problem_row(batch_id,row_number,message,row_text) VALUES (%s,%s,%s,%s)',(batch_id,number,'Some details were kept as supplied because their values were not understood.',json.dumps(raw)))
                            counts[result] += 1
                    except Exception as error:
                        counts['with_problems'] += 1
                        message = str(error) if isinstance(error,(ValueError,KeyError)) else 'This row could not be read. Check its location and values.'
                        conn.execute('INSERT INTO import_problem_row(batch_id,row_number,message,row_text) VALUES (%s,%s,%s,%s)',(batch_id,number,message[:500],json.dumps(raw)))
                conn.execute('UPDATE import_batch SET rows_new=%s,rows_changed=%s,rows_same=%s,rows_possible_match=%s,rows_skipped_before=%s,rows_with_problems=%s WHERE id=%s',(counts['new'],counts['changed'],counts['same'],counts['possible_match'],counts['skipped_before'],counts['with_problems'],batch_id))
        with db.transaction() as conn:
            message = None
            # An unreadable row can hide a known ID. Skip missing detection for that file.
            if system['is_full_list'] and not counts['with_problems']:
                known = conn.execute('SELECT a.id,a.name,a.area_id,l.source_id,l.last_seen_at FROM asset a JOIN source_link l ON l.id=a.main_link_id JOIN area r ON r.id=a.area_id WHERE a.is_active AND l.department_system_id=%s AND r.path LIKE %s',(system['id'],check_area(conn,user,area_id)['path']+'%')).fetchall()
                missing = [r for r in known if r['last_seen_at']<batch['started_at']]
                limit = float(conn.execute("SELECT value FROM app_setting WHERE key='missing_share_limit'").fetchone()['value'])
                if known and len(missing)/len(known)>limit:
                    message = f"This file may be incomplete: {len(missing)/len(known):.0%} of the known assets are not in it. No 'missing' requests were made."
                else:
                    for item in missing:
                        result = make_request(conn,'mark_missing',{'source_id':item['source_id'],'name':item['name']},system['id'],item['area_id'],user,batch_id,item['id'])
                        if result=='missing':
                            counts['missing'] += 1
            conn.execute("UPDATE import_batch SET status='done',rows_missing=%s,message=%s,finished_at=now() WHERE id=%s",(counts['missing'],message,batch_id))
            conn.execute('UPDATE department_system SET last_imported_at=now() WHERE id=%s',(system['id'],))
    except Exception as error:
        db.run("UPDATE import_batch SET status='failed',message=%s,finished_at=now() WHERE id=%s",(str(error)[:500] if isinstance(error,ValueError) else 'This file could not be processed. Check its format and department setup.',batch_id))
