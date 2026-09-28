from contextlib import contextmanager
from pathlib import Path
import os
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

pool = None

def open_pool():
    global pool
    if pool is None:
        pool = ConnectionPool(os.environ['DATABASE_URL'], min_size=5, max_size=10, kwargs={'row_factory': dict_row}, open=True)
        pool.wait()

def migrate():
    open_pool()
    with transaction() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(731204)')
        conn.execute('CREATE TABLE IF NOT EXISTS schema_version (name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())')
        for path in sorted((Path(__file__).parents[1] / 'db/migrations').glob('*.sql')):
            if not conn.execute('SELECT name FROM schema_version WHERE name=%s', (path.name,)).fetchone():
                conn.execute(path.read_text(encoding='utf-8'))
                conn.execute('INSERT INTO schema_version (name) VALUES (%s)', (path.name,))

@contextmanager
def transaction():
    open_pool()
    with pool.connection() as conn:
        with conn.transaction():
            yield conn

def one(sql, values=()):
    with transaction() as conn:
        return conn.execute(sql, values).fetchone()

def all(sql, values=()):
    with transaction() as conn:
        return conn.execute(sql, values).fetchall()

def run(sql, values=()):
    with transaction() as conn:
        return conn.execute(sql, values).rowcount
