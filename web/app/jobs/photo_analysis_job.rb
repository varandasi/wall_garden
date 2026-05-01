class PhotoAnalysisJob < ApplicationJob
  queue_as :default

  def perform(photo_id = nil)
    return unless WallGarden::CostGuard.skip_unless_affordable!('PhotoAnalysisJob')

    photo = photo_id ? Photo.find(photo_id) : Photo.order(taken_at: :desc).first
    return unless photo && File.exist?(photo.path)

    prior = LlmAnalysis.where(kind: 'photo').order(ran_at: :desc).first&.output
    profiles_text = PlantProfile.all.map { |p| "- #{p.common_name}: #{p.notes}" }.join("\n")
    spec = Ai::Prompts::PhotoAnalysis.build(prior_caption: prior, plant_profiles: profiles_text)

    Ai::VisionClient.new(model: spec[:model]).analyze(
      image_path: photo.path,
      prompt: 'Analyse this wall garden photo per the system prompt.',
      system: spec[:system],
      cached_blocks: spec[:cached_blocks],
    )
  rescue Ai::Error => e
    Alert.create!(severity: 'info', source: 'rails', code: 'llm_unavailable',
                  message: "PhotoAnalysisJob: #{e.message}")
  end
end
