module Ai
  module Prompts
    class DailyDigest
      MODEL = 'claude-haiku-4-5-20251001'

      SYSTEM = <<~MD.freeze
        Summarise yesterday's wall garden activity in two short paragraphs for
        a daily email. Lead with the most notable thing — a problem or a
        positive trend. Mention concrete numbers (mL watered, alerts, hours
        of light). Avoid bullet lists.
      MD

      def self.build(activity_text)
        {
          system: SYSTEM,
          prompt: activity_text,
          model: MODEL,
          kind: 'digest',
        }
      end
    end
  end
end
