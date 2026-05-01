# Postgres LISTEN/NOTIFY → AlertDispatcherJob.
#
# Skipped during db setup, asset precompile, and tests so it doesn't try to
# open a long-lived connection at boot time.

if defined?(Rails::Server) && !Rails.env.test? && ENV['ALERT_LISTENER_DISABLED'] != '1'
  Rails.application.config.after_initialize do
    Thread.new do
      begin
        # Wait briefly so Puma master finishes its boot work before we open a
        # second persistent connection.
        sleep 2
        ActiveRecord::Base.connection_pool.with_connection do |conn|
          raw = conn.raw_connection
          raw.exec('LISTEN wallgarden_alerts')
          loop do
            raw.wait_for_notify(30) do |_channel, _pid, payload|
              alert_id = Integer(payload, 10)
              AlertDispatcherJob.perform_later(alert_id)
            rescue ArgumentError, TypeError
              # Bad payload — ignore, the AlertDispatcher's poll fallback will catch it.
            end
            # The 30s wake-up doubles as a safety poll: enqueue any alerts that
            # somehow slipped past LISTEN/NOTIFY (e.g. the listener was down).
            Alert.pending_dispatch.where('fired_at > ?', 5.minutes.ago).pluck(:id).each do |id|
              AlertDispatcherJob.perform_later(id)
            end
          end
        end
      rescue StandardError => e
        Rails.logger.error("AlertListener died: #{e.class}: #{e.message}")
        # Will not auto-respawn; supervisor (Puma) will restart on next deploy.
      end
    end
  end
end
