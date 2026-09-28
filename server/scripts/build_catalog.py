"""Copy the supplied table definitions and catalog without dropping entries."""
import json
import re
from pathlib import Path

root = Path(__file__).resolve().parents[2]
spec = (root / 'docs/02_implementation.md').read_text(encoding='utf-8')
blocks = re.findall(r'```sql\n(.*?)```', spec, re.S)
for name, body in [('0001_tables.sql', '\n'.join(blocks[:2])), ('0002_history.sql', blocks[2])]:
    (root / 'server/db/migrations' / name).write_text(body, encoding='utf-8')
extra = (root / 'docs/04_extras.md').read_text(encoding='utf-8')
catalog = []
choices = {'MATERIAL':'cast iron|ductile iron|PVC|HDPE|steel|concrete|other', 'SURFACE':'asphalt|concrete|paving blocks|gravel|earth|other'}
stages = [{'key':k,'label':v,'is_end':k=='retired'} for k,v in [('planned','Planned'),('being_built','Being built'),('in_use','In use'),('needs_repair','Needs repair'),('under_repair','Under repair'),('retired','Retired')]]
for line in re.search(r'```text\n(.*?)```', extra, re.S)[1].splitlines():
    if line.startswith('FAMILY: '):
        family = line[8:]
    elif ' | ' in line:
        key, name, shape, fields = line.split(' | ')
        details = []
        for field in fields.split('; '):
            field_key, kind = field.split(':', 1)
            item = {'key':field_key, 'label':field_key.replace('_',' ').capitalize(), 'kind':kind.split('[')[0]}
            if '[' in kind:
                values = kind.split('[')[1][:-1]
                item['choices'] = choices.get(values, values).split('|')
            details.append(item)
        catalog.append(dict(family=family,key=key,name=name,usual_shape=shape,detail_fields=details,stages=stages))
assert len(catalog) == 37
(root / 'server/db/seed/asset_catalog.json').write_text(json.dumps(catalog, indent=2), encoding='utf-8')
