from datetime import date
import calendar
from fastapi import APIRouter, Depends, HTTPException
from psycopg.types.json import Jsonb
from app import database as db
from app.people import read_user, need_role, area_limit, check_asset
from app.apply_changes import write_history

router = APIRouter()

def warranty_end(completion,months):
    month = completion.month-1+months
    year = completion.year+month//12
    month = month%12+1
    return date(year,month,min(completion.day,calendar.monthrange(year,month)[1]))

def under_warranty(completion,end,months,day):
    return months>0 and completion<=day<=end

def refresh_asset_warranty(conn,asset_ids):
    for asset_id in asset_ids:
        row = conn.execute('SELECT c.completion_date,c.warranty_end_date FROM contract c JOIN contract_asset ca ON ca.contract_id=c.id WHERE ca.asset_id=%s AND c.warranty_months>0 ORDER BY c.warranty_end_date DESC,c.id DESC LIMIT 1',(asset_id,)).fetchone()
        conn.execute('UPDATE asset SET warranty_start=%s,warranty_end=%s WHERE id=%s',(row['completion_date'] if row else None,row['warranty_end_date'] if row else None,asset_id))

def visible_contract(conn,user,contract_id):
    row = conn.execute('SELECT c.* FROM contract c WHERE c.id=%s AND EXISTS (SELECT 1 FROM contract_asset ca JOIN asset a ON a.id=ca.asset_id JOIN area r ON r.id=a.area_id WHERE ca.contract_id=c.id AND r.path LIKE %s)',(contract_id,area_limit(user)+'%')).fetchone()
    if not row:
        raise HTTPException(404,'This contract is not available to you.')
    row['assets'] = conn.execute('SELECT a.id,a.register_code,a.name,a.area_id FROM contract_asset ca JOIN asset a ON a.id=ca.asset_id JOIN area r ON r.id=a.area_id WHERE ca.contract_id=%s AND r.path LIKE %s ORDER BY a.register_code',(contract_id,area_limit(user)+'%')).fetchall()
    return row

@router.get('/contracts')
def list_contracts(user=Depends(read_user)):
    return db.all('SELECT c.* FROM contract c WHERE EXISTS (SELECT 1 FROM contract_asset ca JOIN asset a ON a.id=ca.asset_id JOIN area r ON r.id=a.area_id WHERE ca.contract_id=c.id AND r.path LIKE %s) ORDER BY c.id DESC',(area_limit(user)+'%',))

@router.get('/contracts/{contract_id}')
def contract_page(contract_id:int,user=Depends(read_user)):
    with db.transaction() as conn:
        return visible_contract(conn,user,contract_id)

def propose_contract(body,user,contract_id=None):
    with db.transaction() as conn:
        current = visible_contract(conn,user,contract_id) if contract_id else None
        if current:
            body = dict({k:(v.isoformat() if isinstance(v,date) else v) for k,v in current.items() if k!='assets'},**body)
            for row in conn.execute('SELECT asset_id FROM contract_asset WHERE contract_id=%s',(contract_id,)).fetchall():
                check_asset(conn,user,row['asset_id'])
        ids = body.get('asset_ids')
        if body.get('import_batch_id'):
            ids = [str(r['asset_id']) for r in conn.execute("SELECT DISTINCT asset_id FROM change_request WHERE batch_id=%s AND kind='add_asset' AND status='approved'",(body['import_batch_id'],)).fetchall()]
        if not ids:
            raise HTTPException(400,'Choose at least one asset for this contract.')
        assets = [check_asset(conn,user,item) for item in sorted(set(ids))]
        months = int(body['warranty_months'])
        if not 0<=months<=1200:
            raise HTTPException(400,'Use a warranty from 0 to 1,200 months.')
        completion = date.fromisoformat(body['completion_date'])
        proposed = {key:body.get(key) for key in ['contract_number','title','contractor_name','start_date','completion_date','cost_amount','notes']}
        if not all(proposed[k] for k in ['contract_number','title','contractor_name']):
            raise HTTPException(400,'Give the contract number, title and contractor.')
        proposed.update(warranty_months=months,warranty_end_date=warranty_end(completion,months).isoformat(),asset_ids=[str(a['id']) for a in assets],contract_id=contract_id)
        return conn.execute('INSERT INTO change_request(kind,area_id,summary,proposed,current,created_by) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id',('update_contract' if current else 'add_contract',assets[0]['area_id'],'Review contract '+body['contract_number'],Jsonb(proposed),Jsonb({'contract_number':current['contract_number']}) if current else None,user['id'])).fetchone()

@router.post('/contracts')
def add_contract(body:dict,user=Depends(need_role('editor','admin'))):
    return propose_contract(body,user)

@router.patch('/contracts/{contract_id}')
def change_contract(contract_id:int,body:dict,user=Depends(need_role('editor','admin'))):
    return propose_contract(body,user,contract_id)

def apply_contract(conn,request,user):
    row = request['proposed']
    old_ids = []
    if row.get('contract_id'):
        conn.execute('SELECT id FROM contract WHERE id=%s FOR UPDATE',(row['contract_id'],))
        old_ids = [str(a['asset_id']) for a in conn.execute('SELECT asset_id FROM contract_asset WHERE contract_id=%s',(row['contract_id'],)).fetchall()]
    ids = sorted(set(old_ids+row['asset_ids']))
    for asset_id in ids:
        check_asset(conn,user,asset_id,True)
    values = tuple(row.get(k) for k in ['contract_number','title','contractor_name','start_date','completion_date','warranty_months','warranty_end_date','cost_amount','notes'])
    if row.get('contract_id'):
        contract_id = row['contract_id']
        conn.execute('UPDATE contract SET contract_number=%s,title=%s,contractor_name=%s,start_date=%s,completion_date=%s,warranty_months=%s,warranty_end_date=%s,cost_amount=%s,notes=%s WHERE id=%s',values+(contract_id,))
        conn.execute('DELETE FROM contract_asset WHERE contract_id=%s',(contract_id,))
    else:
        contract_id = conn.execute('INSERT INTO contract(contract_number,title,contractor_name,start_date,completion_date,warranty_months,warranty_end_date,cost_amount,notes) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id',values).fetchone()['id']
    for asset_id in row['asset_ids']:
        conn.execute('INSERT INTO contract_asset VALUES (%s,%s)',(contract_id,asset_id))
    refresh_asset_warranty(conn,ids)
    for asset_id in ids:
        write_history(conn,asset_id,user,'contract_linked','Contract links approved: '+row['contract_number'],after=row,request_id=request['id'])
