class WeeklyReportJob < ApplicationJob
  queue_as :default

  def perform
    return unless WallGarden::CostGuard.skip_unless_affordable!('WeeklyReportJob')

    last = LlmAnalysis.where(kind: 'weekly_report').order(ran_at: :desc).first&.output
    summary = build_data_summary

    spec = Ai::Prompts::WeeklyReport.build(
      plant_profiles: PlantProfile.all.to_a,
      zones: Zone.includes(:plant_profile).order(:id).to_a,
      last_week_report: last,
      data_summary: summary,
    )
    output = Ai::Client.new(model: spec[:model]).chat(
      prompt: spec[:prompt],
      system: spec[:system],
      cached_blocks: spec[:cached_blocks],
      kind: spec[:kind],
    )
    AlertMailer.with(body: output).digest.deliver_later
  rescue Ai::Error => e
    Alert.create!(severity: 'info', source: 'rails', code: 'llm_unavailable',
                  message: "WeeklyReportJob: #{e.message}")
  end

  private

  def build_data_summary
    lines = []
    Zone.order(:id).each do |zone|
      lines << "Zone #{zone.id} (#{zone.name}):"
      moisture = zone.sensor_readings.where(kind: 'soil_moisture_pct')
                     .where('taken_at >= ?', 7.days.ago).pluck(:value).map(&:to_f)
      if moisture.any?
        lines << "  moisture min/mean/max: #{moisture.min.round(1)}/#{(moisture.sum/moisture.size).round(1)}/#{moisture.max.round(1)}"
      end
      ml = zone.watering_events.where('started_at >= ?', 7.days.ago).sum(:actual_ml).to_i
      lines << "  watered total: #{ml} mL across #{zone.watering_events.where('started_at >= ?', 7.days.ago).count} events"
    end
    lines << ''
    lines << "Alerts last 7d: #{Alert.where('fired_at >= ?', 7.days.ago).count}"
    lines.join("\n")
  end
end
