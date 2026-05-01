class AnomalyScanJob < ApplicationJob
  queue_as :default

  def perform
    detector = WallGarden::AnomalyDetector.new
    anomalies = detector.scan
    return if anomalies.empty?
    return unless WallGarden::CostGuard.skip_unless_affordable!('AnomalyScanJob')

    summary = anomalies.map(&:to_summary).join("\n")
    spec = Ai::Prompts::AnomalyExplainer.build(summary)

    explanation = Ai::Client.new(model: spec[:model]).chat(
      prompt: spec[:prompt],
      system: spec[:system],
      kind: spec[:kind],
    )

    Alert.create!(
      severity: 'warn', source: 'llm', code: 'anomaly_detected',
      message: explanation.to_s.truncate(800),
    )
  rescue Ai::Error => e
    Alert.create!(severity: 'info', source: 'rails', code: 'llm_unavailable',
                  message: "AnomalyScanJob: #{e.message}")
  end
end
