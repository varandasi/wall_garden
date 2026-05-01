module Ai
  module Prompts
    # Composes a WeeklyReport prompt with cacheable preamble (system + plant
    # profiles + last week's report) separated from the volatile data.
    class WeeklyReport
      MODEL = 'claude-sonnet-4-6'

      SYSTEM = <<~MD.freeze
        You are the caretaker analyst for a small vertical wall garden.
        You speak like a plain-language gardener, not a doctor or a lawyer.
        Each week you receive: zone configurations, plant profiles, the last
        week's report (for continuity), and aggregated sensor + watering data
        for the past seven days. Produce a Markdown report with these sections:
        1. **Headline** — one sentence: are plants healthy, stressed, or in trouble?
        2. **Per-zone notes** — for each zone, one paragraph covering moisture
           profile, watering totals vs cap, and any anomalies.
        3. **Suggested adjustments** — concrete threshold or schedule changes
           to consider, with reasons. Use no more than three suggestions.
        4. **What changed since last week** — explicit deltas from the prior
           report's recommendations.
        Be specific with numbers. Be terse. Avoid hedging.
      MD

      def self.build(plant_profiles:, zones:, last_week_report:, data_summary:)
        cached = [
          plant_profiles_block(plant_profiles),
          zones_block(zones),
          last_report_block(last_week_report),
        ].compact

        {
          system: SYSTEM,
          cached_blocks: cached,
          prompt: data_summary,
          model: MODEL,
          kind: 'weekly_report',
        }
      end

      def self.plant_profiles_block(profiles)
        return nil if profiles.blank?
        lines = ['<plant_profiles>']
        profiles.each do |p|
          lines << "- #{p.common_name} (#{p.scientific_name}): " \
                   "ideal_moisture #{p.ideal_moisture_min}–#{p.ideal_moisture_max}%, " \
                   "lux ≥ #{p.ideal_lux_min}, temp #{p.ideal_temp_c_min}–#{p.ideal_temp_c_max}°C. " \
                   "#{p.notes}"
        end
        lines << '</plant_profiles>'
        lines.join("\n")
      end

      def self.zones_block(zones)
        return nil if zones.blank?
        lines = ['<zones>']
        zones.each do |z|
          lines << "- Zone #{z.id} (#{z.name}, plant: #{z.plant_profile&.common_name}): " \
                   "target #{z.target_moisture_pct}% (±#{z.hysteresis_pct/2}), " \
                   "cap #{z.max_ml_per_day} mL/day, cooldown #{z.cooldown_minutes} min."
        end
        lines << '</zones>'
        lines.join("\n")
      end

      def self.last_report_block(text)
        return nil if text.blank?
        "<last_week_report>\n#{text}\n</last_week_report>"
      end
    end
  end
end
