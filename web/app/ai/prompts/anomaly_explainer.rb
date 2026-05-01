module Ai
  module Prompts
    class AnomalyExplainer
      MODEL = 'claude-haiku-4-5-20251001'

      SYSTEM = <<~MD.freeze
        You are a terse explainer of garden anomalies. The caller has already
        decided that a value is statistically anomalous (mean ± 2σ over 7d).
        Your job is to describe in one or two sentences:
        - what looks unusual about this reading,
        - the most likely cause (sensor fault, environmental, plant change),
        - whether the user needs to act now or it can wait.
        Do not hedge. Do not list multiple possibilities — pick the most likely.
      MD

      def self.build(anomaly_summary)
        {
          system: SYSTEM,
          prompt: anomaly_summary,
          model: MODEL,
          kind: 'anomaly',
        }
      end
    end
  end
end
