class AlertDispatcherJob < ApplicationJob
  queue_as :default

  # Idempotent: if `dispatched_at` is already set, do nothing.
  def perform(alert_id)
    alert = Alert.find_by(id: alert_id)
    return unless alert
    return if alert.dispatched_at.present?

    title = "[#{alert.severity.upcase}] #{alert.code}"
    body = "#{alert.message}\n\nFired at #{I18n.l(alert.fired_at, format: :short)}"

    ntfy_result = WallGarden::NtfyDispatcher.new.post(
      title: title,
      message: body,
      severity: alert.severity,
      tags: ntfy_tags_for(alert),
      click: rails_url_for_alert(alert),
    )

    AlertMailer.with(alert: alert).critical.deliver_later if alert.severity == 'critical'

    alert.update!(dispatched_at: Time.current)
    Rails.logger.info("AlertDispatcherJob alert=#{alert.id} ntfy=#{ntfy_result}")
  end

  private

  def ntfy_tags_for(alert)
    case alert.code
    when /reservoir_empty/ then %w[droplet warning]
    when /sensor_stuck/    then %w[skull warning]
    when /sensor_disconnect/ then %w[zap]
    when /daily_cap/       then %w[stop_sign]
    when /daemon_/         then %w[robot warning]
    else %w[bell]
    end
  end

  def rails_url_for_alert(alert)
    Rails.application.routes.url_helpers.alerts_url(host: ENV.fetch('APP_HOST', 'localhost:3100'))
  rescue ArgumentError
    nil
  end
end
