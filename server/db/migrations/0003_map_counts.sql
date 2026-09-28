-- Small saved counts for zoomed-out map views. Asset changes keep them current.
CREATE TABLE map_count (
  zoom int NOT NULL,
  cell_x int NOT NULL,
  cell_y int NOT NULL,
  area_id int NOT NULL REFERENCES area(id),
  asset_type_id int NOT NULL REFERENCES asset_type(id),
  stage_key text NOT NULL,
  has_problem boolean NOT NULL,
  warranty_start date NOT NULL,
  warranty_end date NOT NULL,
  asset_count bigint NOT NULL,
  PRIMARY KEY (zoom,cell_x,cell_y,area_id,asset_type_id,stage_key,has_problem,warranty_start,warranty_end)
);

CREATE FUNCTION refresh_map_counts() RETURNS void AS $$
BEGIN
  -- Called by the guarded load-data script, never by a website request.
  LOCK TABLE asset IN SHARE MODE;
  DELETE FROM map_count;
  INSERT INTO map_count
  SELECT z,round(ST_X(ST_SnapToGrid(ST_Centroid(a.location),360.0/power(2,z)/12))/(360.0/power(2,z)/12))::int,
    round(ST_Y(ST_SnapToGrid(ST_Centroid(a.location),360.0/power(2,z)/12))/(360.0/power(2,z)/12))::int,
    area_id,asset_type_id,stage_key,open_problem_count>0,
    COALESCE(warranty_start,'0001-01-01'::date),COALESCE(warranty_end,'0001-01-01'::date),count(*)
  FROM asset a CROSS JOIN generate_series(0,9) z WHERE a.is_active
  GROUP BY 1,2,3,4,5,6,7,8,9;
END;
$$ LANGUAGE plpgsql;

SELECT refresh_map_counts();

CREATE FUNCTION change_map_counts() RETURNS trigger AS $$
DECLARE
  item asset;
  sign int;
  z int;
  cell geometry;
  width double precision;
BEGIN
  IF current_setting('asset_register.skip_map_counts',true)='true' THEN
    RETURN NULL;
  END IF;
  FOR sign IN SELECT unnest(ARRAY[-1,1]) LOOP
    IF sign=-1 THEN
      IF TG_OP='INSERT' THEN CONTINUE; END IF;
      item := OLD;
    ELSE
      IF TG_OP='DELETE' THEN CONTINUE; END IF;
      item := NEW;
    END IF;
    IF NOT item.is_active THEN CONTINUE; END IF;
    FOR z IN 0..9 LOOP
      width := 360.0/power(2,z)/12;
      cell := ST_SnapToGrid(ST_Centroid(item.location),width);
      INSERT INTO map_count VALUES (z,round(ST_X(cell)/width)::int,round(ST_Y(cell)/width)::int,
        item.area_id,item.asset_type_id,item.stage_key,item.open_problem_count>0,
        COALESCE(item.warranty_start,'0001-01-01'::date),COALESCE(item.warranty_end,'0001-01-01'::date),sign)
      ON CONFLICT (zoom,cell_x,cell_y,area_id,asset_type_id,stage_key,has_problem,warranty_start,warranty_end)
      DO UPDATE SET asset_count=map_count.asset_count+EXCLUDED.asset_count;
    END LOOP;
  END LOOP;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER keep_map_counts AFTER INSERT OR DELETE OR UPDATE OF location,area_id,asset_type_id,stage_key,is_active,open_problem_count,warranty_start,warranty_end
ON asset FOR EACH ROW EXECUTE FUNCTION change_map_counts();
