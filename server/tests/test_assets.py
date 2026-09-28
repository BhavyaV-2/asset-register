import base64
import math
import pytest
from app import database as db

def tile_at(lon,lat,z):
    return z,int((lon+180)/360*2**z),int((1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*2**z)

def read_fields(data):
    # Minimal reader for the map format: reads field numbers, strings and nested messages.
    position=0
    def number():
        nonlocal position
        result=shift=0
        while True:
            byte=data[position];position+=1
            result|=(byte&127)<<shift
            if byte<128:return result
            shift+=7
    fields=[]
    while position<len(data):
        key=number();wire=key&7
        if wire==0:value=number()
        elif wire==2:
            length=number();value=data[position:position+length];position+=length
        elif wire in [1,5]:
            length=8 if wire==1 else 4;value=data[position:position+length];position+=length
        else:raise AssertionError('Invalid map field')
        fields.append((key>>3,value))
    return fields

def test_map_decodes_and_groups(client,sign_in):
    headers=sign_in('viewer')
    z,x,y=tile_at(72.68,23.25,9)
    response=client.get(f'/map/{z}/{x}/{y}.pbf',headers=headers)
    assert response.status_code==200,response.text
    layers=[read_fields(value) for field,value in read_fields(response.content) if field==3]
    assert any((1,b'assets') in layer and (3,b'count') in layer for layer in layers)
    z,x,y=tile_at(72.68,23.25,15)
    response=client.get(f'/map/{z}/{x}/{y}.pbf',headers=headers)
    assert response.status_code==200
    assert read_fields(response.content)
    assert client.get(f'/map/{z}/{x}/{y}.pbf?type_id=999999',headers=headers).status_code==204

def test_area_limit_across_reads(client,sign_in):
    asset=db.one("SELECT a.id FROM asset a JOIN area r ON r.id=a.area_id WHERE r.name='Sector 3' LIMIT 1")['id']
    editor=sign_in('editor')
    image=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')
    photo=client.post(f'/assets/{asset}/photos',headers=editor,files={'file':('sample.png',image,'image/png')})
    assert photo.status_code==200,photo.text
    photo_id=photo.json()['id']
    assert client.get(f'/photos/{photo_id}/file',headers=editor).content==image
    original=db.one("SELECT area_id FROM app_user WHERE role='viewer'")['area_id']
    other=db.one("SELECT id FROM area WHERE name='Sector 4'")['id']
    db.run("UPDATE app_user SET area_id=%s WHERE role='viewer'",(other,))
    try:
        viewer=sign_in('viewer')
        for path in [f'/assets/{asset}',f'/assets/{asset}/history',f'/photos/{photo_id}/file']:
            assert client.get(path,headers=viewer).status_code==404,path
        assert client.get('/assets',headers=viewer).json()==[]
        assert client.get('/assets?q=AR-',headers=viewer).json()==[]
        assert client.get('/reports/summary',headers=viewer).json()['assets']==0
        assert client.get('/map/0/0/0.pbf',headers=viewer).status_code==204
    finally:
        db.run("UPDATE app_user SET area_id=%s WHERE role='viewer'",(original,))

def test_reports_match_database(client,sign_in):
    report=client.get('/reports/summary',headers=sign_in('admin')).json()
    assert report['assets']==db.one('SELECT count(*) AS n FROM asset WHERE is_active')['n']
    assert sum(r['count'] for r in report['by_family'])==report['assets']
    assert sum(r['count'] for r in report['by_stage'])==report['assets']
    assert report['waiting']['count']==db.one("SELECT count(*) AS n FROM change_request WHERE status='waiting'")['n']
    assert report['problems']['count']==db.one("SELECT count(*) AS n FROM problem_report WHERE status<>'closed'")['n']

def test_no_asset_delete_route(client):
    from app.main import app
    assert not any('DELETE' in (getattr(route,'methods',[]) or []) for route in app.routes)

def test_reject_fake_photo(client,sign_in):
    asset=db.one('SELECT id FROM asset LIMIT 1')['id']
    assert client.post(f'/assets/{asset}/photos',headers=sign_in('editor'),files={'file':('bad.png',b'<script>bad</script>','image/png')}).status_code==400
