class DailyDigestJob < ApplicationJob
  queue_as :default

  # Runs at 7am UTC every day (configured in config/recurring.yml).
  def perform
    builder = WallGarden::DigestBuilder.new
    return unless builder.notable?   # skip silent days

    body = builder.yesterday_digest
    body = enrich_with_llm(body) if WallGarden::CostGuard.affordable?

    AlertMailer.with(body: body).digest.deliver_later
    Rails.logger.info('DailyDigestJob delivered')
  end

  private

  def enrich_with_llm(activity_text)
    spec = Ai::Prompts::DailyDigest.build(activity_text)
    Ai::Client.new(model: spec[:model]).chat(
      prompt: spec[:prompt], system: spec[:system], kind: spec[:kind],
    )
  rescue Ai::Error => e
    Rails.logger.warn("DailyDigestJob LLM enrichment failed: #{e.message}")
    activity_text
  end
end
