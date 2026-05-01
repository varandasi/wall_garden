module WallGarden
  # Monthly LLM cost cap. Non-essential jobs check `affordable?` before invoking
  # Ai::Client. The cap is configurable via MONTHLY_LLM_COST_CAP_USD.
  class CostGuard
    def self.affordable?(threshold_usd: WALLGARDEN_LLM_COST_CAP_USD)
      LlmAnalysis.month_to_date_cost_usd < threshold_usd
    end

    def self.skip_unless_affordable!(job_name)
      return true if affordable?
      Alert.create!(
        severity: 'info', source: 'rails', code: 'llm_cost_cap_hit',
        message: "Skipped #{job_name}: month-to-date LLM spend exceeds #{WALLGARDEN_LLM_COST_CAP_USD} USD cap",
      )
      false
    end
  end
end
