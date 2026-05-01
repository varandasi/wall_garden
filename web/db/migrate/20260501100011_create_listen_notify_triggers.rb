class CreateListenNotifyTriggers < ActiveRecord::Migration[8.1]
  # Postgres LISTEN/NOTIFY hooks — Slice 4's AlertDispatcherJob and the daemon's
  # command runner LISTEN on these channels for instant wake-up without polling.
  def up
    execute <<~SQL
      CREATE OR REPLACE FUNCTION notify_alerts() RETURNS trigger AS $$
      BEGIN
        PERFORM pg_notify('wallgarden_alerts', NEW.id::text);
        RETURN NEW;
      END;
      $$ LANGUAGE plpgsql;
    SQL

    execute <<~SQL
      CREATE TRIGGER alerts_after_insert
      AFTER INSERT ON alerts
      FOR EACH ROW EXECUTE FUNCTION notify_alerts();
    SQL

    execute <<~SQL
      CREATE OR REPLACE FUNCTION notify_commands() RETURNS trigger AS $$
      BEGIN
        PERFORM pg_notify('wallgarden_commands', NEW.id::text);
        RETURN NEW;
      END;
      $$ LANGUAGE plpgsql;
    SQL

    execute <<~SQL
      CREATE TRIGGER commands_after_insert
      AFTER INSERT ON commands
      FOR EACH ROW EXECUTE FUNCTION notify_commands();
    SQL
  end

  def down
    execute 'DROP TRIGGER IF EXISTS alerts_after_insert ON alerts'
    execute 'DROP TRIGGER IF EXISTS commands_after_insert ON commands'
    execute 'DROP FUNCTION IF EXISTS notify_alerts()'
    execute 'DROP FUNCTION IF EXISTS notify_commands()'
  end
end
