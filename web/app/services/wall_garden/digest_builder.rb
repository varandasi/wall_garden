module WallGarden
  # Builds the daily-digest body without an LLM (Slice 4). Slice 6 plugs Haiku
  # in to write a paragraph; this Slice ships the deterministic scaffold so the
  # email/digest pipeline can be exercised end-to-end without API access.
  class DigestBuilder
    def initialize(window: 24.hours)
      @window = window
    end

    def yesterday_digest
      events  = WateringEvent.where('started_at >= ?', @window.ago).completed
      alerts  = Alert.where('fired_at >= ?', @window.ago)

      lines = []
      lines << "Wall garden — last #{(@window.in_hours).to_i}h"
      lines << ''
      lines << "Watering events: #{events.count}"
      events.group(:zone_id).sum(:actual_ml).each do |zid, ml|
        lines << "  Zone #{zid}: #{ml.to_i} mL"
      end
      lines << ''
      if alerts.any?
        lines << "Alerts: #{alerts.count} (#{alerts.unacknowledged.count} unacknowledged)"
        alerts.group(:code).count.each { |code, n| lines << "  #{code}: #{n}" }
      else
        lines << 'No alerts.'
      end
      lines.join("\n")
    end

    def notable?
      events_count = WateringEvent.where('started_at >= ?', @window.ago).completed.count
      alerts_count = Alert.where('fired_at >= ?', @window.ago).count
      events_count > 0 || alerts_count > 0
    end
  end
end
