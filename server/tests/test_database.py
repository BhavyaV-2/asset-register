import pytest
import psycopg
from app.database import migrate, transaction, one

def test_migrations_repeat():
    migrate()
    migrate()
    assert one('SELECT count(*) AS n FROM schema_version')['n'] >= 2

@pytest.mark.parametrize('statement', ['UPDATE history_entry SET summary=summary', 'DELETE FROM history_entry', 'TRUNCATE history_entry'])
def test_history_cannot_change(statement):
    with transaction() as conn:
        conn.execute("INSERT INTO area_level VALUES (99, 'Test') ON CONFLICT DO NOTHING")
        area = conn.execute("INSERT INTO area(name,level_rank,path) VALUES ('Test',99,'/test/') RETURNING id").fetchone()['id']
        family = conn.execute("INSERT INTO asset_family(name,sort_order) VALUES ('Test',99) ON CONFLICT(name) DO UPDATE SET name=EXCLUDED.name RETURNING id").fetchone()['id']
        kind = conn.execute("INSERT INTO asset_type(family_id,key,name,usual_shape,stages) VALUES (%s,'test','Test','point','[]') ON CONFLICT(key) DO UPDATE SET name=EXCLUDED.name RETURNING id", (family,)).fetchone()['id']
        asset = conn.execute("INSERT INTO asset(register_code,asset_type_id,area_id,location,stage_key) VALUES ('TEST-'||nextval('asset_number_seq'),%s,%s,ST_SetSRID(ST_Point(72,23),4326),'in_use') RETURNING id",(kind,area)).fetchone()['id']
        conn.execute("INSERT INTO history_entry(asset_id,what,summary) VALUES (%s,'added','Test')",(asset,))
        with pytest.raises(psycopg.errors.RaiseException):
            with conn.transaction():
                conn.execute(statement)
        # Each test rolls back its own rows without changing saved history.
        raise psycopg.Rollback()

def test_source_id_is_unique():
    with transaction() as conn:
        with pytest.raises(psycopg.errors.UniqueViolation):
            with conn.transaction():
                # The unique index exists even before any department records are loaded.
                conn.execute("CREATE TEMP TABLE check_links (LIKE source_link INCLUDING ALL)")
                conn.execute("INSERT INTO check_links(asset_id,department_system_id,source_id,official_record) VALUES (gen_random_uuid(),1,'same','{}'),(gen_random_uuid(),1,'same','{}')")
