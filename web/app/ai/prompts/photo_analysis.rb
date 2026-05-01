module Ai
  module Prompts
    class PhotoAnalysis
      MODEL = 'claude-sonnet-4-6'

      SYSTEM = <<~MD.freeze
        You are looking at a wall garden through a single fixed camera.
        Identify visible plants, their apparent health, and any visible issues
        (yellowing, drooping, pests, new growth, dry/overwatered soil). Compare
        against the prior week's photo if present. If the image carries a [SIM]
        watermark, you are looking at a synthetic placeholder — focus on the
        per-zone moisture estimates encoded in the leaf colours.

        Output Markdown with these sections:
        - **Overall health** (one sentence)
        - **Per-zone observations** (Z1..Z4)
        - **Action items** (≤3 bullets, only if needed)
      MD

      def self.build(prior_caption: nil, plant_profiles: nil)
        cached = []
        cached << "<plant_profiles>\n#{plant_profiles}\n</plant_profiles>" if plant_profiles.present?
        cached << "<prior_week>\n#{prior_caption}\n</prior_week>" if prior_caption.present?
        {
          system: SYSTEM,
          cached_blocks: cached,
          model: MODEL,
          kind: 'photo',
        }
      end
    end
  end
end
