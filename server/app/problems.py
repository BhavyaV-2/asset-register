from html import escape
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from psycopg.types.json import Jsonb
from app import database as db
from app.people import read_user, need_role, area_limit, check_asset
from app.settings import today
from app.apply_changes import write_history

router = APIRouter()
causes = ['bad_workmanship','damage_by_others','normal_wear','not_sure']

@router.post('/assets/{asset_id}/problems')
def report_problem(asset_id:str,body:dict,user=Depends(need_role('editor','admin'))):
    if not body.get('description','').strip() or body.get('urgency') not in ['minor','major','urgent']:
        raise HTTPException(400,'Describe the problem and choose its urgency.')
    with db.transaction() as conn:
        asset = check_asset(conn,user,asset_id,True)
        contract = conn.execute('SELECT c.* FROM contract c JOIN contract_asset ca ON ca.contract_id=c.id WHERE ca.asset_id=%s AND c.warranty_months>0 AND c.completion_date<=%s AND c.warranty_end_date>=%s ORDER BY c.warranty_end_date DESC LIMIT 1',(asset_id,today(),today())).fetchone()
        row = conn.execute('INSERT INTO problem_report(asset_id,reported_by,description,urgency,under_warranty,contract_id) VALUES (%s,%s,%s,%s,%s,%s) RETURNING *',(asset_id,user['id'],body['description'],body['urgency'],bool(contract),contract['id'] if contract else None)).fetchone()
        conn.execute('UPDATE asset SET open_problem_count=open_problem_count+1 WHERE id=%s',(asset_id,))
        if contract:
            proposed = {'problem_id':row['id'],'description':row['description'],'contract_id':contract['id'],'contract_number':contract['contract_number'],'contractor_name':contract['contractor_name'],'days_left':(contract['warranty_end_date']-today()).days}
            conn.execute("INSERT INTO change_request(kind,asset_id,area_id,summary,proposed,created_by) VALUES ('warranty_claim',%s,%s,%s,%s,%s)",(asset_id,asset['area_id'],'This problem is on an asset that is still under warranty.',Jsonb(proposed),user['id']))
        write_history(conn,asset_id,user,'problem_reported','Problem reported: '+body['description'])
        return row

@router.get('/problems')
def list_problems(status:str|None=None,under_warranty:bool|None=None,user=Depends(read_user)):
    return db.all('SELECT p.*,a.register_code,a.name FROM problem_report p JOIN asset a ON a.id=p.asset_id JOIN area r ON r.id=a.area_id WHERE r.path LIKE %s AND (%s::text IS NULL OR p.status=%s) AND (%s::boolean IS NULL OR p.under_warranty=%s) ORDER BY p.id DESC',(area_limit(user)+'%',status,status,under_warranty,under_warranty))

@router.get('/warranty-claims')
def list_claims(user=Depends(read_user)):
    return db.all('SELECT w.*,p.description,p.asset_id,a.register_code,c.contract_number FROM warranty_claim w JOIN problem_report p ON p.id=w.problem_report_id JOIN asset a ON a.id=p.asset_id JOIN area r ON r.id=a.area_id JOIN contract c ON c.id=w.contract_id WHERE r.path LIKE %s ORDER BY w.id DESC',(area_limit(user)+'%',))

def apply_claim(conn,request,user,body):
    choice = body.get('choice')
    if choice not in causes:
        raise HTTPException(400,'Choose what caused the problem.')
    asset = check_asset(conn,user,request['asset_id'],True)
    problem = conn.execute('SELECT * FROM problem_report WHERE id=%s FOR UPDATE',(request['proposed']['problem_id'],)).fetchone()
    if problem['status']=='closed':
        raise HTTPException(409,'This problem has already been closed.')
    if choice=='bad_workmanship':
        conn.execute('INSERT INTO warranty_claim(problem_report_id,contract_id,approved_by) VALUES (%s,%s,%s)',(problem['id'],problem['contract_id'],user['id']))
        conn.execute("UPDATE problem_report SET status='with_contractor' WHERE id=%s",(problem['id'],))
        conn.execute('UPDATE asset SET repair_hold=true WHERE id=%s',(asset['id'],))
    write_history(conn,asset['id'],user,'warranty_reviewed','Warranty review: '+choice.replace('_',' '),request_id=request['id'])
    return asset['id']

@router.post('/problems/{problem_id}/close')
def close_problem(problem_id:int,body:dict,user=Depends(need_role('editor','admin','reviewer'))):
    if not body.get('note','').strip():
        raise HTTPException(400,'Give a closing note.')
    with db.transaction() as conn:
        row = conn.execute('SELECT * FROM problem_report WHERE id=%s',(problem_id,)).fetchone()
        if not row:
            raise HTTPException(404,'This problem was not found.')
        check_asset(conn,user,row['asset_id'],True)
        row = conn.execute('SELECT * FROM problem_report WHERE id=%s FOR UPDATE',(problem_id,)).fetchone()
        if row['status']=='closed':
            raise HTTPException(409,'This problem is already closed.')
        if conn.execute("SELECT id FROM warranty_claim WHERE problem_report_id=%s AND status='sent'",(problem_id,)).fetchone():
            raise HTTPException(409,'Close the warranty claim first.')
        conn.execute("UPDATE problem_report SET status='closed',closed_at=now(),closing_note=%s WHERE id=%s",(body['note'],problem_id))
        conn.execute('UPDATE asset SET open_problem_count=GREATEST(0,open_problem_count-1) WHERE id=%s',(row['asset_id'],))
        write_history(conn,row['asset_id'],user,'problem_closed','Problem closed: '+body['note'])
    return {'saved':True}

@router.post('/warranty-claims/{claim_id}/close')
def close_claim(claim_id:int,body:dict,user=Depends(need_role('editor','admin','reviewer'))):
    if body.get('outcome') not in ['fixed_by_contractor','closed_without_fix'] or not body.get('note','').strip():
        raise HTTPException(400,'Choose the outcome and give a closing note.')
    with db.transaction() as conn:
        row = conn.execute('SELECT w.*,p.asset_id FROM warranty_claim w JOIN problem_report p ON p.id=w.problem_report_id WHERE w.id=%s',(claim_id,)).fetchone()
        if not row:
            raise HTTPException(404,'This claim was not found.')
        check_asset(conn,user,row['asset_id'],True)
        claim = conn.execute('SELECT status FROM warranty_claim WHERE id=%s FOR UPDATE',(claim_id,)).fetchone()
        if claim['status']!='sent':
            raise HTTPException(409,'This claim is already closed.')
        conn.execute('UPDATE warranty_claim SET status=%s,closed_at=now(),closing_note=%s WHERE id=%s',(body['outcome'],body['note'],claim_id))
        conn.execute("UPDATE asset SET repair_hold=EXISTS(SELECT 1 FROM warranty_claim w JOIN problem_report p ON p.id=w.problem_report_id WHERE p.asset_id=%s AND w.status='sent') WHERE id=%s",(row['asset_id'],row['asset_id']))
        write_history(conn,row['asset_id'],user,'claim_closed','Warranty claim closed: '+body['note'])
    return {'saved':True}

@router.get('/warranty-claims/{claim_id}/letter',response_class=HTMLResponse)
def claim_letter(claim_id:int,user=Depends(read_user)):
    row = db.one('SELECT w.*,p.description,p.asset_id,c.contract_number,c.contractor_name,c.completion_date,c.warranty_end_date,a.register_code,a.name,ST_AsText(a.location) AS location,u.full_name FROM warranty_claim w JOIN problem_report p ON p.id=w.problem_report_id JOIN contract c ON c.id=w.contract_id JOIN asset a ON a.id=p.asset_id JOIN area r ON r.id=a.area_id JOIN app_user u ON u.id=w.approved_by WHERE w.id=%s AND r.path LIKE %s',(claim_id,area_limit(user)+'%'))
    if not row:
        raise HTTPException(404,'This claim is not available to you.')
    fields = ''.join('<p><strong>'+label+'</strong>: '+escape(str(row[key] or ''))+'</p>' for label,key in [('Contract','contract_number'),('Contractor','contractor_name'),('Asset','register_code'),('Name','name'),('Location','location'),('Problem','description'),('Completed','completion_date'),('Warranty ends','warranty_end_date'),('Prepared for review by','full_name')])
    return '<!doctype html><html lang="en"><meta charset="utf-8"><title>Warranty claim letter</title><body><h1>Warranty claim letter</h1>'+fields+'<p>Please arrange repair under the contract warranty.</p><footer>Prepared by the Asset Register for a person to review and send. The register does not send anything.</footer></body></html>'
