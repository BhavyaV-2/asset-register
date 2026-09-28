import pytest
import psycopg
from app import database as db
from app.map_pieces import map_piece
from test_assets import read_fields,tile_at

def test_map_piece_limit(client,monkeypatch):
    with db.transaction() as conn:
        conn.execute("SELECT set_config('asset_register.skip_map_counts','true',true)")
        area=conn.execute("SELECT id FROM area WHERE name='Sector 3'").fetchone()['id']
        kind=conn.execute("SELECT id FROM asset_type WHERE key='street_light'").fetchone()['id']
        conn.execute("INSERT INTO asset(register_code,asset_type_id,area_id,location,stage_key) SELECT 'LIMIT-'||nextval('asset_number_seq'),%s,%s,ST_SetSRID(ST_Point(72.9,23.5),4326),'in_use' FROM generate_series(1,20001)",(kind,area))
        monkeypatch.setattr(db,'one',lambda query,values=():conn.execute(query,values).fetchone())
        z,x,y=tile_at(72.9,23.5,15)
        response=map_piece(z,x,y,user={'area_path':None})
        assert response.headers['x-tile-trimmed']=='yes'
        layers=[read_fields(value) for key,value in read_fields(response.body) if key==3]
        assert sum(1 for layer in layers for key,value in layer if key==2)==20000
        raise psycopg.Rollback()
