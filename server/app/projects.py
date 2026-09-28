from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg.types.json import Jsonb
from app import database as db
from app.people import read_user, need_role, area_limit, check_area

router = APIRouter()

PROJECT_STAGES = [
    ('need_identified', 'Need identified'),
    ('feasibility', 'Feasibility'),
    ('planning_design', 'Planning and design'),
    ('approvals', 'Approvals'),
    ('procurement', 'Procurement'),
    ('construction', 'Construction'),
    ('testing_handover', 'Testing and handover'),
    ('operation_maintenance', 'Operation and maintenance'),
    ('renewal_disposal', 'Renewal or disposal')
]

@router.get('/projects/stages')
def list_project_stages():
    return [{'key': k, 'label': l} for k, l in PROJECT_STAGES]

@router.get('/projects')
def list_projects(q: str = '', area_id: int | None = None, stage_key: str | None = None, status: str | None = None, page: int = Query(1, ge=1), user=Depends(read_user)):
    prefix = area_limit(user)
    where = ['r.path LIKE %(path)s']
    values = {'path': prefix + '%', 'offset': (page - 1) * 50}

    if area_id:
        with db.transaction() as conn:
            prefix = check_area(conn, user, area_id)['path']
            values['path'] = prefix + '%'

    if stage_key:
        where.append('p.current_stage_key = %(stage)s')
        values['stage'] = stage_key
    if status:
        where.append('p.status = %(status)s')
        values['status'] = status
    if q:
        where.append('(p.name ILIKE %(q)s OR p.code ILIKE %(q)s OR p.project_type ILIKE %(q)s)')
        values['q'] = f'%{q}%'

    sql = f"""
      SELECT p.id, p.code, p.name, p.project_type, p.area_id, r.name AS area_name,
             p.current_stage_key, p.status, p.approved_budget, p.forecast_cost, p.actual_cost,
             p.target_start_date, p.target_completion_date, p.created_at,
             d.name AS department_name, u.full_name AS owner_name,
             (SELECT count(*) FROM project_asset pa WHERE pa.project_id = p.id)::int AS linked_asset_count
      FROM project p
      JOIN area r ON r.id = p.area_id
      LEFT JOIN department_system d ON d.id = p.department_system_id
      LEFT JOIN app_user u ON u.id = p.owner_user_id
      WHERE {' AND '.join(where)}
      ORDER BY p.created_at DESC
      LIMIT 50 OFFSET %(offset)s
    """
    return db.all(sql, values)

@router.post('/projects')
def create_project(body: dict, user=Depends(need_role('editor', 'admin'))):
    name = (body.get('name') or '').strip()
    project_type = (body.get('project_type') or '').strip()
    area_id = body.get('area_id')
    stage_key = body.get('current_stage_key') or 'need_identified'
    department_id = body.get('department_system_id')
    budget = float(body.get('approved_budget') or 0)
    description = body.get('description') or ''
    details = body.get('details') or {}

    if not name or not project_type or not area_id:
        raise HTTPException(400, 'Project name, type, and area are required.')

    valid_stage_keys = [k for k, _ in PROJECT_STAGES]
    if stage_key not in valid_stage_keys:
        stage_key = 'need_identified'

    with db.transaction() as conn:
        check_area(conn, user, area_id)
        code = body.get('code')
        if not code:
            code = conn.execute("SELECT 'PRJ-'||lpad(nextval('project_number_seq')::text,7,'0') AS c").fetchone()['c']

        row = conn.execute("""
          INSERT INTO project(code, name, project_type, department_system_id, owner_user_id, area_id, current_stage_key, approved_budget, forecast_cost, description, details)
          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
          RETURNING id, code, name, current_stage_key
        """, (code, name, project_type, department_id, user['id'], area_id, stage_key, budget, budget, description, Jsonb(details))).fetchone()

        conn.execute("""
          INSERT INTO project_stage_history(project_id, to_stage, decision, who_user_id, comments)
          VALUES (%s, %s, 'created', %s, 'Project created in register.')
        """, (row['id'], stage_key, user['id']))

        return row

@router.get('/projects/{project_id}')
def get_project(project_id: str, user=Depends(read_user)):
    with db.transaction() as conn:
        p = conn.execute("""
          SELECT p.*, r.name AS area_name, d.name AS department_name, u.full_name AS owner_name
          FROM project p
          JOIN area r ON r.id = p.area_id
          LEFT JOIN department_system d ON d.id = p.department_system_id
          LEFT JOIN app_user u ON u.id = p.owner_user_id
          WHERE p.id = %s AND r.path LIKE %s
        """, (project_id, area_limit(user) + '%')).fetchone()

        if not p:
            raise HTTPException(404, 'Project not found or not in your area.')

        p.pop('location', None)
        p['history'] = conn.execute("""
          SELECT h.*, u.full_name AS who_name, r.full_name AS reviewer_name
          FROM project_stage_history h
          JOIN app_user u ON u.id = h.who_user_id
          LEFT JOIN app_user r ON r.id = h.reviewer_user_id
          WHERE h.project_id = %s
          ORDER BY h.happened_at DESC, h.id DESC
        """, (project_id,)).fetchall()

        p['assets'] = conn.execute("""
          SELECT a.id, a.register_code, a.name, a.stage_key, t.name AS type_name, pa.relation_kind, pa.linked_at
          FROM project_asset pa
          JOIN asset a ON a.id = pa.asset_id
          JOIN asset_type t ON t.id = a.asset_type_id
          WHERE pa.project_id = %s
          ORDER BY a.register_code
        """, (project_id,)).fetchall()

        p['items'] = conn.execute("""
          SELECT i.*, u.full_name AS owner_name
          FROM project_item i
          LEFT JOIN app_user u ON u.id = i.owner_user_id
          WHERE i.project_id = %s
          ORDER BY i.created_at DESC
        """, (project_id,)).fetchall()

        return p

@router.patch('/projects/{project_id}')
def update_project(project_id: str, body: dict, user=Depends(need_role('editor', 'admin'))):
    with db.transaction() as conn:
        p = conn.execute("""
          SELECT p.*, r.path AS area_path
          FROM project p
          JOIN area r ON r.id = p.area_id
          WHERE p.id = %s AND r.path LIKE %s
          FOR UPDATE OF p
        """, (project_id, area_limit(user) + '%')).fetchone()

        if not p:
            raise HTTPException(404, 'Project not found or not in your area.')

        updates = []
        values = []
        for field in ['name', 'project_type', 'status', 'description', 'target_start_date', 'target_completion_date']:
            if field in body:
                updates.append(f'{field} = %s')
                values.append(body[field])

        for num_field in ['approved_budget', 'forecast_cost', 'actual_cost']:
            if num_field in body and body[num_field] is not None:
                updates.append(f'{num_field} = %s')
                values.append(float(body[num_field]))

        if 'area_id' in body and body['area_id']:
            check_area(conn, user, body['area_id'])
            updates.append('area_id = %s')
            values.append(body['area_id'])

        if 'details' in body and isinstance(body['details'], dict):
            updates.append('details = %s')
            values.append(Jsonb(body['details']))

        if not updates:
            return p

        updates.append('updated_at = now()')
        values.append(project_id)
        return conn.execute(f"UPDATE project SET {', '.join(updates)} WHERE id = %s RETURNING id, code, name, status, updated_at", values).fetchone()

@router.post('/projects/{project_id}/stages')
def change_project_stage(project_id: str, body: dict, user=Depends(need_role('reviewer', 'admin'))):
    to_stage = body.get('to_stage')
    decision = body.get('decision') or 'advanced'
    comments = (body.get('comments') or '').strip()
    evidence_url = body.get('evidence_url') or ''

    valid_keys = [k for k, _ in PROJECT_STAGES]
    if to_stage not in valid_keys:
        raise HTTPException(400, 'Invalid project stage.')

    with db.transaction() as conn:
        p = conn.execute("""
          SELECT p.*, r.path AS area_path
          FROM project p
          JOIN area r ON r.id = p.area_id
          WHERE p.id = %s AND r.path LIKE %s
          FOR UPDATE OF p
        """, (project_id, area_limit(user) + '%')).fetchone()

        if not p:
            raise HTTPException(404, 'Project not found.')

        from_stage = p['current_stage_key']

        conn.execute("""
          INSERT INTO project_stage_history(project_id, from_stage, to_stage, decision, who_user_id, reviewer_user_id, comments, evidence_url)
          VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (project_id, from_stage, to_stage, decision, user['id'], user['id'], comments, evidence_url))

        conn.execute("UPDATE project SET current_stage_key = %s, updated_at = now() WHERE id = %s", (to_stage, project_id))
        return {'ok': True, 'project_id': project_id, 'from_stage': from_stage, 'to_stage': to_stage}

@router.post('/projects/{project_id}/assets')
def link_project_asset(project_id: str, body: dict, user=Depends(need_role('editor', 'admin'))):
    asset_id = body.get('asset_id')
    relation_kind = body.get('relation_kind') or 'creates'
    action = body.get('action') or 'link'

    if not asset_id:
        raise HTTPException(400, 'asset_id is required.')

    with db.transaction() as conn:
        if action == 'unlink':
            conn.execute("DELETE FROM project_asset WHERE project_id = %s AND asset_id = %s", (project_id, asset_id))
            return {'ok': True, 'unlinked': asset_id}

        conn.execute("""
          INSERT INTO project_asset(project_id, asset_id, relation_kind)
          VALUES (%s, %s, %s)
          ON CONFLICT (project_id, asset_id) DO UPDATE SET relation_kind = EXCLUDED.relation_kind
        """, (project_id, asset_id, relation_kind))
        return {'ok': True, 'linked': asset_id}

@router.post('/projects/{project_id}/items')
def add_project_item(project_id: str, body: dict, user=Depends(need_role('editor', 'admin'))):
    item_type = body.get('item_type') or 'need'
    title = (body.get('title') or '').strip()
    status = body.get('status') or 'open'
    severity = body.get('severity')
    due_date = body.get('due_date')
    data = body.get('data') or {}

    if not title:
        raise HTTPException(400, 'Item title is required.')

    with db.transaction() as conn:
        row = conn.execute("""
          INSERT INTO project_item(project_id, item_type, title, status, severity, due_date, owner_user_id, data)
          VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
          RETURNING id, project_id, item_type, title, status
        """, (project_id, item_type, title, status, severity, due_date, user['id'], Jsonb(data))).fetchone()
        return row
