import csv
import io
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import Response
from app import database as db
from app.people import need_role, read_user, area_limit, check_area
from app.department_systems import get_system
from app.imports.read_files import read_file, fetch_file
from app.imports.compare import process_import
from app.settings import upload_limit

router = APIRouter()

def start_batch(user,system_id,name,area_id=None):
    with db.transaction() as conn:
        system = get_system(conn,user,system_id)
        check_area(conn,user,area_id or system['default_area_id'])
        return conn.execute('INSERT INTO import_batch(department_system_id,started_by,file_name) VALUES (%s,%s,%s) RETURNING id',(system_id,user['id'],name)).fetchone()

@router.post('/imports')
async def bring_file(background:BackgroundTasks,department_system_id:int=Form(...),file:UploadFile=File(...),area_id:int|None=Form(None),user=Depends(need_role('editor','admin'))):
    data = await file.read(upload_limit()+1)
    if len(data)>upload_limit():
        raise HTTPException(413,'This file is too large.')
    batch = start_batch(user,department_system_id,file.filename,area_id)
    background.add_task(process_import,batch['id'],file.filename,data,user,area_id)
    return batch

@router.post('/imports/preview')
async def preview(file:UploadFile=File(...),user=Depends(need_role('editor','admin'))):
    try:
        rows = read_file(file.filename,await file.read(upload_limit()+1))
        return {'columns':list(rows[0]) if rows else [],'rows':rows[:20]}
    except ValueError as error:
        raise HTTPException(400,str(error))

@router.post('/imports/from-web-address')
def bring_address(body:dict,background:BackgroundTasks,user=Depends(need_role('editor','admin'))):
    with db.transaction() as conn:
        system = get_system(conn,user,body['department_system_id'])
    try:
        name,data = fetch_file(system['web_address'])
    except (ValueError,OSError) as error:
        raise HTTPException(400,str(error))
    batch = start_batch(user,system['id'],name)
    background.add_task(process_import,batch['id'],name,data,user)
    return batch

def get_batch(batch_id,user):
    row = db.one('SELECT b.* FROM import_batch b JOIN department_system d ON d.id=b.department_system_id JOIN area a ON a.id=d.default_area_id WHERE b.id=%s AND a.path LIKE %s',(batch_id,area_limit(user)+'%'))
    if not row:
        raise HTTPException(404,'This import is not available to you.')
    return row

@router.get('/imports/{batch_id}')
def batch_status(batch_id:int,user=Depends(read_user)):
    row = get_batch(batch_id,user)
    row['problems'] = db.all('SELECT row_number,message FROM import_problem_row WHERE batch_id=%s ORDER BY row_number',(batch_id,))
    return row

@router.get('/imports/{batch_id}/problems')
def problem_rows(batch_id:int,user=Depends(read_user)):
    get_batch(batch_id,user)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Row','Message','Original row'])
    for row in db.all('SELECT row_number,message,row_text FROM import_problem_row WHERE batch_id=%s ORDER BY row_number',(batch_id,)):
        writer.writerow([str(v) if not str(v).startswith(('=','+','-','@')) else "'"+str(v) for v in row.values()])
    return Response(output.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename=problem-rows.csv'})
