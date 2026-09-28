"""Photo bytes stay private, whether stored in the database or a bucket."""
import os
import hashlib
import hmac
import http.client
from datetime import datetime,timezone
from urllib.parse import urlsplit,quote

def storage():
    value=os.getenv('PHOTO_STORAGE','database')
    if value not in ['database','s3']:
        raise ValueError('Choose database or s3 photo storage.')
    return value

def bucket_request(method,key,data=b''):
    endpoint=urlsplit(os.environ['S3_ENDPOINT'])
    if endpoint.scheme!='https':
        raise ValueError('Photo storage needs an HTTPS address.')
    path=endpoint.path.rstrip('/')+'/'+quote(os.environ['S3_BUCKET'],safe='')+'/'+quote(key,safe='/')
    now=datetime.now(timezone.utc)
    stamp,day=now.strftime('%Y%m%dT%H%M%SZ'),now.strftime('%Y%m%d')
    region=os.environ.get('S3_REGION','us-east-1')
    digest=hashlib.sha256(data).hexdigest()
    headers=f'host:{endpoint.netloc}\nx-amz-content-sha256:{digest}\nx-amz-date:{stamp}\n'
    names='host;x-amz-content-sha256;x-amz-date'
    canonical='\n'.join([method,path,'',headers,names,digest])
    scope=f'{day}/{region}/s3/aws4_request'
    value='\n'.join(['AWS4-HMAC-SHA256',stamp,scope,hashlib.sha256(canonical.encode()).hexdigest()])
    signing=('AWS4'+os.environ['S3_SECRET']).encode()
    for piece in [day,region,'s3','aws4_request']:
        signing=hmac.new(signing,piece.encode(),hashlib.sha256).digest()
    signature=hmac.new(signing,value.encode(),hashlib.sha256).hexdigest()
    auth=f"AWS4-HMAC-SHA256 Credential={os.environ['S3_KEY']}/{scope}, SignedHeaders={names}, Signature={signature}"
    connection=http.client.HTTPSConnection(endpoint.netloc,timeout=30)
    try:
        connection.request(method,path,body=data if method=='PUT' else None,headers={'Authorization':auth,'x-amz-date':stamp,'x-amz-content-sha256':digest})
        response=connection.getresponse()
        if response.status not in [200,201,204]:
            raise ValueError('Photo storage could not complete this request.')
        return response.read(5*1024*1024+1)
    finally:
        connection.close()
