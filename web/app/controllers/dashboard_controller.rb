class DashboardController < ApplicationController
  def index
    @zones = Zone.enabled.includes(:plant_profile).order(:name)
    @ambient_temp = SensorReading.latest(kind: 'air_temp_c')
    @ambient_rh   = SensorReading.latest(kind: 'air_rh_pct')
    @ambient_lux  = SensorReading.latest(kind: 'lux')
    @reservoir    = SensorReading.latest(kind: 'reservoir')
    @daemon_stale = DaemonHeartbeat.stale?
    @recent_alerts = Alert.unacknowledged.order(fired_at: :desc).limit(5)
  end
end
