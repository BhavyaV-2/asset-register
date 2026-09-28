import math
from datetime import date

def mapped_value(row,mapping,label,default=None):
    if not mapping:
        return default
    if 'fixed' in mapping:
        return mapping['fixed']
    value = str(row.get(mapping['column'],'')).strip()
    if value not in mapping.get('values',{}):
        raise ValueError(f"The {label} '{value}' is not in the mapping.")
    return mapping['values'][value]

def map_row(row,system,types):
    mapping = system['column_mapping']
    source_id = str(row.get(mapping.get('source_id',''),'')).strip()
    if not source_id:
        raise ValueError('The department ID is missing.')
    fixed = next((t['key'] for t in types.values() if t['id']==system['fixed_asset_type_id']),None)
    key = mapped_value(row,mapping.get('asset_type'),'type',fixed)
    if key not in types:
        raise ValueError('The asset type is not in the catalog.')
    kind = types[key]
    stage = mapped_value(row,mapping.get('stage'),'stage',system['default_stage_key'])
    if stage not in [s['key'] for s in kind['stages']]:
        raise ValueError('The stage is not listed for this asset type.')
    location = mapping.get('location',{})
    if location.get('geojson') or '_geometry' in row:
        shape = row.get('_geometry')
    elif 'wkt' in location:
        shape = str(row.get(location['wkt'],'')).strip()
    else:
        lat,lon = float(row[location['latitude']]),float(row[location['longitude']])
        if not math.isfinite(lat+lon) or not (-90<=lat<=90 and -180<=lon<=180):
            raise ValueError('Latitude or longitude is outside its allowed range.')
        shape = {'type':'Point','coordinates':[lon,lat]}
    details = {}
    warnings = {}
    lowered = {str(k).casefold():v for k,v in row.items()}
    for field in kind['detail_fields']:
        column = mapping.get('details',{}).get(field['key'],field['key'])
        value = row.get(column,lowered.get(field['label'].casefold()))
        if value is None or str(value).strip()=='':
            continue
        try:
            if field['kind']=='number':
                value = float(value)
                if not math.isfinite(value):
                    raise ValueError()
            elif field['kind']=='yes_no':
                value = {'yes':True,'true':True,'1':True,'no':False,'false':False,'0':False}[str(value).lower()]
            elif field['kind']=='date':
                value = date.fromisoformat(str(value)).isoformat()
            elif field['kind']=='choice':
                value = str(value).strip()
                if value not in field['choices']:
                    raise ValueError()
            else:
                value = str(value).strip()
            details[field['key']] = value
        except (ValueError,KeyError):
            warnings[field['key']] = value
    if warnings:
        details['_not_understood'] = warnings
    if row.get('_sample') in [True,'true','True']:
        details['_sample'] = True
    return {'source_id':source_id,'name':str(row.get(mapping.get('name',''),'')).strip() or None,'type_key':key,'asset_type_id':kind['id'],'stage_key':stage,'geometry':shape,'details':details,'raw':row}
