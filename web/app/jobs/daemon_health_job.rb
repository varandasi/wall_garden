class DaemonHealthJob < ApplicationJob
  queue_as :default

  STALE_AFTER = 2.minutes

  # Runs every minute; alerts once when heartbeat is stale.
  def perform
    return unless DaemonHeartbeat.stale?(STALE_AFTER)

    Alert.create!(
      severity: 'critical',
      source: 'rails',
      code: 'daemon_heartbeat_stale',
      message: "Daemon heartbeat hasn't arrived in #{STALE_AFTER.in_minutes.to_i} min — control loop may be down."
    )
  end
end
