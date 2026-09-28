CREATE FUNCTION stop_history_changes() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION 'History entries cannot be changed or deleted'; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER history_no_change BEFORE UPDATE OR DELETE ON history_entry
  FOR EACH ROW EXECUTE FUNCTION stop_history_changes();
CREATE TRIGGER history_no_wipe BEFORE TRUNCATE ON history_entry
  FOR EACH STATEMENT EXECUTE FUNCTION stop_history_changes();
