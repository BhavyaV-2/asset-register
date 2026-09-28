from fastapi import APIRouter, Depends, HTTPException, Query
from app import database as db
from app.people import read_user, need_role, area_limit, check_area
from app.apply_changes import apply_request, write_history

router = APIRouter()

@router.get('/change-requests')
def list_requests(status:str='waiting',kind:str|None=None,batch_id:int|None=None,area_id:int|None=None,q:str='',page:int=Query(1,ge=1),user=Depends(read_user)):
    prefix = area_limit(user)
    if area_id:
        with db.transaction() as conn:
            prefix = check_area(conn,user,area_id)['path']
    return db.all('SELECT c.*,u.full_name AS made_by FROM change_request c JOIN area a ON a.id=c.area_id JOIN app_user u ON u.id=c.created_by WHERE a.path LIKE %s AND c.status=%s AND (%s::text IS NULL OR c.kind=%s) AND (%s::bigint IS NULL OR c.batch_id=%s) AND c.summary ILIKE %s ORDER BY c.id DESC LIMIT 50 OFFSET %s',(prefix+'%',status,kind,kind,batch_id,batch_id,'%'+q+'%',(page-1)*50))

def get_request(conn,user,request_id,lock=False):
    query = 'SELECT c.*,u.full_name AS made_by FROM change_request c JOIN area a ON a.id=c.area_id JOIN app_user u ON u.id=c.created_by WHERE c.id=%s AND a.path LIKE %s'
    if lock:
        query += ' FOR UPDATE OF c'
    row = conn.execute(query,(request_id,area_limit(user)+'%')).fetchone()
    if not row:
        raise HTTPException(404,'This request is not available to you.')
    return row

@router.get('/change-requests/{request_id}')
def request_page(request_id:int,user=Depends(read_user)):
    with db.transaction() as conn:
        return get_request(conn,user,request_id)

def decide_request(request_id,body,user,approve=True,conn=None):
    if conn is None:
        with db.transaction() as current:
            return decide_request(request_id,body,user,approve,current)
    if user['role'] not in ['reviewer','admin']:
        raise HTTPException(403,'Your role cannot decide requests.')
    row = get_request(conn,user,request_id,True)
    if row['created_by']==user['id']:
        raise HTTPException(403,'A different person must approve this request.')
    if row['status']!='waiting':
        raise HTTPException(409,'This request was already decided.')
    if not approve and not str(body.get('note','')).strip():
        raise HTTPException(400,'Give a reason for rejecting this request.')
    result = None
    if approve:
        result = apply_request(conn,row,user,body)
    elif row['asset_id']:
        write_history(conn,row['asset_id'],user,'request_rejected','Request rejected: '+body['note'],request_id=row['id'])
    status = 'approved' if approve else 'rejected'
    if row['kind']=='warranty_claim' and body.get('choice')!='bad_workmanship':
        status = 'rejected'
    conn.execute('UPDATE change_request SET status=%s,decided_by=%s,decided_at=now(),decision_note=%s,decision_choice=%s WHERE id=%s',(status,user['id'],body.get('note'),body.get('choice'),request_id))
    return {'id':request_id,'status':status,'asset_id':str(result) if result else None}

@router.post('/change-requests/approve-many')
def approve_many(body:dict,user=Depends(need_role('reviewer','admin'))):
    ids = body.get('ids',[])
    if not 1<=len(ids)<=200 or len(set(ids))!=len(ids):
        raise HTTPException(400,'Choose between 1 and 200 different requests.')
    with db.transaction() as conn:
        results = []
        for request_id in sorted(ids):
            row = get_request(conn,user,request_id,True)
            if row['kind'] not in ['add_asset','update_asset']:
                raise HTTPException(400,'Only additions and updates can be approved together.')
            results.append(decide_request(request_id,{},user,True,conn))
        return results

@router.post('/change-requests/{request_id}/approve')
def approve(request_id:int,body:dict,user=Depends(need_role('reviewer','admin'))):
    return decide_request(request_id,body,user)

@router.post('/change-requests/{request_id}/reject')
def reject(request_id:int,body:dict,user=Depends(need_role('reviewer','admin'))):
    return decide_request(request_id,body,user,False)
