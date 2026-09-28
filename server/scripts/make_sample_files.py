"""All records here are made up, with repeatable locations around Gandhinagar."""
import csv
import json
from pathlib import Path
import random

folder=Path(__file__).resolve().parents[1]/'db/seed/samples'

def write_csv(name,rows):
    with (folder/name).open('w',newline='',encoding='utf-8') as output:
        writer=csv.DictWriter(output,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

def make_sample_files():
    folder.mkdir(exist_ok=True)
    random.seed(42)
    roads=[]
    for number in range(65):
        lat=23.19+(number//8)*.006
        lon=72.61+(number%8)*.008
        roads.append(dict(road_id=f'R-{number+1:03}',road_name=f'Sample Sector Road {number+1}',width=6, surface_type='asphalt',lanes=2,status='Working',wkt=f'LINESTRING({lon} {lat},{lon+.005} {lat+.001})',_sample='true'))
    write_csv('roads_first.csv',roads[:60])
    second=[dict(row) for row in roads[:58]+roads[60:]]
    for row in second[:5]:row['width']=7.5
    for row in second[5:8]:row['status']='Broken'
    write_csv('roads_second_version.csv',second)
    lights=[]
    for number in range(400):
        road=number%60
        lights.append(dict(light_no=f'L-{number+1:04}',place=f'Sample Road {road+1} light {number+1}',lat=23.19+(road//8)*.006+(number//60)*.00013,lon=72.61+(road%8)*.008+(number//60)*.00065,lamp='LED',watts=40,working='yes',_sample='true'))
    write_csv('lights_first.csv',lights)
    copies=[dict(row,light_no=f'W-{n+1:04}',lat=row['lat']+.00009,place=row['place']+' pole') for n,row in enumerate(lights[:100])]
    write_csv('lights_second.csv',copies)
    features=[]
    for number in range(48):
        lon=72.61+(number%8)*.008
        lat=23.195+(number//8)*.006
        kind='pipeline' if number<40 else 'tank' if number<46 else 'plant'
        geometry={'type':'LineString','coordinates':[[lon,lat],[lon+.005,lat+.001]]} if kind=='pipeline' else {'type':'Point','coordinates':[lon,lat]}
        features.append({'type':'Feature','properties':{'id':f'WATER-{number+1}','name':f'Sample water {kind} {number+1}','kind':kind,'_sample':True},'geometry':geometry})
    (folder/'water_network.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},indent=2))
    print('Sample files: 60 roads, 400 lights, 100 possible matches, 48 water assets.')

if __name__=='__main__':make_sample_files()
