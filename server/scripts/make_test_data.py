"""Repeatable made-up data for a dedicated local load database only."""
import argparse
import os
from urllib.parse import urlparse
from app import database as db
from db.seed.make_seed import make_seed

def make_data(count,confirmed):
    address=urlparse(os.environ['DATABASE_URL'])
    if not confirmed or address.hostname not in ['localhost','127.0.0.1','db'] or address.path!='/asset_register_load':
        raise RuntimeError('Use the local asset_register_load database and --yes-this-is-a-test-database.')
    db.migrate();make_seed()
    existing=db.one("SELECT count(*) AS n FROM asset WHERE details->>'_load'='true'")['n']
    for start in range(existing+1,count+1,10000):
        with db.transaction() as conn:
            conn.execute("SELECT set_config('asset_register.skip_map_counts','true',true)")
            conn.execute('''INSERT INTO asset(register_code,asset_type_id,area_id,name,location,stage_key,details,last_checked_at,open_problem_count,warranty_start,warranty_end)
            SELECT 'LOAD-'||lpad(n::text,8,'0'),types.ids[1+(n%%array_length(types.ids,1))],areas.ids[1+(n%%array_length(areas.ids,1))],
            'Sample asset '||n,
            CASE WHEN n%%3=0 THEN ST_SetSRID(ST_MakeLine(ST_Point(68.5+(n*7919%%50000)/10000.0,20.2+(n*3571%%45000)/10000.0),ST_Point(68.501+(n*7919%%50000)/10000.0,20.201+(n*3571%%45000)/10000.0)),4326)
            ELSE ST_SetSRID(ST_Point(68.5+(n*7919%%50000)/10000.0,20.2+(n*3571%%45000)/10000.0),4326) END,
            (ARRAY['planned','being_built','in_use','needs_repair','under_repair','retired'])[1+n%%6],
            '{"_sample":true,"_load":true}'::jsonb,now()-make_interval(months=>(n%%24)::int),CASE WHEN n%%10=0 THEN 1 ELSE 0 END,
            CASE WHEN n%%5=0 THEN current_date-30 END,CASE WHEN n%%5=0 THEN current_date+60 END
            FROM generate_series(%s::bigint,%s::bigint) n,
            (SELECT array_agg(id ORDER BY id) AS ids FROM asset_type) types,
            (SELECT array_agg(id ORDER BY id) AS ids FROM area WHERE level_rank=4) areas''',(start,min(start+9999,count)))
    with db.transaction() as conn:
        conn.execute('SELECT refresh_map_counts()')
        conn.execute('ANALYZE asset')
        conn.execute('ANALYZE map_count')
    print(f'Created {count:,} made-up assets in the load database.')

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--count',type=int,default=200000)
    parser.add_argument('--yes-this-is-a-test-database',action='store_true')
    args=parser.parse_args()
    if not 1<=args.count<=2000000:raise SystemExit('Choose 1 to 2,000,000 assets.')
    make_data(args.count,args.yes_this_is_a_test_database)
