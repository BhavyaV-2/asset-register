from fastapi import APIRouter,Depends
from app import database as db
from app.people import read_user,area_limit,check_area
from app.settings import today

router=APIRouter()

def report_path(user,area_id):
    if area_id:
        with db.transaction() as conn:
            return check_area(conn,user,area_id)['path']
    return area_limit(user)

@router.get('/reports/summary')
def summary(area_id:int|None=None,user=Depends(read_user)):
    prefix=report_path(user,area_id)+'%'
    months=int(db.one("SELECT value FROM app_setting WHERE key='not_checked_months'")['value'])
    assets=db.one('''SELECT count(*) AS assets,count(*) FILTER (WHERE a.warranty_start<=%s AND a.warranty_end>=%s) AS under_warranty,
      count(*) FILTER (WHERE a.warranty_start<=%s AND a.warranty_end BETWEEN %s AND %s+90) AS warranty_ending,
      count(*) FILTER (WHERE a.last_checked_at IS NULL OR a.last_checked_at<now()-make_interval(months=>%s)) AS not_checked
      FROM asset a JOIN area r ON r.id=a.area_id WHERE a.is_active AND r.path LIKE %s''',(today(),today(),today(),today(),today(),months,prefix))
    assets['waiting']=db.one("SELECT count(*) AS count,min(c.created_at) AS oldest FROM change_request c JOIN area r ON r.id=c.area_id WHERE c.status='waiting' AND r.path LIKE %s",(prefix,))
    assets['problems']=db.one("SELECT count(*) AS count,count(*) FILTER (WHERE p.under_warranty) AS under_warranty FROM problem_report p JOIN asset a ON a.id=p.asset_id JOIN area r ON r.id=a.area_id WHERE p.status<>'closed' AND r.path LIKE %s",(prefix,))
    assets['by_family']=db.all('SELECT f.id,f.name,count(*) AS count FROM asset a JOIN area r ON r.id=a.area_id JOIN asset_type t ON t.id=a.asset_type_id JOIN asset_family f ON f.id=t.family_id WHERE a.is_active AND r.path LIKE %s GROUP BY f.id ORDER BY f.id',(prefix,))
    assets['by_stage']=db.all('SELECT a.stage_key AS key,count(*) AS count FROM asset a JOIN area r ON r.id=a.area_id WHERE a.is_active AND r.path LIKE %s GROUP BY a.stage_key ORDER BY a.stage_key',(prefix,))
    assets['not_checked_months']=months
    return assets

@router.get('/reports/by-area')
def by_area(area_id:int|None=None,user=Depends(read_user)):
    chosen=area_id or user['area_id']
    prefix=report_path(user,chosen)+'%'
    return db.all('''SELECT child.id,child.name,count(a.id) AS count FROM area child
      LEFT JOIN area r ON r.path LIKE child.path || '%%'
      LEFT JOIN asset a ON a.area_id=r.id AND a.is_active
      WHERE child.parent_id IS NOT DISTINCT FROM %s AND child.path LIKE %s GROUP BY child.id ORDER BY child.id''',(chosen,prefix))
