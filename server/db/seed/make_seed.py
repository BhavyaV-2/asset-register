import json
import os
from pathlib import Path
import bcrypt
from psycopg.types.json import Jsonb
from app.database import transaction

def make_seed():
    with transaction() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(731205)')
        if conn.execute('SELECT id FROM app_user LIMIT 1').fetchone():
            return
        password = os.environ.get('DEMO_PASSWORD', '')
        if not 10 <= len(password.encode()) <= 72:
            raise ValueError('Set DEMO_PASSWORD to 10 to 72 bytes before the first start.')
        for rank, name in enumerate(['State','District','City','Zone or Ward'], 1):
            conn.execute('INSERT INTO area_level VALUES (%s,%s)', (rank,name))
        parent = None
        path = '/'
        for rank, name in enumerate(['Gujarat','Gandhinagar district','Gandhinagar city'], 1):
            parent = conn.execute('INSERT INTO area(parent_id,name,level_rank,path) VALUES (%s,%s,%s,%s) RETURNING id',(parent,name,rank,path)).fetchone()['id']
            path += str(parent)+'/'
            conn.execute('UPDATE area SET path=%s WHERE id=%s',(path,parent))
        for number in range(1,9):
            row = conn.execute('INSERT INTO area(parent_id,name,level_rank,path) VALUES (%s,%s,4,%s) RETURNING id',(parent,f'Sector {number}',path)).fetchone()
            conn.execute('UPDATE area SET path=%s WHERE id=%s',(path+str(row['id'])+'/',row['id']))
        catalog = json.loads((Path(__file__).parent/'asset_catalog.json').read_text())
        for item in catalog:
            family = conn.execute('INSERT INTO asset_family(name,sort_order) VALUES (%s,%s) ON CONFLICT(name) DO UPDATE SET name=EXCLUDED.name RETURNING id',(item['family'],len(catalog))).fetchone()['id']
            conn.execute('INSERT INTO asset_type(family_id,key,name,usual_shape,detail_fields,stages) VALUES (%s,%s,%s,%s,%s,%s)',(family,item['key'],item['name'],item['usual_shape'],Jsonb(item['detail_fields']),Jsonb(item['stages'])))
        hashed = bcrypt.hashpw(password.encode(),bcrypt.gensalt()).decode()
        for role in ['viewer','editor','reviewer','admin']:
            conn.execute('INSERT INTO app_user(email,full_name,password_hash,role,area_id) VALUES (%s,%s,%s,%s,%s)',(role+'@example.org','Sample '+role,hashed,role,None if role=='admin' else parent))
        systems = [
            ('Roads Department road list','Roads Department','road',True,{'source_id':'road_id','name':'road_name','asset_type':{'fixed':'road'},'stage':{'column':'status','values':{'Working':'in_use','Broken':'needs_repair'}},'location':{'wkt':'wkt'},'details':{'width_m':'width','surface':'surface_type','lanes':'lanes'}}),
            ('Municipal street light list','Municipality','street_light',True,{'source_id':'light_no','name':'place','asset_type':{'fixed':'street_light'},'stage':{'column':'working','values':{'yes':'in_use','no':'needs_repair'}},'location':{'latitude':'lat','longitude':'lon'},'details':{'lamp_kind':'lamp','watts':'watts'}}),
            ('Ward electrical list','Ward office','street_light',False,{'source_id':'light_no','name':'place','asset_type':{'fixed':'street_light'},'location':{'latitude':'lat','longitude':'lon'},'details':{'lamp_kind':'lamp','watts':'watts'}}),
            ('Water Board network','Water Board',None,True,{'source_id':'id','name':'name','asset_type':{'column':'kind','values':{'pipeline':'water_pipeline','tank':'water_tank','plant':'water_treatment'}},'location':{'geojson':True}}),
        ]
        for name,department,kind,full,mapping in systems:
            type_id = conn.execute('SELECT id FROM asset_type WHERE key=%s',(kind,)).fetchone() if kind else None
            conn.execute("INSERT INTO department_system(name,department_name,connection,default_area_id,fixed_asset_type_id,column_mapping,is_full_list) VALUES (%s,%s,'file',%s,%s,%s,%s)",(name,department,parent,type_id['id'] if type_id else None,Jsonb(mapping),full))

if __name__ == '__main__':
    from app.database import migrate
    migrate()
    make_seed()
