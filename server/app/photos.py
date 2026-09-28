import uuid
from fastapi import APIRouter,Depends,HTTPException,UploadFile,File,Form
from fastapi.responses import Response
from app import database as db
from app.people import read_user,need_role,check_asset,area_limit
from app.apply_changes import write_history
from app.file_store import storage,bucket_request

router=APIRouter()

def image_kind(data):
    if data.startswith(b'\xff\xd8\xff') and data.endswith(b'\xff\xd9'):
        return 'image/jpeg'
    if data.startswith(b'\x89PNG\r\n\x1a\n') and b'IEND' in data[-16:]:
        return 'image/png'
    if data.startswith(b'RIFF') and data[8:12]==b'WEBP':
        return 'image/webp'
    raise HTTPException(400,'Choose a JPEG, PNG or WebP picture.')

@router.post('/assets/{asset_id}/photos')
async def add_photo(asset_id:str,file:UploadFile=File(...),taken_lat:float|None=Form(None),taken_lon:float|None=Form(None),problem_id:int|None=Form(None),user=Depends(need_role('editor','admin'))):
    data=await file.read(5*1024*1024+1)
    if len(data)>5*1024*1024:
        raise HTTPException(413,'Use a picture smaller than 5 MB.')
    kind=image_kind(data)
    if file.content_type!=kind:
        raise HTTPException(400,'The picture type does not match its contents.')
    if (taken_lat is None)!=(taken_lon is None) or (taken_lat is not None and not (-90<=taken_lat<=90 and -180<=taken_lon<=180)):
        raise HTTPException(400,'Give a valid latitude and longitude together.')
    with db.transaction() as conn:
        check_asset(conn,user,asset_id)
        if problem_id and not conn.execute('SELECT id FROM problem_report WHERE id=%s AND asset_id=%s',(problem_id,asset_id)).fetchone():
            raise HTTPException(400,'This problem does not belong to this asset.')
        key='photos/'+uuid.uuid4().hex if storage()=='s3' else None
        if key:
            bucket_request('PUT',key,data)
        row=conn.execute('INSERT INTO photo(asset_id,problem_report_id,uploaded_by,content_type,file_bytes,file_key,taken_lat,taken_lon) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id',(asset_id,problem_id,user['id'],kind,None if key else data,key,taken_lat,taken_lon)).fetchone()
        write_history(conn,asset_id,user,'photo_added','Photo added. Any phone location is a hint only.')
        return row

@router.get('/photos/{photo_id}/file')
def photo_file(photo_id:int,user=Depends(read_user)):
    row=db.one('SELECT p.* FROM photo p JOIN asset a ON a.id=p.asset_id JOIN area r ON r.id=a.area_id WHERE p.id=%s AND r.path LIKE %s',(photo_id,area_limit(user)+'%'))
    if not row:
        raise HTTPException(404,'This photo is not available to you.')
    data=bucket_request('GET',row['file_key']) if row['file_key'] else bytes(row['file_bytes'])
    return Response(data,media_type=row['content_type'],headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})
