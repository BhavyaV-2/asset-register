import csv
import io
import json
import zipfile
import shapefile
import ipaddress
import socket
import ssl
import http.client
from urllib.parse import urlsplit
from app.settings import upload_limit

def read_file(name, data):
    if len(data)>upload_limit():
        raise ValueError('This file is too large.')
    ending = name.lower().rsplit('.',1)[-1]
    if ending=='csv':
        text = data.decode('utf-8-sig')
        try:
            dialect = csv.Sniffer().sniff(text[:8192],delimiters=',;')
        except csv.Error:
            dialect = csv.excel
        rows = list(csv.DictReader(io.StringIO(text),dialect=dialect))
    elif ending in ['json','geojson']:
        content = json.loads(data)
        if content.get('type')!='FeatureCollection':
            raise ValueError('Choose a GeoJSON FeatureCollection.')
        rows = [dict(item.get('properties') or {},_geometry=item.get('geometry')) for item in content['features']]
    elif ending=='zip':
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = archive.namelist()
            if sum(i.file_size for i in archive.infolist())>upload_limit()*4:
                raise ValueError('The unpacked file is too large.')
            parts = {}
            for suffix in ['shp','shx','dbf','prj']:
                matches = [n for n in names if n.lower().endswith('.'+suffix)]
                if len(matches)!=1:
                    raise ValueError('Include one Shapefile with its shp, shx, dbf and prj files.')
                parts[suffix] = archive.read(matches[0])
            projection = parts.pop('prj').decode('utf-8').upper()
            if 'PROJCS' in projection or not ('GEOGCS' in projection and ('WGS_1984' in projection or 'WGS 84' in projection)):
                raise ValueError('This Shapefile is not in latitude/longitude. Please convert it to WGS84 and upload again.')
            reader = shapefile.Reader(**{k:io.BytesIO(v) for k,v in parts.items()})
            rows = [dict(item.record.as_dict(),_geometry=item.shape.__geo_interface__) for item in reader.iterShapeRecords()]
    else:
        raise ValueError('Choose a CSV, GeoJSON or zipped Shapefile.')
    if len(rows)>200000:
        raise ValueError('Use at most 200,000 rows in one file.')
    return rows

def public_address(address):
    parsed = urlsplit(address)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.port not in [None,443]:
        raise ValueError('Use a public HTTPS address on its usual port.')
    answers = socket.getaddrinfo(parsed.hostname,443,type=socket.SOCK_STREAM)
    if not answers or any(not ipaddress.ip_address(answer[4][0]).is_global for answer in answers):
        raise ValueError('Private and local web addresses are not allowed.')
    return parsed,answers[0][4][0]

def fetch_file(address):
    parsed,ip = public_address(address)
    # Use the checked address for the actual connection, preserving certificate checks.
    # Do not resolve again and do not follow redirects.
    connection = http.client.HTTPSConnection(parsed.hostname,timeout=30)
    connection.sock = ssl.create_default_context().wrap_socket(socket.create_connection((ip,443),timeout=30),server_hostname=parsed.hostname)
    try:
        connection.request('GET',parsed.path+('?' + parsed.query if parsed.query else '') or '/',headers={'Accept':'text/csv, application/geo+json, application/json'})
        response = connection.getresponse()
        if response.status!=200:
            raise ValueError('The web address did not return a file. Redirects are not followed.')
        kind = response.getheader('Content-Type','').split(';')[0]
        if kind not in ['text/csv','application/json','application/geo+json']:
            raise ValueError('The web address must return CSV or GeoJSON.')
        data = response.read(upload_limit()+1)
        if len(data)>upload_limit():
            raise ValueError('This file is too large.')
        return ('download.csv' if kind=='text/csv' else 'download.geojson'),data
    finally:
        connection.close()
