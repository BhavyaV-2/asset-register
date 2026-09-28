import math
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from app import database as db
from app.people import read_user
from app.assets import asset_filter

router=APIRouter()

@router.get('/map/{z}/{x}/{y}.pbf')
def map_piece(z:int,x:int,y:int,type_id:int|None=None,family_id:int|None=None,stage_key:str|None=None,under_warranty:bool|None=None,has_open_problem:bool|None=None,user=Depends(read_user)):
    if not 0<=z<=22 or not 0<=x<2**z or not 0<=y<2**z:
        raise HTTPException(400,'Choose a valid part of the map.')
    where,values=asset_filter(user,type_id=type_id,family_id=family_id,stage_key=stage_key,under_warranty=under_warranty,has_open_problem=has_open_problem)
    values.update(z=z,x=x,y=y,tolerance=0 if z>=14 else 40075016.686/(2**z*4096))
    common='''WITH env AS (SELECT ST_TileEnvelope(%(z)s,%(x)s,%(y)s) AS box),picked AS (
      SELECT a.* FROM asset a JOIN area r ON r.id=a.area_id JOIN asset_type t ON t.id=a.asset_type_id,env
      WHERE a.location && ST_Transform(env.box,4326) AND '''+where+') '
    if z<=9:
        width=360.0/(2**z)/12
        north=math.degrees(math.atan(math.sinh(math.pi*(1-2*y/(2**z)))))
        south=math.degrees(math.atan(math.sinh(math.pi*(1-2*(y+1)/(2**z)))))
        values.update(left=-6*(2**z)+12*x-1,right=-6*(2**z)+12*(x+1)+1,bottom=math.floor(south/width)-1,top=math.ceil(north/width)+1)
        query='''WITH env AS (SELECT ST_TileEnvelope(%(z)s,%(x)s,%(y)s) AS box),dots AS (
          SELECT ST_SetSRID(ST_Point(m.cell_x*360.0/power(2,%(z)s)/12,m.cell_y*360.0/power(2,%(z)s)/12),4326) AS dot,sum(m.asset_count)::int AS count
          FROM map_count m JOIN area r ON r.id=m.area_id JOIN asset_type t ON t.id=m.asset_type_id,env
          WHERE m.zoom=%(z)s AND m.asset_count>0 AND r.path LIKE %(path)s
          AND m.cell_x BETWEEN %(left)s AND %(right)s
          AND m.cell_y BETWEEN %(bottom)s AND %(top)s
          AND (%(type)s::int IS NULL OR m.asset_type_id=%(type)s)
          AND (%(family)s::int IS NULL OR t.family_id=%(family)s)
          AND (%(stage)s::text IS NULL OR m.stage_key=%(stage)s)
          AND (%(problem)s::boolean IS NULL OR m.has_problem=%(problem)s)
          AND (%(warranty)s::boolean IS NULL OR (m.warranty_start<=%(day)s AND m.warranty_end>=%(day)s)=%(warranty)s)
          GROUP BY m.cell_x,m.cell_y
        ),packed AS (SELECT count,ST_AsMVTGeom(ST_Transform(dot,3857),env.box,4096,64,true) AS geom FROM dots,env)
        SELECT ST_AsMVT(packed,'assets',4096,'geom') AS tile,false AS trimmed FROM packed WHERE geom IS NOT NULL'''
    else:
        query=common+''' ,chosen AS (SELECT * FROM picked ORDER BY ST_Area(location) DESC,ST_Length(location) DESC,id LIMIT 20000),packed AS (
          SELECT id::text AS id,asset_type_id AS type_id,stage_key AS stage,(open_problem_count>0) AS has_problem,
          COALESCE(warranty_start<=%(day)s AND warranty_end>=%(day)s,false) AS under_warranty,
          ST_AsMVTGeom(ST_SimplifyPreserveTopology(ST_Transform(location,3857),%(tolerance)s),env.box,4096,64,true) AS geom FROM chosen,env)
          SELECT ST_AsMVT(packed,'assets',4096,'geom') AS tile,(SELECT count(*)>20000 FROM picked) AS trimmed FROM packed WHERE geom IS NOT NULL'''
    row=db.one(query,values)
    data=bytes(row['tile'])
    headers={'Cache-Control':'private, max-age=60','Vary':'Authorization'}
    if row['trimmed']:
        headers['X-Tile-Trimmed']='yes'
    return Response(data,status_code=200 if data else 204,media_type='application/vnd.mapbox-vector-tile',headers=headers)
